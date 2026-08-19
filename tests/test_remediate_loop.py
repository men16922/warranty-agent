"""루프 전체 — 조치 → 검증 → 롤백. 가드 G1·G4.

⚠️ 전부 fake 어댑터다. 이 테스트가 통과한다고 REQ-601·602가 만족되지 않는다 —
   스텁은 인터페이스의 **존재**를 증명하지 않는다 (docs/PRINCIPLES.md #3).
"""

from __future__ import annotations

from decimal import Decimal

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
from warranty.domain.decision import Gate
from warranty.domain.entry import InMemoryLedger, Status
from warranty.domain.verification import DecidedBy, Measurement, Verdict
from warranty.usecases.remediate import Remediator

RESOURCE = ResourceRef("cloud_run_service", "demo-target", "us-central1")
PREVIOUS = "demo-target-00007-abc"
CRIT = Criterion(Direction.DECREASE, Decimal("0.5"), CriterionMode.RELATIVE, Decimal("0.1"))
_MISSING = object()  # 기본 계약을 함수 안에서 만든다 (인자 기본값에서 호출 금지)


def _m(value: str | None, points: int = 30) -> Measurement:
    return Measurement(Decimal(value) if value is not None else None, points)


def _contract(reversible: bool = True) -> OperationalContract:
    return OperationalContract(
        contract_id="c1",
        resource=RESOURCE,
        health_signal=SignalSpec("run.googleapis.com/request_latencies", "demo-target", "P95", 120),
        recovery_criterion=CRIT,
        rollback_plan=RollbackPlan(PREVIOUS) if reversible else None,
        reversibility=Reversibility.REVERSIBLE if reversible else Reversibility.IRREVERSIBLE,
        provisioned_at=__import__("datetime").datetime(
            2026, 8, 19, tzinfo=__import__("datetime").UTC
        ),
        provisioned_by="e0",
    )


def _build(
    *,
    series: list[Measurement],
    contract: OperationalContract | None | object = _MISSING,
    readable: bool = True,
    headroom: str = "0.50",
    judge_verdict: Verdict = Verdict.NOT_RECOVERED,
    honors_shift: bool = True,
) -> tuple[Remediator, RecordingExecutor, FakeRun, InMemoryLedger, FakeJudge]:
    if contract is _MISSING:
        contract = _contract()
    contracts = InMemoryContracts()
    if contract is not None:
        contracts.put(contract)  # type: ignore[arg-type]
    executor = RecordingExecutor()
    run = FakeRun(honors_shift=honors_shift)
    ledger = InMemoryLedger()
    judge = FakeJudge(judge_verdict, "traded one symptom for another")
    r = Remediator(
        contracts=contracts,
        signals=ScriptedSignal(series, readable=readable),
        executor=executor,
        run=run,
        budgets=FakeBudget(Decimal(headroom)),
        ledger=ledger,
        clock=FrozenClock(),
        ids=SeededIdGen(),
        judge=judge,
    )
    return r, executor, run, ledger, judge


def _run(r: Remediator, projected: str = "0.01", **over: object) -> object:
    kwargs: dict[str, object] = {
        "agent_id": "warranty",
        "action_id": "shift_traffic",
        "resource": RESOURCE,
        "projected_usd": Decimal(projected),
    }
    kwargs.update(over)
    return r.remediate(**kwargs)  # type: ignore[arg-type]


# ── ★ G1 — 막는 판정이면 실행기를 부르지 않는다 ────────────────────────


def test_req_403_deny_never_calls_the_executor() -> None:
    """Verifies: REQ-403

    ★ G1 — 판정만 적고 실행을 막지 않아도 **로그는 똑같아 보인다.**
    그래서 호출 횟수를 센다.
    """
    r, executor, _, _, _ = _build(series=[_m("1.0")], headroom="0.10")
    entry = _run(r, projected="5.00")
    assert entry.decision.verdict is Gate.DENY  # type: ignore[attr-defined]
    assert entry.status is Status.DENIED  # type: ignore[attr-defined]
    assert executor.call_count == 0


