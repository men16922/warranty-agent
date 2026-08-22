"""변이 기록 신선도 — **기록이 말하는 "전부 red 확인"이 아직 참인가.**

⚠️ 변이 기록은 *과거에* 참이었던 문장을 적어 둔 곳이다. 그런데 맨 아래 「전체 스윕」 절만은
   **현재에 대한 주장**이다 — *"지금 이 스위트에서 M-01~M-NN이 전부 red다."*
   그 문장은 **스위트가 바뀌는 순간 조용히 거짓이 된다.** 아무도 안 물으면 게이트는 초록이다.

⛔ 실제로 났다: 예산 예약(REQ-405)을 넣자 M-18·M-27이 초록으로 돌아섰다(`5a049f1`).
   바깥 방어층이 안쪽 층의 변이를 흡수했고, 기록의 *"전부 red 확인"*은 **그 커밋부터 거짓**이었다.
   게이트는 아무 말도 안 했다. 사람이 전체 스윕을 다시 돌려 보고서야 알았다.

그래서 묻는 것은 *"변이가 red인가"*가 아니다 — 그건 오프라인 게이트가 못 하는 질문이다
(스윕은 스위트를 변이당 세 번 돌린다). 대신 **기록이 그때 본 세계와 지금 세계가 같은가**를 묻는다:

  ① 최신 스윕이 선언한 기준선(`N passed`)이 **지금 스위트 크기**와 같은가
  ② 최신 스윕이 덮는다고 말한 변이 집합이 **하네스가 실제로 돌릴 수 있는 집합**과 같은가
  ③ 하네스가 정의한 변이마다 `red 확인` 행이 있는가

①이 red면 답은 *"기록을 고쳐라"*가 아니라 **`make mutate`를 다시 돌려라**다.
스위트가 늘었다는 것은 하중 분포가 바뀌었다는 뜻이고, 그때가 정확히 흡수가 생기는 때다.

⚠️ **오래된 절은 안 건드린다.** 그것들은 그 시점에 참이었던 역사다 — 지금과 맞대면
   append-only 기록을 매번 고쳐 쓰게 되고, 그러면 기록은 기록이 아니다.
   **현재를 주장하는 절은 맨 마지막 「전체 스윕」 하나뿐이다.**

⚠️ 스위트 크기는 **pytest에게 묻는다**(`--collect-only`). `def test_`를 세는 두 번째 계산기를
   만들면 파라미터화·클래스에서 조용히 갈라진다 — 기록이 적은 숫자는 pytest가 센 숫자다.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MUTATIONS = ROOT / "docs" / "evidence" / "mutations.md"
HARNESS = ROOT / "scripts" / "mutate.sh"

#: 현재를 주장하는 절의 표제. ⚠️ 바뀌면 파서가 **못 찾고 예외를 낸다** — 0개를 읽고
#: 아래 검사를 공허하게 통과시키는 것보다 낫다 (test_tunables.py와 같은 규칙).
SWEEP_HEADING = "## 전체 스윕"

#: 공허 통과 방지의 바닥. 파서가 깨지면 이 파일의 모든 단언이 조용히 참이 된다.
MIN_SWEEPS = 3
MIN_MUTATIONS = 40

SUITE_SIZE_RE = re.compile(r"(\d+) passed")
SWEEP_RANGE_RE = re.compile(r"M-(\d+)~M-(\d+)")
SWEEP_COUNT_RE = re.compile(r"\*\*(\d+)종")
MUTATION_ID_RE = re.compile(r"M-\d+")
#: 하네스가 실제로 **적용할 수 있는** 변이 = `case` 분기의 표지.
HARNESS_CASE_RE = re.compile(r"^ {4}(M-\d+)\)", re.MULTILINE)
#: `all`이 도는 목록. ⚠️ case가 있는데 여기 없으면 스윕은 그 변이를 **안 돌고도** 초록이다.
HARNESS_ALL_RE = re.compile(
    r"^\s*if \[ \"\$MUT\" = \"all\" \]; then for m in ([^;]+);", re.MULTILINE
)
#: 사용법 문자열. T0-6이 남긴 자리 — **기계가 안 읽는 문자열은 재발한다**고 적어 둔 그 자리다.
HARNESS_USAGE_RE = re.compile(r"<M-\d+\.\.(M-\d+)\|all>")
#: pytest가 스스로 센 수. ⚠️ `-q`를 또 주면 `-qq`가 되어 이 줄이 **사라진다**
#: (하네스 자신의 첫 번째 결함이 그것이었다 — mutations.md 「하네스가 다섯 번 틀렸다」).
COLLECTED_RE = re.compile(r"^(\d+) tests? collected", re.MULTILINE)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _newest_sweep() -> str:
    """맨 마지막 「전체 스윕」 절의 본문. **이 절만이 현재를 주장한다.**"""
    text = _read(MUTATIONS)
    start = text.rfind(SWEEP_HEADING)
    if start < 0:
        raise AssertionError(
            f"{MUTATIONS.name}에서 {SWEEP_HEADING!r} 절을 못 찾았다 — "
            "표제가 바뀌었거나 기록이 지워졌다. 이 가드는 이 절 하나에만 물린다."
        )
    end = text.find("\n## ", start + 1)
    return text[start:] if end < 0 else text[start:end]


def _sweep_count() -> int:
    return _read(MUTATIONS).count(SWEEP_HEADING)


def _expand(first: str, last: str) -> set[str]:
    """`M-01~M-46` → 46개. ⚠️ 범위를 안 펼치면 **가운데가 검사에서 빠진다**."""
    return {f"M-{n:02d}" for n in range(int(first), int(last) + 1)}


def _number(mutation_id: str) -> int:
    """`M-100` → 100. ⛔ **문자열로 비교하면 `"M-100" < "M-99"`다.**

    T11-2가 정확히 여기서 막혔다 — 새 가드의 공허 통과 경로를 태울 변이를 넣으려는데
    `M-100`을 정의하는 순간 아래 「사용법 문자열」 검사가 *"마지막은 M-99인데 M-100이라 적혔다"*
    로 red를 냈다. 그래서 그 변이를 **못 넣고 적어 두고 끝냈다**(mutations.md T11-2 절).
    ⇒ 정렬의 기준은 표기가 아니라 **번호**다. 두 자리 천장은 하네스의 성질이 아니라 이 한 줄이었다.
    """
    return int(mutation_id.split("-", 1)[1])


def _declared_mutations(sweep: str) -> set[str]:
    match = SWEEP_RANGE_RE.search(sweep)
    if match is None:
        raise AssertionError(
            f"최신 스윕이 덮는 변이 범위(`M-01~M-NN`)를 못 읽었다: {sweep[:120]!r}"
        )
    return _expand(match.group(1), match.group(2))


def _harness_cases() -> set[str]:
    return set(HARNESS_CASE_RE.findall(_read(HARNESS)))


def _harness_all_list() -> set[str]:
    match = HARNESS_ALL_RE.search(_read(HARNESS))
    if match is None:
        raise AssertionError(f"{HARNESS.name}에서 `all` 목록을 못 읽었다 — 루프 형태가 바뀌었다")
    return set(MUTATION_ID_RE.findall(match.group(1)))


def _recorded_ids() -> set[str]:
    """`red 확인` 행이 붙은 변이만. **적어 두기만 한 변이는 안 센다** (G6과 같은 규칙)."""
    rows = (
        line.split("|")[1].strip()
        for line in _read(MUTATIONS).splitlines()
        if line.startswith("|") and "red 확인" in line
    )
    return {cell for cell in rows if MUTATION_ID_RE.fullmatch(cell)}


@pytest.fixture(scope="module")
def suite_size() -> int:
    """**pytest에게** 이 스위트가 몇 건인지 묻는다.

    ⚠️ 세는 주체가 하나여야 한다. 여기서 `def test_`를 직접 세면 파라미터화가 늘어나는 순간
       기록의 숫자(pytest가 센 것)와 가드의 숫자(우리가 센 것)가 갈라지고, **가드는 자기가
       만든 숫자만 지킨다.** 그건 M-44가 보여 준 값-대-구문 착각의 다른 얼굴이다.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    match = COLLECTED_RE.search(proc.stdout)
    if proc.returncode != 0 or match is None:
        raise AssertionError(
            f"수집만 하는 실행이 스위트 크기를 안 알려 줬다 (rc={proc.returncode}). "
            f"stdout 끝: {proc.stdout[-300:]!r} · stderr 끝: {proc.stderr[-300:]!r}"
        )
    return int(match.group(1))


