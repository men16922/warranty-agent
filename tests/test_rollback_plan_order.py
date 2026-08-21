"""롤백 계획 — **언제 고정됐고 어디서 왔는가.**

Spec: specs/warranty/design/03-atomic-rollback.md (REQ-301)

⚠️ 이것도 값의 질문이 아니다. 계약은 루프 시작에 한 번 읽은 **얼어붙은 값**이라,
   `contract.rollback_plan`을 조치 뒤에 읽어도 **값은 하나도 안 바뀐다** — 판정도,
   트래픽 전환 대상도, 원장도 그대로다. 그래서 값을 보는 테스트로는 안 보인다.

실제로 재 보고 알았다 (T9-2):
  · M-60(계획을 **조치 뒤에** 읽는다)은 **살아남았다** — 144건 전부 초록이었다.
  · M-61(계획을 **계약 저장소에서 다시 읽는다**)은 red였다. 죽인 것은
    `test_req_301_...`의 `contracts.lookups == 1`이다 — 즉 지금까지 물어진 것은
    *"다시 조회하지 않는가"*뿐이고, *"조치 전에 고정되는가"*는 아무도 안 물었다.

그 둘은 같은 문장이 아니다. 재조회는 **오늘의 위반**이고, 묶이는 시점은 **내일의 위반을
막는 자리**다 — 계획이 조치 뒤에 묶여 있으면, 나중에 누가 `contract`를 조치 뒤에 다시
읽도록 고쳐도 그 자리는 **이미 조치 뒤**라 아무것도 어긋나 보이지 않는다.

⚠️ 설계와의 어긋남 하나를 알고 있다: design 03§2의 절차는 *"원장 항목에 고정"*이라고
   적는데 코드는 지역 이름에 묶는다. 그래서 여기서는 그 블록을 파싱하지 않고 **자리를
   AST로** 묻는다 — 설계를 고치는 것은 이 항목의 범위 밖이다(로그에 남겼다).
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REMEDIATE = ROOT / "src" / "warranty" / "usecases" / "remediate.py"

#: 게이트를 통과한 뒤의 루프 전체. 롤백 자체는 다른 메서드다.
LOOP_METHOD = "_execute_and_verify"
ROLLBACK_METHOD = "_rollback"

#: 계약에서 계획을 읽는 표현식 — `contract.rollback_plan`.
CONTRACT_PARAM = "contract"
PLAN_ATTR = "rollback_plan"

#: 조치를 실행하는 자리 · 계약 저장소를 다시 읽는 자리.
EXECUTOR_CALL = ("executor", "execute")
STORE_PORT = "contracts"


def _tree() -> ast.Module:
    return ast.parse(REMEDIATE.read_text(encoding="utf-8"), filename=str(REMEDIATE))


def _method(name: str) -> ast.FunctionDef:
    for node in ast.walk(_tree()):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{REMEDIATE.name}에서 `{name}`을 못 찾았다 — 루프가 옮겨졌다")


def _port_calls(scope: ast.AST, port: str, attr: str | None = None) -> list[ast.Call]:
    """`self.<port>.<attr>(...)` 호출 전부. `attr`가 `None`이면 그 포트의 호출 전부."""
    found: list[ast.Call] = []
    for node in ast.walk(scope):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Attribute):
            continue
        if func.value.attr != port:
            continue
        if attr is None or func.attr == attr:
            found.append(node)
    return found


def _self_calls(scope: ast.AST, method: str) -> list[ast.Call]:
    """`self.<method>(...)` 호출 전부."""
    return [
        node
        for node in ast.walk(scope)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
        and node.func.attr == method
    ]


def _plan_bindings(scope: ast.AST) -> list[tuple[str, int]]:
    """`<이름> = contract.rollback_plan` — `[(이름, 줄), ...]`."""
    bindings: list[tuple[str, int]] = []
    for node in ast.walk(scope):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if not isinstance(value, ast.Attribute) or value.attr != PLAN_ATTR:
            continue
        if not isinstance(value.value, ast.Name) or value.value.id != CONTRACT_PARAM:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                bindings.append((target.id, node.lineno))
    return bindings


# ── ⓪ 공허 통과 방지 ───────────────────────────────────────────────────────


def test_req_301_the_loop_is_actually_scanned() -> None:
    """Verifies: REQ-301

    스캐너가 아무것도 못 찾으면 아래 셋이 **전부 조용히 초록**이다.
    이 저장소는 같은 방식으로 세 번 속았다 (M-03·M-25·M-45).
    """
    loop = _method(LOOP_METHOD)
    assert _port_calls(loop, *EXECUTOR_CALL), (
        f"루프에서 `self.{EXECUTOR_CALL[0]}.{EXECUTOR_CALL[1]}(...)`를 못 찾았다 — "
        "조치 실행이 옮겨졌거나 스캐너가 깨졌다"
    )
    assert _self_calls(loop, ROLLBACK_METHOD), (
        f"루프에서 `self.{ROLLBACK_METHOD}(...)`를 못 찾았다 — 롤백 호출이 옮겨졌다"
    )
    assert _plan_bindings(loop), (
        f"루프에서 `... = {CONTRACT_PARAM}.{PLAN_ATTR}`를 못 찾았다 — "
        "계획이 계약에서 안 오거나 이름에 안 묶인다"
    )


# ── ① 시점 — 계획은 조치 **전에** 묶인다 (REQ-301) ─────────────────────────


def test_req_301_the_plan_is_bound_before_the_executor_is_called() -> None:
    """Verifies: REQ-301

    ★ **조치 뒤에 읽어도 값은 하나도 안 바뀐다** — 계약은 이미 얼어붙은 값이라 판정도
    트래픽 전환 대상도 그대로다. 그래서 M-60은 144건 전부 초록으로 살아남았다.

    ⚠️ 조치 후에 롤백 대상을 찾는 코드는 **바로 그 조치가 깨뜨린 상태에 의존**한다.
    지금은 우연히 안 그런 것이고, 묶이는 자리가 조치 뒤로 내려가는 순간 그 우연이 끝난다.
    """
    loop = _method(LOOP_METHOD)
    action = min(node.lineno for node in _port_calls(loop, *EXECUTOR_CALL))
    late = [(name, line) for name, line in _plan_bindings(loop) if line > action]
    assert not late, (
        f"롤백 계획이 조치({action}줄) **뒤에** 묶인다: {late} — "
        "조치 뒤에 찾은 계획은 그 조치가 깨뜨린 상태에서 온 것이다"
    )


# ── ② 출처 — 롤백은 그때 묶은 이름을 쓴다 · 다시 조회하지 않는다 ────────────


def test_req_301_the_rollback_uses_the_name_that_was_bound_before_the_action() -> None:
    """Verifies: REQ-301

    ⚠️ 시점만 묻고 출처를 안 물으면 우회가 남는다: 조치 전에 묶어 두고 **호출부에서
    `contract.rollback_plan`을 다시 써도** ①은 초록이다. 그러면 묶어 둔 이름은 장식이 된다.
    """
    loop = _method(LOOP_METHOD)
    bound = {name for name, _ in _plan_bindings(loop)}
    for call in _self_calls(loop, ROLLBACK_METHOD):
        args = [ast.unparse(arg) for arg in call.args]
        assert bound & set(args), (
            f"`{ROLLBACK_METHOD}`가 조치 전에 묶은 이름({sorted(bound)})을 안 받는다: {args}"
        )


def test_req_301_nothing_reads_the_contract_store_again_after_the_action() -> None:
    """Verifies: REQ-301

    ★ REQ-301의 측정 가능한 절반: **롤백에 필요한 추가 API 호출이 0이다.**
    (동적으로는 `contracts.lookups == 1`이 같은 것을 묻는다 — 여기서는 자리로 묻는다.)
    """
    loop = _method(LOOP_METHOD)
    action = min(node.lineno for node in _port_calls(loop, *EXECUTOR_CALL))
    after = [node.lineno for node in _port_calls(loop, STORE_PORT) if node.lineno > action]
    assert not after, (
        f"조치({action}줄) 뒤에 계약 저장소를 다시 읽는다: {after}줄 — "
        "그 계약은 조치가 바꾼 세상에서 온 것이고, 추가 API 호출은 0이어야 한다"
    )
    inside = [node.lineno for node in _port_calls(_method(ROLLBACK_METHOD), STORE_PORT)]
    assert not inside, f"`{ROLLBACK_METHOD}`가 계약 저장소를 읽는다: {inside}줄"