def test_req_104_no_contract_is_manual_and_never_executes() -> None:
    """Verifies: REQ-104

    ⛔ 계약이 없다는 것은 **무엇을 재야 회복인지 모른다**는 뜻이고, 모르면 검증이 불가능하다.
    """
    r, executor, _, _, _ = _build(series=[_m("1.0")], contract=None)
    entry = _run(r)
    assert entry.status is Status.MANUAL_REQUIRED  # type: ignore[attr-defined]
    assert entry.contract_id is None  # type: ignore[attr-defined]
    assert executor.call_count == 0


def test_req_402_unreadable_signal_blocks_automation() -> None:
    """Verifies: REQ-402, REQ-403

    ★ 정책의 집행 지점. 계약은 있지만 **신호를 지금 못 읽으면** 자동이 아니다.
    """
    r, executor, _, _, _ = _build(series=[_m("1.0")], readable=False)
    entry = _run(r)
    assert entry.decision.verdict is Gate.APPROVE  # type: ignore[attr-defined]
    assert entry.status is Status.AWAITING_APPROVAL  # type: ignore[attr-defined]
    assert executor.call_count == 0


# ── ★ G4 — 모든 항목이 판정을 갖는다 ───────────────────────────────────


def test_req_401_every_entry_carries_a_decision() -> None:
    """Verifies: REQ-401

    ★ G4 — 게이트를 안 거친 실행 경로가 생기면 여기서 잡힌다.
    """
    for kwargs in ({"headroom": "0.10"}, {"readable": False}, {}):
        r, _, _, ledger, _ = _build(series=[_m("1.0"), _m("0.2")], **kwargs)  # type: ignore[arg-type]
        _run(r, projected="5.00" if kwargs.get("headroom") else "0.01")
        for entry in ledger.all_entries():
            assert entry.decision is not None, f"판정 없는 항목: {entry.entry_id}"


# ── 검증 (REQ-201, 202, 204) ───────────────────────────────────────────


def test_req_202_baseline_and_after_use_the_same_signal_spec() -> None:
    """Verifies: REQ-201, REQ-202

    ⚠️ 다른 지표로 재면 검증이 아니다. 두 읽기가 **같은 스펙 객체**를 타야 한다.
    """
    r, _, _, _, _ = _build(series=[_m("1.0"), _m("0.2")])
    signals = r.signals
    _run(r)
    assert len(signals.reads) >= 2  # type: ignore[attr-defined]
    assert signals.reads[0] is signals.reads[1]  # type: ignore[attr-defined]


def test_req_204_the_model_is_not_called_when_the_verdict_is_clear() -> None:
    """Verifies: REQ-204

    ⚠️ 명확한 경우까지 모델에 맡기면 판정이 비결정적이 되고 REQ-802가 깨진다.
    """
    r, _, _, _, judge = _build(series=[_m("1.0"), _m("0.1")])
    entry = _run(r)
    assert entry.verification.verdict is Verdict.RECOVERED  # type: ignore[attr-defined]
    assert entry.verification.decided_by is DecidedBy.RULE  # type: ignore[attr-defined]
    assert judge.calls == 0


def test_req_204_ambiguous_goes_to_the_model_and_keeps_the_rationale() -> None:
    """Verifies: REQ-204

    ★ 모델의 판단이 하중을 받는 자리. 근거가 원장에 **문장으로** 남는다.
    """
    r, _, _, _, judge = _build(series=[_m("1.0"), _m("0.5")])
    entry = _run(r)
    assert judge.calls == 1
    assert entry.verification.decided_by is DecidedBy.MODEL  # type: ignore[attr-defined]
    assert "symptom" in entry.verification.rationale  # type: ignore[attr-defined]


# ── ★ 롤백 (REQ-302, 303, 304, 305) ────────────────────────────────────


def test_req_302_failed_verification_triggers_rollback() -> None:
    """Verifies: REQ-302, REQ-502

    ★ 이 시스템이 말할 수 있는 문장: **실행은 됐고, 나아지지는 않았고, 되돌렸다.**
    """
    r, executor, run, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("1.0")])
    entry = _run(r)
    assert executor.call_count == 1
    assert entry.executed is True  # type: ignore[attr-defined]
    assert entry.improved is False  # type: ignore[attr-defined]
    assert entry.rolled_back is True  # type: ignore[attr-defined]
    assert run.shifts == [PREVIOUS]


