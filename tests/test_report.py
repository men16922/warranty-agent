"""일간 리포트 — ★ `improvement_rate`가 헤드라인이다 (REQ-508).

Spec: specs/warranty/design/05-accountability-ledger.md §5 (REQ-508)

⚠️ 이 파일이 지키는 것은 **숫자의 정의**다. 회복률의 분모가 흔들리거나, 회복 실패
   조치의 비용이 전체 비용으로 번지거나, `unverifiable` 칸이 조용히 빠지는 것 —
   셋 다 리포트를 봐서는 안 보이고 **전부 성적이 좋아 보이는 방향으로만** 틀린다.
"""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from warranty.adapters.fakes import (
    FakeBudget,
    FakeJudge,
    FakeRun,
    FrozenClock,
    InMemoryContracts,
    RecordingExecutor,
    ScriptedSignal,
    SeededIdGen,
)
from warranty.domain.attribution import Attribution, Method
from warranty.domain.contract import (
    Criterion,
    CriterionMode,
    Direction,
    OperationalContract,
    ResourceRef,
    Reversibility,
    RollbackPlan,
    SignalSpec,
)
from warranty.domain.cost import Basis, CostFact
from warranty.domain.entry import InMemoryLedger, LedgerEntry, Rollback, Status
from warranty.domain.report import DailyReport, ReportError, daily_report
from warranty.domain.verification import DecidedBy, Measurement, Verdict, Verification
from warranty.usecases.remediate import Remediator

FROZEN = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)  # REQ-802: 살아 있는 시계를 안 쓴다
DAY = FROZEN.date()
AGENT = "warranty"

#: design 05§5가 이름 붙인 칸. **여기서 하나라도 빠지면 리포트가 다른 문서가 된다.**
DESIGN_COLUMNS = frozenset(
    {
        "date",
        "agent_id",
        "executed",
        "improved",
        "improvement_rate",
        "rolled_back",
        "escalated",
        "unverifiable",
        "manual_required",
        "wasted_usd",
        "model_decided",
    }
)


def _m(value: str, points: int = 30) -> Measurement:
    return Measurement(Decimal(value), points)


def _assumed(amount: str) -> CostFact:
    return CostFact(
        amount_usd=Decimal(amount),
        priced_at=FROZEN,
        basis=Basis.PUBLISHED_RATE,
        inputs={"cpu_seconds": Decimal(60)},
        unit_prices={"cpu_seconds": Decimal(amount) / Decimal(60)},
    )


def _measured(amount: str) -> CostFact:
    return CostFact(amount_usd=Decimal(amount), priced_at=FROZEN, basis=Basis.BILLING_EXPORT)


def _verified(verdict: Verdict, by: DecidedBy = DecidedBy.RULE) -> Verification:
    return Verification(
        verdict=verdict,
        decided_by=by,
        baseline=_m("100"),
        after=_m("30"),
        rationale="fake" if by is DecidedBy.MODEL else "",
    )


def _entry(entry_id: str, **over: Any) -> LedgerEntry:
    """⚠️ 기본값도 타입 검사를 받게 생성자로 만든다 — `dict[str, object]`로 쌓으면
    `LedgerEntry(**base)`의 억제가 **기본값의 오타까지** 함께 덮는다(T0-9).
    ⛔ 재정의 인자는 여전히 검사 밖이다(`Any`).
    """
    base = LedgerEntry(
        entry_id=entry_id,
        agent_id=AGENT,
        action_id="shift_traffic",
        status=Status.EXECUTED,
        started_at=FROZEN,
        attribution=Attribution(Method.RESOURCE_LABEL, label_value=entry_id),
        assumed=_assumed("0.10"),
    )
    return replace(base, **over)


def _report(*entries: LedgerEntry, day: date = DAY, agent_id: str = AGENT) -> DailyReport:
    """**저장된 원장을 읽어서** 낸다 — 호출자가 들고 있는 사본이 아니라."""
    ledger = InMemoryLedger()
    for entry in entries:
        ledger.create(entry)
    return daily_report(ledger.all_entries(), day=day, agent_id=agent_id)


# ── ★ 헤드라인 ─────────────────────────────────────────────────────────────


def test_req_508_headline_is_improved_over_executed_not_executed_itself() -> None:
    """Verifies: REQ-508, REQ-502

    ★ 이 프로젝트의 문장 전체가 이 숫자다. `executed`를 성공으로 세는 순간
    다른 도구와 같아진다 — 셋 중 하나만 실제로 나아졌다.
    """
    report = _report(
        _entry("e1", verification=_verified(Verdict.RECOVERED)),
        _entry("e2", verification=_verified(Verdict.NOT_RECOVERED)),
        _entry("e3", verification=_verified(Verdict.NOT_RECOVERED)),
    )
    assert report.executed == 3
    assert report.improved == 1
    assert report.improvement_rate == Decimal(1) / Decimal(3)
    assert report.as_dict()["improvement_rate"] == 0.33


