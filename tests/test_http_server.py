"""HTTP 서버 — **이미지가 포트를 여는가, 그리고 무엇이라 답하는가** (T12-1 · REQ-602).

Spec: specs/warranty/design/08-interfaces.md §3-4 (REQ-602)

⛔ **함정 하나를 없애는 자리다.** 직전까지 이미지의 `CMD`는 오프라인 데모였고, 데모는
   끝나면 종료한다 — 컨테이너가 포트를 한 번도 안 열어서 **포트 프로브에서 죽는다.**
   그 실패는 빌드에서도 게이트에서도 안 보이고 **첫 배포에서만** 보인다. 그래서 배포가
   못 하는 확인을 게이트가 대신 한다. 묻는 것은 여덟이다:

  ① 설계 표 파서가 **실제로 읽는가** (공허 통과 방지)
  ② 코드의 `ROUTES`가 design 08§3 표와 **같은 집합**인가 (사본이 따로 썩지 않는가)
  ③ ★ `/healthz`가 `200`인가 — 프로브가 두드리는 그 자리
  ④ 배선 안 된 경로가 `501`인가 — **`200`이면 배포가 조용히 가짜로 돈다**
  ⑤ 미등록 경로는 `404`, 잘못된 메서드는 `405`인가 (design 08§4)
  ⑥ 포트가 `config.py` **한 곳**에서 오는가 · 산출물이 그 숫자를 다시 안 적는가
  ⑦ ★ 실제 핸들러를 **요청→응답으로 태운다** — 소켓 없이
  ⑧ `CMD`가 **서버**를 가리키는가 — 데모를 가리키면 컨테이너는 끝나고 프로브는 실패한다

⚠️ ⑦이 ③~⑤의 되풀이가 아닌 이유: ③~⑤는 `resolve`(순수 함수)에 묻는다. 판정이 옳아도
   핸들러가 그것을 **바이트로 못 내면** 프로브는 여전히 실패한다 — `Content-Length`가
   빠지면 클라이언트는 응답의 끝을 모르고 타임아웃으로 죽고, 그건 서버가 답을 안 한
   것처럼 보인다. ⑦은 그 한 칸을 묻는다.

⛔ **소켓을 안 연다.** 무인 루프의 권한 경계가 그것을 막고(D14), 막지 않더라도 포트를 여는
   테스트는 게이트를 기계 상태에 묶는다. 대신 핸들러를 `__new__`로 만들고 파일 객체 둘을
   물려 **실제 `do_GET`/`do_POST`를 돌린다** — 소켓이 하는 일은 그 둘을 주는 것뿐이다.

⚠️ ①이 없으면 ②는 **0개를 맞대고** 초록이다. 이 저장소는 같은 방식으로 여러 번 속았다
   (M-03·M-25·M-45·M-118).
"""

from __future__ import annotations

import io
import json
import re
from http.client import HTTPMessage
from pathlib import Path

import pytest

from warranty import server
from warranty.config import (
    DEFAULT_PORT,
    MAX_PORT,
    PORT_ENV_KEY,
    SERVICE_NAME,
    ConfigError,
    load_port,
)
from warranty.server import (
    HEALTH_PATH,
    METHOD_NOT_ALLOWED,
    NOT_FOUND,
    NOT_IMPLEMENTED,
    OK,
    ROUTES,
    WarrantyHandler,
    resolve,
)

ROOT = Path(__file__).resolve().parent.parent
INTERFACES = ROOT / "specs" / "warranty" / "design" / "08-interfaces.md"
DOCKERFILE = ROOT / "Dockerfile"

#: `CMD ["python", "-m", "warranty.server"]` → `warranty.server`.
#: ⚠️ `test_deploy_artifacts`와 같은 모양을 읽는다 — 거기는 *실재*를, 여기는 *무엇*을 묻는다.
DOCKER_CMD_MODULE_RE = re.compile(r'CMD\s*\[[^\]]*"-m"\s*,\s*"([\w.]+)"')

#: 설계의 HTTP 계약 표가 사는 절.
CONTRACT_HEADING = "## 3. HTTP 계약"

#: 공허 통과 방지의 바닥. 설계 표에는 여덟 행이 있다 — 파서가 이보다 적게 읽으면 깨진 것이다.
MIN_ROUTES = 6

#: `| `POST` | `/resources:provision` | … |` 한 행에서 메서드와 경로.
DESIGN_ROW_RE = re.compile(r"^\|\s*`(GET|POST|PUT|PATCH|DELETE)`\s*\|\s*`([^`]+)`", re.MULTILINE)

