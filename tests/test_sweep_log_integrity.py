"""스윕 원본 로그의 **범위 집행** — 인용한 증거가 그 스윕을 실제로 담는가 (T11-6 · REQ-802).

Spec: specs/warranty/requirements.md (REQ-802)

⛔ **실제로 났다.** `mutation-sweep-2026-08-22-192.log`는 **97줄 · 20 case**다(M-20에서 끊긴다).
   그런데 192 스윕 절은 그 파일을 *"M-01~M-112 112종 전부 red 확인"*의 **원본으로 인용한다.**
   무인 루프가 스윕 도중 `STOP`을 맞아 tee가 끊긴 모양이고, 게이트는 **초록이었다.**
   T11-2가 정한 *"이번부터 원본 로그를 커밋한다"* 규칙이 **한 판 만에 조용히 샜다.**

신선도 가드(`test_mutation_freshness.py`)는 최신 절이 *무엇을 주장하는지*는 본다.
여기서 묻는 것은 그 다음 한 칸이다 — **인용한 로그가 그 주장을 담는가.**

  ① 최신 스윕 절이 원본 로그를 **인용하고**, 그 파일이 실재하는가
  ② 그 로그가 절이 선언한 case를 **전부** 담는가 (잘린 꼬리는 여기서 운다)
  ③ 열린 블록이 없는가 — 마지막 case가 결과 행 없이 끊기지 않았는가
  ④ 실패 표지(`❌`)가 0인가 — *"판정 불가"*가 섞인 로그는 *"전부 red"*의 원본이 아니다

⛔ **이 가드는 워킹트리가 아니라 `HEAD`를 읽는다. 그게 이 자리의 설계 전부다.**
   앞선 한 판이 워킹트리를 읽었고 **되돌렸다.** 이유는 버그가 아니라 자기참조다:
   로그는 스윕이 만들고, 스윕은 변이 하나마다 이 스위트를 **세 번** 지난다. 그러면
   *"로그가 다 차 있는가"*는 **로그가 만들어지는 동안 이미 참이어야 한다** — 수렴하지 않는다.
   `HEAD`는 스윕이 도는 내내 얼어 있다. 그래서 여기서 묻는 것은 언제나
   **직전에 커밋된 증거**이고, 그 질문은 스윕 중이든 아니든 같은 답을 낸다.

⚠️ **대가는 한 커밋의 지연이다** — 잘린 로그를 커밋하는 그 커밋의 게이트는 초록이고,
   **바로 다음 게이트가 red**다. 없앨 수 있는 지연이 아니다(위의 자기참조가 그것을 산다).
   무인 루프에서 그 red는 *깨끗한 워킹트리에서 나는 red*이고, 그건 멈추라는 신호다.

⛔ **로그 자체를 겨냥하는 변이는 만들지 않는다** — 스윕이 그 파일을 쓰고 있는 중이라
   원리상 판정 불가다. 태우는 자리는 **스캐너와 표본**이다 (M-105·M-118과 같은 규칙).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MUTATIONS_PATH = "docs/evidence/mutations.md"
EVIDENCE_DIR = "docs/evidence"

#: 현재를 주장하는 절의 표제. ⚠️ 신선도 가드와 **같은 문자열이어야 한다** — 두 가드가 다른
#: 절을 보면 하나는 최신을, 다른 하나는 역사를 판정한다.
SWEEP_HEADING = "## 전체 스윕"

#: 공허 통과 방지의 바닥. 파서가 깨지면 이 파일의 모든 단언이 조용히 참이 된다.
MIN_CASES = 40

#: 로그의 case 머리. ⚠️ `── M-01 ──` 형태다.
CASE_RE = re.compile(r"^── (M-\d+) ──\s*$", re.MULTILINE)
#: case 블록이 **닫혔다는 표지**. 하네스가 한 case의 마지막에 찍는 잔여 대조 행이다.
CLOSE_MARK = "잔여"
#: 하네스가 *"이 결과는 가드에 대한 판정이 아니다"*라고 말할 때 찍는 표지.
FAIL_MARK = "❌"

#: `원본: [`...log`](...log)` — 절이 인용한 원본 파일 이름.
CITED_LOG_RE = re.compile(r"원본:\s*\[`([^`]+\.log)`\]")
SWEEP_RANGE_RE = re.compile(r"M-(\d+)~M-(\d+)")


class LogScan:
    """로그 한 벌을 읽은 결과. **세 값이 각각 다른 질문에 답한다.**"""

    def __init__(self, cases: list[str], open_cases: list[str], failed_cases: list[str]) -> None:
        self.cases = cases
        self.open_cases = open_cases
        self.failed_cases = failed_cases


def scan_log(text: str) -> LogScan:
    """스윕 로그를 case 블록으로 가른다.

    ⚠️ **열린 블록**은 결과 행이 하나도 안 붙은 채 끝난 case다 — tee가 끊기면 마지막 하나가
       정확히 그 꼴이 된다(192 로그의 M-20). 그것이 *"덜 돌았다"*의 유일한 구조적 흔적이다.
    """
    marks = list(CASE_RE.finditer(text))
    cases: list[str] = []
    open_cases: list[str] = []
    failed_cases: list[str] = []
    for index, mark in enumerate(marks):
        name = mark.group(1)
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        body = text[mark.end() : end]
        cases.append(name)
        if CLOSE_MARK not in body:
            open_cases.append(name)
        if FAIL_MARK in body:
            failed_cases.append(name)
    return LogScan(cases, open_cases, failed_cases)


def _head_text(path: str) -> str | None:
    """**커밋된** 내용. ⚠️ 워킹트리가 아니다 — 이 파일의 docstring이 그 이유다.

    `HEAD`에 그 경로가 없으면 `None`. *"아직 안 커밋됐다"*와 *"읽기가 깨졌다"*는 다른 값이다.
    """
    proc = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


@pytest.fixture(scope="module")
def committed_record() -> str:
    text = _head_text(MUTATIONS_PATH)
    if text is None:
        raise AssertionError(
            f"`HEAD`에서 {MUTATIONS_PATH}를 못 읽었다 — 저장소가 아니거나 커밋이 없다. "
            "이 가드는 워킹트리가 아니라 **커밋된 증거**를 본다."
        )
    return text


@pytest.fixture(scope="module")
def newest_sweep(committed_record: str) -> str:
    """맨 마지막 「전체 스윕」 절. **이 절만이 현재를 주장한다** (신선도 가드와 같은 규칙)."""
    start = committed_record.rfind(SWEEP_HEADING)
    if start < 0:
        raise AssertionError(
            f"커밋된 기록에서 {SWEEP_HEADING!r} 절을 못 찾았다 — 표제가 바뀌었거나 지워졌다."
        )
    end = committed_record.find("\n## ", start + 1)
    return committed_record[start:] if end < 0 else committed_record[start:end]


@pytest.fixture(scope="module")
def cited_log(newest_sweep: str) -> str:
    """최신 절이 인용한 원본 로그의 **커밋된 내용**."""
    match = CITED_LOG_RE.search(newest_sweep)
    assert match is not None, (
        f"최신 스윕 절이 원본 로그를 인용하지 않는다: {newest_sweep[:160]!r}. "
        "T11-2가 정한 규칙은 *'원본을 커밋한다'*이고, 인용이 없으면 그 규칙은 문장일 뿐이다."
    )
    name = match.group(1)
    text = _head_text(f"{EVIDENCE_DIR}/{name}")
    assert text is not None, (
        f"최신 스윕이 인용한 원본 로그가 `HEAD`에 없다: {name}. "
        "기록만 커밋하고 로그를 빠뜨렸거나 경로가 틀렸다."
    )
    return text


# ── ① 스캐너를 표본으로 태운다 ──────────────────────────────────────────────

#: ⚠️ 표본은 **실패해야 하는 것들을 일부러 담는다**. 스캐너를 스캐너로 검사할 수는 없고,
#:    기대값이 박힌 표본이 유일한 바닥이다 (M-105·M-118이 먼저 쓴 규칙).
COMPLETE_SAMPLE = """\
bash scripts/mutate.sh all
── M-01 ──
  기준선: 초록 (197 passed)
  ✅ red — 가드가 하중을 받는다 (3 failed, 194 passed)
  ✅ 복구 후 초록 (197 passed)
  ✅ 잔여 없음 (백업 대조)
