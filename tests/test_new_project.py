"""신규 프로젝트 — **기존 코드를 편입하지 않았는가** (T5-3 · REQ-902).

Spec: specs/warranty/requirements.md REQ-902
      specs/warranty/design/10-deployment.md §8

⛔ **이 파일이 생긴 이유**: REQ-902는 08-29에 사람이 손으로 걸어 **참인 것을 확인했다**
   (T8-4 — 첫 커밋 08-19, 사설 소스 0건, `vendor/` 없음). 그런데 상태 칸은 `TODO`였다.
   겨냥한 테스트가 하나도 없었기 때문이다.
   ⇒ 손으로 한 번 본 것은 **다음 주에 안 본다.** 집행하는 자리가 있어야 상태를 올린다(§9).

⚠️ **git 이력을 묻지 않는다.** *"제출 기간 중 작성됐다"*의 가장 곧은 증거는 커밋 날짜지만,
   테스트가 `git log`를 읽으면 shallow clone·아카이브 tarball·squash에서 **참인데 red**가
   된다. 그건 요구사항이 아니라 체크아웃 방식을 태우는 것이다.
   ⇒ 여기서 태우는 것은 **저장소 안에서 확인 가능한 절반**이다: *편입한 코드가 있는가.*
   날짜 절반은 커밋 이력과 `docs/PROGRESS_LOG.md`가 갖는다 — 그래서 이 요구사항의
   `VERIFIED`는 *"편입 없음이 집행된다"*까지이고, 그 이상을 주장하지 않는다.

묻는 것은 둘이다 — 규범 문단이 약속한 문장이 둘이기 때문이다:
  ① 선언이 **사설·로컬 출처**에서 코드를 끌어오지 않는가 (`git+`·`file://`·사설 인덱스)
  ② 저장소가 **베끼어 심은 소스 트리**를 싣고 있지 않는가 (`vendor/`·`third_party/` 등)

⚠️ ②가 ①의 되풀이가 아닌 이유: 편입의 가장 흔한 모양은 선언이 아니라 **복사**다.
   `pip`을 거치지 않고 디렉터리째 붙여 넣으면 ①은 영원히 초록이다.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"

#: 선언 하나가 **원격 저장소·로컬 경로에서 코드를 끌어오는** 표지.
#: ⚠️ 이름이 아니라 **출처**를 본다 — 공개 PyPI 이름은 몇 개든 편입이 아니다.
FOREIGN_SOURCE_MARKERS = ("git+", "file://", "hg+", "svn+", "bzr+", "@ http", "@ git")

#: 설치를 **다른 인덱스로 돌리는** 표지. 사설 인덱스는 이 저장소 밖의 코드를 뜻한다.
FOREIGN_INDEX_MARKERS = ("--index-url", "--extra-index-url", "--find-links")

#: 베끼어 심은 소스 트리의 관용적 이름.
VENDORED_DIR_NAMES = ("vendor", "vendored", "third_party", "thirdparty", "external", "_vendor")

#: ②가 **실제로 저장소를 걸었다**고 인정하는 바닥. ⚠️ 숨김 필터가 넓어지면 0을 훑고
#: 초록이 된다 — 그 초록은 "편입이 없다"가 아니라 "아무것도 안 봤다"이다.
MIN_WALKED_DIRECTORIES = 8


def _declared_requirements() -> tuple[str, ...]:
    """`pyproject.toml`이 적은 의존성 문자열 전부 — 기본과 추가분을 **함께** 본다.

    ⚠️ 추가분(`optional-dependencies`)을 빼고 세면 `[cloud]`에 심은 편입을 못 본다.
    배포 이미지가 설치하는 것이 정확히 그쪽이다.
    """
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = data.get("project", {})
    declared: list[str] = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        declared.extend(group)
    return tuple(declared)


def test_req_902_no_dependency_is_pulled_from_a_private_or_local_source() -> None:
    """① 선언이 **공개 배포판 이름만** 적는가.

    Verifies: REQ-902

    ⛔ `git+https://…`·`file://…` 한 줄이면 이 저장소는 **다른 저장소의 코드로 돈다.**
       그 순간 *"제출 기간 중 새로 작성됐다"*는 이 저장소만 봐서는 확인할 수 없는 문장이 된다.
    """
    declared = _declared_requirements()
    assert declared, (
        "`pyproject.toml`에서 의존성을 하나도 못 읽었다 — 선언이 지워졌거나 파서가 깨졌다. "
        "0개를 훑는 초록은 *'편입이 없다'*가 아니라 **'아무것도 안 봤다'**이다."
    )
    foreign = sorted(
        requirement
        for requirement in declared
        if any(marker in requirement for marker in FOREIGN_SOURCE_MARKERS)
    )
    assert not foreign, (
        f"선언이 저장소 밖 출처에서 코드를 끌어온다: {foreign}. "
        "REQ-902는 기존 코드를 편입하지 않는다고 말한다 — 공개 배포판 이름만 적는다."
    )

    raw = PYPROJECT.read_text(encoding="utf-8")
    indexes = sorted(marker for marker in FOREIGN_INDEX_MARKERS if marker in raw)
    assert not indexes, (
        f"`pyproject.toml`이 설치를 다른 인덱스로 돌린다: {indexes}. "
        "사설 인덱스는 이 저장소 밖의 코드를 뜻하고, 심사자는 그것을 재현할 수 없다."
    )


def _repo_directories() -> tuple[Path, ...]:
    """이 저장소가 **스스로 소유한** 디렉터리들. 숨김 경로는 걷지 않는다.

    ⛔ `.venv`·`.venv-live`·`.git`은 저장소의 산출물이 아니라 **도구의 것**이다. 걸으면
       설치된 서드파티 안의 `licenses/vendor` 같은 이름이 잡혀 *"편입했다"*로 읽힌다 —
       실제로 첫 판에서 그렇게 red가 났다. 숨김 성분 하나로 셋을 함께 자른다.
    """
    return tuple(
        path
        for path in ROOT.rglob("*")
        if path.is_dir()
        and not any(part.startswith(".") for part in path.relative_to(ROOT).parts)
        and "__pycache__" not in path.parts
    )


def test_req_902_no_vendored_source_tree_is_carried_in_the_repo() -> None:
    """② 베끼어 심은 소스 트리가 **없는가**.

    Verifies: REQ-902

    ⛔ 편입의 가장 흔한 모양은 선언이 아니라 **복사**다. `pip`을 거치지 않으므로 ①은
       영원히 초록이고, 그 코드는 제출 기간 밖에서 왔는데 저장소는 아무 말도 하지 않는다.
    """
    walked = _repo_directories()
    # ⚠️ **스캐너를 먼저 태운다.** 0개를 훑는 초록은 *'편입이 없다'*가 아니라
    #    **'아무것도 안 봤다'**이다 — 숨김 필터가 너무 넓어지면 정확히 그 모양이 된다.
    assert len(walked) >= MIN_WALKED_DIRECTORIES, (
        f"저장소 디렉터리를 {len(walked)}개만 걸었다 — 필터가 너무 넓다. "
        "이 상태의 초록은 판정이 아니다."
    )
    found = sorted(
        str(path.relative_to(ROOT))
        for path in walked
        if path.name in VENDORED_DIR_NAMES
    )
    assert not found, (
        f"베끼어 심은 소스 트리가 있다: {found}. "
        "REQ-902는 기존 코드를 편입하지 않는다고 말한다 — 의존성은 선언으로 얻는다."
    )