def test_the_record_and_the_harness_are_actually_read(suite_size: int) -> None:
    """공허 통과 방지 — 파서가 0개를 읽으면 아래 셋이 전부 조용히 통과한다.

    ⚠️ 이 저장소는 같은 방식으로 두 번 속았다(M-03·M-25·M-45). 스캔 경로 하나가 틀리면
       *"어긋난 게 없다"*와 *"아무것도 안 봤다"*가 **같은 초록**으로 보인다.
    """
    assert _sweep_count() >= MIN_SWEEPS, (
        f"「전체 스윕」 절을 {_sweep_count()}개만 읽었다 (최소 {MIN_SWEEPS}) — 파서가 깨졌다"
    )
    assert len(_harness_cases()) >= MIN_MUTATIONS, (
        f"하네스에서 변이를 {len(_harness_cases())}개만 읽었다 (최소 {MIN_MUTATIONS}) — "
        "`case` 표지 형태가 바뀌었거나 스크립트가 잘렸다"
    )
    assert suite_size >= MIN_MUTATIONS, f"스위트를 {suite_size}건만 수집했다 — 수집 경로가 틀렸다"


def test_the_newest_sweep_baseline_matches_the_suite_size_now(suite_size: int) -> None:
    """① ⛔ **이 가드의 본체다.** 최신 스윕이 선언한 기준선이 지금 스위트와 같은가.

    스위트가 늘었는데 스윕을 다시 안 돌렸다면, 기록의 *"전부 red 확인"*은 **늘어난 테스트가
    만든 새 하중 분포에 대해 아무 말도 안 한 문장**이다. 예약이 M-18·M-27을 가렸을 때가
    정확히 그 상태였고, 게이트는 초록이었다.

    ⚠️ red일 때 고칠 것은 **숫자가 아니라 스윕**이다. 숫자만 고치면 이 가드는 자기 자신을 속인다.
    """
    sweep = _newest_sweep()
    declared = [int(n) for n in SUITE_SIZE_RE.findall(sweep)]
    assert declared, f"최신 스윕이 기준선(`N passed`)을 선언하지 않았다: {sweep[:120]!r}"
    stale = sorted({n for n in declared if n != suite_size})
    assert not stale, (
        f"최신 스윕은 {stale}건짜리 스위트를 보고 적혔는데 지금은 {suite_size}건이다 — "
        "기록의 '전부 red 확인'은 지금 스위트에 대한 문장이 아니다. "
        "`make mutate`를 다시 돌리고 새 스윕 절을 덧붙여라 (숫자만 고치지 마라)."
    )