── M-02 ──
  기준선: 초록 (197 passed)
  ✅ red — 가드가 하중을 받는다 (1 failed, 196 passed)
  ✅ 복구 후 초록 (197 passed)
  ✅ 잔여 없음 (백업 대조)
"""

#: tee가 끊긴 꼴 — 192 로그가 정확히 이 모양이다(M-20에서 머리만 남았다).
TRUNCATED_SAMPLE = """\
── M-01 ──
  기준선: 초록 (192 passed)
  ✅ red — 가드가 하중을 받는다 (3 failed, 189 passed)
  ✅ 복구 후 초록 (192 passed)
  ✅ 잔여 없음 (백업 대조)
── M-02 ──
  기준선: 초록 (192 passed)
"""

#: 다 돌았지만 **판정이 아닌** 꼴 — 변이 대상이 없었다.
FAILED_SAMPLE = """\
── M-01 ──
  기준선: 초록 (197 passed)
  ✅ red — 가드가 하중을 받는다 (3 failed, 194 passed)
  ✅ 복구 후 초록 (197 passed)
  ✅ 잔여 없음 (백업 대조)
── M-02 ──
  기준선: 초록 (197 passed)
  ❌ 변이 대상이 없다: src/warranty/ghost.py — 이 결과는 가드에 대한 판정이 아니다
  ✅ 잔여 없음 (백업 대조)
