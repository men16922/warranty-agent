"""실물 합성 지점 — 포트를 GCP 어댑터에 붙이고 ADK에 넘길 도구 넷을 만든다."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from warranty.adapters.adk_agent import TOOL_NAMES
from warranty.adapters.genai_transport import VertexGenaiTransport
from warranty.adapters.live_action import LiveActionExecutor
from warranty.adapters.live_budget import LiveBudgetStore
from warranty.adapters.live_run import LiveRunControl
from warranty.adapters.live_signal import LiveSignalSource
from warranty.adapters.live_store import LiveContractStore, LiveLedger
from warranty.adapters.model_judge import PromptedJudge
from warranty.adapters.system import SystemClock, UlidGen
from warranty.config import Adapters, Settings
from warranty.domain.contract import ResourceRef
from warranty.domain.tokens import TokenPrices
from warranty.ports import ContractStore, SignalSource
from warranty.tunables import DEMO_BUDGET_USD
from warranty.usecases.meter import MeteredModel, ModelCallMeter
from warranty.usecases.remediate import Remediator
from warranty.wire import remediate_response

AGENT_ID = "warranty"
RESOURCE_KIND = "cloud_run_service"


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

    def provision(self, resource_name: str) -> dict[str, object]:
        """Create a resource and operational contract. Day-1 is not wired in this demo."""
        return {
            "status": "not_implemented",
            "resource_name": resource_name,
            "detail": "Day-1 provisioning is outside the current live demo path",
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
        target_revision: str,
        projected_usd: str = "0.01",
        region: str = "",
    ) -> dict[str, Any]:
        """Run gate, action, same-signal verification, rollback, and ledger recording."""
        try:
            projected = Decimal(projected_usd)
        except InvalidOperation as exc:
            raise RuntimeError(f"projected_usd가 수가 아니다: {projected_usd!r}") from exc
        entry = self.remediator.remediate(
            agent_id=AGENT_ID,
            action_id=target_revision,
            resource=_resource(resource_name, region or self.default_region),
            projected_usd=projected,
        )
        return remediate_response(entry)

    def report(self, date: str) -> dict[str, object]:
        """Return the daily recovery report. The live report reader is not wired yet."""
        return {
            "status": "not_implemented",
            "date": date,
            "detail": "daily live report reader is outside the current demo path",
        }

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
    return AgentTools(remediator, contracts, signals, settings.region, model_calls)