#: 포트를 다시 적으면 안 되는 산출물. ⚠️ `deploy.sh`까지 보는 이유: `gcloud`에 `--port`를
#: 붙이는 순간 그 숫자가 코드 밖에 하나 더 생긴다.
ARTIFACTS = (ROOT / "Dockerfile", ROOT / "scripts" / "deploy.sh")


def _design_routes() -> set[tuple[str, str]]:
    """design 08§3 표가 선언한 `(메서드, 경로)` 집합.

    ⚠️ 질의 문자열을 떼어 낸다 — 표의 `/report/daily?date=`에서 **경로인 것은 앞부분**이다.
    """
    text = INTERFACES.read_text(encoding="utf-8")
    start = text.find(CONTRACT_HEADING)
    if start < 0:
        raise AssertionError(
            f"{INTERFACES.name}에서 {CONTRACT_HEADING!r} 절을 못 찾았다 — 표제가 바뀌었다. "
            "이 가드는 그 절 하나에 물린다."
        )
    end = text.find("\n## 4.", start)
    section = text[start:] if end < 0 else text[start:end]
    return {(method, path.split("?", 1)[0]) for method, path in DESIGN_ROW_RE.findall(section)}


# ── ⑦의 도구: 소켓 없이 핸들러를 돌린다 ────────────────────────────────────────


class Exchange:
    """왕복 하나가 남긴 것 전부. **`leftover`가 따로 있는 이유**는 아래 ⑦ 두 번째를 볼 것."""

    def __init__(self, status: int, headers: HTTPMessage, payload: bytes, leftover: bytes) -> None:
        self.status = status
        self.headers = headers
        self.payload = payload
        #: 핸들러가 **안 읽고 남긴** 요청 본문. keep-alive에서 이것이 다음 요청 줄이 된다.
        self.leftover = leftover


def _drive(method: str, target: str, *, body: bytes = b"") -> Exchange:
    """실제 `WarrantyHandler`에 요청 하나를 먹이고 **낸 바이트를 그대로** 돌려준다.

    ⚠️ `__init__`을 건너뛰는 이유는 그것이 소켓을 잡기 때문이다. 여기서 채우는 다섯 값이
       `socketserver`가 평소에 채워 주는 전부다 — 그 아래로는 전부 진짜 코드가 돈다.
    """
    handler = WarrantyHandler.__new__(WarrantyHandler)
    handler.path = target
    handler.requestline = f"{method} {target} HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 0)
    source = io.BytesIO(body)
    handler.rfile = source
    sink = io.BytesIO()
    handler.wfile = sink
    headers = HTTPMessage()
    if body:
        headers["Content-Length"] = str(len(body))
    handler.headers = headers

    if method == "GET":
        handler.do_GET()
    else:
        handler.do_POST()

    raw = sink.getvalue()
    head, separator, payload = raw.partition(b"\r\n\r\n")
    assert separator, f"핸들러가 머리와 본문을 가르지 않았다: {raw[:120]!r}"
    lines = head.decode("latin-1").split("\r\n")
    status = int(lines[0].split(" ")[1])
    parsed = HTTPMessage()
    for line in lines[1:]:
        name, _, value = line.partition(":")
        parsed[name.strip()] = value.strip()
    return Exchange(status, parsed, payload, source.read())


# ── ① 파서가 실제로 읽는가 ─────────────────────────────────────────────────────


def test_the_design_contract_table_is_actually_read() -> None:
    """① 바닥. ⚠️ 파서가 0개를 읽으면 ②는 **빈 집합끼리 맞대고** 조용히 통과한다."""
    routes = _design_routes()
    assert len(routes) >= MIN_ROUTES, (
        f"design 08§3 표에서 경로를 {len(routes)}개만 읽었다 (최소 {MIN_ROUTES}) — "
        "표 모양이 바뀌었거나 절이 옮겨졌다. 이 수가 0이면 ②는 아무것도 안 맞댄다."
    )
    assert ("GET", HEALTH_PATH) in routes, (
        f"설계 표에 헬스 경로가 없다: {sorted(routes)} — 파서가 다른 절을 읽고 있다"
    )


# ── ② 코드의 경로 표가 설계와 같은가 ──────────────────────────────────────────


def test_the_router_serves_exactly_what_the_design_declares() -> None:
    """② ⛔ **사본은 따로 썩는다.** `ROUTES`는 design 08§3 표의 사본이고, 여기가 그 둘을
    맞대는 유일한 자리다.

    ⚠️ 한쪽으로만 묻지 않는다: 설계에 있는데 코드에 없으면 그 경로는 **조용히 `404`**이고,
       코드에 있는데 설계에 없으면 아무도 합의 안 한 경로가 열린 것이다.
    """
    declared = _design_routes()
    served = {(route.method, route.template) for route in ROUTES}
    assert served == declared, (
        f"설계 표와 라우터가 갈라졌다.\n"
        f"  설계에만 있다: {sorted(declared - served)}\n"
        f"  코드에만 있다: {sorted(served - declared)}"
    )


