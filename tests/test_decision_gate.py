"""판정 게이트 — 축이 셋. 가드 G9.

⛔ 검증할 수 없는 조치는 자동으로 실행하지 않는다.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from warranty.domain.contract import Reversibility
from warranty.domain.decision import BLOCKING, Decision, Gate, decide

HEADROOM = Decimal("0.50")
CHEAP = Decimal("0.01")


def _decide(
    rev: Reversibility,
    verifiable: bool,
    *,
    projected_usd: Decimal = CHEAP,
    destructive: bool = False,
) -> Decision:
    """⚠️ 재정의 항목을 `**over: object`로 받으면 반환도 `object`가 되고, 그 뒤의 모든
    단언이 `type: ignore`를 달아야 한다 — **픽스처가 느슨하면 억제는 테스트가 문다.**
    `decide`의 인자를 그대로 열거해서 오타난 재정의도 여기서 걸리게 한다.
    """
    return decide(
        reversibility=rev,
        verifiable=verifiable,
        projected_usd=projected_usd,
        headroom_usd=HEADROOM,
        destructive=destructive,
    )


@pytest.mark.parametrize(
    ("reversibility", "verifiable", "expected"),
    [
        (Reversibility.REVERSIBLE, True, Gate.AUTO),
        (Reversibility.REVERSIBLE, False, Gate.APPROVE),
        (Reversibility.IRREVERSIBLE, True, Gate.APPROVE),
        (Reversibility.IRREVERSIBLE, False, Gate.MANUAL),
    ],
)
def test_req_402_every_cell_of_the_matrix_is_reached_by_value(
    reversibility: Reversibility, verifiable: bool, expected: Gate
) -> None:
    """Verifies: REQ-402

    ⚠️ 행복 경로만 태우면 가드가 하중을 안 받는다. **네 칸을 값으로 명시**해 태운다.
    """
    assert _decide(reversibility, verifiable).verdict is expected


def test_req_402_no_headroom_denies_regardless_of_the_other_axes() -> None:
    """Verifies: REQ-402

    다섯째 칸. 돈은 언제나 비가역이다 — 초과분은 되돌릴 수 없다.
    """
    for rev in Reversibility:
        for verifiable in (True, False):
            d = _decide(rev, verifiable, projected_usd=Decimal("9.00"))
            assert d.verdict is Gate.DENY


def test_req_402_unverifiable_can_never_be_auto() -> None:
    """Verifies: REQ-402

    ★ G9 — **이 프로젝트의 정책을 지키는 가드다.**
    검증 가능성 축을 빼도 다른 테스트는 다 통과한다. 그래서 별도로 묻는다.

    되돌릴 수 있어도 나아졌는지 확인할 수 없으면 자동으로 하지 않는다 —
    확인 못 하는 자동화는 자동화가 아니라 방치다.
    """
    for rev in Reversibility:
        for projected in (Decimal("0.00"), CHEAP, HEADROOM):
            d = _decide(rev, False, projected_usd=projected)
            assert d.verdict is not Gate.AUTO, (
                f"검증 불가인데 AUTO가 나왔다: {rev} projected={projected}"
            )


def test_req_406_destructive_actions_are_never_auto() -> None:
    """Verifies: REQ-406

    파괴적 조치는 가역성과 무관하게 최소 APPROVE다.
    ⚠️ 이 검사가 없으면 '가역이고 검증 가능한 삭제'가 자동 실행된다.
    """
    d = _decide(Reversibility.REVERSIBLE, True, destructive=True)
    assert d.verdict is Gate.APPROVE


def test_req_403_blocking_verdicts_are_exactly_deny_and_manual() -> None:
    """Verifies: REQ-403

    ⚠️ 형제 집합이다 — **하나라도 빠지면 그 판정에서 조치가 실행된다.**
    """
    assert {Gate.DENY, Gate.MANUAL} == BLOCKING
    assert Gate.AUTO not in BLOCKING and Gate.APPROVE not in BLOCKING


def test_req_401_decision_records_which_cell_it_came_from() -> None:
    """Verifies: REQ-401

    데모에서 "왜 막혔죠?"에 답하려면 근거가 **응답**에 있어야 한다 (REQ-604).
    """
    d = _decide(Reversibility.REVERSIBLE, False)
    assert d.rule == "reversible but not verifiable"
    assert d.verifiable is False
