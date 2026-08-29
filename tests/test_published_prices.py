"""공시 단가 — **`wasted_usd`가 0을 벗어나는 자리** (REQ-503·504·505).

Spec: specs/warranty/design/05-accountability-ledger.md §2 (REQ-503, REQ-505)

⛔ **이 모듈이 없던 동안 원장의 모든 조치·모델 호출이 `amount_usd = 0` ·
   `attribution.method = none`이었다.** 계량이 없어서가 아니다 — `ModelCallMeter`는
   단가를 못 찾으면 **조용한 0을 만들지 않고** 이유를 붙여 왔다. 빠진 것은 **숫자 두 개와
   그 출처**였고, 그래서 이 저장소가 말할 수 있는 가장 강한 문장(`wasted_usd`)이
   언제나 0으로 나왔다.

다섯을 묻는다:
  ① 단가표의 키가 **우리가 실제로 부르는 모델**과 같은가 — 다르면 조용히 0으로 되돌아간다
  ② 값이 수량 × 단가로 **재계산되는가** (총액만 있으면 왜 그 값인지 못 묻는다)
  ③ 출처와 **유효기간**이 값과 함께 있는가 — 날짜 없는 단가는 언제부터 틀렸는지 모른다
  ④ 모르는 모델에 **0이 아니라 예외**가 나는가
  ⑤ 실물 합성이 **빈 단가표로 되돌아가지 않았는가**

⚠️ ①이 본체다. 키 한 글자가 어긋나면 게이트는 초록이고 원장만 조용히 0으로 돌아간다 —
   이 파일이 막으려는 것이 정확히 그 침묵이다.
"""

from __future__ import annotations

import ast
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from warranty.domain.cost import Basis
from warranty.domain.tokens import (
    INPUT_TOKENS,
    OUTPUT_TOKENS,
    TokenUsage,
    UnpricedModelError,
)
from warranty.prices import (
    EFFECTIVE_THROUGH,
    PUBLISHED_RATES,
    SOURCE_URL,
    published_prices,
)

ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = ROOT / ".env.example"
RUNTIME = ROOT / "src" / "warranty" / "runtime.py"

PRICED_AT = datetime(2026, 8, 29, tzinfo=UTC)


