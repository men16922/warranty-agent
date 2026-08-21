"""REQ-804 — 대기·창 길이가 **한 모듈**에 있는지 집행한다.

⚠️ *"상수는 한 곳에 둔다"*는 관례로는 안 지켜진다. 실제로 깨지는 순서는 늘 같다 —
영상 재촬영 전에 타이머를 줄이고, **호출부 하나에 박아 둔 숫자를 못 본다.**
그 파일은 예전 값으로 계속 돌고 게이트는 초록이다.

그래서 세 가지를 묻는다 (design 11§5):
  ① `warranty.tunables` **밖에** 대기·창 모양의 모듈 상수가 정의돼 있지 않은가
  ② 대기·창을 받는 자리(`sleep(...)`·`window_s=`)에 **숫자 리터럴**이 박혀 있지 않은가
  ③ design 11§5가 **선언한 이름 집합**과 그 모듈이 정의한 집합이 같은가

⚠️ 스캔 범위는 `src/warranty/`뿐이다. 테스트는 자기 픽스처로 창 길이를 정할 수 있어야
   한다 — 그건 산재가 아니라 **그 테스트가 무엇을 재는지**의 일부다. 프로덕션 코드가
   재촬영 때 놓치는 자리이지, 픽스처가 아니다.

⚠️ ③이 값이 아니라 **이름**을 묻는 이유: design 11§2가 *"타이머를 영상 길이에 맞춘다"*고
   말한다. 값까지 묶으면 조정할 때마다 가드가 red고, 그런 가드는 결국 꺼진다.
   집행할 수 있는 것은 *"어떤 손잡이가 있는가"*이지 *"손잡이가 몇 도인가"*가 아니다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "warranty"
TUNABLES = SRC / "tunables.py"
DESIGN = ROOT / "specs" / "warranty" / "design" / "11-demo.md"

#: design 11§5의 상수 블록을 여는 표제. ⚠️ 표제가 바뀌면 파서가 **못 찾고 예외를 낸다** —
#: 조용히 0개를 읽고 아래 검사를 공허하게 통과시키는 것보다 낫다.
DESIGN_SECTION = "## 5. 상수 (REQ-804)"

#: 대기·창 모양의 이름. ⚠️ 값이 아니라 **이름 모양**으로 잡는다 — 45라는 숫자를 쫓으면
#: 관계없는 45까지 잡히고, 타이머를 60으로 바꾸는 순간 가드가 눈이 먼다.
TUNABLE_NAME_RE = re.compile(
    r"(^|_)(DELAY|WINDOW|TIMEOUT|INTERVAL|WAIT|WARMUP|BACKOFF|COOLDOWN|BUDGET)(_|$)|_S$"
)

#: 대기·창이 **값으로 들어가는** 자리. 여기에 리터럴이 오면 그 숫자는 tunables 밖에 산다.
#: ⚠️ 아래 두 헬퍼가 **이 이름을 쓴다** — 산문으로만 적어 두면 코드와 갈라진다.
SLEEP_METHOD = "sleep"
WINDOW_KWARG = "window_s"

#: 공허 통과 방지 — 스캐너가 아무것도 못 읽고 초록을 내는 것을 막는다.
MIN_SCANNED_FILES = 8
MIN_TUNABLES = 4


def _source_files() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if p != TUNABLES)


def _module_constants(path: Path) -> dict[str, int]:
    """모듈 **최상위**에 대입된 대문자 이름 → 줄 번호.

    ⚠️ 임포트는 대상이 아니다. `from warranty.tunables import VERIFY_DELAY_S`는
       산재가 아니라 **가리키기**다 — 값이 하나뿐이라는 사실을 안 깬다.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, int] = {}
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                found[target.id] = node.lineno
    return found


def _literal_sinks(path: Path) -> list[str]:
    """`x.sleep(3)` · `window_s=120` 처럼 **박힌 숫자**를 찾는다."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == SLEEP_METHOD:
            hits += [
                f"{path.name}:{arg.lineno} {SLEEP_METHOD}({arg.value!r})"
                for arg in node.args
                if isinstance(arg, ast.Constant)
            ]
        hits += [
            f"{path.name}:{kw.value.lineno} {kw.arg}={kw.value.value!r}"
            for kw in node.keywords
            if kw.arg == WINDOW_KWARG and isinstance(kw.value, ast.Constant)
        ]
    return hits


def _sink_call_sites(path: Path) -> int:
    """가드가 하중을 받는 자리의 수. **0이면 위 검사는 아무것도 안 물은 것이다.**"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    sites = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == SLEEP_METHOD:
                sites += 1
            sites += sum(1 for kw in node.keywords if kw.arg == WINDOW_KWARG)
    return sites