def test_req_508_a_blocked_action_does_not_dilute_the_headline() -> None:
    """Verifies: REQ-508, REQ-507

    거부·수동 필요도 원장에 남지만(REQ-507) **분모는 `executed`다.** 전체 건수로
    나누면 게이트가 잘 막을수록 성적이 나빠 보이고, 그건 게이트를 끄라는 압력이 된다.
    """
    report = _report(
        _entry("e1", verification=_verified(Verdict.RECOVERED)),
        _entry("e2", status=Status.DENIED, assumed=_assumed("0")),
        _entry("e3", status=Status.MANUAL_REQUIRED, assumed=_assumed("0")),
        _entry("e4", status=Status.AWAITING_APPROVAL, assumed=_assumed("0")),
    )
    assert report.executed == 1
    assert report.improvement_rate == Decimal(1)
    assert report.manual_required == 1


def test_req_508_improvement_rate_is_undefined_when_nothing_executed() -> None:
    """Verifies: REQ-508

    ⚠️ `0.0`이 아니라 `None`이다. 0은 *"해 봤는데 하나도 못 고쳤다"*로 읽히고,
    그건 *"할 게 없었다"*와 전혀 다른 문장이다 — `delta_of`가 배율을 0으로 안 내는
    것과 같은 이유다(REQ-509).
    """
    report = _report(_entry("e1", status=Status.DENIED, assumed=_assumed("0")))
    assert report.executed == 0
    assert report.improvement_rate is None
    assert report.as_dict()["improvement_rate"] is None


def test_req_508_report_derives_the_rate_and_does_not_store_it() -> None:
    """Verifies: REQ-508, REQ-502

    G8과 같은 계열 — 저장하면 `improved`/`executed`와 어긋날 수 있고,
    **어긋난 쪽이 사람에게 보인다.**
    """
    stored = {f.name for f in fields(DailyReport)}
    assert "improvement_rate" not in stored
    assert isinstance(type(_report(_entry("e1"))).improvement_rate, property)


# ── 롤백과 에스컬레이션은 다른 칸이다 ──────────────────────────────────────


def test_req_508_rolled_back_and_escalated_are_counted_separately() -> None:
    """Verifies: REQ-508, REQ-305

    ⚠️ `escalated`를 `rolled_back`의 부정으로 세면 **회복된 조치가 전부
    에스컬레이션으로 잡힌다** — 아래 `e1`이 그것을 태운다.
    """
    report = _report(
        _entry("e1", verification=_verified(Verdict.RECOVERED)),
        _entry(
            "e2",
            verification=_verified(Verdict.NOT_RECOVERED),
            rollback=Rollback(performed=True, verified_traffic={"r7": 100}, signal_restored=True),
        ),
        _entry(
            "e3",
            verification=_verified(Verdict.NOT_RECOVERED),
            rollback=Rollback(performed=False, reason="irreversible — escalated"),
        ),
    )
    assert report.rolled_back == 1
    assert report.escalated == 1


# ── 회복 실패 조치가 쓴 비용 ───────────────────────────────────────────────


def test_req_508_wasted_is_only_what_executed_without_recovering() -> None:
    """Verifies: REQ-508

    ★ 이 칸이 "쓴 돈 전부"가 되면 아무것도 안 말한다. 회복된 조치의 비용은
    낭비가 아니고, **되돌린 조치의 비용은 되돌아오지 않는다.**
    """
    report = _report(
        _entry("e1", assumed=_assumed("0.90"), verification=_verified(Verdict.RECOVERED)),
        _entry(
            "e2",
            assumed=_assumed("0.50"),
            verification=_verified(Verdict.NOT_RECOVERED),
            rollback=Rollback(performed=True, verified_traffic={"r7": 100}),
        ),
        _entry("e3", assumed=_assumed("0.34"), verification=_verified(Verdict.NOT_RECOVERED)),
    )
    assert report.wasted_usd == Decimal("0.84")


def test_req_508_wasted_prefers_the_bill_and_says_how_much_is_still_a_guess() -> None:
    """Verifies: REQ-508, REQ-505

    청구서가 온 건은 실측으로 센다. 그래도 `assumed`는 **원장에서 그대로다**(I-1) —
    여기서는 읽을 때 고를 뿐이다. 그리고 아직 추정인 건수를 함께 낸다: 총액만 내면
    그 총액을 지배하는 것이 추정인지 실측인지 영원히 모른다.
    """
    reconciled = _entry(
        "e1",
        assumed=_assumed("0.02"),
        measured=_measured("1.90"),
        verification=_verified(Verdict.NOT_RECOVERED),
    )
    guessed = _entry("e2", assumed=_assumed("0.10"), verification=_verified(Verdict.NOT_RECOVERED))
    report = _report(reconciled, guessed)

    assert report.wasted_usd == Decimal("2.00")
    assert report.wasted_assumed_only == 1
    assert reconciled.assumed.amount_usd == Decimal("0.02")


# ── 정직성 칸 ──────────────────────────────────────────────────────────────


