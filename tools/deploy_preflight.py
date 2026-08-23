"""배포 전 검사 — **올리기 전에** 서비스 못 하는 이미지를 잡는다 (T12-4 · design 10§5).

Spec: specs/warranty/design/10-deployment.md §5 (REQ-602)

⛔ **이 도구는 아무것도 배포하지 않고, 네트워크도 안 연다.** 읽는 것은 이 저장소의 파일뿐이다.
   `gcloud`를 부르는 것은 `scripts/deploy.sh`이고 **사람이** 부른다.

⚠️ **왜 배포 *전*인가.** design 10§5의 `deploy-check`는 올린 **뒤**의 절반이다
   (`/healthz` + 실제 remediate 1건 왕복) — 실물 서비스가 없으면 판정이 안 되고, 그래서
   무인 게이트가 못 만드는 종류다. 여기 있는 것은 그 앞의 절반이다: **렌더된 배포 계획과
   이미지 선언을 맞대서 올리기 전에 막는다.** 뒤의 절반이 잡는 실패를 앞에서 잡으면
   비용이 *빌드 + 리비전 + 실패한 프로브*에서 **0**이 된다.

⛔ **T11-1이 예고해 둔 자리다**: *"이대로 올리면 포트 프로브에서 죽고, 그것을 잡을
   `deploy-check`도 아직 없다."* T12-1이 서버를 만들었고, 여기가 그것을 **집행하는** 자리다.

묻는 것은 둘이다:

  ① `CMD`가 가리키는 진입점이 **실제로 서비스하는가** — 포트를 `config`에서 읽고,
     소켓을 열고, **안 끝나는가**
  ② 지금 빌드할 이미지가 **렌더된 계획이 배포하는 그 이미지인가**

⚠️ ①이 `test_http_server` ⑧의 되풀이가 아닌 이유: 그것이 묻는 것은 *"`CMD`의 모듈 이름이
   서버 모듈의 이름과 같은가"*다. 이름은 같은데 그 모듈이 **더는 서비스하지 않는** 상태가
   그 검사에는 안 보인다 — `serve_forever` 한 줄만 빠져도 컨테이너는 뜨자마자 정상 종료하고,
   그 실패는 빌드에도 게이트에도 안 나타난다. 여기서 묻는 것은 이름이 아니라 **하는 일**이다.

⚠️ ②는 셸을 겨냥한다. 값의 출처는 `warranty.config` 하나지만, **빌드하는 주소와 배포하는
   주소를 각각 집는 것은 셸**이다(`scripts/deploy.sh`). 그 둘이 갈라지면 올라간 이미지와
   도는 이미지가 다르고, 그 어긋남은 로그에 *"배포 성공"*으로 남는다. 이 저장소는 셸이
   갈라지는 모양에 이미 세 번 태워 봤다(M-87·M-91·M-98).
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from warranty import config
from warranty.config import ConfigError, deploy_argv, load_settings

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / "Dockerfile"
SRC = ROOT / "src"

#: `CMD ["python", "-m", "warranty.server"]` → `warranty.server`
DOCKER_CMD_MODULE_RE = re.compile(r'CMD\s*\[[^\]]*"-m"\s*,\s*"([\w.]+)"')

#: 포트의 유일한 출처. ⚠️ 이름을 문자열로 **베끼지 않는다** — config가 자기 이름을 말한다.
#:    베끼면 `load_port`를 개명하는 순간 이 검사는 *"아무도 안 부른다"*고 영원히 운다.
PORT_SOURCE = config.load_port.__name__

#: 소켓을 열고 **안 돌아오는** 호출. stdlib의 이름이라 여기 적을 수밖에 없다.
#: ⛔ 이 한 줄이 *"서비스한다"*와 *"실행하고 끝난다"*를 가르는 유일한 구조적 표지다.
BLOCKING_CALL = "serve_forever"

#: 공허 통과 방지의 바닥. 스캔 경로가 틀리면 아래 판정이 **0바이트를 파싱하고** 초록이다.
#: ⚠️ 이 저장소는 같은 방식으로 여러 번 속았다(M-03·M-25·M-45·M-118).
MIN_ENTRYPOINT_LINES = 10


def entrypoint_module(dockerfile_text: str) -> str | None:
    """이미지가 돌리는 모듈. 못 읽으면 `None` — *"없다"*와 *"못 읽었다"*는 다른 값이다."""
    match = DOCKER_CMD_MODULE_RE.search(dockerfile_text)
    return None if match is None else match.group(1)


def entrypoint_path(module: str) -> Path:
    """`warranty.server` → `src/warranty/server.py`."""
    return SRC / Path(*module.split(".")).with_suffix(".py")


def _called_names(tree: ast.AST) -> set[str]:
    """모듈 어디에서든 **불리는 이름들**. `f()`도 `x.f()`도 같은 이름으로 센다.

    ⚠️ 구문으로 묻는 이유: 값으로는 안 보이는 결격이다. `serve_forever`가 빠진 서버는
       임포트도 되고 타입도 맞고 단위 테스트도 전부 통과한다 — 갈라지는 것은
       **프로세스가 끝나는가**뿐이고, 그건 첫 배포의 프로브에서만 보인다.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def _has_main_guard(tree: ast.Module) -> bool:
    """`if __name__ == "__main__":`가 최상위에 있는가.

    ⚠️ 없으면 `python -m`은 모듈을 임포트만 하고 **조용히 0으로 끝난다.** 그 컨테이너는
       죽지도 않고 서비스하지도 않으며, 로그에는 아무것도 안 남는다.
    """
    for node in tree.body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            left = node.test.left
            if isinstance(left, ast.Name) and left.id == "__name__":
                return True
    return False


