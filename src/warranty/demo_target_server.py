"""demo-target 배포 진입점 — **지연을 실제 벽시계로 쓴다** (T2-3 · design 11§1).

Spec: specs/warranty/design/11-demo.md (REQ-803)
      specs/warranty/design/10-deployment.md §2 (REQ-602)

⛔ **`demo_target`은 벽시계를 안 만진다.** 그건 결정론(REQ-802) 때문이고, 그래서 지연을
   `pause`로 주입받는다. 그 주입을 하는 자리가 **여기 하나**다 — 배포된 프로세스.
   ⇒ 게이트는 이 모듈의 `main()`을 부르지 않는다. 부르면 스위트가 1.5초씩 자게 된다.

⛔ **어느 리비전인지는 환경이 정한다. 기본값을 두지 않는다.**
   기본값을 두면 배포가 조용히 *"건강한 쪽"*으로 뜨고, 장애 주입은 일어나지 않는데
   화면은 멀쩡하다 — 그게 이 프로젝트가 통째로 반대하는 모양이다(design 08§5).

⚠️ **이미지는 `warranty-api`와 같은 것을 쓴다.** `gcloud run deploy --command/--args`로
   진입점만 바꾼다 — 두 서비스가 같은 커밋에서 왔다는 것이 태그로 증명되고,
   demo-target용 두 번째 Dockerfile이 따로 썩지 않는다.
"""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from warranty.config import load_port
from warranty.demo_target import DEGRADED, HEALTHY, Response, Revision

#: 어느 리비전으로 뜰지 정하는 환경변수. ⛔ 기본값 없음.
REVISION_ENV_KEY = "WR_DEMO_REVISION"

#: 받는 값 → 리비전. ⚠️ 리비전 **이름**이 아니라 역할로 받는다 — 이름은
#: `demo_target`이 서비스명에서 파생하므로 여기 적으면 사본이 된다.
ROLES: dict[str, Revision] = {"healthy": HEALTHY, "degraded": DEGRADED}


class RevisionError(RuntimeError):
    """리비전을 정할 수 없다. ⚠️ **뜨지 않는 편이 낫다** — 조용히 건강한 쪽으로 뜨면
    장애 주입이 안 일어나고, 데모는 아무것도 실증하지 못한 채 초록이다."""


def resolve_revision(env: dict[str, str] | None = None) -> Revision:
    """환경에서 리비전 하나. **순수하다** — 소켓도 시계도 안 만진다."""
    raw = (env if env is not None else dict(os.environ)).get(REVISION_ENV_KEY, "").strip()
    if not raw:
        raise RevisionError(
            f"{REVISION_ENV_KEY}가 없다 — 받는 값: {sorted(ROLES)}. "
            "기본값을 두지 않는 이유는 design 08§5다: 조용히 건강한 쪽으로 뜨면 "
            "장애 주입이 안 일어나고 데모는 아무것도 실증하지 못한다."
        )
    if raw not in ROLES:
        raise RevisionError(f"{REVISION_ENV_KEY}={raw!r}를 모른다 — 받는 값: {sorted(ROLES)}")
    return ROLES[raw]


def _handler(revision: Revision) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            # ⛔ **여기가 진짜 지연이 일어나는 유일한 자리다.** `time.sleep`을 이 파일 밖
            #    어디에도 두지 않는다 — 두면 게이트가 그것을 상속받는다.
            result: Response = revision.serve(path, time.sleep)
            body = json.dumps(
                {
                    "revision": result.revision,
                    "path": path,
                    "latency_ms": result.latency_ms,
                },
                sort_keys=True,
            ).encode("utf-8")
            self.send_response(result.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            # ⚠️ 기본 구현은 stderr에 쓴다. Cloud Run 로그에서 우리 줄과 섞이면
            #    *"어느 리비전이 답했는가"*를 읽기 어려워진다.
            print(f"{revision.name} {fmt % args}", flush=True)

    return Handler


def main() -> int:
    revision = resolve_revision()
    port = load_port()
    httpd = ThreadingHTTPServer(("", port), _handler(revision))
    # ⚠️ 어느 리비전인지를 **먼저** 말한다 — 트래픽 전환을 되짚을 때 로그만으로
    #    *"안 떴다"*와 *"떴는데 다른 리비전"*을 갈라야 한다.
    print(f"{revision.name} listening on :{port} (work {revision.work_latency_ms}ms)", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
