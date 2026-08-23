"""모델 id 사본 집행 — **선언들이 서로 어긋나지 않는가** (T12-6 · REQ-802).

Spec: specs/warranty/design/06-agent-runtime.md §2 (REQ-802)

⛔ `gemini-3.7-flash`가 지금 **일곱 파일**에 산다(`.env.example` · design 06 둘 · 테스트 픽스처
   다섯). 태스크는 *"네 곳"*이라고 적었고 **손으로 센 그 숫자가 틀렸다** — T0-5와 같은 자리다
   (*"손 목록은 가드가 아니다"*). 지금까지 그 사본들을 맞대는 자리는 **하나도 없었다.**

⚠️ **`config.py`는 `WR_MODEL`을 환경에서 요구한다**(기본값 없음 · 일부러 그렇다).
   그래서 여기서 묻는 것은 *"런타임 기본값이 하나인가"*가 아니라
   **"선언들이 서로 어긋나지 않는가"**다. 값의 출처는 `.env.example`의 `WR_MODEL` 하나이고,
   실패 메시지가 **어느 쪽을 고칠지** 정한다 (T11-5 ②가 먼저 쓴 규칙).

⛔ **왜 게이트가 이것을 못 보고 있었나**: 모델 id가 틀려도 게이트는 초록이다. 그 사실은
   빌드에서도 테스트에서도 안 보이고 **실물 호출에서 404로** 온다 — T2-1이 Vertex location에서
   정확히 그렇게 다쳤다(M-157·M-158). 사본이 늘어날수록 그 404는 늦게 온다.

넷을 묻는다:
  ① 스캐너가 **실제로 읽고 가르는가** (표본으로 태운다 · 바닥)
  ② 선언들이 **서로 같은가** — 화살표 없는 자리는 전부 지금 이름이어야 한다
  ③ 갱신 기록(`옛 id → 새 id`)의 **오른쪽이 지금 이름인가**
  ④ 그 이름이 **대회 요건의 바닥을 넘는가** (일치가 아니라 **값**)

⚠️ ④가 ②의 되풀이가 아닌 이유: **일곱 곳을 함께 낮추면 ②는 초록이다.** 그때 게이트 어디에도
   *"3.5 이상이어야 한다"*고 말하는 자리가 없다 — REQ-601은 대회 필수 요건이고, 그것을 값으로
   묻는 자리는 여기 하나다. (M-97이 `min-instances`에 대해 먼저 태운 갈라짐과 같은 계열이다.)

⚠️ ③이 필요한 이유: 은퇴한 이름이 살아 있어도 되는 자리는 **갱신 기록 한 줄뿐이다.**
   그 줄을 통째로 면제하면 기록의 오른쪽이 낡아도 아무도 안 본다 — 그러면 설계 문서가
   *"우리는 X를 쓴다"*고 말하는데 배포는 Y로 나간다.

⚠️ **`docs/evidence/`는 일부러 안 훑는다.** 증거는 과거의 사실이고, 지금 값에 맞춰 고치면
   그건 증거가 아니라 창작이다(T12-8이 쓴 규칙). `specs/warranty/tasks.md`도 같은 이유로 뺐다 —
   거기 적힌 id는 *그때 몇 곳이었나*의 기록이다.

⚠️ 산문의 표시 이름(*"Gemini 3.7 Flash"*)은 안 본다 — id 표기(`gemini-3.7-flash`)만 본다.
   ⛔ 그래서 **표시 이름이 따로 썩는 것은 이 가드가 못 잡는다**(PRINCIPLES #3). 적어 둔다.

⚠️ **상태를 안 올리고 `Verifies:`도 안 붙였다** — 이 열이 태우는 것은 *"선언이 서로 맞는가"*이지
   *"그 모델이 우리 Vertex 경로에서 유효한가"*가 아니다. 후자는 실물 호출이고 REQ-601이 갖는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = ROOT / ".env.example"
REQUIREMENTS = ROOT / "specs" / "warranty" / "requirements.md"

#: ⛔ **이 파일 자신은 안 본다** — 표본이 *일부러 틀린* id를 담기 때문이다.
#:    대가는 구멍 하나다: 여기에 어긋난 사본을 적으면 아무도 안 잡는다. 적지 마라.
SELF = Path(__file__).name

#: 훑는 곳. ⚠️ 파일 목록이 아니라 **뿌리**다 — 새 사본이 어디에 생기든 자동으로 훑힌다.
#:    손으로 적은 목록은 T0-5가 보여 준 대로 **다섯이라 적고 여섯인** 채로 썩는다.
SCAN_ROOTS = (
    ENV_EXAMPLE,
    ROOT / "specs" / "warranty" / "design",
    ROOT / "src",
    ROOT / "tools",
    ROOT / "tests",
)
SCAN_SUFFIXES = (".py", ".md")

#: id 표기만 잡는다. ⚠️ 산문의 `Gemini 3.x`·`Gemini 3.7 Flash`는 **일부러 안 잡는다** —
#:    산문을 스캔하면 영어 문장을 고칠 때마다 게이트가 red고, 그런 가드는 꺼진다(T11-5).
MODEL_ID_RE = re.compile(r"gemini-\d+(?:\.\d+)*-[a-z][a-z0-9-]*")
#: 값의 출처. ⚠️ `config.py`에 기본값이 없으니 **커밋된 견본이 가장 가까운 선언**이다.
WR_MODEL_RE = re.compile(r"^WR_MODEL=(\S+)$", re.MULTILINE)
#: 대회 요건이 적은 바닥. 하드코딩한 상수가 썩는 것을 이 정규식이 막는다(④의 뒷절반).
FLOOR_RE = re.compile(r"Gemini (\d+)\.(\d+) 이상")
VERSION_RE = re.compile(r"^gemini-(\d+)\.(\d+)")
#: 갱신 기록 — `옛 id → 새 id`. **은퇴한 이름이 살아 있어도 되는 유일한 자리다.**
ARROW = "→"

#: ⛔ **값이다** — 일곱 곳을 함께 낮추면 ②는 초록이고, 그때 이 상수만 red를 낸다.
#:    출처는 REQ-601(대회 필수)이고, 아래 ④가 요구사항 원문과 이 값을 맞댄다.
MODEL_FLOOR = (3, 5)

#: 공허 통과 방지의 바닥. 스캔 뿌리가 하나 빠지거나 정규식이 깨지면 ②·③·④가
#: **아무것도 안 보고** 초록이 된다 — 이 저장소가 같은 방식으로 여러 번 속았다(M-03·M-25·M-45).
MIN_DECLARATION_FILES = 5
MIN_DECLARATIONS = 6


@dataclass(frozen=True, slots=True)
class Scan:
    """훑은 결과. **두 값이 각각 다른 질문에 답한다.**

    ⚠️ 선언과 기록을 한 통에 담으면 갱신 기록의 은퇴한 이름이 *어긋난 사본*으로 잡히고,
       그것을 면제하려고 줄 전체를 빼면 이번엔 **기록의 오른쪽이 낡아도 조용하다.**
    """

    #: `파일:줄` → id. **지금 이름이어야 하는** 자리들.
    declarations: tuple[tuple[str, str], ...]
    #: `파일:줄` → (은퇴한 id들, 지금이라고 말하는 id).
    history: tuple[tuple[str, tuple[str, ...], str], ...]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def scan_text(label: str, text: str) -> Scan:
    """한 파일을 선언과 갱신 기록으로 가른다.

    ⚠️ 화살표는 **마지막 것으로** 가른다(`A → B → C`면 지금 이름은 `C`다).
    ⚠️ 화살표가 있어도 한쪽에 id가 없으면 갱신 기록이 아니라 **선언으로 본다** —
       이 스캐너는 일부러 **더 세는 쪽으로** 틀린다. 덜 세면 어긋난 사본이 조용히 산다.
    """
    declarations: list[tuple[str, str]] = []
    history: list[tuple[str, tuple[str, ...], str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        found = MODEL_ID_RE.findall(line)
        if not found:
            continue
        where = f"{label}:{number}"
        head, arrow, tail = line.rpartition(ARROW)
        retired = tuple(MODEL_ID_RE.findall(head)) if arrow else ()
        current = MODEL_ID_RE.findall(tail) if arrow else []
        if retired and current:
            history.append((where, retired, current[0]))
            declarations.extend((where, extra) for extra in current[1:])
        else:
            declarations.extend((where, one) for one in found)
    return Scan(tuple(declarations), tuple(history))


def _scanned_files() -> dict[str, str]:
    """훑을 파일들. ⚠️ 이 파일 자신은 뺀다(모듈 상자 참조)."""
    out: dict[str, str] = {}
    for root in SCAN_ROOTS:
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if path.name == SELF or not path.is_file():
                continue
            if root.is_dir() and path.suffix not in SCAN_SUFFIXES:
                continue
            out[str(path.relative_to(ROOT))] = _read(path)
    return out


def scan_repo() -> Scan:
    declarations: list[tuple[str, str]] = []
    history: list[tuple[str, tuple[str, ...], str]] = []
    for label, text in _scanned_files().items():
        scan = scan_text(label, text)
        declarations.extend(scan.declarations)
        history.extend(scan.history)
    return Scan(tuple(declarations), tuple(history))


def declared_model() -> str:
    """`.env.example`의 `WR_MODEL`. ⚠️ 못 읽으면 **예외다** — 0개를 읽고 아래를 공허하게
    통과시키는 것보다 낫다(`test_tunables.py`가 먼저 쓴 규칙)."""
    match = WR_MODEL_RE.search(_read(ENV_EXAMPLE))
    if match is None:
        raise AssertionError(
            f"{ENV_EXAMPLE.name}에서 `WR_MODEL=<id>` 줄을 못 읽었다 — "
            "값의 출처가 사라졌다. 이 가드는 그 한 줄을 기준으로 나머지를 맞댄다."
        )
    return match.group(1)


def _version(model: str) -> tuple[int, int]:
    match = VERSION_RE.match(model)
    if match is None:
        raise AssertionError(
            f"선언된 모델 id에서 버전을 못 읽었다: {model!r} — "
            "`gemini-<major>.<minor>-<이름>` 표기가 아니면 대회 요건의 바닥과 맞댈 수 없다."
        )
    return int(match.group(1)), int(match.group(2))


# ── ① 스캐너를 표본으로 태운다 ──────────────────────────────────────────────

#: ⚠️ 표본은 **실패해야 하는 것들을 일부러 담는다** — 산문의 `Gemini 3.x`, 표시 이름
#:    `Gemini 3.7 Flash`, 그리고 갱신 기록의 **은퇴한 이름**. 셋이 안 갈리면 아래 셋은
#:    판정이 아니다. 스캐너를 스캐너로 검사할 수는 없고, **기대값이 박힌 표본**이 유일한
#:    바닥이다 (M-105·M-118·M-121이 먼저 쓴 규칙).
SAMPLE = """\
### 모델 갱신 — `gemini-3.5-flash` → `gemini-3.7-flash` (2026-08-23)
WR_MODEL=gemini-3.7-flash
     model: gemini-3.7-flash (Vertex AI)