def _declared_model() -> str:
    """`.env.example`의 `WR_MODEL`. ⚠️ 못 읽으면 **예외다** — 0개를 읽고 아래를 공허하게
    통과시키면 이 파일 전체가 아무것도 안 묻는다."""
    match = re.search(r"^WR_MODEL=(\S+)$", ENV_EXAMPLE.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        raise AssertionError(f"{ENV_EXAMPLE.name}에서 `WR_MODEL=<id>` 줄을 못 읽었다")
    return match.group(1)


def test_the_table_prices_the_model_we_actually_call() -> None:
    """① ★ **키 한 글자가 어긋나면 원장은 조용히 0으로 돌아간다.**

    ⛔ `ModelCallMeter`는 단가를 못 찾아도 죽지 않는다 — `Method.NONE` + 0을 적고 넘어간다.
       그 설계는 옳지만(모르는 것과 공짜인 것을 안 섞는다), 그래서 **오타가 예외로 안 나타난다.**
       게이트는 초록이고 `wasted_usd`만 0이 된다. 그 침묵을 여기서 막는다.
    """
    model = _declared_model()
    assert model in PUBLISHED_RATES, (
        f"우리가 부르는 모델 {model!r}이 단가표에 없다 — 원장은 조용히 0으로 돌아간다. "
        f"단가표의 키: {sorted(PUBLISHED_RATES)}"
    )


def test_the_cost_is_recomputable_from_quantity_and_rate() -> None:
    """② ⚠️ 총액만 남기면 **왜 그 값인지** 물을 수 없다 (REQ-503).

    1,000 입력 · 200 출력을 $0.75/$3.75 per MTok으로:
      입력 1000 × 0.75/1e6 = 0.00075
      출력  200 × 3.75/1e6 = 0.00075
      합계                 = 0.00150
    """
    usage = TokenUsage(_declared_model(), input_tokens=1_000, output_tokens=200)
    fact = published_prices().cost_of(usage, priced_at=PRICED_AT)

    assert fact.basis is Basis.PUBLISHED_RATE
    assert fact.amount_usd == Decimal("0.00150")
    # 수량과 단가가 **짝으로** 남아 있다 — 한쪽만 있으면 재계산이 안 된다.
    assert fact.inputs[INPUT_TOKENS] == Decimal(1_000)
    assert fact.inputs[OUTPUT_TOKENS] == Decimal(200)
    assert fact.unit_prices[INPUT_TOKENS] == Decimal("0.75") / Decimal(1_000_000)
    assert fact.unit_prices[OUTPUT_TOKENS] == Decimal("3.75") / Decimal(1_000_000)
    # ⛔ 값이 스스로 재계산과 일치한다 — 저장된 총액과 계산식이 갈라지면 어느 쪽이 참인지 모른다.
    assert fact.recompute() == fact.amount_usd


def test_a_rate_carries_its_source_and_its_expiry() -> None:
    """③ ⛔ **날짜 없는 단가는 언제부터 틀렸는지 아무도 모른다.**

    ⚠️ 아래 값은 도입가이고 2027-01-01에 두 배가 된다. 금액만 적고 유효기간을 안 적으면
       그날부터 원장의 모든 행이 **절반짜리 진실**이 되고, 그 침묵은 조용하다.
    """
    note = published_prices().source_note
    assert SOURCE_URL in note, "출처 URL이 없다 — 출처 없는 단가는 추정이 아니라 소문이다"
    assert EFFECTIVE_THROUGH in note, "유효기간이 없다 — 언제부터 틀리는지 못 묻는다"
    # 우리가 Vertex로 부르는데 읽은 페이지는 Developer API 쪽이라는 것을 숨기지 않는다.
    assert "Vertex" in note


def test_an_unpriced_model_raises_instead_of_reporting_zero() -> None:
    """④ ⛔ **0을 돌려주면 "모르는 것"과 "공짜인 것"의 구분이 영원히 사라진다.**"""
    # ⚠️ 이름을 `gemini-*` 모양으로 쓰지 않는다 — `test_model_id_declarations.py`가 그것을
    #    **모델 선언으로 읽고** red를 낸다. 그 가드가 옳다: 저장소 어디든 `gemini-x.y-z`가
    #    적혀 있으면 그것은 우리가 부르는 모델에 대한 주장이다.
    usage = TokenUsage("unpriced-model-for-this-test", input_tokens=10, output_tokens=10)
    with pytest.raises(UnpricedModelError):
        published_prices().cost_of(usage, priced_at=PRICED_AT)


def test_the_live_runtime_does_not_synthesize_an_empty_price_table() -> None:
    """⑤ ⛔ 빈 단가표로 되돌아가는 것이 이 축을 죽이는 가장 쉬운 방법이다.

    ⚠️ 실물 합성 함수를 **부를 수 없다** — G5가 게이트 중 라이브 어댑터 생성을 금지한다
       (REQ-801). 그래서 묻는 것은 호출이 아니라 **소스의 모양**이다
       (`tools/deploy_plan.py`·`adapters/adk_agent.py`와 같은 수법).
    """
    tree = ast.parse(RUNTIME.read_text(encoding="utf-8"))

    empty_tables = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "TokenPrices"
        and node.args
        and isinstance(node.args[0], ast.Dict)
        and not node.args[0].keys
    ]
    assert not empty_tables, (
        "runtime이 빈 단가표를 합성한다 — 원장의 모든 행이 다시 `method=none` · 0이 된다"
    )

    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "published_prices" in called, "runtime이 공시 단가표를 합성하지 않는다"