def serves_findings(module: str, source: str) -> list[str]:
    """진입점 소스가 **서비스하지 않는** 이유들. 빈 목록이면 통과다."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"{module}을 파싱하지 못했다: {exc}"]

    findings: list[str] = []
    names = _called_names(tree)
    if PORT_SOURCE not in names:
        findings.append(
            f"{module}이 포트를 `config.{PORT_SOURCE}`에서 안 읽는다 — "
            "이미지가 듣는 포트와 플랫폼이 프로브하는 포트가 따로 썩는다"
        )
    if BLOCKING_CALL not in names:
        findings.append(
            f"{module}이 `{BLOCKING_CALL}`을 안 부른다 — 프로세스는 정상 종료하고, "
            "끝난 컨테이너는 포트를 한 번도 안 연 채 프로브에서 죽는다"
        )
    if not _has_main_guard(tree):
        findings.append(
            f'{module}에 `if __name__ == "__main__"` 가드가 없다 — '
            "`python -m`이 임포트만 하고 조용히 끝난다"
        )
    return findings


def entrypoint_findings(dockerfile_text: str) -> list[str]:
    """① 이미지 선언 → 진입점 → **서비스하는가**."""
    module = entrypoint_module(dockerfile_text)
    if module is None:
        return ["Dockerfile의 `CMD`에서 모듈을 못 읽었다 — 진입점 모양이 바뀌었다"]

    path = entrypoint_path(module)
    if not path.is_file():
        return [f"`CMD`가 없는 모듈을 가리킨다: {module} — 컨테이너는 뜨자마자 죽는다"]

    source = path.read_text(encoding="utf-8")
    lines = len(source.splitlines())
    if lines < MIN_ENTRYPOINT_LINES:
        return [
            f"진입점 소스를 {lines}줄만 읽었다 ({path.name}) — 스캔 경로가 틀렸거나 잘렸다. "
            "0바이트를 파싱한 초록은 '서비스한다'가 아니라 '아무것도 안 봤다'이다"
        ]
    return serves_findings(module, source)


def image_findings(image: str, rendered: Sequence[str]) -> list[str]:
    """② 빌드할 이미지 ↔ 렌더된 계획이 배포하는 이미지."""
    if not image.strip():
        return ["빌드할 이미지 주소가 비어 있다 — 무엇을 올리는지 말하지 않는 배포는 안 한다"]
    if f"--image={image}" in rendered:
        return []
    deployed = [arg.split("=", 1)[1] for arg in rendered if arg.startswith("--image=")]
    return [
        f"빌드할 이미지와 계획이 배포하는 이미지가 다르다: 빌드 {image} · "
        f"배포 {deployed or '없음'} — 올라가는 것과 도는 것이 갈라진다"
    ]


def exit_code(findings: Sequence[str]) -> int:
    """⛔ **`set -e`가 멈추는 것은 이 값 하나다.** 발견이 있는데 0을 내면 검사는 장식이다."""
    return 1 if findings else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="배포 전 검사 (배포도 네트워크도 안 한다)")
    parser.add_argument("--tag", required=True, help="이미지 태그. `latest`를 쓰지 않는다")
    parser.add_argument("--image", required=True, help="지금 빌드할 이미지 주소")
    ns = parser.parse_args(argv)

    try:
        rendered = deploy_argv(load_settings(), ns.tag)
    except ConfigError as exc:
        print(f"설정이 성립하지 않는다: {exc}", file=sys.stderr)
        return 2

    findings = entrypoint_findings(DOCKERFILE.read_text(encoding="utf-8"))
    findings += image_findings(ns.image, rendered)
    for finding in findings:
        print(f"⛔ {finding}", file=sys.stderr)
    if findings:
        print("올리지 않는다 — 배포 전 검사가 막았다 (design 10§5)", file=sys.stderr)
    else:
        print("배포 전 검사 통과 — 진입점이 포트를 열고, 계획이 빌드할 이미지를 가리킨다")
    return exit_code(findings)


if __name__ == "__main__":
    raise SystemExit(main())