"""


def test_scanner_reads_a_complete_sample() -> None:
    """① 바닥 — 온전한 표본에서 case가 뽑히고 **아무 것도 안 울려야** 한다."""
    scan = scan_log(COMPLETE_SAMPLE)
    assert scan.cases == ["M-01", "M-02"], (
        f"표본에서 뽑힌 case가 기대와 다르다: {scan.cases}. case 머리 형태가 바뀌었다."
    )
    assert not scan.open_cases, f"온전한 표본을 열린 블록으로 읽었다: {scan.open_cases}"
    assert not scan.failed_cases, f"온전한 표본을 실패로 읽었다: {scan.failed_cases}"


def test_scanner_flags_a_truncated_sample() -> None:
    """① ⛔ **이 표본이 이 가드의 존재 이유다** — 192 로그가 이 꼴이었다.

    ⚠️ 열린 블록을 못 읽으면 *"잘렸다"*와 *"다 돌았다"*가 **같은 초록**으로 보인다.
    """
    scan = scan_log(TRUNCATED_SAMPLE)
    assert scan.open_cases == ["M-02"], (
        f"잘린 표본에서 열린 블록을 {scan.open_cases}로 읽었다 — 기대는 ['M-02']다. "
        "닫힘 표지가 안 잡히면 tee가 끊긴 로그가 온전한 증거로 통과한다."
    )


def test_scanner_flags_a_failed_case_sample() -> None:
    """① *"판정 불가"*가 섞인 로그는 *"전부 red 확인"*의 원본이 아니다."""
    scan = scan_log(FAILED_SAMPLE)
    assert scan.failed_cases == ["M-02"], (
        f"실패 표본에서 실패 case를 {scan.failed_cases}로 읽었다 — 기대는 ['M-02']다."
    )


# ── ② 커밋된 증거를 실제로 읽는가 (바닥) ────────────────────────────────────


def test_the_committed_log_is_actually_read(cited_log: str) -> None:
    """공허 통과 방지 — 스캐너가 0개를 읽으면 아래 셋이 전부 조용히 통과한다.

    ⚠️ 이 저장소는 같은 방식으로 여러 번 속았다(M-03·M-25·M-45·M-118). 스캔 경로가 틀리면
       *"어긋난 게 없다"*와 *"아무것도 안 봤다"*가 같은 초록으로 보인다.
    """
    scan = scan_log(cited_log)
    assert len(scan.cases) >= MIN_CASES, (
        f"인용된 원본 로그에서 case를 {len(scan.cases)}개만 읽었다 (최소 {MIN_CASES}) — "
        "로그가 잘렸거나 case 머리 형태가 바뀌었다."
    )


# ── ③ 인용한 로그가 선언한 범위를 담는가 ───────────────────────────────────


def test_the_cited_log_covers_every_case_the_newest_sweep_declares(
    newest_sweep: str, cited_log: str
) -> None:
    """③ ⛔ **이 가드의 본체다.** *"112종 전부 red"*라고 적고 20 case짜리 로그를 인용했다.

    ⚠️ red일 때 고칠 것은 **선언이 아니라 스윕**이다. 잘린 꼬리를 채우거나 범위를 좁히면
       그건 증거가 아니라 **창작**이다 — 다시 돌리고 새 로그를 커밋해라.
    """
    match = SWEEP_RANGE_RE.search(newest_sweep)
    assert match is not None, (
        f"최신 스윕이 덮는 변이 범위(`M-01~M-NN`)를 못 읽었다: {newest_sweep[:160]!r}"
    )
    declared = {f"M-{n:02d}" for n in range(int(match.group(1)), int(match.group(2)) + 1)}
    logged = set(scan_log(cited_log).cases)
    missing = sorted(declared - logged, key=lambda name: int(name.split("-", 1)[1]))
    assert not missing, (
        f"최신 스윕은 {len(declared)}종을 덮는다고 적었는데 인용한 원본 로그에 "
        f"{len(missing)}종이 없다: {missing[:8]}{' …' if len(missing) > 8 else ''}. "
        "기록의 주장과 증거의 범위가 다르다 — `make mutate M=all`을 다시 돌리고 "
        "새 로그를 커밋해라 (선언을 좁히지 마라)."
    )


# ── ④ 잘리지 않았고 실패 표지가 없는가 ─────────────────────────────────────


def test_the_cited_log_is_neither_truncated_nor_failed(cited_log: str) -> None:
    """④ 열린 블록 0 · `❌` 0.

    ⚠️ ③과 다른 질문이다 — 범위는 다 담고도 **마지막 case가 결과 없이 끊길 수 있고**,
       다 닫히고도 *"이 결과는 판정이 아니다"*가 섞일 수 있다.
    """
    scan = scan_log(cited_log)
    assert not scan.open_cases, (
        f"인용된 원본 로그에 결과 없이 끊긴 case가 있다: {scan.open_cases}. "
        "스윕이 도중에 죽었다 — 그 로그는 '전부 red 확인'의 원본이 아니다."
    )
    assert not scan.failed_cases, (
        f"인용된 원본 로그에 `{FAIL_MARK}` 표지가 붙은 case가 있다: {scan.failed_cases}. "
        "하네스가 *'이 결과는 가드에 대한 판정이 아니다'*라고 말한 자리다."
    )
