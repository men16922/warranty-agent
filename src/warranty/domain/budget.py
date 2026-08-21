"""예산 예약 — 판정과 지출 사이의 창을 닫는다.

Spec: specs/warranty/design/04-decision-gate.md (REQ-405)

⚠️ 게이트는 여유를 **읽고**, 지출은 실행 **뒤에** 일어난다. 그 사이에 들어온 두 번째
   조치는 **같은 여유를 다시 본다** — 둘 다 판정을 통과하고 합계는 한도를 넘는다.
   돈은 언제나 비가역이라(design 04§1) 초과분은 되돌릴 수 없다.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


class ReservationError(Exception):
    """예약 불변식이 깨졌다."""


@dataclass(frozen=True, slots=True)
class Reservation:
    """붙잡아 둔 여유 한 건.

    ⚠️ `amount`는 **예상 비용**이다. 정산될 때까지 `headroom`에서 빠져 있고,
       정산에서 실제 비용과의 차이가 되돌아온다.
    """

    reservation_id: str
    agent_id: str
    amount: Decimal