Gemini 3.x는 Vertex에서 global에만 있다 — Gemini 3.7 Flash도 그렇다
    model="gemini-2.5-flash",
"""


def test_scanner_splits_declarations_from_the_update_record() -> None:
    """① 스캐너가 산문을 버리고, 갱신 기록의 **양쪽을 따로** 읽는가."""
    scan = scan_text("표본", SAMPLE)
    assert scan.declarations == (
        ("표본:2", "gemini-3.7-flash"),
        ("표본:3", "gemini-3.7-flash"),
        ("표본:5", "gemini-2.5-flash"),
    ), (
        f"표본에서 뽑힌 선언이 기대와 다르다: {scan.declarations}. "
        "산문의 `Gemini 3.x`/`Gemini 3.7 Flash`가 섞였거나, 갱신 기록의 은퇴한 이름을 "
        "선언으로 셌거나, id 정규식이 깨졌다."
    )
    assert scan.history == (("표본:1", ("gemini-3.5-flash",), "gemini-3.7-flash"),), (
        f"표본에서 뽑힌 갱신 기록이 기대와 다르다: {scan.history}. "
        "화살표를 안 갈랐으면 은퇴한 이름이 어긋난 사본으로 잡힌다."
    )


def test_there_is_enough_to_judge() -> None:
    """① 바닥 — 0개를 훑는 초록은 *'다 맞다'*가 아니라 **'아무것도 안 봤다'**이다.

    ⚠️ 이 가드가 죽는 가장 값싼 길은 스캔 뿌리가 하나 빠지는 것이다. 그러면 사본 다섯이
       검사 밖으로 나가고 남은 둘이 서로 같아서 ②는 **초록이다.**
    """
    scan = scan_repo()
    files = {where.rsplit(":", 1)[0] for where, _ in scan.declarations}
    assert len(files) >= MIN_DECLARATION_FILES, (
        f"모델 id를 선언한 파일을 {len(files)}개만 읽었다 (최소 {MIN_DECLARATION_FILES}): "
        f"{sorted(files)} — 스캔 뿌리가 빠졌거나 id 정규식이 깨졌다."
    )
    assert len(scan.declarations) >= MIN_DECLARATIONS, (
        f"모델 id 선언을 {len(scan.declarations)}개만 읽었다 (최소 {MIN_DECLARATIONS}) — "
        "②가 맞댈 것이 없다."
    )
    assert declared_model(), "값의 출처가 비었다 — `.env.example`의 `WR_MODEL`이 없다."


# ── ② 선언들이 서로 같은가 ─────────────────────────────────────────────────


def test_every_declaration_names_the_same_model() -> None:
    """② ⛔ **이 가드의 본체다.** 한 곳만 바꾸면 red다.

    ⚠️ 고칠 방향을 실패 메시지가 정한다 — **값의 출처는 `.env.example`의 `WR_MODEL` 하나**이고,
       나머지는 그것을 따라온다. 방향을 안 정하면 다음 사람은 *더 쉬운 쪽*을 고치고,
       그 쪽이 배포되는 값일 수도 있다.
    """
    declared = declared_model()
    scan = scan_repo()
    stale = sorted({(where, model) for where, model in scan.declarations if model != declared})
    assert not stale, (
        f"모델 id 선언이 `.env.example`의 `WR_MODEL`({declared})과 다르다: {stale}. "
        "값의 출처는 그 한 줄이다 — 모델을 바꿨다면 사본들도 같이 바꾼다. "
        "은퇴한 이름을 남기려면 `옛 id → 새 id` 갱신 기록으로만 적는다."
    )


# ── ③ 갱신 기록이 지금 이름을 가리키는가 ───────────────────────────────────


def test_the_update_record_points_at_the_current_model() -> None:
    """③ 은퇴한 이름이 사는 유일한 자리 — 그 줄의 **오른쪽이 지금 이름인가.**

    ⚠️ ②의 되풀이가 아니다. ②는 갱신 기록 줄을 **안 본다**(안 그러면 은퇴한 이름 자체가
       위반으로 잡힌다). 그 면제를 그대로 두면 설계 문서가 *"우리는 X를 쓴다"*고 말하는데
       배포는 Y로 나가고, **그 어긋남을 아무도 안 본다.**
    ⚠️ 왼쪽이 지금 이름과 같은 기록은 갱신이 아니다(*"X → X"*) — 그런 줄은 면제를
       공짜로 얻는 자리가 된다.
    """
    declared = declared_model()
    scan = scan_repo()
    stale = [(where, current) for where, _, current in scan.history if current != declared]
    assert not stale, (
        f"갱신 기록이 가리키는 이름이 지금 선언({declared})과 다르다: {stale}. "
        "모델을 바꿨으면 기록도 `옛 id → 새 id`로 이어 적는다 — 낡은 기록은 기록이 아니라 오보다."
    )
    circular = [(where, retired) for where, retired, _ in scan.history if declared in retired]
    assert not circular, (
        f"갱신 기록의 **은퇴한 쪽**이 지금 이름이다: {circular} — "
        "그 줄은 갱신이 아니고, 면제만 공짜로 얻는다."
    )


# ── ④ 그 이름이 대회 요건의 바닥을 넘는가 (값) ─────────────────────────────


def test_the_declared_model_clears_the_contest_floor() -> None:
    """④ ⛔ **일곱 곳을 함께 낮추면 ②는 초록이다.** 여기만 그것을 잡는다.

    ⚠️ 바닥을 상수로 박아 두면 그 상수가 따로 썩는다 — 그래서 요구사항 원문(REQ-601)이
       적은 숫자와 맞댄다. 두 출처가 갈라지면 red고, 고칠 것은 *둘 중 하나*가 아니라
       **대회 요건을 다시 읽는 것**이다.
    """
    written = {(int(major), int(minor)) for major, minor in FLOOR_RE.findall(_read(REQUIREMENTS))}
    assert written == {MODEL_FLOOR}, (
        f"요구사항이 적은 바닥 {sorted(written)}과 이 가드의 상수 {MODEL_FLOOR}가 다르다 — "
        "대회 요건이 바뀌었거나 한쪽이 썩었다."
    )
    declared = declared_model()
    assert _version(declared) >= MODEL_FLOOR, (
        f"선언된 모델이 {declared}다. REQ-601이 요구하는 바닥은 "
        f"Gemini {MODEL_FLOOR[0]}.{MODEL_FLOOR[1]} 이상이고, "
        "그 아래는 **대회 필수 요건 위반**이다 — 선언들이 서로 같은 것만으로는 못 잡는다."
    )
