"""게이트 전체에 tripwire를 건다 — G5 (T12-5 · REQ-801).

⛔ **모듈 임포트 시점에 건다. 픽스처가 아니다.** 세션 픽스처는 *첫 테스트가 실행될 때*
   세워지는데, 테스트 모듈은 그보다 **먼저 임포트된다.** 임포트만으로 라이브 어댑터를
   만드는 자리가 생기면 픽스처는 그것을 못 본다 — pytest는 rootdir의 이 파일을
   수집보다 먼저 읽으므로, 여기 한 줄이 그 창을 닫는다.

⚠️ 푸는 자리는 없다. 게이트 프로세스는 이 상태로 끝난다 — 중간에 풀면 그 뒤의 모든
   테스트가 G5 밖에서 돌고, **그 사실은 어디에도 안 나타난다.**
"""

from __future__ import annotations

from warranty.adapters import live_guard

live_guard.arm()
