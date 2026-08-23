"""의존성 선언 정합성 — **선언과 실제 임포트가 어긋나지 않는가** (T11-3).

⛔ **이 태스크가 찾은 결함**: `google-adk`가 어디에도 선언돼 있지 않았다. REQ-601은 그것을
   대회 필수로 이름하고, design 06§2는 `google-adk 2.7.1`을 실제로 설치해 introspect한
   증거까지 남겼는데, `pyproject.toml`은 그 이름을 **한 번도 적지 않았다.**
   배포 이미지는 `pip install ".[cloud]"` 한 줄로 의존성을 얻는다 — 선언에 없으면
   **이미지에 안 실린다.** 그리고 그 사실은 빌드에서도 게이트에서도 안 보인다.
   실물 호출을 처음 하는 날에 보인다.

⚠️ 반대 방향은 **묻지 않는다.** *"선언했으면 임포트해야 한다"*는 지금 이 저장소에서 거짓이다 —
   클라우드 스택 넷은 실물 어댑터가 없어서 아직 아무도 임포트하지 않는다. 그건 결함이 아니라
   순서다. 그러니 이 파일이 태우는 방향은 하나다: **임포트한 것은 선언돼 있어야 한다.**

묻는 것은 다섯이다:
  ① 스캐너가 **실제로 코드를 읽고 임포트를 분류하는가** (표본으로 태운다)
  ② 실제 서드파티 임포트마다 **선언이 있는가**
  ③ 선언한 배포판마다 **스캐너가 그 이름을 아는가** — 매핑과 선언이 함께 썩지 않게
  ④ 대회 필수 프레임워크가 **선언돼 있는가** (일치가 아니라 **값**을 묻는다)
  ⑤ 클라우드 스택이 **이미지에는 실리고 게이트에는 안 실리는가**

⚠️ ③이 ②의 되풀이가 아닌 이유: ②는 *"모르는 임포트"*를 잡지만, 매핑이 비어 가는 것은
   **못 잡는다** — 아무도 그 배포판을 아직 임포트하지 않으면 ②는 조용히 초록이다.
   ③은 선언 쪽에서 같은 자리를 본다. 새 의존성을 선언한 사람이 스캐너에게 그 이름을
   가르치지 않으면, 그 배포판은 **처음 임포트되는 날 ②에서 "선언 안 됨"으로 잡힌다.**

⚠️ ⑤가 ④의 되풀이가 아닌 이유: `google-adk`를 `[project].dependencies`로 **옮겨도** ④는
   초록이다(선언은 선언이니까). 그러면 게이트의 `.[dev]` 설치가 클라우드 스택을 끌고,
   fake 어댑터의 전제(REQ-801)가 깨진다. ⑤만 그것을 본다.

⚠️ 설치는 안 한다. 이 파일은 **선언 문서와 소스 코드만** 읽는다 — 게이트는 네트워크가 없다.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
DOCKERFILE = ROOT / "Dockerfile"
MAKEFILE = ROOT / "Makefile"

#: 훑는 곳. ⚠️ `tests`를 빼면 이 스위트가 쓰는 유일한 서드파티(`pytest`)가 안 보이고,
#: 그러면 ②는 **아무것도 안 보고** 초록이다 — 공허 통과의 가장 값싼 모양이다.
SOURCE_DIRS = (ROOT / "src", ROOT / "tools", ROOT / "tests")

#: 우리 코드의 최상위 이름. 상대 임포트는 언제나 우리 것이라 따로 안 센다.
FIRST_PARTY = ("warranty", "tools")

#: 임포트 이름 → 배포판 이름. ⛔ **둘은 같지 않다.** `import google.adk`를 하려면
#: `google-adk`를 설치해야 하고, `google`이라는 이름을 파는 배포판은 없다(네임스페이스다).
#: ⇒ 최상위 이름만 보고 판정하면 클라우드 스택 넷이 **전부 같은 것으로 보인다.**
#: ③이 이 표와 선언을 맞대므로, 새 의존성을 선언하면서 여기 안 적으면 게이트가 red다.
IMPORT_TO_DIST: dict[str, str] = {
    "google.adk": "google-adk",
    "google.cloud.bigquery": "google-cloud-bigquery",
    "google.cloud.run_v2": "google-cloud-run",
    "google.cloud.firestore": "google-cloud-firestore",
    "google.genai": "google-genai",
    "mypy": "mypy",
    "pytest": "pytest",
    "ruff": "ruff",
}

#: 대회 필수 프레임워크 (REQ-601 · design 06§1의 표). ⚠️ **값이다.**
#: 두 문서가 서로 같은지가 아니라 *"이 이름이 선언에 있는가"*를 묻는다 — M-97의 교훈이다.
MANDATORY_FRAMEWORK = "google-adk"

#: 스캐너를 태우는 표본: 소스 한 줄 → (서드파티 모듈 경로, 그 배포판).
#: ⛔ 표본이 없으면 분류가 깨져도 ②는 **0건을 잡고 초록**이다 — T11-2가 남긴 그 자리다.
CONTROL_THIRD_PARTY: tuple[tuple[str, str, str | None], ...] = (
    # 설치돼 있지만(pytest의 전이 의존) 선언은 없다 — ②가 잡아야 하는 바로 그 모양이다.
    ("import pluggy", "pluggy", None),
    ("from google.adk import agents", "google.adk", "google-adk"),
    # ⚠️ 배포판을 가르는 이름이 **뒤에** 있는 형태. `google.cloud`까지만 보면 못 푼다.
    ("from google.cloud import firestore", "google.cloud.firestore", "google-cloud-firestore"),
)

#: 서드파티가 **아닌** 표본. 하나라도 서드파티로 잡히면 ②는 거짓 red를 낸다.
CONTROL_NOT_THIRD_PARTY: tuple[str, ...] = (
    "import os",
    "from __future__ import annotations",
    "from warranty.config import Settings",
    "from tools import spec_trace",
    "from . import sibling",
)

#: 공허 통과 방지의 바닥. 하나라도 0이 되면 아래 검사는 아무것도 안 보고 초록이다.
MIN_SOURCE_FILES = 25
MIN_DECLARED = 5

#: `"google-adk>=2.7"` → `google-adk`. 뒤의 버전·마커·extra는 배포판 이름이 아니다.
DIST_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+")

#: `pip install ... ".[cloud]"` 에서 extra 이름을 읽는다. Dockerfile과 Makefile **둘 다**
#: 같은 모양이라 파서도 하나다 — 두 벌 두면 인정 규칙이 갈라진다(PRINCIPLES #10).
INSTALL_EXTRAS_RE = re.compile(r"pip install[^\n]*\.\[([A-Za-z0-9_,-]+)\]")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _pyproject() -> dict[str, Any]:
    data: dict[str, Any] = tomllib.loads(_read(PYPROJECT))
    return data


def _dist_name(requirement: str) -> str:
    """요구사항 문자열에서 배포판 이름만. PEP 503대로 정규화한다(`_` → `-`, 소문자)."""
    match = DIST_NAME_RE.match(requirement.strip())
    if match is None:
        raise AssertionError(f"의존성 선언에서 배포판 이름을 못 읽었다: {requirement!r}")
    return match.group(0).lower().replace("_", "-")


def _declared_groups() -> dict[str, frozenset[str]]:
    """`{그룹: {배포판, ...}}`. 그룹은 `runtime`(=`[project].dependencies`) + 각 extra."""
    project = _pyproject().get("project", {})
    groups = {"runtime": frozenset(_dist_name(r) for r in project.get("dependencies", []))}
    for extra, requirements in project.get("optional-dependencies", {}).items():
        groups[extra] = frozenset(_dist_name(r) for r in requirements)
    return groups


def _declared() -> frozenset[str]:
    """선언된 배포판 전부 — 어느 그룹인지는 안 따진다(⑤가 따진다)."""
    return frozenset().union(*_declared_groups().values())


def _installed_extras(path: Path) -> frozenset[str]:
    """그 파일의 설치 줄이 켜는 extra 이름들.

    ⚠️ 못 읽으면 예외다. 0개를 읽고 *"클라우드 스택이 이미지에 없다"*를 조용히 통과시키는
       것보다 낫다 — 실제로 그때가 이미지에서 ADK가 빠지는 순간이다.
    """
    match = INSTALL_EXTRAS_RE.search(_read(path))
    if match is None:
        raise AssertionError(
            f'{path.name}에서 `pip install ".[<extra>]"` 줄을 못 찾았다 — '
            "설치가 extra 없이 도는 중이거나 형태가 바뀌었다"
        )
    return frozenset(name.strip() for name in match.group(1).split(","))


def _dists_of(extras: frozenset[str]) -> frozenset[str]:
    groups = _declared_groups()
    return frozenset().union(*(groups.get(extra, frozenset()) for extra in extras)) or frozenset()


def _is_stdlib(module: str) -> bool:
    return module.split(".", 1)[0] in sys.stdlib_module_names


def _is_first_party(module: str) -> bool:
    return module.split(".", 1)[0] in FIRST_PARTY


def _distribution_of(module: str) -> str | None:
    """모듈 경로 → 배포판. **가장 긴 접두사가 이긴다** (`google.cloud.bigquery` ≠ `google`)."""
    parts = module.split(".")
    for cut in range(len(parts), 0, -1):
        dist = IMPORT_TO_DIST.get(".".join(parts[:cut]))
        if dist is not None:
            return dist
    return None


def _third_party_imports(source: str, filename: str) -> set[str]:
    """한 소스가 임포트하는 **서드파티 모듈 경로**들."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Import):
            candidates = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module:
                continue  # 상대 임포트 — 언제나 우리 코드다
            # `from google.cloud import firestore`: 배포판을 가르는 이름이 **뒤에** 있다.
            # ⚠️ 모듈 경로만으로 풀리면 거기서 멈춘다 — 더 깊이 가면 같은 배포판을
            #    `google.adk.agents` 같은 긴 이름으로 부르게 되고, 이름이 둘이 된다.
            if _distribution_of(node.module):
                candidates = [node.module]
            else:
                deeper = [f"{node.module}.{alias.name}" for alias in node.names]
                candidates = [name for name in deeper if _distribution_of(name)] or [node.module]
        else:
            continue
        found.update(
            name for name in candidates if not _is_stdlib(name) and not _is_first_party(name)
        )
    return found


