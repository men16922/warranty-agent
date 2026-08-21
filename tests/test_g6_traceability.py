"""G6 — spec 추적성 가드.

⚠️ **이 가드가 SDD를 장식이 아니게 만드는 유일한 장치다.**
없으면 spec을 안 지켜도 아무 일이 일어나지 않는다.

이 가드는 커버리지를 재지 않는다. **spec의 주장을 현실에 맞댄다** —
`상태: IMPLEMENTED`라고 적혀 있으면 테스트가 있어야 하고, `VERIFIED`라면
변이로 red를 확인한 기록이 있어야 한다. 주장과 현실이 어긋나면 red다.

형제 검사 넷을 함께 한다 (design/07-verification.md §3.2):
  ① 상태가 주장하는 테스트/변이 기록이 실제로 있는가
  ② 모든 요구사항에 그것을 만드는 태스크가 있는가
  ③ 모든 요구사항에 설계 귀속처가 있는가
  ④ 코드의 `Spec:`가 가리키는 설계 경로와 인용 REQ가 실재하는가
①만 묻는 G6는 절반만 묻는 가드다.

⚠️ ④가 없으면 참조가 **한 방향으로만** 지켜진다. 실제로 `fleet-ledger` → `warranty`
   이름 변경 때 다섯 곳의 `Spec:`가 없는 파일을 가리켰고 게이트는 초록이었다.
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


def test_g6_reports_no_violations(matrix: list[spec_trace.TraceRow]) -> None:
    """위 검사들의 합. `make trace`와 같은 판정을 쓴다 — 두 경로가 갈라지면 안 된다."""
    assert not spec_trace.all_violations(matrix)