# ── ③ 프로브가 두드리는 자리 ──────────────────────────────────────────────────


def test_the_health_path_answers_two_hundred() -> None:
    """③ ★ **이 하나가 첫 배포의 생사다.** 여기서 `200`이 안 나오면 리비전은 트래픽을
    한 번도 못 받고, 나머지 경로가 무엇을 내든 아무도 못 본다.
    """
    response = resolve("GET", HEALTH_PATH)
    assert response.status == OK, (
        f"헬스 경로가 {response.status}를 냈다 — 포트 프로브가 실패하고 배포가 죽는다"
    )
    body = json.loads(response.payload().decode("utf-8"))
    assert body["service"] == SERVICE_NAME, (
        f"헬스 응답이 다른 서비스를 말한다: {body} — 이름은 config가 소유한다"
    )


# ── ④ 배선 안 된 경로가 조용히 성공하지 않는가 ────────────────────────────────


@pytest.mark.parametrize(
    ("method", "target"),
    [
        ("POST", "/resources:provision"),
        ("POST", "/actions/act-1:remediate"),
        ("GET", "/ledger/01k2m9x7q3f4b8n0v6c1t5r2wz"),
        ("GET", "/report/daily?date=2026-08-23"),
    ],
)
def test_an_unwired_route_says_so_instead_of_faking_success(method: str, target: str) -> None:
    """④ ⛔ **가장 위험한 초록이 여기 있다.** 실물 어댑터가 없는데 fake를 물려 `200`을 내면
    이 서비스는 *"돌아간다"*와 *"가짜로 돌아간다"*를 구별할 수 없게 된다 — design 08§5가
    `WR_ADAPTERS`의 기본값을 `fake`로 두지 않는 이유가 정확히 그것이다.

    ⚠️ 상태 코드만 묻지 않는다. 이유가 본문에 없으면 심사자는 이 응답을 **버그**로 읽는다.
    """
    response = resolve(method, target)
    assert response.status == NOT_IMPLEMENTED, (
        f"{method} {target}이 {response.status}를 냈다 — 어댑터가 없는데 성공을 흉내 내면 "
        "배포가 조용히 가짜로 돈다"
    )
    body = json.loads(response.payload().decode("utf-8"))
    assert body["detail"], f"`501`에 이유가 없다: {body} — 이유 없는 501은 버그로 읽힌다"


# ── ⑤ 오류 모델 (design 08§4) ─────────────────────────────────────────────────


def test_an_unknown_path_is_not_found_and_a_wrong_method_is_not_allowed() -> None:
    """⑤ ⚠️ 둘을 가르는 것이 요점이다. 미등록을 `405`로, 잘못된 메서드를 `404`로 내면
    클라이언트는 *"경로를 잘못 적었다"*와 *"동사를 잘못 골랐다"*를 구별 못 한다.

    ⚠️ 셋째 줄은 **회귀 검사**지 하중을 받는 자리가 아니다: `/ledger/{entry_id}`와
       `/ledger/{entry_id}:approve`는 메서드가 달라서, 자리표시자가 콜론을 먹어도 승인은
       여전히 `501`로 간다. 그래서 자리표시자를 겨냥한 변이는 안 만들었다
       (docs/evidence/mutations.md의 「안 태운 자리」).
    """
    assert resolve("GET", "/nope").status == NOT_FOUND
    assert resolve("DELETE", HEALTH_PATH).status == METHOD_NOT_ALLOWED
    assert resolve("POST", "/ledger/entry-1:approve").status == NOT_IMPLEMENTED, (
        "승인 경로가 조회 경로에 먹혔다 — 경로 틀이 콜론을 잘못 다루고 있다"
    )


# ── ⑥ 포트의 출처가 하나인가 ──────────────────────────────────────────────────


def test_the_port_comes_from_the_environment_and_falls_back_to_one_default() -> None:
    """⑥ Cloud Run은 `PORT`를 **주입한다**. 그 이름과 기본값은 config 한 곳에 있다.

    ⚠️ 값이 있는데 숫자가 아닐 때 **조용히 기본값으로 접지 않는다**. 접으면 컨테이너는
       뜨고 프로브는 실패하며 로그에는 아무 이유도 안 남는다.
    """
    assert load_port({PORT_ENV_KEY: "9090"}) == 9090, "주입된 포트를 안 읽는다"
    assert load_port({}) == DEFAULT_PORT, "`PORT`가 없을 때 기본값이 안 나온다"
    for bad in ("", "  ", "http", "0", str(MAX_PORT + 1), f"${PORT_ENV_KEY}"):
        if not bad.strip():
            assert load_port({PORT_ENV_KEY: bad}) == DEFAULT_PORT
            continue
        with pytest.raises(ConfigError):
            load_port({PORT_ENV_KEY: bad})


