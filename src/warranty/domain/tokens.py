"""토큰 계량 — 모델 호출 1건이 **얼마였는가**.

Spec: specs/warranty/design/06-agent-runtime.md (REQ-603, REQ-503)

⚠️ **단가를 코드에 박지 않는다.** 이 저장소는 아직 실물 모델을 호출해 본 적이 없고
   (design/06-agent-runtime.md §2), 확인 못 한 공시 단가를 상수로 박으면 그 숫자가
   **사실처럼 굳는다** — 추정의 가정이 총액을 지배하고 안심시키는 쪽으로 틀린다
   (docs/PRINCIPLES.md #1). 그래서 단가표는 **주입된다.**
⚠️ 단가표에 없는 모델을 **조용히 0으로** 적지 않는다. 0원짜리 행은 "계량했는데 공짜였다"로
   읽히고, 그건 "얼마인지 모른다"와 전혀 다른 문장이다 (docs/PRINCIPLES.md #2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType

from warranty.domain.cost import Basis, CostFact
from warranty.domain.verification import Verdict

#: 공시 단가의 단위. ⚠️ 상수는 **한 곳에만** 있다 (REQ-804).
TOKENS_PER_MTOK = Decimal(1_000_000)

#: `CostFact.inputs`/`unit_prices`의 키. 두 사전이 **같은 키**를 써야 재계산이 성립한다.
INPUT_TOKENS = "input_tokens"
OUTPUT_TOKENS = "output_tokens"


class TokenError(ValueError):
    """토큰 사용량이 성립하지 않는다."""


class UnpricedModelError(LookupError):
    """단가표에 없는 모델이다 — 얼마인지 **모른다**."""


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """한 번의 모델 호출이 쓴 토큰.

    ⚠️ 입력과 출력을 **따로** 갖는다. 단가가 다르므로 합계만 남기면 재계산이 불가능하고,
       재계산이 불가능한 추정은 왜 틀렸는지 물을 수 없다 (REQ-503).
    """

    model: str
    input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        if not self.model:
            raise TokenError("모델 id가 비어 있다 — 어느 단가를 쓸지 정할 수 없다")
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise TokenError(f"토큰 수가 음수다: in={self.input_tokens} out={self.output_tokens}")


@dataclass(frozen=True, slots=True)
class Rate:
    """모델 하나의 공시 단가 (USD / 1M 토큰)."""

    input_per_mtok: Decimal
    output_per_mtok: Decimal


@dataclass(frozen=True, slots=True)
class TokenPrices:
    """주입되는 단가표. **출처를 함께 갖는다** — 출처 없는 단가는 주장이다 (#10)."""

    per_model: Mapping[str, Rate]
    source_note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "per_model", MappingProxyType(dict(self.per_model)))

    def cost_of(self, usage: TokenUsage, *, priced_at: datetime) -> CostFact:
        """수량과 단가를 짝지어 `CostFact`를 만든다 (REQ-503).

        단가표에 없으면 `UnpricedModelError`다. **0을 돌려주지 않는다** — 모르는 것과
        공짜인 것을 같은 값으로 적으면 그 구분은 영원히 사라진다.
        """
        rate = self.per_model.get(usage.model)
        if rate is None:
            raise UnpricedModelError(f"단가표에 없는 모델이다: {usage.model}")

        draft = CostFact(
            amount_usd=Decimal(0),
            priced_at=priced_at,
            basis=Basis.PUBLISHED_RATE,
            inputs={
                INPUT_TOKENS: Decimal(usage.input_tokens),
                OUTPUT_TOKENS: Decimal(usage.output_tokens),
            },
            unit_prices={
                INPUT_TOKENS: rate.input_per_mtok / TOKENS_PER_MTOK,
                OUTPUT_TOKENS: rate.output_per_mtok / TOKENS_PER_MTOK,
            },
            source_note=self.source_note,
        )
        # ⚠️ 곱셈을 여기서 다시 쓰지 않는다. 계산식은 `CostFact.recompute` **한 곳**에만
        #    있고, 복사본 둘은 다음 고침이 한쪽에만 닿는 방식이다 (design 05§2).
        return replace(draft, amount_usd=draft.recompute())


@dataclass(frozen=True, slots=True)
class ModelReply:
    """모델의 응답은 **사용량과 함께** 온다.

    Spec: specs/warranty/design/06-agent-runtime.md (REQ-603)

    ⚠️ 사용량을 선택 값으로 두면 계량이 *추정의 추정*이 된다 — 호출은 있었는데
       얼마인지 아무도 모르는 행이 남고, 그 행은 리포트에서 0으로 보인다.
    """

    verdict: Verdict
    rationale: str
    usage: TokenUsage