def _source_files() -> tuple[Path, ...]:
    return tuple(path for directory in SOURCE_DIRS for path in sorted(directory.rglob("*.py")))


def _imports_by_file() -> dict[str, set[str]]:
    return {
        str(path.relative_to(ROOT)): _third_party_imports(_read(path), str(path))
        for path in _source_files()
    }


def test_the_scanner_reads_real_code_and_actually_classifies_imports() -> None:
    """① 공허 통과 방지 — 분류가 깨지면 ②는 **0건을 잡고** 초록이다.

    ⚠️ 표본을 두는 이유는 매핑의 길이가 스캐너의 능력이 아니기 때문이다. 일곱 항목이
       그대로 있어도 stdlib 판정이 한 줄 어긋나면 잡는 것은 0건이고, 그 초록은
       *"선언이 다 있다"*가 아니라 **"아무것도 안 봤다"**이다.
    """
    files = _source_files()
    assert len(files) >= MIN_SOURCE_FILES, (
        f"소스를 {len(files)}개만 훑었다 (최소 {MIN_SOURCE_FILES}) — 스캔 경로가 틀렸다"
    )
    assert len(_declared()) >= MIN_DECLARED, (
        f"선언을 {len(_declared())}개만 읽었다 (최소 {MIN_DECLARED}) — pyproject 파서가 깨졌다"
    )

    for source, expected_module, expected_dist in CONTROL_THIRD_PARTY:
        found = _third_party_imports(source, "<표본>")
        assert found == {expected_module}, (
            f"표본을 잘못 분류했다: {source!r} → {sorted(found)} (기대 {expected_module!r}) — "
            "이러면 ②는 늘 초록이다"
        )
        assert _distribution_of(expected_module) == expected_dist, (
            f"{expected_module!r}의 배포판을 {_distribution_of(expected_module)!r}로 풀었다 "
            f"(기대 {expected_dist!r})"
        )
    for source in CONTROL_NOT_THIRD_PARTY:
        found = _third_party_imports(source, "<표본>")
        assert not found, f"서드파티가 아닌 표본을 서드파티로 잡았다: {source!r} → {sorted(found)}"

    scanned = {module for modules in _imports_by_file().values() for module in modules}
    assert "pytest" in scanned, (
        f"실제 소스에서 `pytest` 임포트를 못 찾았다 (잡은 것: {sorted(scanned)}) — "
        "이 스위트가 쓰는 유일한 서드파티다. 못 찾았다면 훑은 것이 코드가 아니다"
    )