def test_no_deployment_artifact_repeats_the_port_number() -> None:
    """⑥ 반대편 — 산출물이 그 숫자를 다시 적는가.

    ⛔ 다시 적히면 *이미지가 듣는 포트*와 *프로브가 두드리는 포트*가 따로 썩고,
       그 어긋남은 **첫 배포에서만** 보인다. 게이트가 그것을 대신 묻는다.
    """
    copies = [
        f"{path.name}: {str(DEFAULT_PORT)!r}"
        for path in ARTIFACTS
        if path.is_file() and str(DEFAULT_PORT) in path.read_text(encoding="utf-8")
    ]
    assert not copies, f"배포 산출물이 포트를 다시 적는다: {copies} — 포트의 출처는 config 하나다"


# ── ⑧ 이미지가 무엇을 돌리는가 ────────────────────────────────────────────────


def test_the_image_entrypoint_is_the_server_and_not_the_demo() -> None:
    """⑧ ⛔ **함정 자체가 여기 있었다.** `CMD`가 데모를 가리키면 컨테이너는 출력을 찍고
    **정상 종료한다** — 포트는 한 번도 안 열리고 프로브는 실패한다.

    ⚠️ `test_deploy_artifacts` ⑥는 이것을 **못 본다.** 그것이 묻는 것은 *"`CMD`가 가리키는
       모듈이 실재하는가"*이고 `warranty.demo`는 실재한다. 그 초록이 정확히 이 함정을
       통과시킨 초록이다 — 있는 모듈을 가리키는 것과 **서버를 가리키는 것**은 다른 질문이다.

    ⚠️ 기대값을 문자열로 적지 않는다 — 서버 모듈이 자기 이름을 말하게 한다(사본 금지).
    """
    module = DOCKER_CMD_MODULE_RE.search(DOCKERFILE.read_text(encoding="utf-8"))
    assert module is not None, "Dockerfile의 `CMD`에서 모듈을 못 읽었다 — 진입점 모양이 바뀌었다"
    assert module.group(1) == server.__name__, (
        f"`CMD`가 서버가 아니라 {module.group(1)}을 가리킨다 — 그 프로세스는 끝나고, "
        "끝난 컨테이너는 포트 프로브에서 죽는다"
    )


# ── ⑦ 실제 핸들러를 요청→응답으로 태운다 ─────────────────────────────────────


def test_the_handler_actually_writes_a_well_formed_response() -> None:
    """⑦ ★ 판정이 옳아도 **바이트로 못 내면** 프로브는 여전히 실패한다.

    ⚠️ `Content-Length`를 함께 묻는 이유: 없으면 HTTP/1.1 클라이언트는 응답의 끝을 모르고
       연결을 붙든 채 타임아웃으로 죽는다 — 서버가 답을 안 한 것과 **구별되지 않는다**.
    """
    exchange = _drive("GET", HEALTH_PATH)
    assert exchange.status == OK, f"핸들러가 헬스에 {exchange.status}를 냈다"
    length = exchange.headers.get("Content-Length")
    assert length == str(len(exchange.payload)), (
        f"`Content-Length`({length})가 본문 길이({len(exchange.payload)})와 다르다 — "
        "클라이언트가 응답의 끝을 모른다"
    )
    assert json.loads(exchange.payload.decode("utf-8"))["status"] == "ok"


def test_the_handler_reads_the_request_body_before_answering() -> None:
    """⑦ 반대편 — 본문을 **안 읽으면** keep-alive에서 다음 요청이 그 본문을 요청 줄로 읽고,
    두 번째 요청부터 조용히 깨진다. 부하에서 나는 실패가 아니라 **두 번째 클릭**에서 난다.

    ⚠️ 남은 바이트를 값으로 본다 — *"핸들러가 읽었다고 우리가 믿는다"*가 아니라
       *"입력 스트림에 아무것도 안 남았다"*를 묻는다.
    """
    exchange = _drive("POST", "/resources:provision", body=b'{"resource": "x"}')
    assert exchange.status == NOT_IMPLEMENTED, f"배선 안 된 경로가 {exchange.status}를 냈다"
    assert json.loads(exchange.payload.decode("utf-8"))["error"] == "not_implemented"
    assert exchange.leftover == b"", (
        f"핸들러가 요청 본문을 {len(exchange.leftover)}바이트 남겼다: {exchange.leftover[:40]!r} — "
        "keep-alive에서 다음 요청이 이것을 요청 줄로 읽는다"
    )