def test_req_508_unverifiable_is_a_column_not_a_silence() -> None:
    """Verifies: REQ-508, REQ-205

    ⚠️ 검증 불가는 **성공이 아니다.** 그래서 `improved`에 안 들고, 그렇다고 사라지지도
    않는다 — 감추면 회복률이 좋아 보이는 방향으로만 틀린다.
    """
    report = _report(
        _entry("e1", verification=_verified(Verdict.RECOVERED)),
        _entry("e2", verification=_verified(Verdict.UNVERIFIABLE)),
    )
    assert report.unverifiable == 1
    assert report.improved == 1
    assert report.executed == 2
    assert report.as_dict()["unverifiable"] == 1


def test_req_508_report_carries_every_column_the_design_names() -> None:
    """Verifies: REQ-508

    ⚠️ 칸이 조용히 빠지는 것을 막는다. 특히 `unverifiable`·`escalated`는 성적을
    나쁘게 보이게 하는 칸이라 **빠져도 아무도 불평하지 않는다.**
    """
    assert _report(_entry("e1")).as_dict().keys() >= DESIGN_COLUMNS


def test_req_508_model_decided_is_counted_so_the_judge_is_visible() -> None:
    """Verifies: REQ-508, REQ-204

    모델이 몇 건을 판정했는지가 안 보이면 "규칙이 판정했다"와 구분이 안 된다.
    """
    report = _report(
        _entry("e1", verification=_verified(Verdict.RECOVERED)),
        _entry("e2", verification=_verified(Verdict.RECOVERED, DecidedBy.MODEL)),
    )
    assert report.model_decided == 1


# ── 범위 ───────────────────────────────────────────────────────────────────


def test_req_508_report_is_scoped_to_one_agent_and_one_day() -> None:
    """Verifies: REQ-508

    "일간 리포트"라고 부르면서 전체 원장을 세면 회복률이 **날마다 안 변한다.**
    """
    report = _report(
        _entry("e1", verification=_verified(Verdict.RECOVERED)),
        _entry("e2", agent_id="other-agent", verification=_verified(Verdict.NOT_RECOVERED)),
        _entry(
            "e3",
            started_at=FROZEN - timedelta(days=1),
            verification=_verified(Verdict.NOT_RECOVERED),
        ),
    )
    assert report.executed == 1
    assert report.improvement_rate == Decimal(1)


def test_req_508_a_timestamp_without_a_timezone_is_refused() -> None:
    """Verifies: REQ-508, REQ-802

    UTC라고 가정하고 넘어가면 경계 근처 항목이 **조용히 다른 날에 실린다.**
    """
    naive = _entry("e1", started_at=datetime(2026, 8, 19, 12, 0))
    with pytest.raises(ReportError, match="시간대가 없어"):
        _report(naive)


# ── 실제 루프가 만든 원장 위에서 ───────────────────────────────────────────


def test_req_508_counts_what_the_real_loop_actually_wrote() -> None:
    """Verifies: REQ-508, REQ-502

    ⚠️ 손으로 만든 행만 세면 *"우리가 원장을 이렇게 쓴다고 상상한다"*를 검증한다.
    조치→검증 실패→롤백을 **실제로 돌려서** 나온 행으로 리포트를 낸다
    (docs/PRINCIPLES.md #8 — 픽스처가 늘 완벽하면 가드가 하중을 못 받는다).
    """
    resource = ResourceRef("cloud_run_service", "demo-target", "us-central1")
    contracts = InMemoryContracts()
    contracts.put(
        OperationalContract(
            contract_id="c1",
            resource=resource,
            health_signal=SignalSpec(
                "run.googleapis.com/request_latencies", "demo-target", "P95", 120
            ),
            recovery_criterion=Criterion(
                Direction.DECREASE, Decimal("0.5"), CriterionMode.RELATIVE, Decimal("0.1")
            ),
            rollback_plan=RollbackPlan("demo-target-00007-abc"),
            reversibility=Reversibility.REVERSIBLE,
            provisioned_at=FROZEN,
            provisioned_by="e0",
        )
    )
    ledger = InMemoryLedger()
    remediator = Remediator(
        contracts=contracts,
        signals=ScriptedSignal([_m("100"), _m("99"), _m("100")]),  # 안 나아진다
        executor=RecordingExecutor(),
        run=FakeRun(),
        budgets=FakeBudget(Decimal("0.50")),
        ledger=ledger,
        clock=FrozenClock(),
        ids=SeededIdGen(),
        judge=FakeJudge(),
    )
    remediator.remediate(
        agent_id=AGENT,
        action_id="shift_traffic",
        resource=resource,
        projected_usd=Decimal("0.01"),
    )

    report = daily_report(ledger.all_entries(), day=DAY, agent_id=AGENT)
    assert report.executed == 1
    assert report.improved == 0
    assert report.improvement_rate == Decimal(0)
    assert report.rolled_back == 1
    assert report.escalated == 0
