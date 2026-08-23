"""배포 전 검사 — **서비스 못 하는 이미지를 올리기 전에 막는가** (T12-4 · REQ-602).

Spec: specs/warranty/design/10-deployment.md §5 (REQ-602)

⛔ **T11-1이 예고해 둔 자리다**: *"이대로 올리면 포트 프로브에서 죽고, 그것을 잡을
   `deploy-check`도 아직 없다."* T12-1이 서버를 만들어 함정 하나를 없앴지만, 그때 생긴 것은
   **지금 이 순간의 초록**이지 집행이 아니다 — `serve_forever` 한 줄만 빠지면 컨테이너는
   뜨자마자 정상 종료하고, 그 실패는 빌드에도 게이트에도 안 나타난다.

⚠️ `test_http_server` ⑧이 이것을 **못 본다.** 그것이 묻는 것은 *"`CMD`의 모듈 이름이 서버
   모듈의 이름과 같은가"*다. 이름은 그대로인데 그 모듈이 **더는 서비스하지 않는** 상태는
   그 검사에 초록이다 — 이름을 묻는 것과 **하는 일**을 묻는 것은 다른 질문이다.

묻는 것은 열하나다:

  ① 분석기가 진입점 소스를 **실제로 읽는가** (공허 통과 방지)
  ② 지금 이미지의 진입점이 검사를 **통과하는가** (바닥 — 가드가 늘 red면 결국 꺼진다)
  ③ ⛔ **본체** — 데모를 가리키면 거부하는가 (`CMD`가 실제로 그랬던 그 상태)
  ④ 포트를 `config`에서 안 읽는 진입점을 거부하는가
  ⑤ 안 끝나는 호출이 없는 진입점을 거부하는가 (**뜨고 바로 종료**)
  ⑥ `__main__` 가드가 없는 진입점을 거부하는가 (`python -m`이 임포트만 하고 끝난다)
  ⑦ 없는 모듈을 가리키는 `CMD`를 거부하는가
  ⑧ 빌드할 이미지와 계획이 배포하는 이미지가 갈라지면 거부하는가
  ⑨ 발견이 있으면 **종료 코드가 0이 아닌가** — `set -e`가 멈추는 자리는 그 값 하나다
  ⑩ ★ `scripts/deploy.sh`가 **빌드보다 먼저** 검사를 부르는가 (뒤에 부르면 안 막은 것과 같다)
  ⑪ 검사 도구가 **네트워크도 `gcloud`도 안 부르는가** (REQ-801)

⚠️ ⑪을 함께 묻는 이유: *"배포 전 검사"*는 정확히 실물을 한 번 찔러 보고 싶어지는 종류의
   물건이다. 한 번 찌르는 순간 이 도구는 과금·네트워크·자격증명을 요구하게 되고, 무인 루프의
   권한 경계 안에서는 영영 못 돌게 된다(D14). 여기서 막지 않으면 그 문장은 주석일 뿐이다.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from tools.deploy_preflight import (
    BLOCKING_CALL,
    DOCKERFILE,
    MIN_ENTRYPOINT_LINES,
    PORT_SOURCE,
    entrypoint_findings,
    entrypoint_module,
    entrypoint_path,
    exit_code,
    image_findings,
    serves_findings,
)

from warranty.config import Adapters, Settings, deploy_argv, image_uri

ROOT = Path(__file__).resolve().parent.parent
DEPLOY_SH = ROOT / "scripts" / "deploy.sh"
PREFLIGHT_TOOL = "tools/deploy_preflight.py"

#: 셸이 이미지를 **올리는** 줄. ⚠️ 검사는 이 줄보다 위에 있어야 한다.
BUILD_MARK = "gcloud builds submit"

#: ⑪이 겨냥하는 것들 — 실물을 찌르려면 **반드시 이 중 하나가 먼저 임포트된다.**
#: ⚠️ `subprocess`가 여기 있는 이유: `gcloud`를 부르는 것도 네트워크를 여는 것이다.
LIVE_IMPORTS = ("subprocess", "socket", "urllib", "http", "requests", "httpx", "ssl")

#: 렌더러에 넣는 설정. ⚠️ `.env`를 안 읽는다 — 게이트가 이 기계의 파일에 기대면
#: 그 초록은 여기서만 참이다(REQ-802 · test_deploy_artifacts와 같은 규칙).
SAMPLE = Settings(
    project_id="warranty-hack",
    region="us-central1",
    model="gemini-3.7-flash",
    adapters=Adapters.LIVE,
    reconcile_deadline_days=3,
    billing_table=None,
)
SAMPLE_TAG = "abc1234"

#: 서비스하는 진입점의 **최소 모양**. ⚠️ 실제 서버를 베낀 게 아니라 셋을 다 갖춘 표본이다 —
#: 아래 ④~⑥이 여기서 하나씩만 빼서 *"그 하나가 판정을 뒤집는가"*를 묻는다.
SERVING_SOURCE = textwrap.dedent(f"""\
    def main() -> int:
        port = {PORT_SOURCE}()
        httpd = serve(port)
        httpd.{BLOCKING_CALL}()
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    """)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _without(line_fragment: str) -> str:
    """표본에서 한 줄만 뺀다. **바뀌는 것이 그 한 줄뿐이어야** 판정의 원인이 분명하다."""
    kept = [line for line in SERVING_SOURCE.splitlines() if line_fragment not in line]
    return "\n".join(kept) + "\n"


def _deploy_recipe_lines() -> list[str]:
    """주석을 뺀 `scripts/deploy.sh`의 실행 줄들. **선언이 아니라 도는 것을 본다.**"""
    return [
        line
        for line in _read(DEPLOY_SH).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _index_of(lines: list[str], needle: str) -> int | None:
    for index, line in enumerate(lines):
        if needle in line:
            return index
    return None


def _imported_roots(source: str) -> set[str]:
    """모듈이 들여오는 최상위 패키지들. `import a.b`도 `from a.b import c`도 `a`로 센다."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


