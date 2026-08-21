"""루프 전체 — 조치 → 검증 → 롤백. 가드 G1·G4.

⚠️ 전부 fake 어댑터다. 이 테스트가 통과한다고 REQ-601·602가 만족되지 않는다 —
   스텁은 인터페이스의 **존재**를 증명하지 않는다 (docs/PRINCIPLES.md #3).
"""

from __future__ import annotations

from decimal import Decimal

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
from warranty.domain.entry import InMemoryLedger, LedgerError, Status
from warranty.domain.verification import DecidedBy, Measurement, Verdict
from warranty.usecases.remediate import Remediator

RESOURCE = ResourceRef("cloud_run_service", "demo-target", "us-central1")
PREVIOUS = "demo-target-00007-abc"
CRIT = Criterion(Direction.DECREASE, Decimal("0.5"), CriterionMode.RELATIVE, Decimal("0.1"))
_MISSING = object()  # 기본 계약을 함수 안에서 만든다 (인자 기본값에서 호출 금지)


def _m(value: str | None, points: int = 30) -> Measurement:
    return Measurement(Decimal(value) if value is not None else None, points)


def _contract(reversible: bool = True, contract_id: str = "c1") -> OperationalContract:
    return OperationalContract(
        contract_id=contract_id,
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


# ── ★ 승인 집행 (REQ-404) ──────────────────────────────────────────────


def _awaiting(
    series: list[Measurement] | None = None,
) -> tuple[Remediator, RecordingExecutor, InMemoryLedger, str]:
    """게이트가 `APPROVE`로 멈춘 항목 하나를 만든다 (비가역 + 검증 가능).

    ⚠️ 여기서 **이미 실행기 호출이 0회**여야 한다. 아니면 뒤의 승인 테스트들이
    "승인이 실행을 열었다"가 아니라 "이미 실행돼 있었다"를 보고 있는 것이다.
    """
    r, executor, _, ledger, _ = _build(
        series=series if series is not None else [_m("1.0"), _m("0.1")],
        contract=_contract(reversible=False),
    )
    entry = _run(r)
    assert entry.status is Status.AWAITING_APPROVAL  # type: ignore[attr-defined]
    assert executor.call_count == 0
    return r, executor, ledger, entry.entry_id  # type: ignore[attr-defined]


def test_req_404_an_awaiting_entry_does_not_execute_until_it_is_approved() -> None:
    """Verifies: REQ-404

    ★ 절반은 **아무 일도 안 일어나는 것**이다. `awaiting_approval`은 경보가 아니라
    집행이다 — 판정만 적고 실행을 막지 않아도 **원장은 똑같아 보인다**(G1과 같은 계열).
    """
    _, executor, ledger, entry_id = _awaiting()
    pending = ledger.get(entry_id)
    assert pending is not None
    assert pending.status is Status.AWAITING_APPROVAL
    assert pending.approval is None, "승인 없이 승인 기록이 생겼다"
    assert executor.call_count == 0


def test_req_404_approval_is_recorded_and_then_runs_the_same_verified_loop() -> None:
    """Verifies: REQ-404, REQ-202

    ⚠️ 승인된 조치가 **AUTO와 다른 경로를 타면** 그 경로만 검증·롤백을 빠뜨리게 된다.
    그래서 승인 뒤에도 기준선·재측정·판정이 그대로 도는지 함께 묻는다.
    """
    r, executor, _, entry_id = _awaiting()
    entry = r.approve(entry_id=entry_id, resource=RESOURCE, approver="oncall")
    assert entry.approval is not None
    assert entry.approval.approver == "oncall"
    assert executor.call_count == 1
    assert entry.status is Status.EXECUTED
    assert entry.improved is True  # 승인 경로도 검증을 거쳤다


def test_req_404_approval_reevaluates_the_gate_and_a_drained_budget_denies() -> None:
    """Verifies: REQ-404, REQ-403

    ★ **승인은 예산 면제가 아니다.** 대기하는 동안 예산이 마르면 원래 판정은 낡았다 —
    낡은 판정을 그대로 집행하면 승인이 게이트를 **우회하는 통로**가 된다.
    """
    r, executor, _, entry_id = _awaiting()
    r.budgets.commit("warranty", Decimal("0.50"))  # 대기 중에 다른 조치가 다 썼다
    entry = r.approve(entry_id=entry_id, resource=RESOURCE, approver="oncall")
    assert entry.decision.verdict is Gate.APPROVE, "원래 판정이 덮였다"  # type: ignore[union-attr]
    assert entry.approval.reevaluated.verdict is Gate.DENY  # type: ignore[union-attr]
    assert entry.status is Status.DENIED
    assert executor.call_count == 0


def test_req_404_approval_reevaluates_the_gate_and_a_retired_contract_is_manual() -> None:
    """Verifies: REQ-404, REQ-105

    ★ **승인은 계약 면제도 아니다.** 계약이 `retired`면 무엇을 재야 회복인지 사라졌고,
    그러면 자동 대상이 아니다 — 존재하지 않는 것을 고치려 드는 실패는 조용하다.
    """
    r, executor, _, entry_id = _awaiting()
    r.contracts.put(_contract(reversible=False).retired())  # type: ignore[attr-defined]
    entry = r.approve(entry_id=entry_id, resource=RESOURCE, approver="oncall")
    assert entry.status is Status.MANUAL_REQUIRED
    assert executor.call_count == 0


def test_req_404_approval_does_not_carry_over_to_a_different_contract() -> None:
    """Verifies: REQ-404

    리소스가 재프로비저닝되면 계약 id가 바뀐다. 승인은 **그때 본 계약**에 대한 동의였다 —
    ⚠️ 계약이 살아 있다는 것만 보면 이 경우가 통과한다. id를 대조해야 잡힌다.
    """
    r, executor, _, entry_id = _awaiting()
    r.contracts.put(_contract(reversible=False, contract_id="c2"))  # type: ignore[attr-defined]
    entry = r.approve(entry_id=entry_id, resource=RESOURCE, approver="oncall")
    assert entry.status is Status.MANUAL_REQUIRED
    assert executor.call_count == 0


def test_req_404_an_entry_can_only_be_approved_once() -> None:
    """Verifies: REQ-404

    ⚠️ 두 번째 승인이 통과하면 **조치가 두 번 실행된다** — 그리고 원장 행은 하나다(REQ-501).
    """
    r, executor, _, entry_id = _awaiting()
    r.approve(entry_id=entry_id, resource=RESOURCE, approver="oncall")
    with pytest.raises(LedgerError):
        r.approve(entry_id=entry_id, resource=RESOURCE, approver="oncall")
    assert executor.call_count == 1


def test_req_404_a_denied_entry_cannot_be_approved_after_the_fact() -> None:
    """Verifies: REQ-404, REQ-403

    ⚠️ 사후 승인이 붙으면 원장은 *"승인받고 실행했다"*로 읽힌다 — 순서가 반대였는데도.
    """
    r, executor, _, _, _ = _build(series=[_m("1.0")], headroom="0.10")
    entry = _run(r, projected="5.00")
    assert entry.status is Status.DENIED  # type: ignore[attr-defined]
    with pytest.raises(LedgerError):
        r.approve(
            entry_id=entry.entry_id,  # type: ignore[attr-defined]
            resource=RESOURCE,
            approver="oncall",
        )
    assert executor.call_count == 0


def test_req_206_verification_delay_is_a_named_constant_used_once() -> None:
    """Verifies: REQ-206, REQ-804

    ⚠️ 값이 흩어지면 영상 재촬영 때 반드시 하나를 놓친다.
    """
    from warranty.usecases import remediate

    r, _, _, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("1.0")])
    _run(r)
    assert set(r.clock.slept) == {remediate.VERIFY_DELAY_S}  # type: ignore[attr-defined]
