"""회복 정책이 **도달 가능한가** — 가드 G9.

⛔ *"무엇을 회복이라 부를지"*는 사람이 정하는 유일한 정책이다(REQ-103). 그런데 정책은
   **물리보다 높게 잡힐 수 있고**, 그러면 시스템은 고장 없이 영원히 실패를 보고한다.

⚠️ 2026-08-30 실물이 그것을 보여 줬다. 기준이 `threshold 0.5 · tolerance 0.1`이라
   *"60% 넘게 줄어야 회복"*이었는데, 주입된 결함의 최대 개선폭은 900ms → 620ms = **31%**다.
   조치가 지연을 `990 → 674ms`(32%)로 낮췄는데도 판정은 `not_recovered`였다.
   ⛔ **이것은 검증이 아니라 검증의 부재다** — 성공이 불가능하면 실패 보고는 정보가 없다.
"""

from __future__ import annotations

from decimal import Decimal

from warranty.demo_target import DEGRADED_LATENCY_MS, HEALTHY_LATENCY_MS
from warranty.runtime import LIVE_RECOVERY_CRITERION


def _best_possible_improvement() -> Decimal:
    """주입된 결함을 **완전히** 되돌렸을 때의 상대 개선폭."""
    degraded = Decimal(DEGRADED_LATENCY_MS)
    healthy = Decimal(HEALTHY_LATENCY_MS)
    return (degraded - healthy) / degraded


def test_a_perfect_fix_can_actually_be_called_recovered() -> None:
    """⛔ 완벽한 조치가 `RECOVERED`를 못 받으면 그 정책은 **측정이 아니라 장식**이다.

    `classify`는 `change >= threshold + tolerance`일 때만 회복이라 부른다.
    그러므로 **최대 개선폭이 그 합보다 커야** 한다.

    Verifies: REQ-103
    """
    reachable = _best_possible_improvement()
    needed = LIVE_RECOVERY_CRITERION.threshold + LIVE_RECOVERY_CRITERION.tolerance
    assert needed < reachable, (
        f"회복 기준({needed})이 낼 수 있는 최대 개선({reachable:.3f})보다 크거나 같다 — "
        "어떤 조치도 회복으로 판정될 수 없고, 그러면 not_recovered는 정보가 아니다"
    )


def test_doing_nothing_is_still_not_recovered() -> None:
    """⚠️ 반대쪽 벽. 기준을 낮추다 보면 **아무것도 안 해도 회복**이 된다.

    변화 0은 `change <= threshold - tolerance`여야 하고, 그래야 `NOT_RECOVERED`가 나온다.

    Verifies: REQ-103
    """
    assert LIVE_RECOVERY_CRITERION.threshold > LIVE_RECOVERY_CRITERION.tolerance, (
        "threshold가 tolerance 이하다 — 변화가 없어도 ambiguous 이상으로 올라간다"
    )
