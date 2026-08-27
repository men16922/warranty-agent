"""아키텍처 다이어그램 제출 표면 — **원본 하나를 직접 가리키는가** (T13-4 · REQ-901).

Spec: specs/warranty/requirements.md (REQ-901)

REQ-901은 독립 아키텍처 다이어그램을 요구한다. 새 그림을 만들지 않는다. 이미
`docs/OVERVIEW.md` §4에 있는 Mermaid가 권위이고, README의 제출 표면은 그 앵커를 직접
가리킨다. 같은 Mermaid를 다른 문서에 복사하면 둘이 따로 썩으므로 red다.

⛔ 여기서 REQ-901을 VERIFIED로 올리지 않는다. 영상·저장소 URL·실물 실행의 시각 증거는
여전히 사람 판정이다. 이 테스트가 묻는 것은 오프라인에서 판정할 수 있는 세 가지뿐이다:
링크가 정확한가 · 그 앵커에 Mermaid가 있는가 · 그 Mermaid의 출처가 하나인가.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
OVERVIEW = ROOT / "docs" / "OVERVIEW.md"
TASKS = ROOT / "specs" / "warranty" / "tasks.md"
EXPECTED_TARGET = "docs/OVERVIEW.md#4-아키텍처"
EXPECTED_LABEL = "Architecture diagram"
EXPECTED_LINK_TEXT = "System architecture"

LINK_RE = re.compile(r"\[([^]\n]+)\]\(([^)\s]+)\)")
MERMAID_RE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _architecture_section(text: str) -> str:
    match = re.search(r"^## 4\. 아키텍처\n(.*?)(?=^## 5\.)", text, re.MULTILINE | re.DOTALL)
    assert match is not None, "OVERVIEW의 `## 4. 아키텍처` 섹션이 사라졌다."
    return match.group(1)


def _markdown_paths() -> list[Path]:
    return [
        README,
        *(ROOT / "docs").rglob("*.md"),
        *(ROOT / "specs").rglob("*.md"),
    ]


def test_readme_exposes_the_canonical_architecture_link() -> None:
    """제출 진입점은 일반 문서가 아니라 **선택한 다이어그램 앵커**를 이름으로 가리킨다."""
    readme = _read(README)
    assert f"| **{EXPECTED_LABEL}** |" in readme, f"README에 {EXPECTED_LABEL!r} 항목이 없다."
    links = LINK_RE.findall(readme)
    matches = [target for label, target in links if label == EXPECTED_LINK_TEXT]
    assert matches == [EXPECTED_TARGET], (
        f"README의 {EXPECTED_LABEL!r} 링크가 권위 앵커 하나를 가리켜야 한다: {matches}."
    )


def test_pointer_resolves_to_one_architecture_mermaid() -> None:
    """링크의 파일과 앵커가 살아 있고, 그 섹션에 렌더할 Mermaid가 정확히 하나인가."""
    relative_path, anchor = EXPECTED_TARGET.split("#", 1)
    assert (ROOT / relative_path).is_file(), f"다이어그램 원본 파일이 없다: {relative_path}"
    assert anchor == "4-아키텍처", f"제출 링크가 아키텍처 앵커가 아니다: {anchor}"
    blocks = MERMAID_RE.findall(_architecture_section(_read(OVERVIEW)))
    assert len(blocks) == 1, f"§4 아키텍처 Mermaid는 하나여야 한다: {len(blocks)}개"
    assert blocks[0].startswith("flowchart TB\n"), "§4가 시스템 아키텍처 flowchart가 아니다."


def test_architecture_mermaid_has_one_source() -> None:
    """권위 블록의 정확한 사본이 생기면 두 파일이 따로 썩기 전에 red다."""
    canonical = MERMAID_RE.findall(_architecture_section(_read(OVERVIEW)))[0]
    fenced = f"```mermaid\n{canonical}```"
    owners = [path.relative_to(ROOT) for path in _markdown_paths() if fenced in _read(path)]
    assert owners == [Path("docs/OVERVIEW.md")], (
        f"아키텍처 Mermaid의 출처는 docs/OVERVIEW.md 하나여야 한다: {owners}"
    )


def test_uniqueness_scan_covers_submission_documents() -> None:
    """공허 통과 방지 — README나 계획을 스캔 밖으로 빼면 '사본 없음'을 말할 수 없다."""
    paths = set(_markdown_paths())
    required = {README, OVERVIEW, TASKS}
    assert required <= paths, f"다이어그램 사본 스캔에서 빠진 제출 문서: {required - paths}"
