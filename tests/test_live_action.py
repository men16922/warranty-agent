"""조치 실행기 — **조치는 하나가 아니다** (P1 · REQ-301·302·303).

Spec: specs/warranty/design/03-atomic-rollback.md (REQ-301, REQ-302, REQ-303)

⭐ 이 파일이 묻는 것은 능력이 아니라 **논지**다. 조치가 트래픽 전환 하나뿐인 동안 이
   시스템은 카나리 롤백 도구와 구분되지 않는다. 두 번째 조치(동시성)가 **검증·롤백
   코드를 한 줄도 안 늘리고** 같은 루프를 타는가 — 그게 여기서 태우는 주장이다.

여섯을 묻는다:
  ① 구분자 없는 옛 형태가 **여전히** 트래픽 전환인가 (08-28 원장이 그 형태다)
  ② `concurrency:N`이 **트래픽 전환을 안 부르는가** — 부르면 조치가 하나로 되돌아간다
  ③ 모르는 접두어가 **조용히 트래픽 전환이 되지 않는가**
  ④ 범위 밖 동시성이 실행 전에 **`ActionError`로** 거절되는가 (크래시가 아니라 거절)
  ⑤ 트래픽 조치가 **다른 서비스의 리비전**으로 못 가는가
  ⑥ ★ 동시성 조치가 실패했을 때 **기존 롤백 경로가 그대로 되돌리는가**

⚠️ ⑥이 본체다. 나머지가 전부 초록이어도 ⑥이 red면 *"조치를 더해도 롤백은 한 벌"*이라는
   문장은 근거가 없다.
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
    ScriptedSignal,
    SeededIdGen,
)
from warranty.adapters.live_action import (
    CONCURRENCY,
    TRAFFIC,
    ActionError,
    LiveActionExecutor,
    parse_action,
    target_revision,
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
from warranty.domain.entry import InMemoryLedger, Status
from warranty.domain.verification import Measurement, Verdict
from warranty.usecases.remediate import Remediator

RESOURCE = ResourceRef("cloud_run_service", "demo-target", "us-central1")
PREVIOUS = "demo-target-00001-abc"


def test_the_action_targets_only_a_revision_of_the_requested_service() -> None:
    """⑤ ⛔ 이름만 보고 옮기면 **엉뚱한 서비스의 트래픽이 움직인다.**"""
    assert target_revision("demo-target-00002-lss", RESOURCE) == "demo-target-00002-lss"
    with pytest.raises(ActionError):
        target_revision("other-service-00002-lss", RESOURCE)
    with pytest.raises(ActionError):
        parse_action("traffic:other-service-00002-lss", RESOURCE)


def test_a_bare_action_id_is_still_a_traffic_shift() -> None:
    """① ⛔ 옛 형태를 깨면 **이미 실물에서 참인 기록이 재현 불가**가 된다.

    ⚠️ 08-28 원장 `01m13fpgc8e091es3ekpqx48f4`와 배포된 에이전트가 리비전 이름을
       그대로 넘긴다. 문법을 더하면서 그 형태를 못 읽게 되면, 더한 것은 능력이 아니라
       회귀다.
    """
    bare = parse_action("demo-target-00002-lss", RESOURCE)
    explicit = parse_action("traffic:demo-target-00002-lss", RESOURCE)
    assert bare == explicit
    assert bare.kind == TRAFFIC

    run = FakeRun()
    assert LiveActionExecutor(run).execute("demo-target-00002-lss", RESOURCE) is True
    assert run.shifts == ["demo-target-00002-lss"]
    assert run.concurrencies == []


def test_a_concurrency_action_does_not_shift_traffic() -> None:
    """② ★ **이 단언이 두 번째 조치의 전부다.**

    ⛔ `run.shifts`가 비어 있지 않으면 동시성 조치는 이름만 다른 트래픽 전환이고,
       그때 *"조치가 둘"*은 거짓이다 — Flagger 반론이 그대로 살아난다.
    """
    action = parse_action("concurrency:16", RESOURCE)
    assert action.kind == CONCURRENCY
    assert action.concurrency == 16

    run = FakeRun()
    assert LiveActionExecutor(run).execute("concurrency:16", RESOURCE) is True
    assert run.concurrencies == [16]
    assert run.shifts == []


def test_an_unknown_action_is_refused_instead_of_defaulting_to_traffic() -> None:
    """③ ⛔ 기본값을 주면 **오타 하나가 조용히 트래픽 전환**이 되고, 원장에는 그것이
    *"요청한 조치"*로 남는다."""
    run = FakeRun()
    # ⚠️ 첫 항목이 이 테스트의 하중이다: **값이 유효한 리비전 이름**이라 "모르는 접두어는
    #    트래픽 전환으로 친다"는 기본값이 생기면 그 순간 **실제로 트래픽이 옮겨진다.**
    #    나머지 둘은 값까지 틀려서 어떤 기본값을 줘도 어차피 거절된다 — 그것만 태우면
    #    이 가드는 자기가 무엇을 막는지 모른 채 초록이다.
    for unknown in ("restart:demo-target-00002-lss", "concurrancy:16", "scale:4"):
        with pytest.raises(ActionError):
            parse_action(unknown, RESOURCE)
        with pytest.raises(ActionError):
            LiveActionExecutor(run).execute(unknown, RESOURCE)
    assert run.shifts == []
    assert run.concurrencies == []


@pytest.mark.parametrize("bad", ["concurrency:0", "concurrency:1001", "concurrency:x", ""])
def test_a_concurrency_outside_the_range_is_refused_before_execution(bad: str) -> None:
    """④ ⚠️ **거절이지 크래시가 아니다.** 범위 초과가 `RunControlError`로 새어 나가면
    호출자는 그것을 못 잡고, 그 조치는 원장에 판정 없이 사라진다."""
    run = FakeRun()
    with pytest.raises(ActionError):
        LiveActionExecutor(run).execute(bad, RESOURCE)
    assert run.concurrencies == []
    assert run.shifts == []


def test_the_boundary_values_are_accepted() -> None:
    """④ 공허 통과 방지 — 경계가 **전부** 거절이면 위 테스트는 아무것도 안 묻는다."""
    assert parse_action("concurrency:1", RESOURCE).concurrency == 1
    assert parse_action("concurrency:1000", RESOURCE).concurrency == 1000


def test_a_failed_concurrency_action_rolls_back_through_the_same_atomic_path() -> None:
    """⑥ ★ **조치를 하나 더한 대가로 롤백 코드는 한 줄도 안 늘었다.**

    Spec: specs/warranty/design/03-atomic-rollback.md (REQ-302, REQ-303)

    동시성을 올린다 → 신호가 나빠진다 → `not_recovered` → **이전 리비전으로 트래픽
    전환** → 배분을 되읽어 100%를 확인한다. 그 마지막 두 걸음은 트래픽 조치를 위해
    이미 있던 것이고, 여기서 새로 쓴 것이 없다.

    ⚠️ `FakeRun.set_concurrency`가 새 리비전으로 배분을 옮기기 때문에 이 테스트는
       **실제로 되돌릴 것이 있는 상태**에서 롤백을 묻는다. 대역이 배분을 안 옮기면
       롤백은 아무것도 안 하고도 초록이 된다.
    """
    contract = OperationalContract(
        contract_id="c-concurrency",
        resource=RESOURCE,
        health_signal=SignalSpec("run.googleapis.com/request_latencies", "demo-target", "P95", 120),
        recovery_criterion=Criterion(
            Direction.DECREASE, Decimal("0.20"), CriterionMode.RELATIVE, Decimal("0.10")
        ),
        rollback_plan=RollbackPlan(PREVIOUS),
        reversibility=Reversibility.REVERSIBLE,
        provisioned_at=__import__("datetime").datetime(
            2026, 8, 29, tzinfo=__import__("datetime").UTC
        ),
        provisioned_by="e0",
    )
    contracts = InMemoryContracts()
    contracts.put(contract)
    run = FakeRun()
    ledger = InMemoryLedger()
    remediator = Remediator(
        contracts=contracts,
        signals=ScriptedSignal(
            # 기준선 → 조치 후(더 나빠졌다) → 롤백 후(돌아왔다)
            [_m("674.2"), _m("988.6"), _m("674.2")]
        ),
        executor=LiveActionExecutor(run),
        run=run,
        budgets=FakeBudget(Decimal("0.50")),
        ledger=ledger,
        clock=FrozenClock(),
        ids=SeededIdGen(),
        judge=FakeJudge(Verdict.NOT_RECOVERED, "concurrency raised, goodput fell"),
    )

    entry = remediator.remediate(
        agent_id="warranty",
        action_id="concurrency:16",
        resource=RESOURCE,
        projected_usd=Decimal("0.01"),
    )

    assert run.concurrencies == [16]  # 조치는 동시성 변경이었다
    assert entry.status is Status.EXECUTED
    assert entry.verification is not None
    assert entry.verification.verdict is Verdict.NOT_RECOVERED  # 실행됨 ≠ 나아졌음

    rollback = entry.rollback
    assert rollback is not None
    assert rollback.performed is True
    assert run.shifts == [PREVIOUS]  # 되돌리기는 **트래픽 전환** — 있던 그 경로다
    assert rollback.verified_traffic == {PREVIOUS: 100}  # 주장이 아니라 되읽은 값이다


def _m(value: str, points: int = 30) -> Measurement:
    return Measurement(Decimal(value), points)