# ── ① 분석기가 실제로 읽는가 ────────────────────────────────────────────────


def test_the_entrypoint_source_is_actually_read() -> None:
    """① 공허 통과 방지 — 스캔 경로가 틀리면 아래가 **0바이트를 파싱하고** 초록이다.

    ⚠️ 이 저장소는 같은 방식으로 여러 번 속았다(M-03·M-25·M-45·M-118). *"서비스한다"*와
       *"아무것도 안 봤다"*가 같은 초록으로 보이는 그 모양이다.
    """
    module = entrypoint_module(_read(DOCKERFILE))
    assert module is not None, "Dockerfile의 `CMD`에서 모듈을 못 읽었다 — 진입점 모양이 바뀌었다"
    path = entrypoint_path(module)
    assert path.is_file(), f"진입점 경로가 파일이 아니다: {path} — 스캔 경로가 틀렸다"
    assert len(_read(path).splitlines()) >= MIN_ENTRYPOINT_LINES, (
        f"{path.name}을 {len(_read(path).splitlines())}줄만 읽었다 — 잘렸거나 경로가 틀렸다"
    )
    assert serves_findings("표본", SERVING_SOURCE) == [], (
        "서비스하는 표본을 거부했다 — 분석기가 무엇이든 거부하면 아래 ③~⑥은 공허하다"
    )


# ── ② 지금 이미지가 통과하는가 (바닥) ───────────────────────────────────────


def test_the_current_image_entrypoint_passes_the_preflight() -> None:
    """② 바닥 — 늘 red인 가드는 결국 꺼진다(test_tunables ③과 같은 규칙).

    ⛔ 여기가 red면 고칠 것은 이 테스트가 아니라 **진입점**이다: 지금 그 이미지는
       Cloud Run에서 포트 프로브를 통과하지 못한다.
    """
    findings = entrypoint_findings(_read(DOCKERFILE))
    assert findings == [], f"지금 이미지의 진입점이 서비스하지 않는다: {findings}"


# ── ③~⑥ 서비스하지 않는 진입점을 거부하는가 ────────────────────────────────


