"""비용 사실(CostFact) — 총액만 적지 않는다.

Spec: specs/warranty/design/05-accountability-ledger.md §2 (REQ-503, REQ-505)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType


class Basis(StrEnum):
    """이 금액이 어디서 왔는가. **측정과 가정을 구분하는 것이 논지의 절반이다.**"""

    PUBLISHED_RATE = "published_rate"  # 수량 × 공시 단가 = 계산값
    BILLING_EXPORT = "billing_export"  # 청구서가 말한 값


class CostFactError(ValueError):
    """CostFact가 성립하지 않는다."""


@dataclass(frozen=True, slots=True)
class CostFact:
    """금액과 **그 금액을 만든 수량·단가**를 함께 갖는다.

    ⚠️ 총액만 남기면 어느 가정이 총액을 지배하는지 영원히 모른다.
    레퍼런스에서 100배 오차의 원인이 정확히 이것이었다 — 정가는 맞았고 수량 가정이
    틀렸는데, 표에는 총액만 있었다 (REFERENCE_FROM_PARENT #1, #2).
    """

    amount_usd: Decimal
    priced_at: datetime
    basis: Basis
    inputs: Mapping[str, Decimal] = field(default_factory=dict)
    unit_prices: Mapping[str, Decimal] = field(default_factory=dict)
    source_note: str = ""

    def __post_init__(self) -> None:
        if self.amount_usd < 0:
            raise CostFactError(f"금액이 음수다: {self.amount_usd}")
        if self.basis is Basis.PUBLISHED_RATE and set(self.inputs) != set(self.unit_prices):
            # ⚠️ 계산값이라면 수량과 단가가 짝을 이뤄야 한다. 안 그러면 재계산이 불가능하고,
            #    재계산이 불가능한 추정은 왜 틀렸는지 물을 수 없다.
            raise CostFactError(
                "published_rate인데 inputs와 unit_prices의 키가 다르다: "
                f"{sorted(set(self.inputs) ^ set(self.unit_prices))}"
            )
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))
        object.__setattr__(self, "unit_prices", MappingProxyType(dict(self.unit_prices)))

    @property
    def is_recomputable(self) -> bool:
        """수량과 단가로 금액을 다시 유도할 수 있는가."""
        return bool(self.inputs) and set(self.inputs) == set(self.unit_prices)

    def recompute(self) -> Decimal:
        if not self.is_recomputable:
            raise CostFactError("수량·단가가 없어 재계산할 수 없다")
        return sum(
            (qty * self.unit_prices[key] for key, qty in self.inputs.items()),
            start=Decimal(0),
        )


@dataclass(frozen=True, slots=True)
class Delta:
    """추정과 실측의 차이. **이 프로젝트의 산출물이다.**"""

    amount_usd: Decimal
    ratio: Decimal | None
    note: str = ""


def delta_of(assumed: CostFact, measured: CostFact) -> Delta:
    """계산식은 **여기 한 곳에만** 둔다. 복사본은 다음 고침이 한쪽에만 닿는다."""
    amount = measured.amount_usd - assumed.amount_usd
    if assumed.amount_usd == 0:
        return Delta(amount, None, "assumed가 0이라 배율이 정의되지 않는다")
    return Delta(amount, measured.amount_usd / assumed.amount_usd)
