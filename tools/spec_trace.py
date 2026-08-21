"""spec 추적성 매트릭스 — requirements.md ↔ design ↔ tasks ↔ tests ↔ 변이 기록.

이 모듈이 SDD를 집행한다. 리포트는 사람이 읽고, 판정은 tests/test_g6_traceability.py가 쓴다.

⚠️ 이 도구는 **spec의 주장을 현실에 맞대는 것**이지 커버리지 측정이 아니다.
   `상태: IMPLEMENTED`라고 적혀 있으면 테스트가 있어야 하고,
   `VERIFIED`라고 적혀 있으면 변이로 red를 확인한 기록이 있어야 한다.
   주장과 현실이 어긋나면 게이트가 red다.

⚠️ 참조는 **양방향으로** 썩는다. spec→코드만 물으면 코드→spec(`Spec:` 도크스트링)이
   없는 문서를 가리켜도 게이트가 초록이다. 그래서 `scan_spec_refs`가 그 방향도 묻는다.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "specs" / "warranty"
REQUIREMENTS = SPEC_DIR / "requirements.md"
TASKS = SPEC_DIR / "tasks.md"
TESTS_DIR = ROOT / "tests"
MUTATIONS = ROOT / "docs" / "evidence" / "mutations.md"

#: 설계 귀속처. ⚠️ `design/`으로 좁히면 REQ-802가 고아로 오탐된다 —
#: 그 요구사항의 설계는 docs/REFERENCE_FROM_PARENT.md에 있다. (design/07-verification.md §3.2)
DESIGN_SOURCES = (
    SPEC_DIR / "design.md",
    SPEC_DIR / "design",
    ROOT / "docs" / "PRINCIPLES.md",
)

#: `Spec:` 도크스트링을 찾는 곳. 코드가 설계를 가리키는 방향의 참조다.
SPEC_REF_SOURCES = (ROOT / "src", ROOT / "tests", ROOT / "tools")

#: 공허 통과 방지. 파서가 망가져 0개를 읽으면 모든 검사가 조용히 통과한다.
MIN_REQUIREMENTS = 30
#: 같은 이유로 `Spec:` 스캐너에도 바닥을 둔다. 0개를 읽으면 정합성 검사가 사라진다.
MIN_SPEC_REFS = 8

REQ_RE = re.compile(r"REQ-(\d{3})")
REQ_SNAKE_RE = re.compile(r"req_(\d{3})")
HEADING_RE = re.compile(r"^### (REQ-\d{3})\s+—\s+(.+?)\s*$", re.MULTILINE)
STATUS_RE = re.compile(r"^상태:\s*`([A-Z]+)`\s*$", re.MULTILINE)
#: 테스트 독스트링에서 이 접두사가 붙은 줄만 추적성 선언으로 인정한다.
VERIFIES_RE = re.compile(r"^Verifies:\s*REQ-")
#: `Spec:` 줄과 **들여쓴 이어짐 줄들**을 한 덩어리로 잡는다 (entry.py가 두 줄이다).
SPEC_BLOCK_RE = re.compile(r"^Spec:[ \t]*(.*(?:\n[ \t]+\S.*)*)", re.MULTILINE)
MD_PATH_RE = re.compile(r"[\w./-]+\.md")
#: `REQ-201~206` 형태. **범위를 펼치지 않으면 끝 번호가 검사에서 빠진다.**
REQ_RANGE_RE = re.compile(r"REQ-(\d{3})~(\d{3})")


class Status(StrEnum):
    TODO = "TODO"
    DESIGNED = "DESIGNED"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFIED = "VERIFIED"
    DROPPED = "DROPPED"


@dataclass(frozen=True, slots=True)
class Requirement:
    req_id: str
    title: str
    status: Status


@dataclass(frozen=True, slots=True)
class SpecRef:
    """코드가 설계를 가리키는 한 건 — `Spec: <경로> (REQ-###)`."""

    source: str
    paths: tuple[str, ...]
    reqs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TraceRow:
    req: Requirement
    designs: tuple[str, ...]
    tasks: tuple[str, ...]
    tests: tuple[str, ...]
    mutations: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not row_violations(self)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_requirements(path: Path = REQUIREMENTS) -> list[Requirement]:
    """`### REQ-### — 제목` 절과 그 아래 `상태:` 표기를 짝지어 읽는다."""
    text = _read(path)
    headings = list(HEADING_RE.finditer(text))
    out: list[Requirement] = []
    for i, match in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[match.start() : end]
        status_match = STATUS_RE.search(body)
        if status_match is None:
            raise ValueError(f"{match.group(1)}에 `상태:` 표기가 없다 — spec이 불완전하다")
        raw = status_match.group(1)
        if raw not in Status.__members__:
            raise ValueError(f"{match.group(1)}의 상태 `{raw}`가 알 수 없는 값이다")
        out.append(Requirement(match.group(1), match.group(2), Status[raw]))
    return out


def _markdown_files(source: Path) -> list[Path]:
    if source.is_dir():
        return sorted(source.rglob("*.md"))
    return [source] if source.exists() else []


def scan_markdown_refs(sources: tuple[Path, ...]) -> dict[str, set[str]]:
    """마크다운에서 REQ 참조를 모은다 → {REQ-###: {가리킨 파일명, ...}}"""
    found: dict[str, set[str]] = {}
    for source in sources:
        for path in _markdown_files(source):
            rel = str(path.relative_to(ROOT))
            for match in REQ_RE.finditer(_read(path)):
                found.setdefault(f"REQ-{match.group(1)}", set()).add(rel)
    return found


def scan_test_refs(tests_dir: Path = TESTS_DIR) -> dict[str, set[str]]:
    """테스트가 **의도적으로 선언한** REQ 참조만 모은다.

    인정하는 두 형태 (둘 다 테스트 함수에 붙어 있어야 한다):
      ① 함수명   `def test_req_204_assumed_is_never_overwritten(...)`
      ② 독스트링 `Verifies: REQ-204, REQ-402`

    ⚠️ **본문의 산문 언급은 세지 않는다.** 첫 판에서 정확히 여기서 틀렸다 —
    "REQ-802가 오탐되지 않는다"고 *설명한* 독스트링 때문에 REQ-802가
    "테스트 있음"으로 잡혔다. 그러면 `IMPLEMENTED`로 올린 요구사항이 **테스트 없이 통과**한다.
    같은 계열의 실패를 레퍼런스 저장소도 겪었다 — 문자열 검사라 호출을 지워도 import 줄이
    남아 통과했고, AST로 실제 호출을 세도록 고쳤다 (REFERENCE_FROM_PARENT #9).
    """
    found: dict[str, set[str]] = {}
    if not tests_dir.exists():
        return found
    for path in sorted(tests_dir.rglob("test_*.py")):
        rel = str(path.relative_to(ROOT))
        tree = ast.parse(_read(path), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not node.name.startswith("test_"):
                continue
            for match in REQ_SNAKE_RE.finditer(node.name):
                found.setdefault(f"REQ-{match.group(1)}", set()).add(rel)
            doc = ast.get_docstring(node) or ""
            for line in doc.splitlines():
                if not VERIFIES_RE.match(line.strip()):
                    continue
                for match in REQ_RE.finditer(line):
                    found.setdefault(f"REQ-{match.group(1)}", set()).add(rel)
    return found


def scan_mutation_refs(path: Path = MUTATIONS) -> dict[str, set[str]]:
    """변이 기록에서 **red가 확인된** 항목만 읽는다.

    형식: `| M-01 | REQ-303 | ... | red 확인 |` — 마지막 칸이 `red 확인`인 행만 센다.
    ⚠️ 적어 두기만 하고 확인 안 한 변이를 세면 이 가드가 자기 자신을 속인다.
    """
    found: dict[str, set[str]] = {}
    if not path.exists():
        return found
    for line in _read(path).splitlines():
        if not line.startswith("|") or "red 확인" not in line:
            continue
        mutation_id = line.split("|")[1].strip()
        for match in REQ_RE.finditer(line):
            found.setdefault(f"REQ-{match.group(1)}", set()).add(mutation_id)
    return found


def scan_spec_refs(sources: tuple[Path, ...] = SPEC_REF_SOURCES) -> list[SpecRef]:
    """도크스트링의 `Spec:` 블록에서 **설계 경로와 인용 REQ**를 읽는다.

    ⚠️ 이 방향의 참조는 **아무도 안 물으면 조용히 썩는다.** 실제로 썩었다 —
    `fleet-ledger` → `warranty` 이름 변경 때 다섯 곳이 안 따라왔고,
    게이트는 초록이었다. 설계 문서를 지우거나 옮겨도 마찬가지다.
    """
    out: list[SpecRef] = []
    for source in sources:
        if not source.exists():
            continue
        for path in sorted(source.rglob("*.py")):
            rel = str(path.relative_to(ROOT))
            tree = ast.parse(_read(path), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(
                    node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
                ):
                    continue
                doc = ast.get_docstring(node) or ""
                for block in SPEC_BLOCK_RE.findall(doc):
                    out.append(_parse_spec_block(rel, block))
    return out


def _parse_spec_block(source: str, block: str) -> SpecRef:
    reqs: set[str] = set()
    for start, end in REQ_RANGE_RE.findall(block):
        reqs.update(f"REQ-{n:03d}" for n in range(int(start), int(end) + 1))
    rest = REQ_RANGE_RE.sub("", block)
    reqs.update(f"REQ-{m.group(1)}" for m in REQ_RE.finditer(rest))
    paths = tuple(sorted(set(MD_PATH_RE.findall(block))))
    return SpecRef(source=source, paths=paths, reqs=tuple(sorted(reqs)))


#: `Spec:` 경로는 **저장소 루트 기준 전체 경로**로만 적는다.
#: ⚠️ 줄임 표기(`· 03-atomic-rollback.md`)를 허용하면 해석 규칙이 "직전 경로의 형제"가 되고,
#:    그 규칙은 조용히 틀린다 — 실제로 remediate.py가 그 형태였고 두 곳이 안 풀렸다.
SPEC_PATH_PREFIX = "specs/"


def unresolved_spec_path(token: str) -> str | None:
    """`Spec:` 경로 하나가 **왜** 안 풀리는지. 풀리면 `None`.

    판정이 한 곳에 있어야 `make trace`와 테스트가 갈라지지 않는다.
    """
    if not token.startswith(SPEC_PATH_PREFIX):
        return f"경로가 줄임 표기다 — 저장소 루트 기준 `{SPEC_PATH_PREFIX}...` 전체 경로로 적는다"
    if not (ROOT / token).is_file():
        return "가리키는 설계 문서가 없다"
    return None


def spec_reference_violations(
    refs: list[SpecRef] | None = None, defined: set[str] | None = None
) -> list[str]:
    """`Spec:`가 가리키는 설계 경로와 인용 REQ가 **실재하는가.**"""
    items = refs if refs is not None else scan_spec_refs()
    known = defined if defined is not None else {req.req_id for req in load_requirements()}

    if len(items) < MIN_SPEC_REFS:
        return [
            f"`Spec:` 참조를 {len(items)}개만 읽었다 (최소 {MIN_SPEC_REFS}) "
            f"— 스캐너가 깨졌거나 참조가 통째로 지워졌다"
        ]

    out: list[str] = []
    for ref in items:
        out += [
            f"{ref.source}: `Spec: {token}` — {reason}"
            for token in ref.paths
            if (reason := unresolved_spec_path(token)) is not None
        ]
        out += [
            f"{ref.source}: `Spec:`가 requirements.md에 없는 {req_id}를 인용한다"
            for req_id in ref.reqs
            if req_id not in known
        ]
    return out


def build_matrix(requirements: list[Requirement] | None = None) -> list[TraceRow]:
    reqs = requirements if requirements is not None else load_requirements()
    designs = scan_markdown_refs(DESIGN_SOURCES)
    tasks = scan_markdown_refs((TASKS,))
    tests = scan_test_refs()
    mutations = scan_mutation_refs()
    return [
        TraceRow(
            req=req,
            designs=tuple(sorted(designs.get(req.req_id, ()))),
            tasks=tuple(sorted(tasks.get(req.req_id, ()))),
            tests=tuple(sorted(tests.get(req.req_id, ()))),
            mutations=tuple(sorted(mutations.get(req.req_id, ()))),
        )
        for req in reqs
    ]


def row_violations(row: TraceRow) -> list[str]:
    """한 요구사항이 자기 상태가 주장하는 것을 실제로 갖고 있는가."""
    req = row.req
    out: list[str] = []
    if req.status is Status.DROPPED:
        return out

    # 상태와 무관한 spec 완결성: 설계 귀속처와 실행 계획은 늘 있어야 한다.
    if not row.designs:
        out.append(f"{req.req_id}: 설계 문서에 귀속처가 없다")
    if not row.tasks:
        out.append(f"{req.req_id}: tasks.md에 이것을 만드는 태스크가 없다")

    # 상태가 주장하는 것.
    if req.status in (Status.IMPLEMENTED, Status.VERIFIED) and not row.tests:
        out.append(f"{req.req_id}: 상태가 {req.status}인데 이것을 가리키는 테스트가 없다")
    if req.status is Status.VERIFIED and not row.mutations:
        out.append(
            f"{req.req_id}: 상태가 VERIFIED인데 red가 확인된 변이 기록이 없다 "
            f"— 지워 보고 red를 확인한 것만 VERIFIED다"
        )
    return out


def all_violations(rows: list[TraceRow] | None = None) -> list[str]:
    matrix = rows if rows is not None else build_matrix()

    # 공허 통과 방지 — 파서가 망가지면 아래 검사가 전부 조용히 통과한다.
    if len(matrix) < MIN_REQUIREMENTS:
        return [
            f"요구사항을 {len(matrix)}개만 읽었다 (최소 {MIN_REQUIREMENTS}) "
            f"— 파서가 깨졌거나 spec이 지워졌다"
        ]

    defined = {row.req.req_id for row in matrix}
    out: list[str] = []
    for row in matrix:
        out.extend(row_violations(row))
    out.extend(orphan_references(defined))
    out.extend(spec_reference_violations(defined=defined))
    return out


def orphan_references(defined: set[str]) -> list[str]:
    """정의되지 않은 REQ를 가리키는 참조 — 오타이거나 지워진 요구사항이다."""
    referenced: set[str] = set()
    for mapping in (
        scan_markdown_refs(DESIGN_SOURCES),
        scan_markdown_refs((TASKS,)),
        scan_test_refs(),
    ):
        referenced |= mapping.keys()
    return [
        f"{req_id}: 어딘가가 가리키는데 requirements.md에 정의가 없다"
        for req_id in sorted(referenced - defined)
    ]


def _mark(items: tuple[str, ...]) -> str:
    return f"{len(items)}" if items else "·"


def render_report(rows: list[TraceRow]) -> str:
    lines = [
        "spec 추적성 매트릭스 — fleet-ledger",
        "",
        f"{'REQ':<9} {'상태':<12} {'설계':>4} {'태스크':>6} {'테스트':>6} {'변이':>4}  제목",
        "-" * 96,
    ]
    for row in rows:
        flag = " " if row.ok else "!"
        lines.append(
            f"{flag}{row.req.req_id:<8} {row.req.status:<12} "
            f"{_mark(row.designs):>4} {_mark(row.tasks):>6} "
            f"{_mark(row.tests):>6} {_mark(row.mutations):>4}  {row.req.title[:38]}"
        )
    counts: dict[Status, int] = {}
    for row in rows:
        counts[row.req.status] = counts.get(row.req.status, 0) + 1
    lines += [
        "-" * 96,
        f"총 {len(rows)}개 · " + " · ".join(f"{s}={n}" for s, n in sorted(counts.items())),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="매트릭스를 출력한다")
    args = parser.parse_args(argv)

    rows = build_matrix()
    if args.report:
        print(render_report(rows))
    problems = all_violations(rows)
    if problems:
        print("\n추적성 위반:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
