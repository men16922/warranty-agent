"""G6 — spec 추적성 가드.

⚠️ **이 가드가 SDD를 장식이 아니게 만드는 유일한 장치다.**
없으면 spec을 안 지켜도 아무 일이 일어나지 않는다.

이 가드는 커버리지를 재지 않는다. **spec의 주장을 현실에 맞댄다** —
`상태: IMPLEMENTED`라고 적혀 있으면 테스트가 있어야 하고, `VERIFIED`라면
변이로 red를 확인한 기록이 있어야 한다. 주장과 현실이 어긋나면 red다.

형제 검사 다섯을 함께 한다 (specs/warranty/design/09-quality-gate.md §3.1):
  ① 상태가 주장하는 테스트/변이 기록이 실제로 있는가
  ② 모든 요구사항에 그것을 만드는 태스크가 있는가
  ③ 모든 요구사항에 설계 귀속처가 있는가
  ④ 코드의 `Spec:`가 가리키는 설계 경로와 인용 REQ가 실재하는가
  ⑤ 요구사항이 **약속한 문장마다** 겨냥한 테스트가 있는가
①만 묻는 G6는 절반만 묻는 가드다.

⚠️ ④가 없으면 참조가 **한 방향으로만** 지켜진다. 실제로 `fleet-ledger` → `warranty`
   이름 변경 때 다섯 곳의 `Spec:`가 없는 파일을 가리켰고 게이트는 초록이었다.

⚠️ ⑤가 없으면 귀속이 **요구사항 단위로만** 지켜진다. 실제로 그랬다 — REQ-506은 셋을
   약속했는데 겨냥한 자리는 하나였고 기한 쪽은 코드가 아예 없었다(T9-5). ①은 못 본다:
   ①이 묻는 것은 *"테스트가 있는가"*지 *"약속한 문장마다 있는가"*가 아니다.
"""

from __future__ import annotations

import pytest
from tools import spec_trace
from tools.spec_trace import Status


@pytest.fixture(scope="module")
def matrix() -> list[spec_trace.TraceRow]:
    return spec_trace.build_matrix()


def test_g6_spec_parses_and_is_not_empty(matrix: list[spec_trace.TraceRow]) -> None:
    """공허 통과 방지 — 파서가 0개를 읽으면 아래 검사가 전부 조용히 통과한다."""
    assert len(matrix) >= spec_trace.MIN_REQUIREMENTS, (
        f"요구사항을 {len(matrix)}개만 읽었다. 파서가 깨졌거나 spec이 지워졌다."
    )


def test_g6_every_requirement_has_a_design_home(matrix: list[spec_trace.TraceRow]) -> None:
    """③ 설계 귀속처. ⚠️ 스캔 범위가 design/ 밖도 포함해야 REQ-802가 오탐되지 않는다."""
    missing = [
        row.req.req_id for row in matrix if row.req.status is not Status.DROPPED and not row.designs
    ]
    assert not missing, f"설계 문서에 귀속처가 없는 요구사항: {missing}"


def test_g6_every_requirement_has_a_task(matrix: list[spec_trace.TraceRow]) -> None:
    """② 실행 계획. 만들 계획이 없는 요구사항은 구멍이다."""
    missing = [
        row.req.req_id for row in matrix if row.req.status is not Status.DROPPED and not row.tasks
    ]
    assert not missing, f"tasks.md에 이것을 만드는 태스크가 없는 요구사항: {missing}"


def test_g6_implemented_requirements_have_tests(matrix: list[spec_trace.TraceRow]) -> None:
    """① 상태가 IMPLEMENTED/VERIFIED라고 주장하면 테스트가 있어야 한다."""
    claimed = {Status.IMPLEMENTED, Status.VERIFIED}
    missing = [row.req.req_id for row in matrix if row.req.status in claimed and not row.tests]
    assert not missing, f"상태는 구현됐다고 주장하는데 가리키는 테스트가 없다: {missing}"