def test_an_entrypoint_that_only_runs_and_exits_is_refused() -> None:
    """③ ⛔ **본체다** — `CMD`가 데모를 가리키던 그 상태를 실제 소스로 태운다.

    ⚠️ 데모는 출력을 찍고 **정상 종료한다.** 종료 코드는 0이고 로그는 초록이며, 컨테이너는
       포트를 한 번도 안 연다 — 보이는 것은 *"리비전이 트래픽을 못 받는다"*뿐이다.
    ⚠️ 기대값을 문자열로 안 적는다 — 데모 모듈의 **실제 소스**에 묻는다. 손으로 지어낸
       표본만 태우면 진짜 데모가 언제 서비스하게 됐는지 아무도 모른다.
    """
    demo_source = _read(entrypoint_path("warranty.demo"))
    findings = serves_findings("warranty.demo", demo_source)
    assert findings, (
        "데모를 진입점으로 받아들였다 — 그 컨테이너는 끝나고, 끝난 컨테이너는 프로브에서 죽는다"
    )
    assert any(BLOCKING_CALL in finding for finding in findings), (
        f"거부는 했는데 이유가 *'안 끝나는가'*가 아니다: {findings} — "
        "이유가 틀리면 사람은 엉뚱한 자리를 고친다"
    )


def test_an_entrypoint_that_hardcodes_its_port_is_refused() -> None:
    """④ 포트가 `config` 한 곳에서 안 온다.

    ⚠️ 이미지는 **뜬다.** 소켓도 열린다. 갈라지는 것은 *이미지가 듣는 포트*와 *플랫폼이
       프로브하는 포트*뿐이고, 그 어긋남은 첫 배포에서만 보인다.
    """
    findings = serves_findings("표본", _without(f"{PORT_SOURCE}()"))
    assert any(PORT_SOURCE in finding for finding in findings), (
        f"포트를 박은 진입점을 통과시켰다: {findings}"
    )


def test_an_entrypoint_that_never_blocks_is_refused() -> None:
    """⑤ ★ **한 줄이 사라지는 것으로 충분하다.**

    ⛔ `serve_forever`가 빠진 서버는 임포트도 되고 타입도 맞고 단위 테스트도 전부 통과한다.
       이름도 여전히 `warranty.server`라 `test_http_server` ⑧도 초록이다. 갈라지는 것은
       **프로세스가 끝나는가**뿐이다.
    """
    findings = serves_findings("표본", _without(BLOCKING_CALL))
    assert any(BLOCKING_CALL in finding for finding in findings), (
        f"안 끝나는 호출이 없는 진입점을 통과시켰다: {findings}"
    )


def test_an_entrypoint_without_a_main_guard_is_refused() -> None:
    """⑥ `python -m`이 **임포트만 하고 조용히 0으로 끝난다.**

    ⚠️ 이 실패에는 로그가 없다. 죽지도 않고 서비스하지도 않는다.
    """
    findings = serves_findings("표본", _without("__main__"))
    assert any("__main__" in finding for finding in findings), (
        f"진입 가드가 없는 진입점을 통과시켰다: {findings}"
    )


def test_a_cmd_pointing_at_a_missing_module_is_refused() -> None:
    """⑦ 없는 모듈 — 컨테이너는 뜨자마자 죽는다(M-46·M-90 계열)."""
    findings = entrypoint_findings('CMD ["python", "-m", "warranty.ghost"]')
    assert findings and any("warranty.ghost" in finding for finding in findings), (
        f"없는 모듈을 가리키는 `CMD`를 통과시켰다: {findings}"
    )


# ── ⑧ 빌드할 이미지 ↔ 계획이 배포하는 이미지 ───────────────────────────────


