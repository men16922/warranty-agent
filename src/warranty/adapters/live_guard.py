"""라이브 어댑터 생성 tripwire — **G5의 관측 지점** (T12-5 · REQ-801).

Spec: specs/warranty/design/09-quality-gate.md §3.2 (G5 · REQ-801)

⛔ *"게이트는 이것을 안 부른다"*는 지금까지 **도크스트링의 문장**이었다
   (`adk_agent.build_agent`·`build_runner`가 그렇게 적어 두었다). 문장은 집행이 아니다 —
   어느 테스트가 내일 그것을 부르기 시작해도 게이트는 아무 말도 안 한다. 그리고 그 순간
   게이트는 네트워크에 나가고 **과금한다.** REQ-801이 약속한 것은 정확히 그 반대다.

⚠️ **묻는 것은 *"임포트가 없다"*가 아니라 *"생성이 없다"*다.** 라이브 어댑터는 지연 임포트
   뒤에 산다 — REQ-801이 그렇게 강제한다(게이트 venv에 `google-adk`가 없다). 그래서
   *"최상위에 `google`이 없다"*는 **배선이 전부 살아 있어도 참**이고, 그 초록은 아무것도
   안 본 초록이다(M-146·M-148이 태운 자리). ⇒ 관측 지점을 임포트가 아니라
   **생성 경로의 입구**에 둔다.

⚠️ **기본값은 안 걸린 상태다.** 거는 곳은 게이트 하나(`tests/conftest.py`)이고, 배포된
   프로세스는 이 tripwire를 안 건다 — 걸면 실물이 자기 자신을 못 만든다.
   ⛔ 그러니 *"안 걸렸다"*는 정상이 아니라 **게이트에서만 비정상**이고, 그것을 묻는 자리가
   `tests/test_live_adapter_guard.py` ③이다. 거는 줄이 사라지면 이 모듈은 조용해진다.

⚠️ 카운터가 아니라 **이름 목록**을 쌓는다. 수만 세면 실패 메시지가 *"뭔가 만들었다"*까지만
   말하고, 그때 사람이 하는 일은 다시 재현해서 찾아내는 것이다.
"""

from __future__ import annotations


class LiveAdapterForbidden(RuntimeError):
    """게이트가 도는 중에 라이브 어댑터를 만들려 했다.

    ⛔ **삼키지 마라.** 여기서 대역으로 넘어가면 게이트는 초록이고, 그 초록은
       *"오프라인이다"*가 아니라 *"오프라인인 척했다"*이다.
    """


#: tripwire가 걸려 있는가. ⚠️ 모듈 상태인 이유는 관측 지점이 **프로세스 하나**이기 때문이다 —
#: 주입으로 만들면 안 지나는 경로가 생기고, 그 경로가 정확히 이 가드가 막으려던 자리다.
_armed = False

#: 지금까지 지난 생성 입구들. 게이트에서는 **비어 있어야 한다**.
_constructions: list[str] = []


def arm() -> None:
    """tripwire를 건다. **게이트만 부른다** (`tests/conftest.py`)."""
    global _armed
    _armed = True


def disarm() -> None:
    """tripwire를 푼다. ⚠️ 게이트 안에서 이걸 부르는 테스트는 그 순간 G5 밖으로 나간다."""
    global _armed
    _armed = False


def is_armed() -> bool:
    return _armed


def constructions() -> tuple[str, ...]:
    """이 프로세스가 지난 생성 입구들 — **순서대로**."""
    return tuple(_constructions)


def note(factory: str) -> None:
    """라이브 클라이언트를 만들기 **직전에** 지나는 자리.

    ⚠️ 기록을 먼저 하고 막는다 — 실패 메시지가 *무엇을* 만들려 했는지 말해야 한다.
    """
    _constructions.append(factory)
    if _armed:
        raise LiveAdapterForbidden(
            f"게이트가 도는 중에 라이브 어댑터를 만들려 했다: {factory} — "
            "REQ-801은 게이트가 오프라인이고 과금하지 않는다고 약속한다. "
            "테스트는 fake를 **명시적으로** 주입한다(design 08§5)."
        )