def test_g6_verified_requirements_have_a_confirmed_mutation(
    matrix: list[spec_trace.TraceRow],
) -> None:
    """① VERIFIED는 **지워 보고 red를 확인한 것**만이다 (REFERENCE_FROM_PARENT #9)."""
    missing = [
        row.req.req_id for row in matrix if row.req.status is Status.VERIFIED and not row.mutations
    ]
    assert not missing, f"VERIFIED인데 red가 확인된 변이 기록이 없다: {missing}"


def test_g6_no_orphan_requirement_references(matrix: list[spec_trace.TraceRow]) -> None:
    """정의 없는 REQ를 가리키는 참조 — 오타이거나 지워진 요구사항이다."""
    orphans = spec_trace.orphan_references({row.req.req_id for row in matrix})
    assert not orphans, orphans


@pytest.fixture(scope="module")
def spec_refs() -> list[spec_trace.SpecRef]:
    return spec_trace.scan_spec_refs()


def test_g6_spec_refs_parse_and_are_not_empty(spec_refs: list[spec_trace.SpecRef]) -> None:
    """공허 통과 방지 — 스캐너가 0개를 읽으면 아래 두 검사가 조용히 통과한다."""
    assert len(spec_refs) >= spec_trace.MIN_SPEC_REFS, (
        f"`Spec:` 참조를 {len(spec_refs)}개만 읽었다. 스캐너가 깨졌거나 참조가 지워졌다."
    )


def test_g6_spec_refs_point_at_existing_designs(spec_refs: list[spec_trace.SpecRef]) -> None:
    """④ 코드 → 설계 방향. **없는 문서를 가리키는 참조는 참조가 아니라 거짓말이다.**"""
    dangling = [
        f"{ref.source} → {token} ({reason})"
        for ref in spec_refs
        for token in ref.paths
        if (reason := spec_trace.unresolved_spec_path(token)) is not None
    ]
    assert not dangling, f"`Spec:`가 안 풀리는 경로를 가리킨다: {dangling}"


def test_g6_spec_refs_cite_defined_requirements(
    spec_refs: list[spec_trace.SpecRef], matrix: list[spec_trace.TraceRow]
) -> None:
    """④ 인용한 REQ가 requirements.md에 실재하는가 (범위 표기 `REQ-201~206`도 펼친다)."""
    defined = {row.req.req_id for row in matrix}
    unknown = [
        f"{ref.source} → {req_id}"
        for ref in spec_refs
        for req_id in ref.reqs
        if req_id not in defined
    ]
    assert not unknown, f"`Spec:`가 정의 없는 요구사항을 인용한다: {unknown}"


# ── ⑤ 문장 단위 커버리지 (T10-1) ────────────────────────────────────────────
#
# ⛔ 여기서 묻는 것은 커버리지 비율이 아니다. **요구사항이 스스로 약속한 문장 수**와
#    **그것을 겨냥한 테스트 함수 수**를 맞대는 것이다. 하나가 여럿을 약속하면
#    하나만 겨냥해도 ①은 초록이고, 그 틈으로 REQ-506의 기한 절반이 통과했다.


def test_g6_promise_splitter_still_sees_multi_sentence_requirements(
    matrix: list[spec_trace.TraceRow],
) -> None:
    """공허 통과 방지 — 분리기가 깨져 전부 한 문장으로 읽히면 ⑤가 조용히 사라진다."""
    multi = [row.req.req_id for row in matrix if len(row.req.promises) > 1]
    assert len(multi) >= spec_trace.MIN_MULTI_PROMISE, (
        f"문장 둘 이상을 약속하는 요구사항을 {len(multi)}개만 읽었다. 분리기가 깨졌다."
    )