def test_the_newest_sweep_covers_every_mutation_the_harness_can_run() -> None:
    """② 기록이 덮는다는 집합 = 하네스가 돌릴 수 있는 집합 = `all`이 도는 집합.

    ⚠️ 셋은 따로 썩는다. `case`만 추가하고 `all`에 안 넣으면 **스윕이 그 변이를 안 돌고도**
       초록이고, 기록에 범위만 늘리면 **안 돌린 변이가 red 확인으로 읽힌다.**
    ⚠️ 사용법 문자열까지 같이 묻는 이유는 T0-6이다 — 기계가 안 읽는 문자열은 재발한다.
    """
    sweep = _newest_sweep()
    declared = _declared_mutations(sweep)
    cases = _harness_cases()
    assert declared == cases, (
        f"최신 스윕이 덮는 변이와 하네스가 정의한 변이가 다르다: "
        f"기록에만 {sorted(declared - cases)} · 하네스에만 {sorted(cases - declared)}"
    )
    counted = SWEEP_COUNT_RE.search(sweep)
    assert counted is not None and int(counted.group(1)) == len(cases), (
        f"최신 스윕이 적은 종수와 실제 변이 수가 다르다: "
        f"{counted.group(1) if counted else '없음'} ≠ {len(cases)}"
    )
    assert _harness_all_list() == cases, (
        f"`all`이 도는 목록과 정의된 변이가 다르다: "
        f"목록에만 {sorted(_harness_all_list() - cases)} · "
        f"정의에만 {sorted(cases - _harness_all_list())} — 스윕이 조용히 덜 돈다"
    )
    usage = HARNESS_USAGE_RE.search(_read(HARNESS))
    last = max(cases, key=_number)
    assert usage is not None and usage.group(1) == last, (
        f"사용법 문자열이 {usage.group(1) if usage else '없음'}까지라고 말하는데 "
        f"실제 마지막 변이는 {last}다"
    )


def test_every_mutation_the_harness_defines_has_a_confirmed_row() -> None:
    """③ 정의된 변이마다 `red 확인` 행이 있는가.

    ⚠️ 범위 선언(`M-01~M-49 전부 red 확인`)은 **한 줄로 49건을 주장한다.** 그 한 줄만 믿으면
       실제로는 안 돌린 변이가 증거를 공짜로 얻는다. 행 단위로도 물어야 `scan_mutation_refs`가
       읽는 증거와 스윕의 주장이 같은 것을 가리킨다.
    """
    missing = sorted(_harness_cases() - _recorded_ids())
    assert not missing, f"하네스가 정의했는데 `red 확인` 행이 없는 변이: {missing}"
