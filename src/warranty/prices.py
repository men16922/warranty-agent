"""공시 단가 — **출처와 유효기간을 값과 함께** 둔다 (REQ-503·505).

Spec: specs/warranty/design/05-accountability-ledger.md §2 (REQ-503, REQ-505)

⛔ **이 모듈이 없던 동안 `wasted_usd`는 언제나 0이었다.** 기계는 다 있었다 —
   `TokenUsage`·`Rate`·`TokenPrices.cost_of`·`CostFact.recompute`가 전부 `VERIFIED`였고,
   `ModelCallMeter`는 단가를 못 찾으면 **조용한 0을 만들지 않고** `Method.NONE`에
   *"단가표에 없는 모델이다"*라는 이유를 붙여 왔다. 즉 0은 **버그가 아니라 정직한 침묵**이었다.
   빠진 것은 계산이 아니라 **숫자 두 개와 그 출처**다. 이 파일이 그 자리다.

⚠️ **값만 있는 자리다.** `tunables.py`와 같은 계열 — 아무것도 임포트하지 않는다
   (`Decimal`과 `Rate` 하나씩 빼고). 그래야 누구나 순환 임포트 걱정 없이 여기를 가리킨다.

⛔ **단가는 썩는다.** 아래 값은 **도입가**이고 2027-01-01에 두 배가 된다. 그래서 금액만
   적지 않고 `EFFECTIVE_THROUGH`와 출처 URL을 **같은 자리에** 둔다 — 날짜 없는 단가는
   언제부터 틀렸는지 아무도 모르고, 그 침묵이 정확히 이 저장소가 반대하는 것이다.
"""

from __future__ import annotations

from decimal import Decimal

from warranty.domain.tokens import Rate, TokenPrices

#: 확인한 날. ⚠️ 사람이 다시 확인한 날이지 값이 바뀐 날이 아니다.
CHECKED_ON = "2026-08-29"

#: 도입가가 유효한 마지막 날. ⛔ **다음 날부터 아래 값은 절반짜리 진실이다.**
EFFECTIVE_THROUGH = "2026-12-31"

#: 2027-01-01부터의 표준가 (USD / 1M 토큰). 여기 적어 두는 이유는 편의가 아니라 **경고**다 —
#: 값이 언제 어떻게 바뀌는지 아는 채로 쓰는 것과 모르고 쓰는 것은 다르다.
STANDARD_FROM_2027 = {"input_per_mtok": Decimal("1.50"), "output_per_mtok": Decimal("7.50")}

#: 출처. ⛔ **출처 없는 단가는 추정이 아니라 소문이다**(docs/PRINCIPLES.md #10).
SOURCE_URL = "https://ai.google.dev/gemini-api/docs/pricing"

#: ⚠️ **읽은 페이지와 우리가 쓰는 API가 다르다는 것을 숨기지 않는다.**
#:    우리는 Vertex AI로 부른다. Vertex 쪽 가격 페이지는 본문이 잘려 직접 못 읽었고,
#:    직접 읽힌 것은 Gemini Developer API 페이지다. 두 값이 같다는 것은 검색 요약이
#:    말했을 뿐 **우리가 Vertex 페이지에서 직접 확인한 것이 아니다.**
#:    ⇒ 이 차이가 드러나면 고쳐야 하는 값이고, 그때 어디를 봐야 하는지가 여기 적혀 있다.
SOURCE_CAVEAT = (
    "read from the Gemini Developer API pricing page; the Vertex AI pricing page was not "
    "directly readable at check time. We call via Vertex AI. Treat as published-rate, not billed."
)

#: 우리가 쓰는 티어. ⚠️ batch/flex는 절반, priority는 1.8배다 — 티어를 안 적으면
#: 같은 모델에 네 가지 값이 있고 어느 것을 썼는지 사라진다.
TIER = "standard (paid)"

#: 모델별 공시 단가 (USD / 1M 토큰).
#: ⚠️ 키는 `.env.example`의 `WR_MODEL`과 **같은 문자열**이어야 한다 —
#:    `tests/test_model_id_declarations.py`가 그 일치를 집행한다.
PUBLISHED_RATES = {
    "gemini-3.7-flash": Rate(
        input_per_mtok=Decimal("0.75"),
        output_per_mtok=Decimal("3.75"),
    ),
}

#: 원장의 모든 `published_rate` 행이 달고 다닐 출처 문장.
#: ⛔ 총액만 남고 출처가 사라지면, 그 총액이 **왜 그 값인지** 물을 수 없다.
SOURCE_NOTE = (
    f"published rate, {TIER}, checked {CHECKED_ON}, "
    f"introductory through {EFFECTIVE_THROUGH}; source: {SOURCE_URL}; {SOURCE_CAVEAT}"
)


def published_prices() -> TokenPrices:
    """실물 런타임이 합성하는 단가표.

    ⚠️ 함수인 이유: 모듈 최상위에서 `TokenPrices`를 만들면 임포트만으로 객체가 생긴다.
       값 모듈은 **값만** 갖고, 조립은 부르는 쪽이 한다.
    """
    return TokenPrices(PUBLISHED_RATES, source_note=SOURCE_NOTE)