def test_g6_promises_are_split_on_punctuation_not_morphology() -> None:
    """분리기가 무엇을 자르고 무엇을 안 자르는지 **값으로** 태운다 (PRINCIPLES #8).

    ⚠️ 쉼표 없는 접속은 **일부러 안 센다** — 덜 세는 쪽으로 틀리는 것이 설계다.
    더 세면 없는 약속에 테스트를 요구하게 되고, 그때 사람이 고치는 방향은
    테스트를 쪼개는 것이라 가드가 자기 하중을 스스로 없앤다.
    """
    # 문장 끝: 종결 `다` 뒤의 마침표.
    assert len(spec_trace.split_promises("`Event` 하나를 만든다. 둘째 문장이다.")) == 2
    # 쉼표 붙은 대등 접속 — REQ-506이 정확히 이 모양이었다.
    assert len(spec_trace.split_promises("맞추고, 결과가 같으며, 사유와 함께 표시한다.")) == 3
    # 쉼표 없는 접속은 한 문장으로 센다.
    assert len(spec_trace.split_promises("에스컬레이션하고 더 조치하지 않는다.")) == 1
    # 소수점과 파일명은 문장 끝이 아니다.
    assert len(spec_trace.split_promises("비율은 0.56이고 근거는 design.md에 있다.")) == 1
    # 마침표가 굵게 **안**에 들어가도 잡는다.
    assert len(spec_trace.split_promises("기록한다. **성공으로 기록하지 않는다.**")) == 2


def test_g6_every_promised_sentence_has_a_test_of_its_own(
    matrix: list[spec_trace.TraceRow],
) -> None:
    """⑤ 구현을 주장하는 요구사항은 **약속한 문장 수만큼** 겨냥한 테스트를 갖는다."""
    claimed = {Status.IMPLEMENTED, Status.VERIFIED}
    thin = [
        f"{row.req.req_id}: 문장 {len(row.req.promises)}개 · 겨냥 {len(row.test_funcs)}개"
        for row in matrix
        if row.req.status in claimed and len(row.test_funcs) < len(row.req.promises)
    ]
    assert not thin, f"약속한 문장보다 겨냥한 테스트가 적다: {thin}"


def test_g6_half_covered_requirement_is_caught() -> None:
    """⑤가 **실제로 하중을 받는가** — 절반만 겨냥한 요구사항을 값으로 태워 본다.

    ⚠️ 현재 상태가 초록이라는 것만으로는 이 검사가 살아 있는지 알 수 없다.
    검사를 통째로 지워도 위 테스트는 초록이기 때문이다(전부 이미 충족돼 있어서).
    그래서 위반하는 행을 하나 만들어 **판정을 직접 묻는다.**
    """
    half = spec_trace.Requirement(
        req_id="REQ-506",
        title="약속 셋 · 겨냥 하나",
        status=Status.IMPLEMENTED,
        promises=("라벨로 맞춘다", "재실행해도 같다", "기한 내 못 맞추면 사유를 남긴다"),
    )
    row = spec_trace.TraceRow(
        req=half,
        designs=("specs/warranty/design.md",),
        tasks=("specs/warranty/tasks.md",),
        tests=("tests/test_domain_ledger.py",),
        mutations=(),
        test_funcs=("tests/test_domain_ledger.py::test_req_506_reconcile_is_idempotent",),
    )
    problems = spec_trace.row_violations(row)
    assert any("문장 3개를 약속하는데" in problem for problem in problems), problems

    # 겨냥이 문장 수를 채우면 더 이상 걸리지 않는다 — 규칙이 항상-red가 아니라는 확인.
    full = spec_trace.TraceRow(
        req=half,
        designs=row.designs,
        tasks=row.tasks,
        tests=row.tests,
        mutations=(),
        test_funcs=tuple(f"tests/t.py::test_req_506_{n}" for n in range(3)),
    )
    assert not spec_trace.row_violations(full)


def test_g6_reports_no_violations(matrix: list[spec_trace.TraceRow]) -> None:
    """위 검사들의 합. `make trace`와 같은 판정을 쓴다 — 두 경로가 갈라지면 안 된다."""
    assert not spec_trace.all_violations(matrix)
