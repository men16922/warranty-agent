"""배포 산출물 — **값이 한 곳에서 오는가** (T11-1 · design 10§1–2, §5).

Spec: specs/warranty/design/10-deployment.md §1–2, §5 (REQ-602, REQ-805)

⛔ **배포는 게이트에 없다.** 과금하고 되돌리기 어려워서 무인 루프의 deny 목록에 있고,
   사람도 자주 안 돌린다. 그래서 `Dockerfile`·`scripts/deploy.sh`가 코드와 갈라져도
   **그 어긋남을 아무도 안 읽는다** — 배포가 실제로 성공할 때까지, 혹은 조용히 틀린
   서비스에 올라갈 때까지. 이 저장소가 두 번 당한 모양이다: 세어 적은 숫자가 넷 다
   틀려 있었고(T0-6·T0-7), 이름 변경 때 `Spec:` 다섯 곳이 안 따라왔다(T0-5).

⇒ 배포가 못 하는 확인을 게이트가 대신 한다. 묻는 것은 여섯이다:
  ① 산출물이 실재하고 스캐너가 그것을 **실제로 읽는가** (공허 통과 방지)
  ② 렌더러가 서비스명·리전·`min-instances`를 **실제로 낸다**
  ③ 산출물이 그 셋을 **다시 적지 않는다** — 값의 출처가 하나인가
  ④ config가 선언한 것이 **설계가 선언한 것**과 같은가 (design 10§1–2를 파싱한다)
  ⑤ 이미지의 파이썬이 pyproject의 `requires-python`과 같은가
  ⑥ `CMD`가 가리키는 모듈이 실재하고, `make deploy`가 그 스크립트를 부르며
     **게이트는 그것을 안 부르는가** (REQ-801)

⚠️ ③이 ②의 되풀이가 아닌 이유: ②는 렌더러가 **낸다**는 것만 묻는다. 렌더러가 옳게
   내는데도 셸이 자기 플래그를 하나 더 붙이면 **뒤에 붙은 것이 이긴다** — `gcloud`는
   마지막 값을 쓴다. 그때 `min-instances=1`은 코드 어디에도 없고 REQ-805는 초록이다.

⚠️ 값은 묶고 **태그는 안 묶는다**: 태그는 커밋마다 달라야 하는 값이라 집행하면 가드가
   늘 red고, 그런 가드는 결국 꺼진다(test_tunables.py의 ③과 같은 규칙). 집행하는 것은
   *"태그가 비어 있지 않은가"*뿐이다.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from warranty.config import (
    MAX_INSTANCES,
    MIN_INSTANCES,
    SERVICE_NAME,
    Adapters,
    ConfigError,
    Settings,
    deploy_argv,
    image_uri,
)

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / "Dockerfile"
DEPLOY_SH = ROOT / "scripts" / "deploy.sh"
MAKEFILE = ROOT / "Makefile"
PYPROJECT = ROOT / "pyproject.toml"
ENV_EXAMPLE = ROOT / ".env.example"
DESIGN = ROOT / "specs" / "warranty" / "design" / "10-deployment.md"
SRC = ROOT / "src"

#: 값이 **한 번만** 적혀야 하는 자리들. 여기 문자열이 산출물에 다시 나오면 그것이 사본이다.
ARTIFACTS = (DOCKERFILE, DEPLOY_SH)

#: design 10§1의 리전 줄. ⚠️ 표제가 바뀌면 파서가 **못 찾고 예외를 낸다** —
#: 0개를 읽고 아래 검사를 공허하게 통과시키는 것보다 낫다(test_tunables.py와 같은 규칙).
DESIGN_REGION_RE = re.compile(r"^\s*리전:\s*(\S+)", re.MULTILINE)
#: design 10§2 표에서 **`min-instances`를 선언한 행**. `demo-target` 행과 갈라내는 표지가 그것이다.
DESIGN_SERVICE_ROW_RE = re.compile(
    r"^\|[^|\n]*`([\w-]+)`[^|\n]*\|[^|\n]*min-instances=(\d+)[^|\n]*max=(\d+)[^|\n]*\|",
    re.MULTILINE,
)
#: `FROM python:3.13-slim` → `3.13`
DOCKER_PYTHON_RE = re.compile(r"^FROM\s+python:(\d+\.\d+)", re.MULTILINE)
#: `requires-python = ">=3.13"` → `3.13`
REQUIRES_PYTHON_RE = re.compile(r'requires-python\s*=\s*">=\s*(\d+\.\d+)"')
#: `CMD ["python", "-m", "warranty.demo"]` → `warranty.demo`
DOCKER_CMD_MODULE_RE = re.compile(r'CMD\s*\[[^\]]*"-m"\s*,\s*"([\w.]+)"')
#: `.env.example`의 리전 기본값.
ENV_REGION_RE = re.compile(r"^WR_REGION=(\S+)", re.MULTILINE)

#: 공허 통과 방지의 바닥. 파서가 깨지면 이 파일의 단언이 전부 조용히 참이 된다.
#: ⚠️ `MIN_ARTIFACTS`가 없으면 목록을 비우는 것만으로 ①·③이 **0개를 훑고 초록**이 된다 —
#:    "어긋난 게 없다"와 "아무것도 안 봤다"가 같은 초록으로 보이는 그 모양이다.
MIN_ARTIFACTS = 2
MIN_DEPLOY_ARGS = 8
MIN_ARTIFACT_LINES = 10

#: 렌더러에 넣는 설정. ⚠️ `.env`를 안 읽는다 — 게이트가 이 기계의 파일에 기대면
#: 그 초록은 여기서만 참이다(REQ-802 · `load_settings`의 environ 분기와 같은 이유).
SAMPLE = Settings(
    project_id="warranty-hack",
    region="us-central1",
    model="gemini-3.7-flash",
    adapters=Adapters.LIVE,
    reconcile_deadline_days=3,
    billing_table=None,
)
SAMPLE_TAG = "abc1234"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _design_service_row() -> tuple[str, int, int]:
    """design 10§2가 선언한 서비스명·min·max. **손으로 베끼지 않고 파싱한다.**"""
    match = DESIGN_SERVICE_ROW_RE.search(_read(DESIGN))
    if match is None:
        raise AssertionError(
            f"{DESIGN.name}에서 `min-instances`를 선언한 서비스 행을 못 찾았다 — 표 모양이 바뀌었다"
        )
    return match.group(1), int(match.group(2)), int(match.group(3))


def _design_region() -> str:
    match = DESIGN_REGION_RE.search(_read(DESIGN))
    if match is None:
        raise AssertionError(f"{DESIGN.name} §1에서 리전 줄을 못 찾았다 — 블록 모양이 바뀌었다")
    return match.group(1)


def _make_recipe(target: str) -> list[str]:
    """Makefile의 한 타깃이 실제로 도는 줄들. **선언이 아니라 레시피를 본다.**"""
    lines = _read(MAKEFILE).splitlines()
    recipe: list[str] = []
    collecting = False
    for line in lines:
        if line.startswith(f"{target}:"):
            collecting = True
            continue
        if collecting:
            if line.startswith("\t"):
                recipe.append(line.strip())
                continue
            if line.strip() and not line.startswith("#"):
                break
    return recipe


def _check_prerequisites() -> list[str]:
    for line in _read(MAKEFILE).splitlines():
        if line.startswith("check:"):
            return line.split(":", 1)[1].split()
    raise AssertionError("Makefile에 `check` 타깃이 없다 — 게이트가 사라졌다")


@pytest.fixture(scope="module")
def rendered() -> tuple[str, ...]:
    return deploy_argv(SAMPLE, SAMPLE_TAG)


def test_the_deploy_artifacts_exist_and_are_actually_read(rendered: tuple[str, ...]) -> None:
    """① 공허 통과 방지 — 경로가 틀리면 아래 검사가 **0바이트를 훑고 전부 초록**이다.

    ⚠️ 이 저장소는 같은 방식으로 세 번 속았다(M-03·M-25·M-45). 스캔 경로 하나가 틀리면
       *"어긋난 게 없다"*와 *"아무것도 안 봤다"*가 **같은 초록**으로 보인다.
    """
    assert len(ARTIFACTS) >= MIN_ARTIFACTS, (
        f"산출물 목록이 {len(ARTIFACTS)}개다 — 목록이 비면 ①도 ③도 **0개를 훑고** 초록이다"
    )
    for path in ARTIFACTS:
        assert path.is_file(), f"배포 산출물이 없다: {path.relative_to(ROOT)}"
        assert len(_read(path).splitlines()) >= MIN_ARTIFACT_LINES, (
            f"{path.name}이 {len(_read(path).splitlines())}줄뿐이다 — 잘렸거나 자리만 잡은 파일이다"
        )
    assert len(rendered) >= MIN_DEPLOY_ARGS, (
        f"렌더러가 인자를 {len(rendered)}개만 냈다 — 아래 검사가 공허하다"
    )
    assert _design_service_row()[0] and _design_region(), "설계 파서가 빈 값을 읽었다"


def test_the_renderer_actually_emits_service_region_and_min_instances(
    rendered: tuple[str, ...],
) -> None:
    """② 렌더러가 셋을 **실제로 낸다**. 여기가 배포 산출물의 유일한 값 출처다."""
    assert SERVICE_NAME in rendered, f"렌더된 인자에 서비스명이 없다: {rendered}"
    assert f"--region={SAMPLE.region}" in rendered, (
        f"리전이 설정에서 안 왔다: {rendered} — 배포와 앱이 다른 리전을 볼 수 있다"
    )
    assert f"--min-instances={MIN_INSTANCES}" in rendered, (
        f"`min-instances`가 렌더에 없다: {rendered} — REQ-805가 아무도 안 읽는 문장이 된다"
    )
    assert f"--max-instances={MAX_INSTANCES}" in rendered
    uri = image_uri(SAMPLE, SAMPLE_TAG)
    assert uri.startswith(f"{SAMPLE.region}-docker.pkg.dev/{SAMPLE.project_id}/"), (
        f"이미지 주소의 리전·프로젝트가 설정에서 안 왔다: {uri}"
    )
    assert uri.endswith(f"/{SERVICE_NAME}:{SAMPLE_TAG}"), f"이미지 주소가 태그를 안 싣는다: {uri}"
    assert f"--image={uri}" in rendered, f"렌더된 인자와 이미지 주소가 갈라졌다: {rendered}"


def test_an_empty_tag_is_refused_rather_than_silently_becoming_latest() -> None:
    """② 반대편 — 태그가 비면 **거부한다**. 값을 안 묶는 대신 침묵을 묶는다.

    ⚠️ `latest`는 어느 리비전이 도는지 안 말한다. 롤백이 리비전 전환인 시스템에서
       그 침묵은 **되돌릴 대상을 모르게 만든다**(REQ-302).
    """
    with pytest.raises(ConfigError):
        image_uri(SAMPLE, "   ")


def test_no_artifact_repeats_a_value_that_config_owns() -> None:
    """③ ⛔ **이 가드의 본체다.** 산출물이 서비스명·리전·`min-instances`를 다시 적지 않는가.

    ⚠️ ②가 초록이어도 이것은 red일 수 있다. 렌더러가 옳게 내는데 셸이 플래그를 하나 더
       붙이면 **뒤에 붙은 것이 이긴다**(`gcloud`는 마지막 값을 쓴다). 그때 그 값은
       코드 어디에도 없고, 그 어긋남은 배포가 성공할 때까지 안 보인다.
    """
    region = _design_region()
    copies = [
        f"{path.name}: {token!r}"
        for path in ARTIFACTS
        for token in (SERVICE_NAME, region, "--min-instances", "--max-instances")
        if token in _read(path)
    ]
    assert not copies, (
        f"배포 산출물이 config가 소유한 값을 다시 적는다: {copies} — "
        "사본은 코드를 고쳐도 안 따라오고, 그 어긋남은 배포가 성공할 때까지 안 보인다"
    )


def test_config_declares_what_the_deployment_design_declares() -> None:
    """④ 설계 → 코드 방향. **산문이 선언한 것과 코드가 선언한 것이 갈라지는가.**

    ⚠️ `.env.example`까지 함께 묻는 이유: 리전은 config의 상수가 아니라 `WR_REGION`이다.
       견본이 설계와 다르면 **처음 채우는 사람이 다른 리전에 배포한다** — 그리고 Vertex의
       모델 가용성은 리전마다 다르다(design 10§1).
    """
    service, min_instances, max_instances = _design_service_row()
    assert (service, min_instances, max_instances) == (
        SERVICE_NAME,
        MIN_INSTANCES,
        MAX_INSTANCES,
    ), (
        f"design 10§2의 선언과 config가 어긋났다: "
        f"설계 {(service, min_instances, max_instances)} ≠ 코드 "
        f"{(SERVICE_NAME, MIN_INSTANCES, MAX_INSTANCES)}"
    )
    env_region = ENV_REGION_RE.search(_read(ENV_EXAMPLE))
    assert env_region is not None, f"{ENV_EXAMPLE.name}에 `WR_REGION` 기본값이 없다"
    assert env_region.group(1) == _design_region(), (
        f"{ENV_EXAMPLE.name}의 리전({env_region.group(1)})이 design 10§1"
        f"({_design_region()})과 다르다 — 처음 채우는 사람이 다른 리전에 배포한다"
    )


def test_the_image_python_matches_what_the_project_requires() -> None:
    """⑤ 베이스 이미지의 파이썬 ↔ `requires-python`.

    ⚠️ 어긋나면 **빌드는 성공한다.** 설치도 대개 성공한다. 갈라지는 것은 런타임 문법·
       표준 라이브러리이고, 그 실패는 첫 요청에서 난다 — 게이트에서 안 난다.
    """
    image = DOCKER_PYTHON_RE.search(_read(DOCKERFILE))
    required = REQUIRES_PYTHON_RE.search(_read(PYPROJECT))
    assert image is not None, "Dockerfile에서 베이스 파이썬 판을 못 읽었다 — `FROM` 모양이 바뀌었다"
    assert required is not None, "pyproject에서 `requires-python`을 못 읽었다"
    assert image.group(1) == required.group(1), (
        f"이미지의 파이썬({image.group(1)})이 pyproject의 요구({required.group(1)})와 다르다 — "
        "빌드는 성공하고 실패는 첫 요청에서 난다"
    )


def test_the_entrypoint_module_exists_and_the_gate_never_deploys() -> None:
    """⑥ `CMD`가 가리키는 모듈이 실재하는가 · `make deploy`가 스크립트를 부르는가 ·
    **게이트가 그것을 안 부르는가**(REQ-801).

    ⛔ `make demo`가 죽어 있던 전례가 있다(M-46) — 선언된 진입점이 죽어도 함수를 직접
       부르는 테스트는 초록이었다. 배포는 그보다 나쁘다: 아무도 안 돌리니 더 오래 죽어 있다.
    """
    module = DOCKER_CMD_MODULE_RE.search(_read(DOCKERFILE))
    assert module is not None, "Dockerfile의 `CMD`에서 모듈을 못 읽었다 — 진입점 모양이 바뀌었다"
    target = SRC / Path(*module.group(1).split(".")).with_suffix(".py")
    assert target.is_file(), (
        f"`CMD`가 없는 모듈을 가리킨다: {module.group(1)} — 컨테이너는 뜨자마자 죽는다"
    )

    recipe = _make_recipe("deploy")
    assert recipe, "Makefile에 `deploy` 레시피가 없다"
    called = str(DEPLOY_SH.relative_to(ROOT))
    assert any(called in shlex.split(line) for line in recipe), (
        f"`make deploy`가 {called}을 안 부른다: {recipe} — 두 번째 배포 경로가 생겼다"
    )
    assert "deploy" not in _check_prerequisites(), (
        f"게이트가 배포를 선행으로 건다: {_check_prerequisites()} — `make check`는 과금하면 안 된다"
    )
