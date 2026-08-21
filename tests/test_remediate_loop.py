"""루프 전체 — 조치 → 검증 → 롤백. 가드 G1·G4.

⚠️ 전부 fake 어댑터다. 이 테스트가 통과한다고 REQ-601·602가 만족되지 않는다 —
   스텁은 인터페이스의 **존재**를 증명하지 않는다 (docs/PRINCIPLES.md #3).
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from enum import Enum, auto
from typing import TypedDict

import pytest

from warranty.adapters.fakes import (
    FakeBudget,
    FakeJudge,
    FakeRun,
    FrozenClock,
    InMemoryContracts,
    RecordingExecutor,
    ReentrantExecutor,
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
from warranty.domain.decision import Decision, Gate
from warranty.domain.entry import (
    Approval,
    InMemoryLedger,
    LedgerEntry,
    LedgerError,
    Rollback,
    Status,
)
from warranty.domain.verification import DecidedBy, Measurement, Verdict, Verification
from warranty.usecases.remediate import Remediator

RESOURCE = ResourceRef("cloud_run_service", "demo-target", "us-central1")
PREVIOUS = "demo-target-00007-abc"
CRIT = Criterion(Direction.DECREASE, Decimal("0.5"), CriterionMode.RELATIVE, Decimal("0.1"))


class _Unset(Enum):
    """*"계약을 안 넘겼다"*와 `contract=None`(**계약이 없는 리소스**)을 가른다.

    기본 계약을 인자 기본값에서 만들 수 없어서 센티널이 필요하다. ⚠️ 그 센티널이
    `object()`면 인자 타입이 `object`로 넓어지고 `contracts.put`이 억제를 달아야 한다 —
    단일 멤버 enum이면 `is`로 좁혀지므로 억제 없이 같은 일을 한다.
    """

    TOKEN = auto()


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


class _Case(TypedDict, total=False):
    """`_build` 재정의 묶음 — 여러 경우를 값으로 태우는 루프가 쓴다.

    ⚠️ `dict[str, object]`로 두면 `_build(**kwargs)`가 억제를 달아야 하고, **키 오타가
    조용히 기본값으로 흘러** 그 경우는 안 물어진 채 초록이 된다.
    """

    contract: OperationalContract | None
    readable: bool
    headroom: str


def _build(
    *,
    series: list[Measurement],
    contract: OperationalContract | None | _Unset = _Unset.TOKEN,
    readable: bool = True,
    headroom: str = "0.50",
    judge_verdict: Verdict = Verdict.NOT_RECOVERED,
    honors_shift: bool = True,
) -> tuple[Remediator, RecordingExecutor, FakeRun, InMemoryLedger, FakeJudge]:
    resolved = _contract() if contract is _Unset.TOKEN else contract
    contracts = InMemoryContracts()
    if resolved is not None:
        contracts.put(resolved)
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


def _run(r: Remediator, projected: str = "0.01", *, destructive: bool = False) -> LedgerEntry:
    """⚠️ 반환을 `object`로 두면 **그 뒤의 모든 단언이 억제를 단다** — 그리고 억제가 붙은
    자리는 `entry.improved`를 `entry.improvd`로 잘못 써도 mypy가 말해 주지 않는다.
    """
    return r.remediate(
        agent_id="warranty",
        action_id="shift_traffic",
        resource=RESOURCE,
        projected_usd=Decimal(projected),
        destructive=destructive,
    )


# ── 선택 필드를 **좁혀서** 읽는다 ──────────────────────────────────────
# ⛔ `decision`·`verification`·`rollback`·`approval`은 넷 다 `| None`이다. 픽스처가
#    `object`를 반환하던 동안 그 사실이 억제 뒤에 가려져 있었다(T0-9). 없을 때 여기서
#    **"왜 없는가"로** 먼저 실패한다 — `NoneType has no attribute`보다 그게 낫다.


def _decision(entry: LedgerEntry) -> Decision:
    assert entry.decision is not None, f"판정 없는 항목: {entry.entry_id}"
    return entry.decision


def _verification(entry: LedgerEntry) -> Verification:
    assert entry.verification is not None, f"검증 없는 항목: {entry.entry_id}"
    return entry.verification


def _rollback(entry: LedgerEntry) -> Rollback:
    assert entry.rollback is not None, f"롤백 기록 없는 항목: {entry.entry_id}"
    return entry.rollback


def _approval(entry: LedgerEntry) -> Approval:
    assert entry.approval is not None, f"승인 기록 없는 항목: {entry.entry_id}"
    return entry.approval


# ── fake의 **기록 표면**을 좁혀서 읽는다 ───────────────────────────────
# ⚠️ `Remediator`의 협력자는 전부 포트 타입이다. `settled`·`slept`·`put`은 fake에만 있고,
#    포트에 없는 것이 옳다 — 실물 어댑터가 그것을 들고 다닐 이유가 없다.


def _budgets(r: Remediator) -> FakeBudget:
    assert isinstance(r.budgets, FakeBudget)
    return r.budgets


def _clock(r: Remediator) -> FrozenClock:
    assert isinstance(r.clock, FrozenClock)
    return r.clock


def _contracts(r: Remediator) -> InMemoryContracts:
    assert isinstance(r.contracts, InMemoryContracts)
    return r.contracts


# ── ★ G1 — 막는 판정이면 실행기를 부르지 않는다 ────────────────────────


def test_req_403_deny_never_calls_the_executor() -> None:
    """Verifies: REQ-403

    ★ G1 — 판정만 적고 실행을 막지 않아도 **로그는 똑같아 보인다.**
    그래서 호출 횟수를 센다.
    """
    r, executor, _, _, _ = _build(series=[_m("1.0")], headroom="0.10")
    entry = _run(r, projected="5.00")
    assert _decision(entry).verdict is Gate.DENY
    assert entry.status is Status.DENIED
    assert executor.call_count == 0


def test_req_403_a_blocking_verdict_with_budget_left_still_never_executes() -> None:
    """Verifies: REQ-403, REQ-405

    ⚠️ **예산이 막는 것과 게이트가 막는 것은 다르다.** 위 테스트는 여유가 없어서 `DENY`인
    경우다 — 판정 집행을 통째로 지워도 **예약이 대신 막아** 초록이 된다(실제로 그랬다:
    M-18이 REQ-405를 넣자마자 초록으로 돌아섰다). 그러면 G1은 하중을 안 받는다.

    그래서 **여유가 남은 채로 막히는** 판정을 태운다 — 비가역 + 검증 불가 = `MANUAL`.
    """
    r, executor, _, _, _ = _build(
        series=[_m("1.0")], contract=_contract(reversible=False), readable=False, headroom="0.50"
    )
    entry = _run(r, projected="0.01")
    assert _decision(entry).verdict is Gate.MANUAL
    assert entry.status is Status.MANUAL_REQUIRED
    assert executor.call_count == 0
    assert r.budgets.headroom("warranty") == Decimal("0.50"), "막힌 조치가 예약을 잡았다"


def test_req_104_no_contract_is_manual_and_never_executes() -> None:
    """Verifies: REQ-104

    ⛔ 계약이 없다는 것은 **무엇을 재야 회복인지 모른다**는 뜻이고, 모르면 검증이 불가능하다.
    """
    r, executor, _, _, _ = _build(series=[_m("1.0")], contract=None)
    entry = _run(r)
    assert entry.status is Status.MANUAL_REQUIRED
    assert entry.contract_id is None
    assert executor.call_count == 0


def test_req_104_a_missing_contract_is_recorded_as_not_verifiable() -> None:
    """Verifies: REQ-104, REQ-402

    ⚠️ **상태만 물으면 이 자리는 비어 있다.** 계약 *없음*을 검증 가능으로 쳐도
    `status`는 아래 전용 분기가 따로 덮어 `manual_required` 그대로고, 실행기도 안 불린다 —
    갈라지는 것은 **판정과 그 사유**뿐이다(M-63). 그리고 그걸 잡던 자리는 데모 서사
    하나였다: 시나리오가 바뀌면 그 하중은 **조용히 사라진다.**

    ⛔ 계약이 없다는 것은 **무엇을 재야 회복인지 모른다**는 뜻이고, 모르면 검증이 불가능하다.
    원장이 *"검증 가능했다"*고 적으면 그 항목은 나중에 자동 대상으로 읽힌다.
    """
    r, executor, _, _, _ = _build(series=[_m("1.0")], contract=None)
    entry = _run(r)
    decision = _decision(entry)
    assert decision.verifiable is False, "계약이 없는데 검증 가능하다고 원장에 적혔다"
    assert decision.verdict is Gate.MANUAL
    assert "not verifiable" in decision.rule, f"막은 사유가 검증 가능성이 아니다: {decision.rule}"
    assert executor.call_count == 0


def test_req_104_no_contract_stays_manual_when_the_budget_is_the_binding_reason() -> None:
    """Verifies: REQ-104

    ⚠️ 여유가 남아 있으면 게이트도 `MANUAL`을 낸다 — 그래서 **계약 없음 전용 분기를 통째로
    지워도 값이 똑같다**(M-64는 그렇게 150건 전부 초록으로 살아남았다). 두 경로가 갈라지는
    경우는 하나뿐이다: **예산이 먼저 막을 때.**

    ⛔ 그때 원장이 `denied`라고만 적으면 *"계약이 없었다"*는 사실은 어디에도 안 남는다 —
    예산을 채우면 자동으로 도는 조치처럼 읽히고, 실제로는 잴 신호조차 없는 리소스다.
    """
    r, executor, _, _, _ = _build(series=[_m("1.0")], contract=None, headroom="0.10")
    entry = _run(r, projected="5.00")
    assert entry.status is Status.MANUAL_REQUIRED, "예산 판정이 계약 없음을 덮어썼다"
    assert entry.contract_id is None
    # 예산이 막았다는 사실 자체는 판정에 남는다 — 상태가 그걸 지우는 게 아니다.
    assert _decision(entry).verdict is Gate.DENY
    assert executor.call_count == 0


def test_req_105_a_retired_contract_is_not_a_contract_on_the_action_path() -> None:
    """Verifies: REQ-105

    ⚠️ 지금까지 `retired`를 태우던 자리는 **승인 경로 하나**였다 — M-65·M-66을 죽인 것도
    그 하나다. 조치 경로는 Day-2의 정상 입구인데, 거기서 죽은 계약을 물어본 적이 없다.

    ⛔ 죽은 계약이 조회에 걸리면 자동 조치가 **존재하지 않는 것을 고치려 든다.**
    그 실패는 조용하다: 조치는 '성공'하고 신호는 안 움직인다.
    ⚠️ 값 하나로 공허해지지 않게 **회복하는 신호**를 태운다 — 계약이 살아 있었다면
    이 입력은 `AUTO`로 실행되고 `recovered`로 닫혔을 것이다.
    """
    r, executor, _, _, _ = _build(series=[_m("1.0"), _m("0.1")], contract=_contract().retired())
    entry = _run(r)
    assert entry.status is Status.MANUAL_REQUIRED
    assert entry.contract_id is None, "종료된 계약이 살아 있는 계약으로 원장에 실렸다"
    assert executor.call_count == 0


def test_req_402_unreadable_signal_blocks_automation() -> None:
    """Verifies: REQ-402, REQ-403

    ★ 정책의 집행 지점. 계약은 있지만 **신호를 지금 못 읽으면** 자동이 아니다.
    """
    r, executor, _, _, _ = _build(series=[_m("1.0")], readable=False)
    entry = _run(r)
    assert _decision(entry).verdict is Gate.APPROVE
    assert entry.status is Status.AWAITING_APPROVAL
    assert executor.call_count == 0


# ── ★ G4 — 모든 항목이 판정을 갖는다 ───────────────────────────────────


def test_req_401_every_entry_carries_a_decision() -> None:
    """Verifies: REQ-401

    ★ G4 — 게이트를 안 거친 실행 경로가 생기면 여기서 잡힌다.
    """
    cases: tuple[_Case, ...] = (_Case(headroom="0.10"), _Case(readable=False), _Case())
    for kwargs in cases:
        r, _, _, ledger, _ = _build(series=[_m("1.0"), _m("0.2")], **kwargs)
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
    # ⚠️ `Remediator.signals`는 포트 타입이다 — 기록 표면(`reads`)은 fake만 갖는다.
    assert isinstance(signals, ScriptedSignal)
    assert len(signals.reads) >= 2
    assert signals.reads[0] is signals.reads[1]


def test_req_204_the_model_is_not_called_when_the_verdict_is_clear() -> None:
    """Verifies: REQ-204

    ⚠️ 명확한 경우까지 모델에 맡기면 판정이 비결정적이 되고 REQ-802가 깨진다.
    """
    r, _, _, _, judge = _build(series=[_m("1.0"), _m("0.1")])
    entry = _run(r)
    assert _verification(entry).verdict is Verdict.RECOVERED
    assert _verification(entry).decided_by is DecidedBy.RULE
    assert judge.calls == 0


def test_req_204_ambiguous_goes_to_the_model_and_keeps_the_rationale() -> None:
    """Verifies: REQ-204

    ★ 모델의 판단이 하중을 받는 자리. 근거가 원장에 **문장으로** 남는다.
    """
    r, _, _, _, judge = _build(series=[_m("1.0"), _m("0.5")])
    entry = _run(r)
    assert judge.calls == 1
    assert _verification(entry).decided_by is DecidedBy.MODEL
    assert "symptom" in _verification(entry).rationale


# ── ★ 롤백 (REQ-302, 303, 304, 305) ────────────────────────────────────


def test_req_302_failed_verification_triggers_rollback() -> None:
    """Verifies: REQ-302, REQ-502

    ★ 이 시스템이 말할 수 있는 문장: **실행은 됐고, 나아지지는 않았고, 되돌렸다.**
    """
    r, executor, run, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("1.0")])
    entry = _run(r)
    assert executor.call_count == 1
    assert entry.executed is True
    assert entry.improved is False
    assert entry.rolled_back is True
    assert run.shifts == [PREVIOUS]


def test_req_302_a_not_recovered_the_model_closed_rolls_back_too() -> None:
    """Verifies: REQ-302, REQ-204

    ⛔ **REQ-302는 누가 판정했는지를 말하지 않는다** — *"검증이 `not_recovered`일 때"*다.
    그런데 위 테스트가 태우는 것은 **규칙이 닫은 경우 하나뿐**이었다. 모델이 닫은
    미회복을 롤백에서 빼도 144건이 전부 초록이었다 (M-62).

    ⚠️ 그 구멍이 특히 나쁜 이유: 모델이 불리는 경우는 정의상 **애매한 경우**다
    (tolerance 안쪽). 즉 *"롤백이 조용히 사라지는 구간"*이 하필 **판단이 어려운 구간**과
    정확히 겹친다 — 그리고 원장은 `executed=true`만 남긴 채 똑같아 보인다.
    """
    r, _, run, _, judge = _build(series=[_m("1.0"), _m("0.5"), _m("1.0")])
    entry = _run(r)
    assert judge.calls == 1, "이 경우가 모델 경로가 아니다 — 이 테스트는 아무것도 안 묻고 있다"
    assert _verification(entry).decided_by is DecidedBy.MODEL
    assert _verification(entry).verdict is Verdict.NOT_RECOVERED
    assert entry.improved is False
    assert entry.rolled_back is True, "모델이 닫은 미회복이 롤백을 건너뛰었다"
    assert run.shifts == [PREVIOUS]


def test_req_302_a_recovered_the_model_closed_does_not_roll_back() -> None:
    """Verifies: REQ-302, REQ-204

    ⚠️ 위 테스트만 있으면 *"모델 경로면 무조건 롤백"*으로 고쳐도 초록이다 — 그건
    **나아진 조치를 되돌리는** 반대편 오류이고, 원장에는 `rolled_back=true`로 남는다.
    롤백을 여는 것은 경로가 아니라 **판정**이어야 한다.
    """
    r, _, run, _, judge = _build(series=[_m("1.0"), _m("0.5")], judge_verdict=Verdict.RECOVERED)
    entry = _run(r)
    assert judge.calls == 1
    assert _verification(entry).decided_by is DecidedBy.MODEL
    assert entry.improved is True
    assert entry.rolled_back is False
    assert run.shifts == []


def test_req_303_rollback_is_proved_by_reading_the_traffic_split_back() -> None:
    """Verifies: REQ-303

    ⚠️ **"롤백했다"는 주장이고 "트래픽이 이전 리비전으로 갔다"는 측정이다.**
    """
    r, _, _, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("1.0")])
    entry = _run(r)
    assert _rollback(entry).verified_traffic == {PREVIOUS: 100}


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
    assert _rollback(entry).performed is False
    assert _rollback(entry).verified_traffic != {PREVIOUS: 100}
    assert "did not reach" in _rollback(entry).reason
    assert entry.rolled_back is False


def test_req_304_the_signal_is_measured_again_after_the_rollback() -> None:
    """Verifies: REQ-304

    되돌렸는데 안 돌아오면 **원인이 조치가 아니었다** — 그건 에스컬레이션 사유다.
    """
    r, _, _, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("1.0")])
    assert _rollback(_run(r)).signal_restored is True

    r2, _, _, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("0.2")])
    assert _rollback(_run(r2)).signal_restored is False


def test_req_305_irreversible_failure_escalates_instead_of_retrying() -> None:
    """Verifies: REQ-305

    ⚠️ **실패한 자동화가 계속 시도하는 것이 가장 나쁜 상태다.**
    """
    r, _, run, _, _ = _build(series=[_m("1.0"), _m("0.95")], contract=_contract(reversible=False))
    entry = _run(r)
    # 비가역 + 검증 가능 → APPROVE 이므로 자동 실행되지 않는다
    assert _decision(entry).verdict is Gate.APPROVE
    assert run.shifts == []


def test_req_305_an_irreversible_action_that_did_not_recover_escalates_and_stops() -> None:
    """Verifies: REQ-305

    ⛔ **위 테스트는 게이트가 막는 경우다** — 조치가 아예 안 돌아서 *"에스컬레이션한다"*는
    절반을 안 태운다. 비가역 계약이 실제로 실행되는 입구는 **승인**뿐이고(REQ-404),
    그때 `_rollback`의 *"계획이 없다"* 분기에 처음 도달한다. 그 자리에 오는 입력이
    스위트에 없었다 — 즉 M-84가 태우는 자리는 여기서만 값이 된다.

    ⚠️ **`escalated`는 `rolled_back`의 부정이 아니다**(REQ-508). 되돌릴 계획이 없으면
    트래픽을 건드리지도 않는다 — 그런데 조치는 이미 나갔고 신호는 안 돌아왔다.
    그 상태를 원장이 *"되돌렸다"*로도 *"아무 일 없었다"*로도 적으면 안 된다.
    """
    r, executor, run, _, _ = _build(
        series=[_m("1.0"), _m("0.95")], contract=_contract(reversible=False)
    )
    entry = _run(r)
    assert _decision(entry).verdict is Gate.APPROVE

    approved = r.approve(entry_id=entry.entry_id, resource=RESOURCE, approver="oncall")

    assert approved.status is Status.EXECUTED
    assert approved.improved is False, "이 경우가 회복이면 롤백 분기에 도달하지 않는다"
    assert _rollback(approved).performed is False
    assert "escalated" in _rollback(approved).reason
    assert approved.escalated is True, "되돌릴 수 없는 미회복이 에스컬레이션으로 안 남았다"
    assert approved.rolled_back is False
    assert run.shifts == [], "롤백 계획이 없는데 트래픽을 옮겼다"
    assert executor.call_count == 1, "에스컬레이션한 뒤에 더 조치했다"


def test_req_305_a_rollback_that_failed_escalates_and_does_not_try_again() -> None:
    """Verifies: REQ-305

    ⛔ **REQ-305의 조건은 둘이다** — *"비가역이라 선언했거나 **롤백이 실패하면**"*.
    배분이 안 옮겨진 경우를 태우는 자리는 있었지만(REQ-303) 그 자리는 `performed is False`
    까지만 물었다. **실패한 자동화가 계속 시도하는 것이 가장 나쁜 상태다** — 재시도를
    넣어도 원장의 `rollback` 칸은 똑같아 보이고, 늘어나는 것은 호출 횟수뿐이다.

    ⚠️ 그래서 값이 아니라 **호출 흔적**에 묻는다: 전환 1회 · 조치 1회.
    """
    r, executor, run, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("1.0")], honors_shift=False)
    entry = _run(r)

    assert _rollback(entry).performed is False, "이 경우가 롤백 성공이면 아무것도 안 묻고 있다"
    assert entry.escalated is True, "실패한 롤백이 에스컬레이션으로 안 남았다"
    assert entry.rolled_back is False
    assert run.shifts == [PREVIOUS], "롤백이 실패하자 전환을 다시 시도했다"
    assert executor.call_count == 1, "롤백이 실패한 뒤에 조치를 다시 했다"


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
    assert entry.status is Status.AWAITING_APPROVAL
    assert executor.call_count == 0
    return r, executor, ledger, entry.entry_id


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
    r.budgets.reserve("warranty", Decimal("0.50"))  # 대기 중에 다른 조치가 다 예약해 갔다
    entry = r.approve(entry_id=entry_id, resource=RESOURCE, approver="oncall")
    assert _decision(entry).verdict is Gate.APPROVE, "원래 판정이 덮였다"
    assert _approval(entry).reevaluated.verdict is Gate.DENY
    assert entry.status is Status.DENIED
    assert executor.call_count == 0


def test_req_404_approval_reevaluates_the_gate_and_an_unreadable_signal_is_manual() -> None:
    """Verifies: REQ-404, REQ-402

    ★ **승인은 검증 가능성 면제도 아니다.** 대기하는 동안 모니터링이 죽으면 회복을
    확인할 방법이 사라진다 — 비가역인데 확인도 못 하면 `MANUAL`이다.

    ⚠️ 이 케이스가 없으면 재판정 가드가 **예산 하나로만** 물린다. 예산이 마른 경우는
    예약(REQ-405)이 대신 막아 주므로, 재판정을 지워도 초록이 된다 — 실제로 그랬다.
    """
    r, executor, _, entry_id = _awaiting()
    r = replace(r, signals=ScriptedSignal([_m("1.0"), _m("0.1")], readable=False))
    entry = r.approve(entry_id=entry_id, resource=RESOURCE, approver="oncall")
    assert _approval(entry).reevaluated.verdict is Gate.MANUAL
    assert entry.status is Status.MANUAL_REQUIRED
    assert executor.call_count == 0
    assert r.budgets.headroom("warranty") == Decimal("0.50"), "막힌 승인이 예약을 잡았다"


def test_req_404_approval_reevaluates_the_gate_and_a_retired_contract_is_manual() -> None:
    """Verifies: REQ-404, REQ-105

    ★ **승인은 계약 면제도 아니다.** 계약이 `retired`면 무엇을 재야 회복인지 사라졌고,
    그러면 자동 대상이 아니다 — 존재하지 않는 것을 고치려 드는 실패는 조용하다.
    """
    r, executor, _, entry_id = _awaiting()
    _contracts(r).put(_contract(reversible=False).retired())
    entry = r.approve(entry_id=entry_id, resource=RESOURCE, approver="oncall")
    assert entry.status is Status.MANUAL_REQUIRED
    assert executor.call_count == 0


def test_req_404_approval_does_not_carry_over_to_a_different_contract() -> None:
    """Verifies: REQ-404

    리소스가 재프로비저닝되면 계약 id가 바뀐다. 승인은 **그때 본 계약**에 대한 동의였다 —
    ⚠️ 계약이 살아 있다는 것만 보면 이 경우가 통과한다. id를 대조해야 잡힌다.
    """
    r, executor, _, entry_id = _awaiting()
    _contracts(r).put(_contract(reversible=False, contract_id="c2"))
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
    assert entry.status is Status.DENIED
    with pytest.raises(LedgerError):
        r.approve(entry_id=entry.entry_id, resource=RESOURCE, approver="oncall")
    assert executor.call_count == 0


# ── ★ 예산 예약 · 정산 (REQ-405) ──────────────────────────────────────


class _ExplodingSignal(ScriptedSignal):
    """재측정 중에 모니터링이 죽는다 — 예약이 예외 경로에서도 풀리는지 묻는 장치."""

    def read(self, spec: SignalSpec) -> Measurement:
        raise RuntimeError("monitoring is down")


def test_req_405_a_reservation_stops_a_second_action_spending_the_same_headroom() -> None:
    """Verifies: REQ-405, REQ-403

    ★ 이 항목의 전부. 게이트는 여유를 **읽고** 돈은 실행 **뒤에** 나간다 — 그 창에서
    들어온 두 번째 조치는 **같은 여유를 다시 본다.** 실행 전에 예약하지 않으면 둘 다
    통과하고 합계(0.60)가 한도(0.50)를 넘는다. 넘은 돈은 되돌릴 수 없다.

    ⚠️ 스레드가 없으니(REQ-802) 그 창은 **재진입으로만** 값이 된다.
    """
    r, _, _, _, _ = _build(series=[_m("1.0"), _m("0.1")], headroom="0.50")
    executor = ReentrantExecutor()
    r = replace(r, executor=executor)
    inner: list[LedgerEntry] = []
    executor.during = lambda: inner.append(_run(r, projected="0.30"))

    outer = _run(r, projected="0.30")

    assert executor.call_count == 1, "안쪽 조치가 실행됐다 — 예산이 초과됐다"
    assert _decision(inner[0]).verdict is Gate.DENY
    assert inner[0].status is Status.DENIED
    assert outer.status is Status.EXECUTED
    assert r.budgets.headroom("warranty") == Decimal("0.20")  # 0.30 하나만 나갔다


def test_req_405_a_successful_action_settles_the_reservation_and_locks_nothing() -> None:
    """Verifies: REQ-405

    정산이 안 돌면 예산이 **조용히 잠긴다** — 잠긴 예산은 "예산 없음"과 구분이 안 된다.
    """
    r, _, _, _, _ = _build(series=[_m("1.0"), _m("0.1")], headroom="0.50")
    _run(r, projected="0.10")
    assert _budgets(r).settled == [Decimal("0.10")]
    assert r.budgets.headroom("warranty") == Decimal("0.40")
    assert r.budgets.unsettled() == 0


def test_req_405_a_failed_action_settles_to_zero_and_gives_the_headroom_back() -> None:
    """Verifies: REQ-405, REQ-507

    ⚠️ **API가 실패했으면 쓴 게 없다.** 예약분을 그대로 지출로 확정하면 실패가
    반복될수록 예산이 마르고, 마른 이유가 원장 어디에도 없다.
    """
    r, _, _, _, _ = _build(series=[_m("1.0"), _m("0.1")], headroom="0.50")
    r = replace(r, executor=RecordingExecutor(succeeds=False))
    entry = _run(r, projected="0.10")
    assert entry.status is Status.FAILED
    assert _budgets(r).settled == [Decimal(0)]
    assert r.budgets.headroom("warranty") == Decimal("0.50")
    assert r.budgets.unsettled() == 0


def test_req_405_a_blocking_verdict_reserves_nothing() -> None:
    """Verifies: REQ-405, REQ-403

    ⚠️ 막힌 조치가 예약을 잡고 놓지 않으면 **거부가 예산을 갉아먹는다** —
    실행기는 안 불렸는데 여유는 줄어 있고, 그 줄어듦은 원장에 안 남는다.
    """
    cases: tuple[_Case, ...] = (_Case(headroom="0.10"), _Case(readable=False), _Case(contract=None))
    for kwargs in cases:
        r, executor, _, _, _ = _build(series=[_m("1.0")], **kwargs)
        _run(r, projected="5.00" if kwargs.get("headroom") else "0.01")
        assert executor.call_count == 0
        assert r.budgets.unsettled() == 0
        assert r.budgets.headroom("warranty") == Decimal(kwargs.get("headroom", "0.50"))


def test_req_405_the_reservation_is_released_even_when_the_loop_raises() -> None:
    """Verifies: REQ-405

    ★ design 04§3이 이름 붙인 실패다: **`settle`이 안 돌면 예산이 조용히 잠긴다.**
    예외가 나면 원장 항목은 미완인 채로 남지만, 예약까지 남으면 **그 에이전트는
    영영 여유가 부족한 것처럼 보인다.**
    """
    r, _, _, _, _ = _build(series=[_m("1.0")], headroom="0.50")
    r = replace(r, signals=_ExplodingSignal([_m("1.0")]))
    with pytest.raises(RuntimeError):
        _run(r, projected="0.10")
    assert r.budgets.unsettled() == 0, "예약이 잠긴 채 남았다"
    assert r.budgets.headroom("warranty") == Decimal("0.50")


def test_req_405_the_approved_path_reserves_through_the_same_seam() -> None:
    """Verifies: REQ-405, REQ-404

    ⚠️ 승인 경로가 예약을 건너뛰면 **승인이 예산 우회로가 된다** — REQ-404가 막으려던
    바로 그것이 예약 축에서 되살아난다.
    """
    r, executor, _, entry_id = _awaiting()
    entry = r.approve(entry_id=entry_id, resource=RESOURCE, approver="oncall")
    assert entry.status is Status.EXECUTED
    assert executor.call_count == 1
    assert _budgets(r).settled == [Decimal("0.01")]
    assert r.budgets.unsettled() == 0


# ── ★ 원장 완결성 — 막힌 것·실패한 것도 남는다 (REQ-507) ─────────────


class _RacingBudget(FakeBudget):
    """게이트가 여유를 **읽은 직후** 다른 조치가 전부 예약해 간다.

    ⚠️ 이 fake 없이는 *"판정은 `AUTO`인데 예약이 막는다"*가 값이 안 된다. 재진입으로는
       안 만들어진다 — 안쪽 조치는 **이미 줄어든 여유를** 게이트가 다시 읽으므로 판정부터
       `DENY`이고, 그러면 예약 실패 분기에는 도달하지 못한다.
    """

    def headroom(self, agent_id: str) -> Decimal:
        seen = super().headroom(agent_id)
        super().reserve("other-agent", seen)  # 창 안에서 다른 조치가 다 가져갔다
        return seen


def test_req_507_a_blocked_action_still_leaves_its_row_in_the_ledger() -> None:
    """Verifies: REQ-507, REQ-403

    ⛔ **반환값이 아니라 원장에 묻는다.** 막힌 조치의 행을 아예 안 만들어도 호출자가 받는
    객체는 똑같다 — 상태도 `denied`/`manual_required` 그대로다. 사라지는 것은 *"원장에
    남았는가"*뿐이고, 그러면 원장은 **실행된 것만** 세게 된다. 게이트가 얼마를 막았는지는
    게이트의 유일한 실적 지표이고, 그 숫자가 없으면 게이트는 비용으로만 보인다.

    ⚠️ 지금까지 이 자리를 물던 것은 승인 경로였다 — `approve()`가 행을 **찾아야 해서**
       죽었을 뿐이다. `awaiting_approval`이 아닌 두 상태는 아무도 안 묻고 있었다.
    """
    cases: tuple[tuple[_Case, str, Status], ...] = (
        (_Case(headroom="0.10"), "5.00", Status.DENIED),
        (
            _Case(contract=_contract(reversible=False), readable=False),
            "0.01",
            Status.MANUAL_REQUIRED,
        ),
        (_Case(contract=None), "0.01", Status.MANUAL_REQUIRED),
    )
    for kwargs, projected, expected in cases:
        r, executor, _, ledger, _ = _build(series=[_m("1.0")], **kwargs)
        entry = _run(r, projected=projected)
        assert executor.call_count == 0, f"막는 판정인데 실행됐다: {expected}"
        assert [row.entry_id for row in ledger.all_entries()] == [entry.entry_id], (
            f"막힌 조치가 원장에 안 남았다: {expected}"
        )
        stored = ledger.get(entry.entry_id)
        assert stored is not None and stored.status is expected


def test_req_507_a_reservation_that_loses_the_race_is_recorded_as_denied() -> None:
    """Verifies: REQ-507, REQ-405

    ⛔ 판정은 `AUTO`인데 **예약이 막은** 경우다 — 게이트가 여유를 읽은 시점과 돈이 나가는
    시점 사이는 창이고, 그 창에서 막히면 판정은 이미 낡았다. 원장을 안 고치면 그 행은
    게이트가 적어 둔 `executed`로 남는다: 실행기는 안 불렸는데 원장이 *"실행했다"*고
    말하고, 그 거짓말은 리포트의 **분모**에 실려 회복률을 희석한다.

    ⚠️ 회복하는 신호를 태운다 — 막히지 않았다면 `executed` + `improved`로 닫혔을 입력이라
       이 단언이 공허하게 통과할 수 없다.
    """
    r, executor, _, ledger, _ = _build(series=[_m("1.0"), _m("0.1")])
    r = replace(r, budgets=_RacingBudget(Decimal("0.50")))
    entry = _run(r, projected="0.10")
    assert _decision(entry).verdict is Gate.AUTO, "게이트에서 먼저 막히면 예약 분기를 안 묻는다"
    assert executor.call_count == 0
    stored = ledger.get(entry.entry_id)
    assert stored is not None
    assert stored.status is Status.DENIED
    assert stored.executed is False


def test_req_507_a_failed_action_is_recorded_as_failed_not_as_executed() -> None:
    """Verifies: REQ-507

    ⚠️ 이 문장의 하중을 들고 있던 것은 **예산 정산 테스트**였다(REQ-405). 실패를
    `executed`로 적어도 그 테스트가 죽는 이유는 상태가 아니라 정산액이고, 정산을 묻는
    자리가 정리되면 *"실패도 원장에 남는다"*는 조용히 안 물어지게 된다.

    ⚠️ 여기서도 회복하는 신호를 태운다 — 실행이 성공했다면 `improved`로 닫혔을 입력이다.
    """
    r, _, _, ledger, _ = _build(series=[_m("1.0"), _m("0.1")])
    r = replace(r, executor=RecordingExecutor(succeeds=False))
    entry = _run(r, projected="0.10")
    stored = ledger.get(entry.entry_id)
    assert stored is not None
    assert stored.status is Status.FAILED
    assert stored.executed is False
    assert stored.improved is False


def test_req_206_the_loop_sleeps_the_value_the_tunables_module_holds() -> None:
    """Verifies: REQ-206, REQ-804

    ⚠️ **이 테스트는 값만 묻는다** — 이름을 쓰는지는 `tests/test_tunables.py`가 구문으로
    묻는다(T0-10). 예전 이름은 *"named constant used once"*였는데 그건 **이 단언이 하지
    않는 약속**이었다: 호출부에 `45`를 박아도 잔 시간은 여전히 45라서 초록이다(M-44).
    여기가 지키는 것은 배선뿐이다 — *그 값이 정말 시계까지 간다.*

    ⚠️ 값을 **`tunables`에서** 읽는다 — `remediate.VERIFY_DELAY_S`는 재수출일 뿐이다(T6-3).
    거기서 읽으면 `remediate`가 상수를 국소로 가려도 자기 자신과는 맞아 초록이 된다.
    """
    from warranty.tunables import VERIFY_DELAY_S

    r, _, _, _, _ = _build(series=[_m("1.0"), _m("0.95"), _m("1.0")])
    _run(r)
    assert set(_clock(r).slept) == {VERIFY_DELAY_S}