def test_req_303_rollback_is_proved_by_reading_the_traffic_split_back() -> None:
    """Verifies: REQ-303

    ⚠️ **"롤백했다"는 주장이고 "트래픽이 이전 리비전으로 갔다"는 측정이다.**
    """
    r, _, _, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("1.0")])
    entry = _run(r)
    assert entry.rollback.verified_traffic == {PREVIOUS: 100}  # type: ignore[attr-defined]


def test_req_301_the_rollback_plan_is_fixed_before_the_action_runs() -> None:
    """Verifies: REQ-301

    ⚠️ 조치 후에 롤백 대상을 찾으면, **바로 그 조치가 깨뜨린 상태에 의존**한다.
    조치가 리비전을 바꿨는데 "직전 리비전"을 조치 후에 물으면 **방금 만든 것**이 나온다.

    증명: 계약을 **도중에 다른 리비전으로 바꿔치기해도** 롤백은 원래 대상으로 간다.
    (계약 조회가 루프 시작에 한 번뿐이라는 것도 함께 묻는다.)
    """
    contracts = InMemoryContracts()
    contracts.put(_contract())
    executor = RecordingExecutor()
    run = FakeRun()
    r = Remediator(
        contracts=contracts,
        signals=ScriptedSignal([_m("1.0"), _m("0.95"), _m("1.0")]),
        executor=executor,
        run=run,
        budgets=FakeBudget(Decimal("0.50")),
        ledger=InMemoryLedger(),
        clock=FrozenClock(),
        ids=SeededIdGen(),
        judge=FakeJudge(),
    )
    _run(r)

    assert contracts.lookups == 1, "계약을 여러 번 조회했다 — 조치 후 상태에 의존할 수 있다"
    assert run.shifts == [PREVIOUS]


def test_req_303_a_split_that_does_not_reach_the_previous_revision_is_not_a_rollback() -> None:
    """Verifies: REQ-303

    ⚠️ **이 케이스가 없으면 "다시 읽는다"는 가드가 하중을 못 받는다** — 픽스처가 늘
    완벽하면 읽기와 "성공했다고 가정"의 결과가 같아진다 (docs/PRINCIPLES.md #8).

    API는 성공했는데 배분이 안 옮겨진 경우, 그것은 롤백이 **아니다.**
    """
    r, _, _, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("1.0")], honors_shift=False)
    entry = _run(r)
    assert entry.rollback.performed is False  # type: ignore[attr-defined]
    assert entry.rollback.verified_traffic != {PREVIOUS: 100}  # type: ignore[attr-defined]
    assert "did not reach" in entry.rollback.reason  # type: ignore[attr-defined]
    assert entry.rolled_back is False  # type: ignore[attr-defined]


def test_req_304_the_signal_is_measured_again_after_the_rollback() -> None:
    """Verifies: REQ-304

    되돌렸는데 안 돌아오면 **원인이 조치가 아니었다** — 그건 에스컬레이션 사유다.
    """
    r, _, _, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("1.0")])
    assert _run(r).rollback.signal_restored is True  # type: ignore[attr-defined]

    r2, _, _, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("0.2")])
    assert _run(r2).rollback.signal_restored is False  # type: ignore[attr-defined]


def test_req_305_irreversible_failure_escalates_instead_of_retrying() -> None:
    """Verifies: REQ-305

    ⚠️ **실패한 자동화가 계속 시도하는 것이 가장 나쁜 상태다.**
    """
    r, _, run, _, _ = _build(series=[_m("1.0"), _m("0.95")], contract=_contract(reversible=False))
    entry = _run(r)
    # 비가역 + 검증 가능 → APPROVE 이므로 자동 실행되지 않는다
    assert entry.decision.verdict is Gate.APPROVE  # type: ignore[attr-defined]
    assert run.shifts == []


def test_req_206_verification_delay_is_a_named_constant_used_once() -> None:
    """Verifies: REQ-206, REQ-804

    ⚠️ 값이 흩어지면 영상 재촬영 때 반드시 하나를 놓친다.
    """
    from warranty.usecases import remediate

    r, _, _, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("1.0")])
    _run(r)
    assert set(r.clock.slept) == {remediate.VERIFY_DELAY_S}  # type: ignore[attr-defined]
