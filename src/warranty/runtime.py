"""실물 합성 지점 — 포트를 GCP 어댑터에 붙이고 ADK에 넘길 도구 넷을 만든다."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from warranty.adapters.adk_agent import TOOL_NAMES
from warranty.adapters.genai_transport import VertexGenaiTransport
from warranty.adapters.live_action import LiveActionExecutor
from warranty.adapters.live_budget import LiveBudgetStore
from warranty.adapters.live_provision import LiveProvisioner
from warranty.adapters.live_run import LiveRunControl
from warranty.adapters.live_signal import LiveSignalSource
from warranty.adapters.live_store import LiveContractStore, LiveLedger
from warranty.adapters.model_judge import PromptedJudge
from warranty.adapters.system import SystemClock, UlidGen
from warranty.config import SERVICE_NAME, Adapters, Settings
from warranty.domain.contract import Criterion, CriterionMode, Direction, ResourceRef
from warranty.domain.report import daily_report
from warranty.domain.tokens import TokenPrices
from warranty.ports import ContractStore, LedgerReader, SignalSource
from warranty.tunables import DEMO_BUDGET_USD
from warranty.usecases.meter import MeteredModel, ModelCallMeter
from warranty.usecases.provision import Provisioner, derive_contract
from warranty.usecases.remediate import Remediator
from warranty.wire import remediate_response

AGENT_ID = "warranty"
RESOURCE_KIND = "cloud_run_service"

#: ⛔ **사람이 정하는 유일한 것** — *"무엇을 회복이라 부를지"*는 정책이지 사실이 아니다
#: (usecases/provision 모듈 독스트링). 나머지 계약 필드는 전부 생성 응답에서 유도된다.
#: ⚠️ 데모의 기준(`demo.py`)과 값이 같지만 **같은 상수가 아니다** — 저쪽은 각본의 일부이고
#: 이쪽은 배포된 정책이다. 하나로 묶으면 각본을 고칠 때 배포 정책이 따라 움직인다.
LIVE_RECOVERY_CRITERION = Criterion(
    direction=Direction.DECREASE,
    threshold=Decimal("0.5"),
    mode=CriterionMode.RELATIVE,
    tolerance=Decimal("0.1"),
)


class RuntimeError(ValueError):
    """도구 요청 또는 실물 조립이 성립하지 않는다."""


def _resource(name: str, region: str) -> ResourceRef:
    if not name.strip() or not region.strip():
        raise RuntimeError("resource_name과 region이 필요하다")
    return ResourceRef(RESOURCE_KIND, name.strip(), region.strip())


@dataclass(frozen=True, slots=True)
class AgentTools:
    """ADK에 붙는 네 함수. 이름과 순서는 design 06§3이 소유한다."""

    remediator: Remediator
    contracts: ContractStore
    signals: SignalSource
    default_region: str
    model_calls: ModelCallMeter | None = None
    provisioner: Provisioner | None = None
    ledger: LedgerReader | None = None
    clock: Any = None
    ids: Any = None

    def provision(self, resource_name: str) -> dict[str, object]:
        """Create a Cloud Run service and record its operational contract in one step.

        ⛔ **만드는 것과 계약이 같은 순간에 난다**(REQ-101). 나눠 두면 사이에 실패가 들어갈
           자리가 생기고, 그 자리에서 만들어진 리소스는 **계약 없는 리소스**가 된다 —
           그런 리소스는 자동 조치 대상이 아니고(REQ-104), 아무도 그것을 모른다.
        ⚠️ 계약은 여기서 조립하지 않는다 — `derive_contract`가 생성 응답에서 유도한다.
           사람이 정하는 것은 `LIVE_RECOVERY_CRITERION` 하나뿐이다(REQ-103).
        """
        if self.provisioner is None or self.clock is None or self.ids is None:
            raise RuntimeError("실물 프로비저너가 합성되지 않았다")
        response = self.provisioner.create(resource_name)
        contract = derive_contract(
            response,
            recovery_criterion=LIVE_RECOVERY_CRITERION,
            contract_id=self.ids.new_entry_id(),
            provisioned_at=datetime.fromisoformat(self.clock.now_iso()),
            provisioned_by=AGENT_ID,
        )
        self.contracts.put(contract)
        return {
            "resource": contract.resource.name,
            "region": contract.resource.region,
            "contract": contract.contract_id,
            "health_signal": {
                "metric_type": contract.health_signal.metric_type,
                "resource_filter": contract.health_signal.resource_filter,
                "aggregation": contract.health_signal.aggregation,
                "window_s": contract.health_signal.window_s,
            },
            "reversibility": contract.reversibility.value,
            "rollback_revision": (
                None if contract.rollback_plan is None else contract.rollback_plan.previous_revision
            ),
        }

    def inspect(self, resource_name: str, region: str = "") -> dict[str, object]:
        """Read the active contract and its current Cloud Monitoring signal."""
        resource = _resource(resource_name, region or self.default_region)
        contract = self.contracts.active_for(resource)
        if contract is None:
            return {"resource": resource.name, "contract": None, "signal": None}
        measured = self.signals.read(contract.health_signal)
        return {
            "resource": resource.name,
            "contract": contract.contract_id,
            "signal": {
                "value": None if measured.value is None else str(measured.value),
                "points": measured.points,
            },
            "rollback_revision": (
                None if contract.rollback_plan is None else contract.rollback_plan.previous_revision
            ),
        }

    def remediate(
        self,
        resource_name: str,
        action: str,
        projected_usd: str = "0.01",
        region: str = "",
    ) -> dict[str, Any]:
        """Run gate, action, same-signal verification, rollback, and ledger recording.

        `action` is one of:
          - `traffic:<revision>`   — send all traffic to that revision of this service
          - `concurrency:<n>`      — change requests-per-instance (1..1000)
        A bare revision name is read as `traffic:<revision>`.

        ⭐ **이 인자가 `target_revision`이던 동안 이 에이전트가 아는 조치는 하나였다** —
           이름이 곧 조치였다. 조치를 어댑터에만 더하면 그것은 **코드에는 있고 에이전트는
           못 부르는 능력**이고, 그런 능력은 데모에서 존재하지 않는 것과 같다.

        ⚠️ 옛 형태(리비전 이름 한 줄)를 계속 받는 이유는 호환이 아니라 **기록**이다.
           08-28 원장과 배포된 리비전이 그 형태로 남아 있다.
        """
        try:
            projected = Decimal(projected_usd)
        except InvalidOperation as exc:
            raise RuntimeError(f"projected_usd가 수가 아니다: {projected_usd!r}") from exc
        entry = self.remediator.remediate(
            agent_id=AGENT_ID,
            action_id=action,
            resource=_resource(resource_name, region or self.default_region),
            projected_usd=projected,
        )
        return remediate_response(entry)

    def report(self, date: str) -> dict[str, object]:
        """Return the daily recovery report: executed vs improved, not executed alone.

        ⛔ **이 도구가 내는 칸이 이 프로젝트의 헤드라인이다**(REQ-508). `executed`만 세고
           그것을 성공이라 부르지 않는다 — `improved`가 **따로** 있고 더 작을 수 있다.
        ⚠️ 무엇을 셀지는 여기서 안 정한다. 원장을 하루치 긁어서 `daily_report`에 넘길
           뿐이다 — 세는 규칙이 두 벌이 되면 회복률의 분모가 조용히 갈라진다.
        """
        if self.ledger is None:
            raise RuntimeError("실물 원장이 합성되지 않았다")
        try:
            day = datetime.fromisoformat(date).date()
        except ValueError as exc:
            raise RuntimeError(f"date가 날짜가 아니다: {date!r}") from exc
        return dict(daily_report(self.ledger.for_day(day), day=day, agent_id=AGENT_ID).as_dict())

    def callables(self) -> tuple[Any, ...]:
        tools = (self.provision, self.inspect, self.remediate, self.report)
        names = tuple(tool.__name__ for tool in tools)
        if names != TOOL_NAMES:
            raise RuntimeError(f"ADK 도구 이름/순서가 설계와 다르다: {names} != {TOOL_NAMES}")
        return tools


def build_live_tools(settings: Settings, pause: Callable[[float], None]) -> AgentTools:
    if settings.adapters is not Adapters.LIVE:
        raise RuntimeError("배포된 에이전트는 WR_ADAPTERS=live에서만 실물 도구를 만든다")
    ids = UlidGen()
    clock = SystemClock(pause)
    contracts = LiveContractStore(settings.project_id)
    ledger = LiveLedger(settings.project_id)
    run = LiveRunControl(settings.project_id)
    signals = LiveSignalSource(settings.project_id)
    model_calls = ModelCallMeter(
        ledger=ledger,
        clock=clock,
        ids=ids,
        prices=TokenPrices({}, source_note="no published rate configured"),
        agent_id=AGENT_ID,
    )
    judge = MeteredModel(
        model=PromptedJudge(
            VertexGenaiTransport(settings.project_id, settings.vertex_location, settings.model)
        ),
        ledger=ledger,
        clock=clock,
        ids=ids,
        prices=model_calls.prices,
        agent_id=AGENT_ID,
    )
    remediator = Remediator(
        contracts=contracts,
        signals=signals,
        executor=LiveActionExecutor(run),
        run=run,
        budgets=LiveBudgetStore(settings.project_id, DEMO_BUDGET_USD, ids),
        ledger=ledger,
        clock=clock,
        ids=ids,
        judge=judge,
    )
    return AgentTools(
        remediator,
        contracts,
        signals,
        settings.region,
        model_calls,
        provisioner=LiveProvisioner(settings.project_id, settings.region, SERVICE_NAME),
        ledger=ledger,
        clock=clock,
        ids=ids,
    )