def test_the_plan_must_deploy_the_image_that_is_about_to_be_built() -> None:
    """⑧ 셸이 두 주소를 각각 집는다 — 갈라지면 올라간 것과 도는 것이 다르다.

    ⚠️ 값의 출처는 `warranty.config` 하나지만, **빌드 주소와 배포 주소를 집는 것은 셸**이다.
       이 저장소는 셸이 갈라지는 모양에 이미 세 번 태워 봤다(M-87·M-91·M-98).
    """
    rendered = deploy_argv(SAMPLE, SAMPLE_TAG)
    assert image_findings(image_uri(SAMPLE, SAMPLE_TAG), rendered) == [], (
        f"같은 태그로 렌더한 주소를 서로 다르다고 판정했다: {rendered}"
    )
    stale = image_findings(image_uri(SAMPLE, "0000000"), rendered)
    assert stale, "빌드할 이미지와 배포할 이미지가 달라도 통과했다 — 다른 리비전이 돈다"
    assert image_findings("   ", rendered), "빈 이미지 주소를 통과시켰다"


# ── ⑨ 발견이 종료 코드가 되는가 ────────────────────────────────────────────


def test_findings_become_a_nonzero_exit_code() -> None:
    """⑨ ⛔ **`set -e`가 멈추는 것은 이 값 하나다.**

    ⚠️ 발견을 stderr에 찍고 0을 내면 `scripts/deploy.sh`는 **그대로 빌드로 넘어간다** —
       사람이 보는 것은 경고가 스쳐 지나간 성공한 배포다.
    """
    assert exit_code([]) == 0, "발견이 없는데 배포를 막았다"
    assert exit_code(["무엇이든"]) != 0, "발견이 있는데 0을 냈다 — 검사가 장식이 된다"


# ── ⑩ 셸이 빌드보다 먼저 부르는가 ──────────────────────────────────────────


def test_the_deploy_script_runs_the_preflight_before_it_builds() -> None:
    """⑩ ★ **순서가 이 태스크의 전부다.** 올린 뒤에 잡는 것은 안 잡는 것과 같다.

    ⚠️ 배포는 게이트에 없다 — 아무도 안 돌리니 이 순서가 뒤집혀도 **다음 배포까지** 아무도
       모른다. 그리고 그 배포는 빌드 비용을 쓰고, 리비전을 만들고, 프로브에서 죽는다.
    """
    lines = _deploy_recipe_lines()
    checked = _index_of(lines, PREFLIGHT_TOOL)
    built = _index_of(lines, BUILD_MARK)
    assert checked is not None, (
        f"{DEPLOY_SH.name}이 {PREFLIGHT_TOOL}을 안 부른다 — 검사는 있는데 아무도 안 지난다"
    )
    assert built is not None, (
        f"{DEPLOY_SH.name}에서 `{BUILD_MARK}` 줄을 못 찾았다 — 셸의 모양이 바뀌었다"
    )
    assert checked < built, (
        f"검사가 빌드 **뒤에** 있다 (검사 {checked}행 · 빌드 {built}행) — "
        "이미 올라간 뒤에 막는 것은 안 막은 것과 같다"
    )


# ── ⑪ 검사가 실물을 안 찌르는가 ────────────────────────────────────────────


def test_the_preflight_never_touches_the_network() -> None:
    """⑪ 오프라인 — 한 번 찌르는 순간 이 도구는 무인 루프에서 영영 못 돈다(REQ-801 · D14).

    ⚠️ **본문 문자열이 아니라 임포트에 묻는다.** 이 도구의 독스트링은 `gcloud`를 여러 번
       말하는데(*"부르는 것은 `scripts/deploy.sh`"*), 산문으로 세면 그 설명이 위반으로 잡힌다.
       ⇒ 세는 자리는 **무엇을 들여왔는가**다. 실물을 찌르려면 반드시 그 문이 먼저 열린다.
    """
    roots = _imported_roots(_read(ROOT / PREFLIGHT_TOOL))
    live = sorted(roots & set(LIVE_IMPORTS))
    assert not live, (
        f"배포 전 검사가 실물을 찌를 수 있는 것을 들여온다: {live} — 그러면 이 검사는 "
        "자격증명과 과금을 요구하고, 무인 루프의 권한 경계 안에서는 영영 못 돈다"
    )