def test_every_third_party_import_is_declared() -> None:
    """② ⛔ **이 가드의 본체다.** 임포트한 서드파티마다 선언이 있는가.

    ⚠️ 설치돼 있다는 것은 선언돼 있다는 뜻이 아니다. `pluggy`·`packaging`·`pathspec`은
       지금 이 `.venv`에 있지만 우리가 선언한 적은 없다 — 전이 의존일 뿐이다. 그걸 임포트하면
       **이 기계에서만 도는 코드**가 되고, 배포 이미지는 `.[cloud]`만 설치하므로 거기서 죽는다.
       그 죽음은 빌드가 아니라 첫 요청에서 보인다.
    """
    declared = _declared()
    undeclared = sorted(
        f"{path}: {module}"
        for path, modules in _imports_by_file().items()
        for module in sorted(modules)
        if (_distribution_of(module) or "") not in declared
    )
    assert not undeclared, (
        f"선언 없이 임포트하는 자리: {undeclared} — "
        "설치돼 있어서 지금 도는 것이지 선언돼 있어서 도는 것이 아니다"
    )


def test_every_declared_distribution_is_known_to_the_scanner() -> None:
    """③ 선언한 배포판마다 스캐너가 그 이름을 아는가 — **매핑과 선언은 따로 썩는다.**

    ⚠️ ②의 되풀이가 아니다. 아직 아무도 임포트하지 않는 배포판(클라우드 스택 넷이 그렇다)에
       대해 ②는 **아무 말도 안 한다.** 매핑이 그 이름을 모르는 채로 남아 있다가, 실물 어댑터를
       쓰는 첫 커밋에서 *"선언 안 된 임포트"*로 잡힌다 — 선언은 그때도 멀쩡히 있는데.
    """
    declared = set(_declared())
    mapped = set(IMPORT_TO_DIST.values())
    assert mapped == declared, (
        f"매핑과 선언이 어긋난다: 매핑에만 {sorted(mapped - declared)} · "
        f"선언에만 {sorted(declared - mapped)} — "
        "선언에만 있는 것은 **임포트되는 날 거짓 red를 낸다**"
    )


