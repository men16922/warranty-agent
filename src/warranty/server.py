"""HTTP 서버 — 이미지가 **포트를 듣는다** (T12-1 · REQ-602의 오프라인 절반).

Spec: specs/warranty/design/08-interfaces.md §3-4 (REQ-602)

⛔ **이 파일이 없애는 것은 함정 하나다.** 직전까지 이 이미지의 `CMD`는 오프라인 데모였고,
   데모는 끝나면 종료한다 — Cloud Run에 올리면 컨테이너가 포트를 한 번도 안 열고
   **포트 프로브에서 죽는다.** T11-1이 그 함정을 예고해 뒀고, 여기가 그 자리다.

⚠️ **표준 라이브러리만 쓴다.** 게이트에 웹 프레임워크가 없고(REQ-801), 넣으면 게이트가
   오프라인이라는 전제와 fake 어댑터의 전제가 함께 깨진다. `http.server`로 충분한 이유는
   이 서비스가 받는 트래픽이 **심사자 한 명과 프로브**이기 때문이다 — 그 이상을 가정하면
   REQ-805(유휴 과금 0)와 어긋나는 물건을 짓게 된다.

`/agent:chat`은 인증 뒤 주입된 실물 ADK 콜백만 호출한다. 콜백이 없으면 `501`, 호출이
실패하면 `503`으로 닫으며 fake 성공을 만들지 않는다. 아직 배선하지 않은 나머지 경로도
`501`을 유지한다. 설정은 `fake`를 **기본값으로 두지 않는다**(design 08§5) — 배포가
조용히 가짜로 도는 것을 막기 위해서다(docs/PRINCIPLES.md #3).

⚠️ **경로 표는 설계가 소유한다.** 여기 적힌 `ROUTES`는 design 08§3 표의 사본이고,
   사본인 이상 따로 썩는다 — 게이트가 둘을 맞댄다(tests/test_http_server.py ②).

⚠️ **부팅에서 `load_settings`를 안 부른다.** 설정 검증은 그 설정을 쓰는 어댑터와 함께
   와야 한다(T2-2). 지금 부르면 *"설정이 옳다"*가 *"핸들러가 그 설정으로 돈다"*로 읽히고,
   이 파일은 그것을 하나도 안 한다.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from warranty.auth import AUTH_ENV_KEY, AUTH_SCHEME, AuthVerdict, authenticate
from warranty.config import SERVICE_NAME, load_port

OK = 200
BAD_REQUEST = 400
UNAUTHORIZED = 401
NOT_FOUND = 404
METHOD_NOT_ALLOWED = 405
NOT_IMPLEMENTED = 501
SERVICE_UNAVAILABLE = 503

AgentChat = Callable[[Mapping[str, object]], Mapping[str, object]]

#: 화면 하나를 그리는 함수. ⚠️ 인자가 없다 — **무엇을 그릴지는 합성 지점이 정한다.**
#: 서버가 날짜·서비스명을 고르기 시작하면 그 선택이 두 곳(여기와 런타임)에 생긴다.
Dashboard = Callable[[], str]

#: 플랫폼이 프로브하는 경로. ⛔ **이것만은 지금 진짜로 답해야 한다** — 나머지가 `501`인
#: 것은 정책이지만, 이것이 `501`이면 리비전은 트래픽을 한 번도 못 받는다.
#:
#: ⛔ **`/healthz`가 아니다.** Cloud Run의 프론트엔드가 그 경로를 **가로챈다** — 2026-08-23
#: 실물 배포에서 확인했다(`docs/evidence/deploy-2026-08-23.log`):
#:
#:     GET /healthz   -> 404  <!DOCTYPE html>   ← Google이 낸다. 컨테이너 로그에 한 줄도 없다
#:     GET /healthz2  -> 404  {"error": "unknown_route", …}  ← 우리 코드가 낸다
#:
#: 두 경로의 차이는 한 글자고, 앞의 것은 **우리 프로세스에 도달조차 안 한다.**
#: ⚠️ **로컬에서는 200이었다.** 이 충돌은 오프라인 게이트가 원리상 볼 수 없다 —
#:    플랫폼의 성질이지 우리 코드의 성질이 아니다(docs/PRINCIPLES.md #3).
#: ⚠️ 지금은 무해했다: `min-instances=0`이라 시작 프로브가 TCP였고 리비전은 떴다.
#:    그러나 헬스 경로를 **쓰는 순간**(deploy-check · T2-4) 그것은 영원히 404다.
HEALTH_PATH = "/livez"
AGENT_PATH = "/agent:chat"

#: ★ 사람이 보는 원장 화면 (design 08§3). ⛔ **조작 표면이 아니다** — 읽기 전용이다.
DASHBOARD_PATH = "/"

JSON_TYPE = "application/json; charset=utf-8"
HTML_TYPE = "text/html; charset=utf-8"

#: `{id}` 같은 자리표시자.
PARAM_RE = re.compile(r"\{[a-z_]+\}")

#: 자리표시자가 먹는 문자. ⚠️ `[^/]+`로 넓히면 `/ledger/x:approve`가 `/ledger/{entry_id}`에
#: 걸린다 — 이 API에서 콜론은 **동사 표지**지 식별자의 일부가 아니다(design 08§3).
PARAM_CHARS = r"[^/:]+"


@dataclass(frozen=True, slots=True)
class Route:
    """design 08§3 표의 한 행."""

    method: str
    template: str


#: design 08§3의 HTTP 계약. ⚠️ **순서가 아니라 집합이 의미다** — 게이트가 설계 표와
#: 집합으로 맞댄다. 여기서 한 행을 지우면 그 경로는 조용히 `404`가 되고, 심사자가 보는
#: 것은 *"아직 구현 안 됨"*이 아니라 *"그런 경로 없음"*이다.
ROUTES: tuple[Route, ...] = (
    Route("POST", "/resources:provision"),
    Route("GET", "/contracts/{id}"),
    Route("POST", "/actions/{action_id}:remediate"),
    Route("POST", "/ledger/{entry_id}:approve"),
    Route("GET", "/ledger/{entry_id}"),
    Route("GET", "/report/daily"),
    Route("POST", AGENT_PATH),
    Route("GET", HEALTH_PATH),
    Route("GET", DASHBOARD_PATH),
)


def _compile(template: str) -> re.Pattern[str]:
    """경로 틀 → 정규식. 자리표시자만 넓히고 **나머지는 전부 문자 그대로** 묶는다."""
    return re.compile(PARAM_CHARS.join(re.escape(chunk) for chunk in PARAM_RE.split(template)))


_PATTERNS: dict[Route, re.Pattern[str]] = {route: _compile(route.template) for route in ROUTES}


@dataclass(frozen=True, slots=True)
class Response:
    """한 요청의 결과. **본문은 JSON으로 실을 수 있는 값만** 담는다."""

    status: int
    body: Mapping[str, object]
    headers: Mapping[str, str] = field(default_factory=dict)
    #: ★ 사람이 보는 화면은 JSON이 아니다. ⚠️ `None`이면 `body`를 JSON으로 낸다 —
    #:    기본값을 바꾸지 않는 이유는 기존 경로 전부가 JSON 계약이기 때문이다.
    text: str | None = None
    content_type: str = JSON_TYPE

    def payload(self) -> bytes:
        """⚠️ 정렬해서 낸다 — 같은 판정이 프로세스마다 다른 바이트를 내면 안 된다(REQ-802)."""
        if self.text is not None:
            return self.text.encode("utf-8")
        return json.dumps(dict(self.body), ensure_ascii=False, sort_keys=True).encode("utf-8")


def resolve(
    method: str,
    target: str,
    *,
    authorization: str | None = None,
    agent_auth_token: str | None = None,
    body: bytes = b"",
    agent_chat: AgentChat | None = None,
    dashboard: Dashboard | None = None,
) -> Response:
    """요청 하나에 대한 응답. **소켓을 모른다** — 그래서 단위로 태울 수 있다.

    ⚠️ 질의 문자열을 여기서 잘라 낸다. design 08§3의 `/report/daily?date=`에서 경로인
       것은 앞부분이고, 뒷부분은 아직 아무도 안 읽는다(그 핸들러가 없다).
    """
    path = target.split("?", 1)[0]
    matched = [route for route in ROUTES if _PATTERNS[route].fullmatch(path)]
    if not matched:
        # design 08§4 — 미등록은 `404`다.
        return Response(NOT_FOUND, {"error": "unknown_route", "path": path})
    if not any(route.method == method for route in matched):
        return Response(
            METHOD_NOT_ALLOWED,
            {
                "error": "method_not_allowed",
                "path": path,
                "allowed": sorted({route.method for route in matched}),
            },
        )
    if path == HEALTH_PATH:
        return Response(OK, {"status": "ok", "service": SERVICE_NAME})
    if path == DASHBOARD_PATH:
        # ⛔ 화면은 **인증을 안 건다.** 읽기 전용이고 조작 표면이 없다 — 심사위원이
        #    링크를 눌러서 봐야 하는 것이 이 화면의 존재 이유다(REQ-901).
        # ⚠️ 원장을 못 읽으면 **빈 화면을 그리지 않는다** — 없음과 실패는 다르다.
        # ⚠️ **둘은 다른 사실이다.** *"합성이 안 됐다"*는 배포 설정 문제이고
        #    *"읽다가 죽었다"*는 Firestore 쪽 문제다. 같은 문장으로 내면 어디를 봐야
        #    하는지가 사라지고, 아래 `except`가 둘을 하나로 만든다.
        if dashboard is None:
            return Response(
                SERVICE_UNAVAILABLE,
                {
                    "error": "ledger_unavailable",
                    "detail": "not_composed: 실물 원장이 주입되지 않아 화면을 그릴 수 없다",
                },
            )
        try:
            return Response(OK, {}, text=dashboard(), content_type=HTML_TYPE)
        except Exception:
            return Response(
                SERVICE_UNAVAILABLE,
                {
                    "error": "ledger_unavailable",
                    "detail": "read_failed: 원장 읽기가 실패했다 — 빈 화면 대신 이 사실을 낸다",
                },
            )
    if path == AGENT_PATH:
        verdict = authenticate(authorization, agent_auth_token)
        if verdict is AuthVerdict.NOT_CONFIGURED:
            return Response(
                SERVICE_UNAVAILABLE,
                {
                    "error": "auth_unavailable",
                    "detail": "agent authentication is not configured",
                },
            )
        if verdict is not AuthVerdict.AUTHORIZED:
            return Response(
                UNAUTHORIZED,
                {"error": "unauthorized"},
                {"WWW-Authenticate": AUTH_SCHEME},
            )
        if agent_chat is None:
            return Response(
                NOT_IMPLEMENTED,
                {
                    "error": "not_implemented",
                    "route": f"{method} {path}",
                    "detail": "인증 경계는 열렸지만 실물 ADK 합성 지점이 주입되지 않았다",
                },
            )
        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return Response(BAD_REQUEST, {"error": "invalid_json", "detail": str(exc)})
        if not isinstance(decoded, dict):
            return Response(
                BAD_REQUEST, {"error": "invalid_body", "detail": "JSON object required"}
            )
        try:
            return Response(OK, agent_chat(decoded))
        except ValueError as exc:
            return Response(BAD_REQUEST, {"error": "invalid_request", "detail": str(exc)})
        except Exception:
            return Response(
                SERVICE_UNAVAILABLE,
                {
                    "error": "agent_unavailable",
                    "detail": "authenticated agent execution failed; inspect Cloud Run logs",
                },
            )
    return Response(
        NOT_IMPLEMENTED,
        {
            "error": "not_implemented",
            "route": f"{method} {path}",
            # ⛔ 이 한 줄이 `501`을 정직하게 만든다. 빼면 심사자는 이 응답을 **버그**로 읽는다.
            "detail": (
                "경로는 선언됐고 어댑터가 아직 없다 — 실물 어댑터 없이 fake로 200을 내면 "
                "배포가 조용히 가짜로 돈다 (REQ-601·602)"
            ),
        },
    )


class WarrantyHandler(BaseHTTPRequestHandler):
    """`resolve`를 HTTP에 붙이는 **얇은 껍데기**. 판정은 하나도 여기서 안 한다.

    ⚠️ 얇게 두는 이유는 취향이 아니다 — 소켓을 쥔 코드는 단위로 태우기 어렵고,
       판정이 그 안에 있으면 *"응답이 옳은가"*를 물으려면 매번 포트를 열어야 한다.
    """

    protocol_version = "HTTP/1.1"
    server_version = "warranty/1"
    agent_chat: AgentChat | None = None
    dashboard: Dashboard | None = None

    #: ⚠️ 메서드 이름은 취향이 아니라 stdlib의 디스패치 규약이다(`do_<METHOD>`).
    def do_GET(self) -> None:
        self._respond("GET")

    def do_POST(self) -> None:
        self._respond("POST")

    def _respond(self, method: str) -> None:
        body = self._read_body()
        response = resolve(
            method,
            self.path,
            authorization=self.headers.get("Authorization"),
            agent_auth_token=os.environ.get(AUTH_ENV_KEY),
            body=body,
            agent_chat=self.agent_chat,
            dashboard=self.dashboard,
        )
        payload = response.payload()
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        for name, value in response.headers.items():
            self.send_header(name, value)
        # ⚠️ `Content-Length`를 안 주면 HTTP/1.1 keep-alive에서 클라이언트가 **응답의 끝을
        #    모른다** — 프로브가 타임아웃으로 죽고, 그건 서버가 답을 안 한 것처럼 보인다.
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_body(self) -> bytes:
        """본문을 읽어 버린다. ⚠️ 안 읽으면 keep-alive에서 **다음 요청이 이 본문을
        요청 줄로 읽는다** — 그러면 두 번째 요청부터 조용히 `400`이 된다.
        """
        raw = self.headers.get("Content-Length", "")
        if raw.isdigit() and int(raw) > 0:
            return self.rfile.read(int(raw))
        return b""


def serve(
    port: int,
    agent_chat: AgentChat | None = None,
    dashboard: Dashboard | None = None,
) -> ThreadingHTTPServer:
    """포트를 **실제로 연다**. ⛔ 게이트는 이것을 안 부른다(REQ-801 — 오프라인)."""
    if agent_chat is None and dashboard is None:
        handler = WarrantyHandler
    else:

        class LiveWarrantyHandler(WarrantyHandler):
            pass

        if agent_chat is not None:
            LiveWarrantyHandler.agent_chat = staticmethod(agent_chat)
        if dashboard is not None:
            LiveWarrantyHandler.dashboard = staticmethod(dashboard)
        handler = LiveWarrantyHandler
    return ThreadingHTTPServer(("", port), handler)


def main() -> int:
    from warranty.agent_chat import lazy_live_agent_chat, lazy_live_dashboard

    port = load_port()
    httpd = serve(port, lazy_live_agent_chat(time.sleep), lazy_live_dashboard(time.sleep))
    # ⚠️ 뜬 것을 말하고 시작한다 — 프로브가 실패했을 때 *"안 떴다"*와 *"떴는데 다른 포트"*를
    #    로그만으로 가를 수 있어야 한다.
    print(f"listening on :{port}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
