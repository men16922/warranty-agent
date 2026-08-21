"""검증 절차 — **순서와 출처가 설계가 적은 그대로인가.**

Spec: specs/warranty/design/02-verification.md (REQ-201, REQ-202, REQ-203)

⚠️ 이 셋은 값의 질문이 아니다. 기준선·재측정·판정에 **맞는 값이 들어 있는가**는
   순서를 뒤집어도, 질의를 새로 만들어도, 기준을 조치가 들고 있어도 **그대로 통과한다.**
   각본 신호는 순서대로 같은 값을 돌려주고, 계약의 기준과 같은 값을 박아 두면 판정도 같다.
   물어야 할 것은 *"그 값이 언제·무엇에서 왔는가"*다 (T0-10 · M-44 계열).

실제로 재 보고 알았다 (T9-1):
  · M-59(판정 기준을 **조치가 들고 있다**)는 **살아남았다** — 141건 전부 초록이었다.
  · M-57(기준선을 **조치 뒤에** 잰다)은 red였지만, 죽인 것은 REQ-201의 가드가 아니라
    **예산 예약 해제 테스트**였다(REQ-405). 우연히 걸린 하중은 다음 리팩터에 사라진다.

⚠️ 절차를 여기 베껴 두지 않는다 — design 02§2의 절차 블록을 **파싱해서** 읽는다.
   베껴 두면 설계가 순서를 바꿔도 사본은 안 따라오고 게이트는 초록이다(T0-10의 교훈).
   여기 있는 것은 **설계의 이름 ↔ 코드의 호출** 대응뿐이고, 설계가 이 테스트가 모르는
   단계를 말하면 **파서가 소리 내어 실패한다** (조용히 0단계를 읽는 것보다 낫다).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REMEDIATE = ROOT / "src" / "warranty" / "usecases" / "remediate.py"
DESIGN = ROOT / "specs" / "warranty" / "design" / "02-verification.md"

#: 절차를 여는 표제. ⚠️ 바뀌면 파서가 **못 찾고 예외를 낸다**
#: (test_provision_contract.py와 같은 규칙 — 조용히 0단계를 읽는 것보다 낫다).
DESIGN_SECTION = "## 2. 절차"

#: `① baseline  = read(contract.health_signal)` / `② execute` / `③ wait VERIFY_DELAY`
#: ⚠️ 공백은 `\s`가 아니라 `[ \t]`다. `\s*`는 **줄바꿈을 먹는다** — 인자 없는 단계(`② execute`)
#:    뒤에서 다음 줄머리를 삼켜 버려 바로 다음 단계가 `^`를 못 만나고 **조용히 빠졌다**.
#:    실제로 났다: 다섯 단계 중 `③ wait`가 사라진 채 파서가 4를 돌려줬다.
DESIGN_STEP_RE = re.compile(
    r"^[ \t]*[①②③④⑤⑥⑦⑧⑨][ \t]*(?:\w+[ \t]*=[ \t]*)?(\w+)[ \t]*(?:\(([^)]*)\))?", re.MULTILINE
)

#: 설계가 부르는 이름 ↔ 코드가 실제로 부르는 자리. **이 대응만이 손으로 적은 것이다.**
#: 포트 이름이 `None`이면 모듈 수준 함수(`classify`)다.
DESIGN_VERB_BY_CALL: dict[tuple[str | None, str], str] = {
    ("signals", "read"): "read",
    ("executor", "execute"): "execute",
    ("clock", "sleep"): "wait",
    (None, "classify"): "judge",
}

#: 루프 전체가 들어 있는 메서드. 롤백 뒤의 재측정(REQ-304)은 다른 메서드라 여기 안 섞인다.
LOOP_METHOD = "_execute_and_verify"

#: 공허 통과 방지의 바닥. 절차 블록을 0단계로 읽으면 아래 단언이 전부 조용히 참이 된다.
MIN_DESIGN_STEPS = 5


def _design_section() -> str:
    text = DESIGN.read_text(encoding="utf-8")
    start = text.find(DESIGN_SECTION)
    if start < 0:
        raise AssertionError(f"design 02의 절차 절을 못 찾았다: {DESIGN_SECTION!r}")
    end = text.find("\n## ", start + 1)
    return text[start:] if end < 0 else text[start:end]


def _design_steps() -> list[tuple[str, tuple[str, ...]]]:
    """design 02§2가 선언한 절차 — `[(단계 이름, 인자 표현식들), ...]`."""
    steps: list[tuple[str, tuple[str, ...]]] = []
    for verb, raw in DESIGN_STEP_RE.findall(_design_section()):
        args = tuple(part.strip() for part in raw.split(",") if part.strip())
        steps.append((verb, args))
    return steps


def _sink_verb(node: ast.Call) -> str | None:
    """이 호출이 설계의 어느 단계인가. 아니면 `None`."""
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
        return DESIGN_VERB_BY_CALL.get((func.value.attr, func.attr))
    if isinstance(func, ast.Name):
        return DESIGN_VERB_BY_CALL.get((None, func.id))
    return None


def _loop_body() -> ast.FunctionDef:
    tree = ast.parse(REMEDIATE.read_text(encoding="utf-8"), filename=str(REMEDIATE))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == LOOP_METHOD:
            return node
    raise AssertionError(f"{REMEDIATE.name}에서 `{LOOP_METHOD}`를 못 찾았다 — 루프가 옮겨졌다")


def _code_steps() -> list[tuple[str, tuple[str, ...]]]:
    """루프가 실제로 타는 절차 — **소스 순서대로.**

    ⚠️ `ast.walk`는 순서를 보장하지 않는다. 순서가 이 테스트의 절반이라 위치로 정렬한다.
    """
    found: list[tuple[int, int, str, tuple[str, ...]]] = []
    for node in ast.walk(_loop_body()):
        if not isinstance(node, ast.Call):
            continue
        verb = _sink_verb(node)
        if verb is None:
            continue
        args = tuple(ast.unparse(arg) for arg in node.args)
        found.append((node.lineno, node.col_offset, verb, args))
    return [(verb, args) for _, _, verb, args in sorted(found)]


# ── ⓪ 공허 통과 방지 ───────────────────────────────────────────────────────


def test_req_201_the_design_procedure_is_actually_read() -> None:
    """Verifies: REQ-201, REQ-202, REQ-203

    파서가 0단계를 읽으면 아래 두 검사가 **아무것도 안 묻고 초록**이다.
    이 저장소는 같은 방식으로 두 번 속았다 (M-03·M-25·M-45).
    """
    steps = _design_steps()
    assert len(steps) >= MIN_DESIGN_STEPS, (
        f"design 02§2의 절차를 {len(steps)}단계만 읽었다 (최소 {MIN_DESIGN_STEPS}): {steps} — "
        "절차 블록이 줄었거나 파서가 깨졌다"
    )
    unknown = sorted({verb for verb, _ in steps} - set(DESIGN_VERB_BY_CALL.values()))
    assert not unknown, (
        f"설계가 이 테스트가 모르는 단계를 말한다: {unknown} — "
        "대응을 안 적으면 그 단계는 **검사에서 조용히 빠진다**"
    )
    assert len(_code_steps()) >= MIN_DESIGN_STEPS, (
        f"루프에서 절차 호출을 {len(_code_steps())}개만 찾았다 — 스캐너가 깨졌거나 루프가 옮겨졌다"
    )


# ── ① 순서 — 기준선은 조치 **전에** 잰다 (REQ-201) ─────────────────────────


def test_req_201_the_loop_runs_the_steps_in_the_order_the_design_declares() -> None:
    """Verifies: REQ-201, REQ-202

    ★ **기준선을 조치 뒤에 재도 값은 하나도 안 바뀐다.** 각본 신호는 순서대로 같은 값을
    돌려주고 판정도 그대로다 — 바뀌는 것은 *"그 값이 무엇의 기준선인가"*뿐이고,
    그 어긋남은 값으로 안 보인다 (M-57).

    ⛔ M-57은 red였지만 죽인 것은 REQ-405의 예약 해제 테스트였다. **우연한 하중은
       가드가 아니다** — 그 테스트가 바뀌면 REQ-201은 아무도 안 지키는 문장이 된다.
    """
    design = [verb for verb, _ in _design_steps()]
    code = [verb for verb, _ in _code_steps()]
    assert code == design, (
        f"루프의 절차 순서가 design 02§2와 다르다: 설계 {design} · 코드 {code} — "
        "조치 뒤에 잰 값은 기준선이 아니다"
    )


# ── ② 출처 — 재측정의 질의와 판정의 기준은 **계약에서 온다** (REQ-202·203) ──


def test_req_203_every_step_takes_the_expression_the_design_names() -> None:
    """Verifies: REQ-202, REQ-203

    ★ **이 태스크의 한 줄 수용 기준이다.** 설계는 각 단계가 무엇을 **인자로 받는지**
    이름으로 적어 뒀다 — `read(contract.health_signal)` · `judge(..., contract.recovery_criterion)`.
    값이 맞는지가 아니라 **어디서 왔는지**를 묻는다.

    ⛔ M-59는 이 가드가 없을 때 **141건 전부 초록으로 살아남았다.** 판정 기준을 조치가
       들고 있어도 계약의 기준과 값이 같으면 아무 테스트도 말하지 않는다 — 그리고 그
       순간부터 계약이 기준을 바꿔도 판정은 안 바뀐다. **모든 조치가 자기 기준으로 성공한다.**
    ⚠️ 재측정 쪽(REQ-202)은 같은 이유로 함께 걸린다: 두 `read`가 **같은 표현식**을 타야
       한다. 두 곳에서 각자 질의를 만들면 언젠가 다른 걸 잰다(design 02§2).
    """
    design = _design_steps()
    code = _code_steps()
    assert len(code) == len(design), f"단계 수가 다르다: 설계 {len(design)} · 코드 {len(code)}"

    mismatched = [
        f"{i + 1}단계 {verb}: 설계 {list(want)} · 코드 {list(got)}"
        for i, ((verb, want), (_, got)) in enumerate(zip(design, code, strict=True))
        if want and want != got
    ]
    assert not mismatched, (
        f"설계가 이름 붙인 출처를 안 타는 단계: {mismatched} — 그 자리는 계약이 바뀌어도 안 바뀐다"
    )