def test_the_mandatory_agent_framework_is_declared() -> None:
    """④ 대회 필수 프레임워크가 선언돼 있는가 — **값으로** 묻는다.

    ⛔ T11-3 이전의 상태가 정확히 이 검사의 red다: REQ-601이 ADK를 필수로 이름하고
       design 06§2가 실물 introspect 증거까지 남겼는데 `pyproject.toml`에는 없었다.
       두 문서는 서로 완벽히 일치했다 — **일치는 그것이 설치된다는 뜻이 아니다.**
    ⚠️ `Verifies:`를 안 붙인다. REQ-601의 수용 기준은 **실물 호출**이고(requirements.md),
       이 열은 *"선언이 있는가"*만 태운다. 붙이면 다음 사람이 증명하지 않은 것을 근거로
       상태를 올린다 — T11-1이 REQ-602에 대해 내린 것과 같은 판단이다.
    """
    declared = _declared()
    assert MANDATORY_FRAMEWORK in declared, (
        f"{MANDATORY_FRAMEWORK!r}가 선언에 없다 (선언된 것: {sorted(declared)}) — "
        "REQ-601은 이것을 대회 필수로 이름한다. 선언에 없으면 이미지에 안 실린다"
    )


def test_the_cloud_stack_ships_in_the_image_and_stays_out_of_the_gate() -> None:
    """⑤ 클라우드 스택이 **이미지에는 실리고 게이트에는 안 실리는가**.

    ⚠️ ④의 되풀이가 아니다. `google-adk`를 `[project].dependencies`로 **옮겨도** ④는 초록이다 —
       선언은 선언이니까. 그러면 게이트의 `.[dev]` 설치가 클라우드 스택을 끌고 오고,
       fake 어댑터의 전제(REQ-801: 게이트는 이것들 **없이** 통과한다)가 조용히 깨진다.
    ⚠️ extra 이름을 여기 안 적는다 — `Dockerfile`과 `Makefile`의 설치 줄에서 읽는다.
       적으면 그 줄이 바뀌어도 이 검사는 옛 이름을 지키는 두 번째 사본이 된다.
    """
    image_extras = _installed_extras(DOCKERFILE)
    gate_extras = _installed_extras(MAKEFILE)
    assert not (image_extras & gate_extras), (
        f"이미지와 게이트가 같은 extra를 설치한다: {sorted(image_extras & gate_extras)} — "
        "그러면 게이트는 클라우드 스택 위에서 도는 것이고 fake 어댑터는 무의미하다"
    )

    groups = _declared_groups()
    #: 클라우드 스택 = 매핑이 `google.*` 아래로 아는 배포판. **두 번째 목록을 안 만든다.**
    cloud_stack = {dist for module, dist in IMPORT_TO_DIST.items() if module.startswith("google.")}
    gate_installed = groups["runtime"] | _dists_of(gate_extras)
    image_installed = _dists_of(image_extras)

    missing = sorted(cloud_stack - image_installed)
    assert not missing, (
        f"이미지가 설치하는 extra({sorted(image_extras)})에 없는 클라우드 스택: {missing} — "
        "빌드는 통과하고 첫 실물 호출에서 죽는다"
    )
    leaked = sorted(cloud_stack & gate_installed)
    assert not leaked, (
        f"게이트가 설치하는 집합에 클라우드 스택이 있다: {leaked} — "
        "REQ-801은 게이트가 이것들 **없이** 통과한다고 말한다"
    )
