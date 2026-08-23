"""REQ-805 — **상시 과금 컴퓨트를 만들지 않는다** (T11-2 · design 10§2).

Spec: specs/warranty/design/10-deployment.md §2 (REQ-805)

⛔ **이 요구사항은 지금까지 훑을 대상이 0개였다.** T11-1 전에는 배포 산출물이 아예 없었으니
   *"만들지 않는다"*는 문장을 맞댈 자리가 없었고, 그것은 위반이 없다는 뜻이 아니라
   **아무것도 안 봤다는 뜻**이다. 이 저장소가 세 번 속은 그 모양이다(M-03·M-25·M-45).
   T11-1이 매니페스트를 만들었으니 이제 집행할 수 있다.

⚠️ **`test_deploy_artifacts.py`가 이미 묻는 것과 다르다.** 그쪽 ④는 *"config가 선언한 것과
   design 10§2가 선언한 것이 같은가"*를 묻는다 — **둘을 함께 1로 바꾸면 초록이다.**
   그때 게이트 어디에도 *"0이어야 한다"*고 말하는 자리가 없다. 여기가 그 자리다:
   **일치가 아니라 값을 묻는다.** (M-97이 정확히 그 갈라짐을 태운다.)

묻는 것은 넷이다:
  ① 훑을 대상이 실재하고 스캐너가 **실제로 잡는가** (금지 목록 · 표본으로 태운다)
  ② 유휴 인스턴스 수가 **0인가** — 코드·렌더·설계 셋 다에서, 서로 맞는지가 아니라 **값으로**
  ③ 실행되는 표면(`Dockerfile`·`deploy.sh`·`Makefile`·렌더된 인자)이 GKE·VM·Cloud SQL을
     **만들지 않는가**
  ④ design 10§2의 구성 요소 표가 그것들을 **선언하지도 않는가**

⚠️ ④가 ③의 되풀이가 아닌 이유: 설계 표는 사람이 먼저 고치는 자리다. 거기에 GKE 행이
   생기고 스크립트가 아직 안 따라왔으면 ③은 초록이고, **그 상태로 사람이 콘솔에서 만든다.**
   ③은 스크립트가 만드는 것을, ④는 우리가 만들기로 **선언한** 것을 본다.

⚠️ 산문 금지 줄(design 10§2의 *"⛔ GKE 없음 · 상시 VM 없음 · Cloud SQL 없음"*)은 안 읽는다 —
   표 행만 읽는다. 산문을 스캔하면 **금지 문장 자신이 위반으로 잡힌다.**

⚠️ 상태를 안 올린다. 이 열이 태우는 것은 *"산출물이 무엇을 선언하는가"*이지
   *"실제로 0으로 수렴했는가"*가 아니다. 후자는 실물 배포(T2-2)의 증거이고, 여기 없다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from warranty.config import (
    MIN_INSTANCES,
    Adapters,
    Settings,
    deploy_argv,
)

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / "Dockerfile"
DEPLOY_SH = ROOT / "scripts" / "deploy.sh"
MAKEFILE = ROOT / "Makefile"
DESIGN = ROOT / "specs" / "warranty" / "design" / "10-deployment.md"

#: design 10§2의 구성 요소 표를 여는 표제. ⚠️ 바뀌면 파서가 **못 찾고 예외를 낸다** —
#: 0행을 읽고 ②·④를 공허하게 통과시키는 것보다 낫다(test_tunables.py와 같은 규칙).
COMPONENT_HEADING = "## 2. 구성 요소"

#: 표 행에서 `min-instances=<수>`를 읽는다. **값을 본다** — 일치가 아니라.
DESIGN_MIN_INSTANCES_RE = re.compile(r"min-instances=(\d+)")

#: ⛔ **유휴에도 도는 것을 만드는 명령들.** 이름이 아니라 **호출 모양**을 잡는다 —
#: 주석에 적힌 `Cloud SQL 안 씀`은 위반이 아니고, `gcloud sql instances create`는 위반이다.
BANNED: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "GKE",
        re.compile(r"gcloud\s+(?:alpha\s+|beta\s+)?container\b"),
        "노드 풀은 요청이 0이어도 돈다",
    ),
    (
        "Compute Engine VM",
        re.compile(r"gcloud\s+(?:alpha\s+|beta\s+)?compute\s+instances\b"),
        "VM은 끄기 전까지 시간당 과금이다",
    ),
    (
        "Cloud SQL",
        re.compile(r"gcloud\s+(?:alpha\s+|beta\s+)?sql\b"),
        "인스턴스는 질의가 없어도 과금이다",
    ),
    (
        "Cloud SQL 연결",
        re.compile(r"--add-cloudsql-instances\b"),
        "붙이려면 인스턴스가 이미 상시로 있어야 한다",
    ),
)

#: 금지 목록마다 **그 정규식이 아직 잡는지**를 태우는 표본. ⛔ 목록만 있고 표본이 없으면
#: 정규식 한 글자가 깨져도 스캔은 조용히 0건을 잡는다 — 그게 이 파일의 가장 값싼 죽음이다.
CONTROL_SAMPLES: dict[str, str] = {
    "GKE": "gcloud container clusters create demo --num-nodes=3",
    "Compute Engine VM": "gcloud compute instances create runner --zone=us-central1-a",
    "Cloud SQL": "gcloud sql instances create warranty-db --tier=db-f1-micro",
    "Cloud SQL 연결": "gcloud run deploy x --add-cloudsql-instances=proj:region:db",
}

#: 공허 통과 방지의 바닥. 하나라도 0이 되면 아래 검사는 **아무것도 안 보고** 초록이다.
MIN_BANNED = 4
MIN_DESIGN_ROWS = 5
MIN_DEPLOY_ARGS = 8

#: 설계가 선언조차 하면 안 되는 리소스의 표기. ④는 **표 행에서만** 이것을 찾는다.
BANNED_IN_DESIGN = ("GKE", "Cloud SQL", "Compute Engine", "VM")

#: 렌더러에 넣는 설정. ⚠️ 배포 값(서비스명·인스턴스 수)은 **하나도 여기 없다** — 그것들은
#: `warranty.config`에서 온다. 여기 있는 것은 이 테스트가 고른 프로젝트·리전뿐이라
#: 두 번째 출처가 아니다. `.env`를 안 읽는 이유는 REQ-802다(이 기계에서만 참인 초록 금지).
SAMPLE = Settings(
    project_id="warranty-hack",
    region="us-central1",
    model="gemini-3.7-flash",
    adapters=Adapters.LIVE,
    reconcile_deadline_days=3,
    billing_table=None,
)
SAMPLE_TAG = "abc1234"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _design_component_rows() -> tuple[tuple[str, ...], ...]:
    """design 10§2 구성 요소 표의 **데이터 행들**. 산문은 안 읽는다(모듈 상자 참조)."""
    text = _read(DESIGN)
    start = text.find(COMPONENT_HEADING)
    if start < 0:
        raise AssertionError(
            f"{DESIGN.name}에서 {COMPONENT_HEADING!r} 절을 못 찾았다 — 표제가 바뀌었다"
        )
    end = text.find("\n## ", start + 1)
    section = text[start:] if end < 0 else text[start:end]

    rows: list[tuple[str, ...]] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = tuple(cell.strip() for cell in line.strip("|").split("|"))
        if set("".join(cells)) <= set("-: ") or cells[0] == "리소스":
            continue
        rows.append(cells)
    return tuple(rows)


def _offenders(surfaces: dict[str, str]) -> list[str]:
    """훑은 표면들에서 금지 명령을 찾는다 → `표면: 라벨 (왜)` 목록."""
    return [
        f"{name}: {label} — {why}"
        for name, text in surfaces.items()
        for label, pattern, why in BANNED
        if pattern.search(text)
    ]


@pytest.fixture(scope="module")
def rendered() -> tuple[str, ...]:
    return deploy_argv(SAMPLE, SAMPLE_TAG)


@pytest.fixture(scope="module")
def surfaces(rendered: tuple[str, ...]) -> dict[str, str]:
    """**실제로 리소스를 만드는 표면들.** 여기 없는 것은 이 가드가 못 보는 자리다."""
    return {
        DOCKERFILE.name: _read(DOCKERFILE),
        DEPLOY_SH.name: _read(DEPLOY_SH),
        MAKEFILE.name: _read(MAKEFILE),
        "렌더된 인자": "gcloud " + " ".join(rendered),
    }


def test_the_scan_has_something_to_read_and_actually_catches_it(
    surfaces: dict[str, str], rendered: tuple[str, ...]
) -> None:
    """① 공허 통과 방지 — 목록이 비거나 정규식이 깨지면 ③은 **0건을 잡고** 초록이다.

    ⚠️ 표본을 두는 이유는 목록의 길이가 스캐너의 능력이 아니기 때문이다. 네 항목이
       그대로 있어도 정규식 한 글자가 어긋나면 잡는 것은 0건이고, 그 초록은
       *"위반이 없다"*가 아니라 *"찾을 줄 모른다"*이다.
    """
    assert len(BANNED) >= MIN_BANNED, (
        f"금지 목록이 {len(BANNED)}종이다 — 비면 ③은 아무것도 안 보고 초록이다"
    )
    assert {label for label, _, _ in BANNED} == set(CONTROL_SAMPLES), (
        "금지 항목과 표본이 짝이 안 맞는다 — 표본 없는 항목은 **잡는지 아무도 안 물은** 항목이다"
    )
    for label, sample in CONTROL_SAMPLES.items():
        hits = _offenders({"표본": sample})
        assert any(label in hit for hit in hits), (
            f"{label} 표본을 못 잡았다: {sample!r} — 정규식이 깨졌고, 그러면 ③은 늘 초록이다"
        )
    for name, text in surfaces.items():
        assert text.strip(), f"훑을 표면이 비어 있다: {name}"
    assert len(rendered) >= MIN_DEPLOY_ARGS, (
        f"렌더러가 인자를 {len(rendered)}개만 냈다 — ②가 공허하다"
    )
    assert len(_design_component_rows()) >= MIN_DESIGN_ROWS, (
        f"design 10§2에서 표 행을 {len(_design_component_rows())}개만 읽었다 — 파서가 깨졌다"
    )


def test_the_service_declares_zero_idle_instances(rendered: tuple[str, ...]) -> None:
    """② ⛔ **이 가드의 본체다.** 유휴 인스턴스 수가 **0인가** — 값으로 묻는다.

    Verifies: REQ-805

    ⚠️ `test_deploy_artifacts.py` ④는 config와 설계가 **같은지**를 묻는다. 둘을 함께 1로
       바꾸면 그것은 초록이고, 그때 *"0이어야 한다"*고 말하는 자리는 게이트에 없다.
       여기는 일치가 아니라 값을 묻는다 — **1은 그 순간부터 상시 과금이다.**
    """
    assert MIN_INSTANCES == 0, (
        f"`MIN_INSTANCES`가 {MIN_INSTANCES}다 — 0이 아닌 순간부터 요청이 없어도 과금이다"
    )
    assert "--min-instances=0" in rendered, (
        f"렌더된 인자가 유휴 0을 안 싣는다: {rendered} — 실린 값이 청구서가 보는 값이다"
    )

    declared = [
        (row[0], int(match.group(1)))
        for row in _design_component_rows()
        for cell in row
        for match in DESIGN_MIN_INSTANCES_RE.finditer(cell)
    ]
    assert declared, "design 10§2에서 `min-instances` 선언을 하나도 못 읽었다 — 표 모양이 바뀌었다"
    nonzero = [(name, value) for name, value in declared if value != 0]
    assert not nonzero, (
        f"design 10§2가 유휴 인스턴스를 선언한다: {nonzero} — "
        "설계와 코드가 함께 틀리면 일치 검사는 초록이다. 이 검사만 그것을 잡는다"
    )


def test_no_deployment_surface_creates_always_billed_compute(surfaces: dict[str, str]) -> None:
    """③ 실행되는 표면이 GKE·VM·Cloud SQL을 **만들지 않는가**.

    Verifies: REQ-805

    ⚠️ 이름이 아니라 호출 모양을 본다. 주석의 *"Cloud SQL 안 씀"*은 위반이 아니고,
       `gcloud sql instances create` 한 줄은 위반이다 — **후자만 청구서에 나온다.**
    ⛔ 배포는 게이트에 없다(design 10§5). 이 줄이 언제 생겼는지 물어 줄 두 번째 경로가
       없으니, 생기는 순간 잡는 자리는 여기 하나다.
    """
    offenders = _offenders(surfaces)
    assert not offenders, (
        f"배포 표면이 상시 과금 리소스를 만든다: {offenders} — "
        "REQ-805는 유휴 0을 약속했고, 이것들은 요청이 0이어도 돈다"
    )


def test_the_design_does_not_even_declare_always_billed_resources() -> None:
    """④ design 10§2의 구성 요소 표가 그것들을 **선언하지도 않는가**.

    ⚠️ ③의 되풀이가 아니다. 설계 표는 사람이 **먼저** 고치는 자리다 — 거기 GKE 행이 생기고
       스크립트가 아직 안 따라왔으면 ③은 초록이고, 그 상태로 사람이 콘솔에서 만든다.
       그리고 손으로 만든 리소스는 계약이 없어서 자동 조치의 대상도 아니다(OVERVIEW §12).
    """
    offenders = [
        f"{row[0]!r}: {token}"
        for row in _design_component_rows()
        for token in BANNED_IN_DESIGN
        if token in " ".join(row)
    ]
    assert not offenders, (
        f"design 10§2가 상시 과금 리소스를 구성 요소로 선언한다: {offenders} — "
        "⛔ 설계의 금지 줄(*GKE 없음 · 상시 VM 없음 · Cloud SQL 없음*)과 표가 어긋났다"
    )
