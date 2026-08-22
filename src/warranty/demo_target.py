"""demo-target — 조치의 **대상**이 되는 앱. 리비전 둘: 건강한 것과 신호를 악화시키는 것.

Spec: specs/warranty/design/11-demo.md (REQ-803)
      specs/warranty/design/10-deployment.md (REQ-303)

⛔ **결과를 박아 두는 것은 실증이 아니다** (design 11§1 원칙 5). 검증이 실패해야 롤백이
   보이는데, 실패를 만드는 정직한 방법은 `verdict`를 박는 것이 아니라 **진짜로 신호를
   악화시키는 리비전**을 준비해 조치가 그리로 트래픽을 옮기게 하는 것이다.
   이 모듈이 그 리비전이고, 롤백이 돌아갈 **건강한 리비전**도 함께 여기 있다.
   ⇒ 데모의 절정은 이 파일의 두 값 사이의 거리에서 나온다.

⚠️ **이것은 T6-1의 오프라인 절반이다.** 두 리비전을 실제로 Cloud Run에 올리는 것은 T2-3이고
   사람이 한다. 여기서 확인된 것은 *"두 리비전이 서로 다른 이야기를 한다"*뿐이지
   *"그 이야기를 Cloud Run이 한다"*가 아니다 (docs/PRINCIPLES.md #3).

⛔ **벽시계를 만지는 자리가 이 파일에 없다.** 지연을 실제로 쓰는 `pause`는 주입받는다.
   여기서 자면 게이트가 그만큼 느려지고, 살아 있는 시계가 새면 결정론이 깨진다(REQ-802).
   실물 sleeper를 주는 것은 배포 진입점(T2-3)의 몫이다.

⛔ **지연을 `warranty.tunables`에 두지 않았다.** 거기 사는 것은 **검증하는 쪽**의 대기·창이다
   (REQ-206·REQ-804 — 재촬영 때 영상 길이에 맞춰 줄이는 그 손잡이). 이 값은 **측정당하는
   쪽**의 지연이다. 둘을 한 손잡이에 묶으면 타이머를 줄이는 순간 **장애의 크기가 함께
   바뀌고**, 그때 데모는 자기가 무엇을 쟀는지 말할 수 없다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

#: 지연을 **실제로 쓰는** 자리 (초 단위). ⚠️ 이 모듈은 구현을 갖지 않는다 — 주입받는다.
Pause = Callable[[float], None]

#: 서비스명 — design 10§2. ⚠️ 리비전 이름도 여기서 **파생**된다. 다시 적으면
#: 서비스 이름을 바꿀 때 리비전 쪽이 안 따라오고, 그 어긋남은 배포에서야 보인다.
SERVICE_NAME = "demo-target"

#: 헬스 프로브 경로. ⛔ **두 리비전 다 여기서는 빠르다** — 아래 `serve`의 상자를 볼 것.
HEALTH_PATH = "/healthz"
#: 신호를 만드는 경로. 계약의 `health_signal`이 재는 것이 **이 경로의 지연**이다.
WORK_PATH = "/work"

OK = 200
NOT_FOUND = 404

MS_PER_SECOND = 1000

#: 건강한 리비전의 p95(ms). ⚠️ *"건강하다"*는 나쁜 쪽에 대해서만 참이다 — 620ms는
#: 애초에 누군가 조치를 요청한 이유이고, 데모에서 그것이 **기준선**이 된다.
HEALTHY_LATENCY_MS = 620

#: ★ 장애 주입 리비전의 p95(ms). ⛔ 이 값이 건강한 쪽에 가까워지면 데모는 조용히
#: 아무것도 실증하지 않게 된다 — 롤백 후 재측정이 *"돌아왔다"*를 **롤백 없이도** 말한다
#: (REQ-304). 그 거리를 테스트가 지킨다 (tests/test_demo_target.py ⑥).
DEGRADED_LATENCY_MS = 900


@dataclass(frozen=True, slots=True)
class Response:
    """한 요청의 결과.

    ⚠️ `latency_ms`는 **선언이 아니라 쓴 값**이다 — `serve`가 `pause`에 넘긴 수와 같다.
       둘이 갈라질 수 있으면 *"느리다고 말하는 리비전"*과 *"느린 리비전"*이 구별되지 않는다.
    """

    status: int
    revision: str
    latency_ms: int


@dataclass(frozen=True, slots=True)
class Revision:
    """한 리비전. ⛔ **두 리비전의 차이는 작업 경로의 지연 하나뿐이다.**

    ⚠️ 상태 코드나 경로 처리를 함께 바꾸면, 검증이 실패했을 때 그것이 *"조치가 신호를
       악화시켰다"*인지 *"뭔가 달라졌다"*인지 말할 수 없다. 데모가 주장하는 것은 전자다.
    """

    name: str
    work_latency_ms: int

    def serve(self, path: str, pause: Pause) -> Response:
        """요청 하나를 처리한다. **지연을 선언만 하지 않고 실제로 쓴다.**

        ⛔ 헬스 프로브는 **두 리비전 다 빠르다.** 나쁜 리비전이 프로브에서 죽으면
           Cloud Run은 그리로 트래픽을 안 옮기고, 그 순간 장애 주입은 **배포 실패**가 된다
           — 데모가 보여 주려던 것(검증 실패 → 자동 롤백)은 한 번도 안 일어난다.
           ⇒ 나쁜 리비전은 **살아 있으면서 느려야** 한다.
        """
        if path == HEALTH_PATH:
            return Response(OK, self.name, 0)
        if path != WORK_PATH:
            return Response(NOT_FOUND, self.name, 0)
        pause(self.work_latency_ms / MS_PER_SECOND)
        return Response(OK, self.name, self.work_latency_ms)


#: 프로비저닝 시점에 서빙 중이던 리비전. **롤백이 돌아갈 곳이다.**
HEALTHY = Revision(name=f"{SERVICE_NAME}-00007-abc", work_latency_ms=HEALTHY_LATENCY_MS)

#: ★ 장애 주입. 조치가 트래픽을 이리로 옮기고, 신호가 **진짜로** 나빠진다.
DEGRADED = Revision(name=f"{SERVICE_NAME}-00008-slow", work_latency_ms=DEGRADED_LATENCY_MS)

#: design 10§2가 *"리비전 2개 이상"*이라고 말하는 그 둘.
REVISIONS: tuple[Revision, ...] = (HEALTHY, DEGRADED)
