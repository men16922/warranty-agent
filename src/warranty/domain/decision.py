"""판정 게이트 — 축이 셋이다.

Spec: specs/warranty/design/04-decision-gate.md (REQ-401~406)

    ⛔ 검증할 수 없는 조치는 자동으로 실행하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from warranty.domain.contract import Reversibility


class Gate(StrEnum):
    AUTO = "AUTO"
    APPROVE = "APPROVE"
    MANUAL = "MANUAL"
    DENY = "DENY"


@dataclass(frozen=True, slots=True)
class Decision:
    verdict: Gate
    rule: str  # 다섯 칸 중 어디서 나온 판정인지 — 데모에서 "왜 막혔죠?"에 답한다
    reversibility: Reversibility
    verifiable: bool
    projected_usd: Decimal
    headroom_usd: Decimal
    destructive: bool = False


def decide(
    *,
    reversibility: Reversibility,
    verifiable: bool,
    projected_usd: Decimal,
    headroom_usd: Decimal,
    destructive: bool = False,
) -> Decision:
    """세 축으로 판정한다. **다섯 칸이 전부 값으로 도달 가능하다.**

    ⚠️ `verifiable`은 **계약의 존재와 신호 도달 가능성에서 유도된 값**을 받는다.
    조치가 자기 검증 가능성을 주장하면 모든 조치가 검증 가능하다고 말한다.
    """
    reversible = reversibility is Reversibility.REVERSIBLE

    def made(verdict: Gate, rule: str) -> Decision:
        return Decision(
            verdict=verdict,
            rule=rule,
            reversibility=reversibility,
            verifiable=verifiable,
            projected_usd=projected_usd,
            headroom_usd=headroom_usd,
            destructive=destructive,
        )

    # 돈은 언제나 비가역이다 — 초과분은 되돌릴 수 없다.
    if projected_usd > headroom_usd:
        return made(Gate.DENY, "projected > headroom")

    if not verifiable:
        # ⛔ 이 프로젝트의 정책. 되돌릴 수 있어도 **확인 못 하면 자동은 방치다.**
        if reversible:
            return made(Gate.APPROVE, "reversible but not verifiable")
        return made(Gate.MANUAL, "irreversible and not verifiable")

    if destructive:
        # 파괴적 조치는 가역성과 무관하게 최소 APPROVE (REQ-406)
        return made(Gate.APPROVE, "destructive action")
    if reversible:
        return made(Gate.AUTO, "reversible and verifiable within budget")
    return made(Gate.APPROVE, "irreversible")


#: 실행기를 부르지 않는 판정. ⚠️ 하나라도 빠지면 그 판정에서 조치가 실행된다.
BLOCKING: frozenset[Gate] = frozenset({Gate.DENY, Gate.MANUAL})
