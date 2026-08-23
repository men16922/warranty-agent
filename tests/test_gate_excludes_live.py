"""게이트가 라이브 테스트를 **안 돈다** — 마커 배제의 집행 (T12-10 · REQ-801).

Spec: specs/warranty/design/09-quality-gate.md §1 (REQ-801)

⛔ **주장만 있고 집행이 없던 자리다.** `pyproject.toml`의 `live` 마커 설명은
   *"게이트에 포함되지 않는다"*고 **말한다.** 그런데 `addopts`에 `-m "not live"`가 없었다 ⇒
   라이브 테스트를 하나라도 만드는 순간 `make check`가 그것을 **돌리고 과금한다.**
   지금까지 무해했던 이유는 라이브 테스트가 **하나도 없어서**일 뿐이다 — 부재는 집행이 아니다.
   ⚠️ REQ-601 승격이 여기 막혀 있었다: 실물 호출은 증거가 있는데(`docs/evidence/`)
   그것을 재현하는 라이브 테스트를 **넣을 수가 없었다.**

⛔ **배제를 넣으면 반대쪽이 조용히 깨질 수 있다.** `addopts`가 `-m "not live"`를 들고 있으면
   `make live-check`의 `-m live`는 **두 번째 `-m`**이다. *나중 것이 이긴다*는 것은 pytest의
   **동작**이지 우리가 적은 문장이 아니다 — 틀리면 `make live-check`는 **0건을 돌고 초록**이고,
   그 초록은 *"라이브가 전부 통과했다"*와 **같은 얼굴**을 한다. ⇒ 문자열이 아니라 값으로 태운다.

묻는 것은 넷이다:
  ① 두 실행이 **실제로 무언가를 돌렸는가** (바닥)
  ② 게이트 설정으로 돌린 표본에서 라이브가 **안 돌았는가**
  ③ `make live-check`의 선택으로 돌리면 **반대로** 라이브만 도는가
  ④ 게이트 타깃이 그 배제를 **덮어쓰지 않는가** — `test`가 자기 `-m`을 들지 않고,
     `check`의 선행에 `live-check`가 없다

⚠️ ②와 ③은 서로의 바닥이다. ②의 초록만으로는 *"배제됐다"*와 *"그 표본은 원래 안 도는
   것이었다"*를 못 가른다 — ③에서 **같은 표본이 실제로 돌아 흔적을 남기는 것**이 그 답이다.
   반대로 ③의 초록만으로는 게이트가 그것을 안 돈다는 말을 못 한다. 그래서 둘 다 있다.

⚠️ **라이브 테스트는 만들지 않는다**(과금한다). 표본은 `tmp_path`에 쓰고 거기서만 돈다 —
   이 저장소의 스위트에는 `live` 마커가 붙은 테스트가 **하나도 없다.**
⚠️ **pytest 출력을 파싱하지 않는다.** 요약 줄의 모양은 `-q`가 겹치면 바뀐다(하네스가 실제로
   그것으로 한 번 죽었다 — mutations.md 「하네스가 다섯 번 틀렸다」). 대신 표본이 **파일을
   남기게** 하고 그 파일의 존재로 판정한다 — *"돌았는가"*의 가장 덜 깨지는 관측 지점이다.
⚠️ **하위 프로세스 둘은 값이 아니라 비용이다** — 스위트가 ~0.8s에서 ~1.8s가 되고 스윕은
   그만큼 길어진다. 한 번으로 못 줄인다: ②와 ③은 **서로 다른 선택**을 묻는 질문이다.
   ①·④는 프로세스 없이 답한다.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
MAKEFILE = ROOT / "Makefile"

#: 라이브 마커의 이름. ⚠️ **값이다** — 선언과 배제가 서로 같은지가 아니라 *"이 이름이
#: 배제되는가"*를 묻는다. 일곱 곳을 함께 낮춰도 일치 검사는 초록이라는 것이 M-97·M-182다.
LIVE_MARKER = "live"

#: Makefile에서 읽는 타깃 셋. 게이트가 도는 자리(`test`)와 그 반대(`live-check`),
#: 그리고 둘을 묶는 자리(`check`).
GATE_TEST_TARGET = "test"
LIVE_TARGET = "live-check"
GATE_TARGET = "check"

#: 표본이 흔적을 남기는 곳. 파일 이름이 곧 *"어느 테스트가 돌았는가"*다.
RAN_DIR = "ran"
OFFLINE_TRACE = "offline"

#: 표본 스위트. ⚠️ **아무것도 부르지 않는다** — 남기는 것은 파일 하나뿐이고, 그 파일의
#: 존재가 *"이 테스트가 돌았다"*의 유일한 관측 지점이다(위의 ⚠️ 참조).
SAMPLE_TESTS = f'''\
"""tmp_path 위의 표본. 게이트의 스위트가 아니다 — `-m` 선택을 값으로 태우기 위한 하중이다."""

import pathlib

import pytest

RAN = pathlib.Path(__file__).resolve().parent / "{RAN_DIR}"


def test_offline_sample() -> None:
    (RAN / "{OFFLINE_TRACE}").write_text("ran", encoding="utf-8")


@pytest.mark.{LIVE_MARKER}
def test_live_sample() -> None:
    (RAN / "{LIVE_MARKER}").write_text("ran", encoding="utf-8")
'''

#: `<target>:` 줄과 **탭으로 들여쓴 레시피**를 한 덩어리로. 주석은 레시피가 아니다.
TARGET_RE = "^{target}:(?P<prereq>[^\n]*)\n(?P<body>(?:\t[^\n]*\n)*)"


@dataclass(frozen=True)
class RunResult:
    """표본 한 판의 결과. **`ran`이 판정이고 나머지는 실패 메시지용이다.**"""

    ran: frozenset[str]
    returncode: int
    output: str
    argv: tuple[str, ...]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _ini_options() -> dict[str, Any]:
    data: dict[str, Any] = tomllib.loads(_read(PYPROJECT))["tool"]["pytest"]["ini_options"]
    return data


def _gate_addopts() -> list[str]:
    """게이트가 **말없이** 붙이는 인자들. `make check`의 `pytest`가 실제로 받는 것이다."""
    return shlex.split(str(_ini_options().get("addopts", "")))


def _declared_markers() -> list[str]:
    """`markers` 선언 줄 전부. 표본 ini에 **그대로** 옮긴다 — `--strict-markers`가 같게 굴게."""
    return [str(entry) for entry in _ini_options().get("markers", [])]


def _recipe(target: str) -> tuple[str, list[str]]:
    """`(선행 조건 줄, 레시피 줄들)`.

    ⚠️ 못 찾으면 예외다. 0줄을 읽고 *"`-m`이 없다"*를 조용히 통과시키는 것보다 낫다 —
       그때가 정확히 게이트가 라이브를 돌기 시작하는 순간이다.
    """
    match = re.search(TARGET_RE.format(target=re.escape(target)), _read(MAKEFILE), re.MULTILINE)
    if match is None:
        raise AssertionError(
            f"{MAKEFILE.name}에서 `{target}:` 타깃을 못 찾았다 — 이름이 바뀌었거나 지워졌다"
        )
    return match.group("prereq"), match.group("body").splitlines()


def _marker_selection(recipe: list[str]) -> list[str]:
    """레시피가 **명령줄로** 주는 `-m <식>`. 없으면 빈 목록.

    ⚠️ `addopts`의 `-m`과 다른 자리다. 명령줄이 나중에 붙으므로 여기 있는 것이 이긴다 —
       그 사실을 문장으로 믿지 않고 ③이 실제로 돌려서 확인한다.
    """
    out: list[str] = []
    for line in recipe:
        tokens = shlex.split(line)
        for index, token in enumerate(tokens):
            if token == "-m" and index + 1 < len(tokens):
                out += ["-m", tokens[index + 1]]
    return out


def _sample_ini() -> str:
    markers = "".join(f"\n    {entry}" for entry in _declared_markers())
    return f"[pytest]\naddopts = {shlex.join(_gate_addopts())}\nmarkers ={markers}\n"


def _run_sample(directory: Path, extra: list[str]) -> RunResult:
    """게이트와 **같은 설정**으로 표본을 돌린다. `extra`는 명령줄에 덧붙는 인자다."""
    (directory / RAN_DIR).mkdir(exist_ok=True)
    (directory / "pytest.ini").write_text(_sample_ini(), encoding="utf-8")
    (directory / "test_sample.py").write_text(SAMPLE_TESTS, encoding="utf-8")
    argv = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *extra]
    proc = subprocess.run(argv, cwd=directory, capture_output=True, text=True, check=False)
    return RunResult(
        ran=frozenset(path.name for path in (directory / RAN_DIR).iterdir()),
        returncode=proc.returncode,
        output=(proc.stdout + proc.stderr)[-600:],
        argv=tuple(argv[1:]),
    )


@pytest.fixture(scope="module")
def gate_run(tmp_path_factory: pytest.TempPathFactory) -> RunResult:
    """게이트가 돌리는 그대로 — 명령줄 인자 없음(`make test`의 `$(PYTEST)`)."""
    return _run_sample(tmp_path_factory.mktemp("gate"), extra=[])


@pytest.fixture(scope="module")
def live_check_run(tmp_path_factory: pytest.TempPathFactory) -> RunResult:
    """`make live-check`가 돌리는 그대로 — 선택은 **Makefile에서 읽는다**(두 번째 사본 금지)."""
    _, recipe = _recipe(LIVE_TARGET)
    return _run_sample(tmp_path_factory.mktemp("live"), extra=_marker_selection(recipe))


def test_both_sample_runs_actually_ran_something(
    gate_run: RunResult, live_check_run: RunResult
) -> None:
    """① 바닥 — *"라이브가 안 돌았다"*와 *"아무것도 안 돌았다"*는 **같은 얼굴**을 한다.

    ⚠️ 표본이 통째로 안 도는 이유는 여럿이다(ini 형태가 깨졌다 · 수집 경로가 틀렸다 ·
       마커 선언이 사라져 `--strict-markers`가 죽었다). 그 전부가 ②를 **조용히 초록**으로
       만든다 — 이 저장소가 M-03·M-25·M-45·M-118에서 네 번 속은 그 모양이다.
    """
    assert LIVE_MARKER in [entry.split(":", 1)[0].strip() for entry in _declared_markers()], (
        f"`{LIVE_MARKER}` 마커가 {PYPROJECT.name}에 선언돼 있지 않다 "
        f"(선언된 것: {_declared_markers()}) — 배제할 이름 자체가 없다"
    )
    for name, result in (("게이트", gate_run), (f"make {LIVE_TARGET}", live_check_run)):
        assert result.returncode == 0, (
            f"{name} 표본 실행이 rc={result.returncode}로 끝났다 (argv={list(result.argv)}) — "
            f"이 결과는 배제에 대한 판정이 아니다. 출력 끝: {result.output!r}"
        )
        assert result.ran, (
            f"{name} 표본 실행이 **아무것도 안 돌렸다** (argv={list(result.argv)}) — "
            f"0건을 돌고 난 초록은 배제의 증거가 아니다. 출력 끝: {result.output!r}"
        )


def test_the_gate_does_not_run_live_tests(gate_run: RunResult) -> None:
    """② ⛔ **이 가드의 본체다.** 게이트 설정으로 돌면 라이브 표본은 **안 돈다**.

    Verifies: REQ-801

    ⛔ red면 고칠 것은 이 테스트가 아니라 `addopts`다. 이 자리가 red라는 것은
       *"`make check`가 실물 클라우드를 부르는 테스트를 돌린다"*는 뜻이고, 그건 무인 루프가
       밤새 돈을 쓴다는 뜻이다(design 09§1 · PRINCIPLES #3).
    """
    assert LIVE_MARKER not in gate_run.ran, (
        f"게이트 설정으로 돌렸는데 `{LIVE_MARKER}` 표본이 **돌았다** "
        f'(흔적: {sorted(gate_run.ran)}) — `addopts`에 `-m "not {LIVE_MARKER}"`가 없다. '
        "마커 설명의 *'게이트에 포함되지 않는다'*는 지금 문장일 뿐이다"
    )
    assert OFFLINE_TRACE in gate_run.ran, (
        f"게이트 설정이 오프라인 표본까지 배제했다 (흔적: {sorted(gate_run.ran)}) — "
        "배제 식이 너무 넓다. 게이트가 도는 테스트가 줄어든 것을 초록으로 읽으면 안 된다"
    )


def test_live_check_selects_live_tests_and_only_those(live_check_run: RunResult) -> None:
    """③ 반대 방향 — `make live-check`는 라이브만 돈다.

    Verifies: REQ-801

    ⛔ **②를 넣는 행위가 이 자리를 깰 수 있다.** `addopts`의 `-m "not live"`가 이기면
       `make live-check`는 라이브를 **하나도 안 돌고** 초록이다. 그러면 실물 검증은
       *"통과했다"*고 보고되면서 실제로는 한 번도 일어나지 않는다 — 이 저장소가 계속
       잡아 온 **실행 성공 ≠ 증상 해소**의 게이트판이다.
    """
    assert live_check_run.ran == frozenset({LIVE_MARKER}), (
        f"`make {LIVE_TARGET}`의 선택({list(live_check_run.argv)})으로 돌린 흔적이 "
        f"{sorted(live_check_run.ran)}다 — 기대는 [{LIVE_MARKER!r}] 하나뿐이다. "
        f"비어 있으면 라이브가 **0건 돌고 초록**인 것이고, 둘 다면 게이트와 구분이 없다"
    )


def test_the_gate_targets_do_not_override_the_exclusion() -> None:
    """④ 배제를 되돌리는 **두 번째 자리**가 없는가 — Makefile 쪽.

    ⚠️ ②의 되풀이가 아니다. `addopts`는 그대로 두고 `test:` 레시피에 `-m` 하나만 붙이면
       ②의 표본은 그 인자를 안 받으므로 **여전히 초록**인데, 실제 `make check`는 라이브를
       돈다. 명령줄이 `addopts`를 이긴다는 성질(③이 쓰는 바로 그 성질)의 반대쪽 얼굴이다.
    """
    _, gate_recipe = _recipe(GATE_TEST_TARGET)
    override = _marker_selection(gate_recipe)
    assert not override, (
        f"`{GATE_TEST_TARGET}:` 레시피가 자기 `-m`을 든다: {override} — "
        f"명령줄이 `addopts`를 이기므로 이 한 줄이 배제를 통째로 되돌린다"
    )
    prereq, _ = _recipe(GATE_TARGET)
    assert LIVE_TARGET not in prereq.split(), (
        f"`{GATE_TARGET}:`의 선행에 `{LIVE_TARGET}`가 있다 ({prereq.strip()!r}) — "
        "게이트가 과금 경로를 직접 부른다"
    )
