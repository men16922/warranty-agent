"""대기·창 길이 — **한 모듈에만** 있다 (REQ-804).

Spec: specs/warranty/design/11-demo.md §5
      specs/warranty/design/02-verification.md §4
      (REQ-206, REQ-804)

영상 재촬영 전에 손대는 값들이다. design 11§2가 *"타이머를 줄인다"*라고 말하는 그
타이머가 여기 있고, **여기 말고 다른 곳에는 없다.**

⚠️ 값이 흩어지면 재촬영 때 **반드시 하나를 놓친다.** 놓친 쪽은 예전 값으로 계속 돌고,
   그 어긋남은 조용하다 — 게이트는 초록이고 영상만 이상해진다.
   그래서 이것은 관례가 아니라 **집행되는 규칙이다**: `tests/test_tunables.py`가
   ① 이 모듈 밖의 대기·창 상수 정의와 ② 호출부에 박힌 숫자 리터럴을 red로 만든다.

⚠️ 이 모듈은 아무것도 임포트하지 않는다(`Decimal` 하나 빼고). **값만 있는 자리**여야
   누구나 순환 임포트 걱정 없이 여기를 가리킬 수 있다.
"""

from __future__ import annotations

from decimal import Decimal

#: 조치가 신호에 반영되기까지 기다리는 시간. ⚠️ 너무 짧으면 Cloud Monitoring의 지표
#: 도착 지연 때문에 **회복을 실패로 오판한다** (design 02§4).
VERIFY_DELAY_S = 45

#: 재측정 창. 기준선과 재측정이 **같은 창**을 써야 두 값이 비교 가능하다 (REQ-202).
VERIFY_WINDOW_S = 120

#: 데모 한 판이 쓸 수 있는 예산. 게이트의 세 번째 축(headroom)이 이것을 읽는다.
DEMO_BUDGET_USD = Decimal("0.50")

#: 촬영 전 콜드 스타트를 녹이는 요청 수. `min-instances=0`이라 첫 요청이 느리다
#: (design 11§4). ⛔ **아직 이것을 읽는 코드가 없다** — 워밍은 T8-3(촬영) 절차이고
#: 코드 경로가 아니다. 그래도 여기 있는 이유는 design 11§5가 이 이름을 선언하기
#: 때문이고, 선언과 코드가 어긋나면 `tests/test_tunables.py`가 red다.
#: 값을 여기 두는 것과 **읽는 곳이 생기는 것**은 다른 일이다.
WARMUP_REQUESTS = 1
