"""`make demo` — 다섯 단계를 **결정론적으로** 재현한다 (REQ-803).

Spec: specs/warranty/design/11-demo.md (REQ-803)

    ① provision   서비스 생성 + ★ 계약 방출 (계약이 화면에 보인다)
    ② inject      신호를 악화시키는 리비전을 준비한다 (장애 주입)
    ③ remediate   게이트 AUTO → 조치 → 검증 실패 → ★ 자동 롤백 → 신호 회복 확인
    ④ manual      계약 없는 리소스 → ★ MANUAL (검증 불가라 자동 안 한다)
    ⑤ report      회복률 · 롤백 수 · 검증 불가 수 · 낭비된 비용

⚠️ **판정은 사람이 출력을 보는 것이 아니다.** 이 서사가 두 번 돌려 같은 결과인지는
   `tests/test_demo.py`가 게이트 안에서 묻는다 (design 11§1 원칙 1).

⚠️ **결과를 박아 두지 않는다** (design 11§1 원칙 5). 여기서 각본인 것은 **신호**뿐이고
   — 오프라인이라 Cloud Monitoring 자리에 `ScriptedSignal`이 선다 — 판정·검증·롤백은
   전부 실물 코드가 계산한다. 조치는 트래픽을 **실제로** 나쁜 리비전으로 옮기고
   (`ShiftTrafficExecutor`), 롤백은 그것을 **실제로** 되돌린다. 그래서 검증이 실패하는
   것도 롤백이 성공하는 것도 이 파일이 정한 값이 아니다.

⛔ 이 데모는 REQ-601·602를 만족시키지 않는다. fake 위에서 도는 서사는 *"우리가 이
   인터페이스를 이렇게 부른다"*를 말할 뿐이다 (docs/PRINCIPLES.md #3).
   `caveats`가 그것을 출력에도 적는다 — 안 적으면 다음 사람이 이 초록을 실물로 읽는다.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from warranty.adapters.fakes import (
    FakeBudget,
    FakeJudge,
    FakeRun,
    FrozenClock,
    InMemoryContracts,
    ScriptedSignal,
    SeededIdGen,
)
from warranty.domain.contract import (
    Criterion,
    CriterionMode,
    Direction,
    OperationalContract,
    ResourceRef,
)
from warranty.domain.entry import InMemoryLedger, LedgerEntry
from warranty.domain.report import daily_report
from warranty.domain.verification import Measurement
from warranty.tunables import DEMO_BUDGET_USD
from warranty.usecases.provision import ProvisionResponse, derive_contract
from warranty.usecases.remediate import Remediator

# ── 데모 상수. ⚠️ 대기·창·예산은 여기 없다 — `warranty.tunables` 한 곳에 있다
#    (design 11§5, REQ-804). 아래 것들은 재촬영 때 손대는 값이 아니라 **서사의 배역**이다.
DEMO_AGENT = "warranty"
DEMO_REGION = "us-central1"
DEMO_SERVICE = "demo-target"
DEMO_ACTION_USD = Decimal("0.02")
#: 살아 있는 시계를 안 쓴다 — 데모가 결정론적이려면 시각도 주입돼야 한다 (REQ-802).
DEMO_CLOCK_ISO = "2026-08-21T09:00:00+00:00"

#: 프로비저닝 시점에 서빙 중이던 리비전. **롤백이 돌아갈 곳이다.**
HEALTHY_REVISION = "demo-target-00007-abc"

#: ★ 생성 API가 돌려줬다고 **치는** 응답. 계약은 여기서 유도된다 (REQ-103).
#: ⛔ 각본인 것은 이 응답이지 계약이 아니다 — 계약의 네 자리는 실물 코드가 이 응답에서
#:    계산한다. 실물 Cloud Run 응답이 이 모양인지는 T3-1에서만 확인된다(`CAVEATS` 참조).
DEMO_PROVISION_RESPONSE = ProvisionResponse(
    kind="cloud_run_service",
    name=DEMO_SERVICE,
    region=DEMO_REGION,
    previous_revision=HEALTHY_REVISION,
)
#: 장애 주입용 — 신호를 악화시키는 리비전. 조치가 여기로 트래픽을 옮긴다.
SLOW_REVISION = "demo-target-00008-slow"

#: 계약 없이 손으로 만든 리소스. **버그가 아니라 정책이다** (REQ-104).
ORPHAN_SERVICE = "hand-made-api"

#: 신호 각본 — 기준선(이미 나쁘다) → 조치 후(더 나빠졌다) → 롤백 후(원래대로).
#: ⚠️ 이 셋이 각본인 것이지 판정이 각본인 것이 아니다. `classify`가 이 값을 보고 계산한다.
BASELINE_MS = Decimal("620")
AFTER_ACTION_MS = Decimal("900")
AFTER_ROLLBACK_MS = Decimal("615")
SIGNAL_POINTS = 30

TITLE = "warranty — make demo (offline · deterministic)"

#: 이 데모가 **증명하지 않는 것.** 출력에 함께 싣는다 — 빼면 fake 위의 초록이
#: 실물 왕복으로 읽힌다 (docs/PRINCIPLES.md #3).
CAVEATS = (
    "신호는 ScriptedSignal이 낸다 — 실물 Cloud Monitoring이 아니다 (REQ-601·602는 TODO).",
    "계약은 생성 응답에서 유도되지만(REQ-103) 그 응답이 각본이다 — "
    "실물 Cloud Run 응답이 이 모양으로 오는지는 확인 안 됐다 (T3-1).",
    "wasted_usd가 0인 것은 낭비가 없어서가 아니라 조치에 비용 경로가 아직 없어서다 (REQ-503).",
)

CIRCLED = ("①", "②", "③", "④", "⑤")


class DemoError(RuntimeError):
    """데모의 서사가 성립하지 않았다."""


@dataclass(frozen=True, slots=True)
class DemoStep:
    """한 단계의 결과. `detail`은 **JSON으로 실을 수 있는 값만** 담는다."""

    name: str
    headline: str
    detail: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class DemoRun:
    steps: tuple[DemoStep, ...]
    caveats: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "steps": [
                {"name": step.name, "headline": step.headline, "detail": dict(step.detail)}
                for step in self.steps
            ],
            "caveats": list(self.caveats),
        }

    def render(self) -> str:
        """사람이 읽는 출력. ⚠️ **정렬해서 낸다** — 사전 순서에 기대면 같은 원장이
        프로세스마다 다른 문자열을 내고, 그건 REQ-803이 말하는 재현이 아니다.
        """
        lines = [TITLE, "=" * len(TITLE), ""]
        for mark, step in zip(CIRCLED, self.steps, strict=True):
            lines.append(f"{mark} {step.name} — {step.headline}")
            lines += [f"    {key}: {_show(step.detail[key])}" for key in sorted(step.detail)]
            lines.append("")
        lines.append("⚠️ 이 데모가 증명하지 않는 것")
        lines += [f"  - {caveat}" for caveat in self.caveats]
        return "\n".join(lines)


def _show(value: object) -> str:
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _measured(value: Decimal) -> Measurement:
    return Measurement(value, SIGNAL_POINTS)


def demo_contract(provisioned_at: datetime) -> OperationalContract:
    """★ Day-1이 Day-2에 넘기는 것 — 무엇을 재고, 무엇을 회복이라 부르고, 어떻게 되돌리나.

    ⚠️ 판정 기준이 **여기 한 곳**에 있다. 테스트가 자기 사본을 들고 있으면 기준을 바꿔도
       테스트는 옛 기준으로 초록이고, 그 어긋남은 조용하다.

    ⚠️ **리소스도 인자가 아니다** (REQ-103). 리소스 이름·리전·롤백 목적지는 전부
       `DEMO_PROVISION_RESPONSE`에서 온다 — 계약을 손으로 조립하던 자리를 지우고
       `derive_contract` 하나만 남겼다. 사람이 정하는 것은 아래 `recovery_criterion`뿐이다.
    """
    return derive_contract(
        DEMO_PROVISION_RESPONSE,
        recovery_criterion=Criterion(
            direction=Direction.DECREASE,
            threshold=Decimal("0.5"),
            mode=CriterionMode.RELATIVE,
            tolerance=Decimal("0.1"),
        ),
        contract_id="ct-demo-0001",
        provisioned_at=provisioned_at,
        provisioned_by="demo-provisioner",
    )


@dataclass(frozen=True, slots=True)
class ShiftTrafficExecutor:
    """데모의 조치 — **트래픽을 실제로 옮긴다** (design 11§1 원칙 5).

    ⚠️ 아무것도 안 옮기는 실행기를 쓰면 롤백의 "배분을 다시 읽어 확인한다"(REQ-303)가
       하중을 못 받는다 — 트래픽이 처음부터 롤백 목적지에 있으니 안 옮겨도 100%다
       (docs/PRINCIPLES.md #8 — 픽스처가 늘 완벽하면 가드가 증명을 멈춘다).
    """

    run: FakeRun
    revision: str
    #: ★ 부른 횟수를 센다 — 게이트가 막았다는 것을 **값으로** 보이게 하는 자리다 (G1).
    calls: list[str] = field(default_factory=list)

    def execute(self, action_id: str, resource: ResourceRef) -> bool:
        self.calls.append(action_id)
        self.run.shift_all_traffic(resource, self.revision)
        return True


def run_demo() -> DemoRun:
    """다섯 단계를 돌리고 **각 단계가 무엇을 냈는지** 돌려준다.

    Spec: specs/warranty/design/11-demo.md (REQ-803)
    """
    clock = FrozenClock(DEMO_CLOCK_ISO)
    started = datetime.fromisoformat(clock.now_iso())
    orphan = ResourceRef("cloud_run_service", ORPHAN_SERVICE, DEMO_REGION)

    # ── ① provision — 계약 방출. ⚠️ **리소스가 계약에서 온다**(REQ-103) — 반대가 아니다.
    #    조치·검증·롤백이 가리키는 리소스는 생성 응답이 말한 그것이지 이 파일이 적은 이름이 아니다.
    contracts = InMemoryContracts()
    contract = demo_contract(started)
    resource = contract.resource
    if contract.rollback_plan is None:
        # 유도가 돌아갈 자리를 못 냈다 → ③(자동 롤백)의 서사가 성립하지 않는다.
        raise DemoError(f"유도된 계약에 롤백 계획이 없다: {contract.contract_id}")
    rollback_to = contract.rollback_plan.previous_revision
    contracts.put(contract)
    run = FakeRun(current=HEALTHY_REVISION)
    provision = DemoStep(
        name="provision",
        headline="서비스를 만든 에이전트가 **어떻게 확인하고 어떻게 되돌리는지**도 함께 적는다",
        detail={
            "resource": f"{resource.kind}/{resource.name} @{resource.region}",
            "contract_id": contract.contract_id,
            "health_signal": contract.health_signal.metric_type,
            "signal_window_s": contract.health_signal.window_s,
            "recovery_criterion": (
                f"{contract.recovery_criterion.direction} "
                f"{contract.recovery_criterion.threshold} "
                f"({contract.recovery_criterion.mode}, ±{contract.recovery_criterion.tolerance})"
            ),
            "rollback_to": rollback_to,
            "reversibility": str(contract.reversibility),
        },
    )

    # ── ② inject — 신호를 악화시키는 리비전을 준비한다 (아직 트래픽은 안 간다)
    executor = ShiftTrafficExecutor(run=run, revision=SLOW_REVISION)
    inject = DemoStep(
        name="inject",
        headline="신호를 악화시키는 리비전을 배포한다 — 조치가 그리로 트래픽을 옮기게 된다",
        detail={
            "degrading_revision": SLOW_REVISION,
            "traffic_before": dict(run.read_traffic(resource)),
            "baseline_p95_ms": str(BASELINE_MS),
            "note": "실물에서는 이 리비전이 진짜로 느리다. 여기서는 신호가 각본이다.",
        },
    )

    # ── ③ remediate — 게이트 AUTO → 조치 → 검증 실패 → 자동 롤백
    ledger = InMemoryLedger()
    judge = FakeJudge()
    budgets = FakeBudget(DEMO_BUDGET_USD)
    remediator = Remediator(
        contracts=contracts,
        signals=ScriptedSignal(
            [
                _measured(BASELINE_MS),
                _measured(AFTER_ACTION_MS),
                _measured(AFTER_ROLLBACK_MS),
            ]
        ),
        executor=executor,
        run=run,
        budgets=budgets,
        ledger=ledger,
        clock=clock,
        ids=SeededIdGen(),
        judge=judge,
    )
    acted = remediator.remediate(
        agent_id=DEMO_AGENT,
        action_id="shift_traffic",
        resource=resource,
        projected_usd=DEMO_ACTION_USD,
    )
    remediate = DemoStep(
        name="remediate",
        headline="실행됐다. 나아지지 않았다. 되돌렸다 — 그리고 **되돌아갔는지 다시 읽었다**",
        detail=_narrative_of(acted, traffic_shifts=list(run.shifts)),
    )

    # ── ④ manual — 계약이 없으면 자동 대상이 아니다 (REQ-104)
    blocked = remediator.remediate(
        agent_id=DEMO_AGENT,
        action_id="shift_traffic",
        resource=orphan,
        projected_usd=DEMO_ACTION_USD,
    )
    manual = DemoStep(
        name="manual",
        headline="계약이 없다 → 검증할 수 없다 → ⛔ 자동으로 하지 않는다",
        detail={
            "resource": f"{orphan.kind}/{orphan.name} @{orphan.region}",
            "contract_id": str(blocked.contract_id),
            "status": str(blocked.status),
            "gate": _gate_of(blocked),
            "gate_rule": _gate_rule_of(blocked),
            # ⛔ ③에서 한 번 불렸고 여기서는 **안 불렸다.** 판정만 찍으면
            #    *"판정은 했는데 실행은 됐다"*를 못 잡는다 (G1과 같은 형태의 질문이다.
            #    여기서 실제로 막는 것은 계약이 없다는 쪽이다 — REQ-104).
            "executor_calls_total": len(executor.calls),
            "model_calls_total": judge.calls,
        },
    )

    # ── ⑤ report — 원장에서 유도한다. 하나도 저장하지 않는다 (REQ-508)
    entries = ledger.all_entries()
    summary = daily_report(entries, day=started.date(), agent_id=DEMO_AGENT).as_dict()
    report = DemoStep(
        name="report",
        headline="executed만 세면 아무것도 안 말한다 — 그 옆에 improved가 있다",
        detail=summary,
    )

    return DemoRun(
        steps=(provision, inject, remediate, manual, report),
        caveats=CAVEATS,
    )


def _narrative_of(entry: LedgerEntry, *, traffic_shifts: list[str]) -> dict[str, object]:
    """조치 한 건이 남긴 것 전부. ⚠️ 셋을 하나의 `success`로 합치지 않는다 (REQ-502)."""
    decision, verification, rollback = entry.decision, entry.verification, entry.rollback
    if decision is None or verification is None or rollback is None:
        # 서사가 성립하지 않았다. 조용히 `None`을 찍으면 데모가 **다른 이야기**를 한다.
        raise DemoError(
            f"조치가 판정·검증·롤백을 다 남기지 않았다: {entry.entry_id} "
            f"(decision={decision is not None}, verification={verification is not None}, "
            f"rollback={rollback is not None})"
        )
    baseline, after = verification.baseline, verification.after
    return {
        "entry_id": entry.entry_id,
        "started_at": entry.started_at.isoformat(),
        "gate": str(decision.verdict),
        "gate_rule": decision.rule,
        "executed": entry.executed,
        "baseline_p95_ms": "·" if baseline is None else str(baseline.value),
        "after_p95_ms": "·" if after is None else str(after.value),
        "verdict": str(verification.verdict),
        "decided_by": str(verification.decided_by),
        "improved": entry.improved,
        "traffic_shifts": traffic_shifts,
        "rolled_back": entry.rolled_back,
        "verified_traffic": dict(rollback.verified_traffic or {}),
        "signal_restored": rollback.signal_restored,
    }


def _gate_of(entry: LedgerEntry) -> str:
    return "·" if entry.decision is None else str(entry.decision.verdict)


def _gate_rule_of(entry: LedgerEntry) -> str:
    return "·" if entry.decision is None else entry.decision.rule


def main() -> int:
    print(run_demo().render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