def _design_declared_names() -> set[str]:
    """design 11§5의 ```python 블록이 **선언한 이름 집합**."""
    text = DESIGN.read_text(encoding="utf-8")
    start = text.find(DESIGN_SECTION)
    if start < 0:
        raise AssertionError(f"design 11의 상수 절을 못 찾았다: {DESIGN_SECTION!r}")
    match = re.search(r"```python\n(.*?)```", text[start:], re.DOTALL)
    if match is None:
        raise AssertionError("design 11§5에 상수 블록(```python)이 없다")
    block = ast.parse(match.group(1))
    return {
        target.id
        for node in block.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }


@pytest.fixture(scope="module")
def scanned() -> list[Path]:
    return _source_files()


def test_req_804_the_scanner_actually_reads_the_source_tree(scanned: list[Path]) -> None:
    """Verifies: REQ-804

    공허 통과 방지 — 경로가 틀리면 아래 검사가 **0개를 훑고 전부 초록**이다.
    실제로 이 저장소가 이름을 바꿨을 때 변이 하네스가 같은 방식으로 틀렸다(#8).
    """
    assert len(scanned) >= MIN_SCANNED_FILES, (
        f"src/warranty에서 파이썬 파일을 {len(scanned)}개만 읽었다 — 스캔 경로가 틀렸다"
    )
    assert TUNABLES.exists(), "대기·창 상수가 사는 모듈이 없다"
    assert sum(_sink_call_sites(path) for path in scanned) >= 2, (
        "대기·창을 값으로 받는 자리를 하나도 못 찾았다 — 리터럴 검사가 공허하다"
    )


def test_req_804_wait_and_window_constants_live_in_one_module(scanned: list[Path]) -> None:
    """Verifies: REQ-206, REQ-804

    ① ⚠️ 한 곳에 **있는 것**만으로는 부족하다. 다른 곳에 **없어야** 한다 —
    재촬영 때 놓치는 것은 새로 생긴 두 번째 자리다.
    """
    defined = {name for name in _module_constants(TUNABLES) if TUNABLE_NAME_RE.search(name)}
    assert len(defined) >= MIN_TUNABLES, (
        f"{TUNABLES.name}이 대기·창 상수를 {len(defined)}개만 갖는다 — 이름 규칙이 어긋났다"
    )
    scattered = [
        f"{path.relative_to(ROOT)}:{line} {name}"
        for path in scanned
        for name, line in _module_constants(path).items()
        if TUNABLE_NAME_RE.search(name)
    ]
    assert not scattered, (
        f"대기·창 상수가 {TUNABLES.name} 밖에 있다: {scattered} — "
        "재촬영 때 한쪽만 바뀌고 그 어긋남은 조용하다"
    )


def test_req_804_no_wait_or_window_literal_is_hardcoded_at_a_call_site(
    scanned: list[Path],
) -> None:
    """Verifies: REQ-206, REQ-804

    ② ⚠️ 상수를 모아 놓고도 **호출부에 숫자를 박으면** 모아 둔 의미가 없다.
    `clock.sleep(45)`는 tunables를 고쳐도 안 바뀐다 — 그리고 그건 안 보인다.
    """
    hardcoded = [hit for path in scanned for hit in _literal_sinks(path)]
    assert not hardcoded, f"대기·창 자리에 숫자가 박혀 있다: {hardcoded} — 이름으로 가리켜야 한다"


def test_req_804_the_module_defines_exactly_what_the_design_declares() -> None:
    """Verifies: REQ-804

    ③ 설계 → 코드 방향. ⚠️ G6④와 같은 계열의 질문이다 — 산문이 손잡이 넷을 선언하는데
    코드에 셋만 있으면, **없는 손잡이를 돌리려던 사람이 촬영 당일에 안다.**
    """
    declared = _design_declared_names()
    defined = set(_module_constants(TUNABLES))
    assert declared, "design 11§5가 이름을 하나도 선언하지 않았다 — 파서가 깨졌다"
    assert declared == defined, (
        f"design 11§5의 선언과 {TUNABLES.name}이 어긋났다: "
        f"설계에만 {sorted(declared - defined)} · 코드에만 {sorted(defined - declared)}"
    )
