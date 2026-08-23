"""ADK 에이전트 배선 — **무엇을 조립하는가, 그리고 게이트가 그것 없이 도는가** (T12-3).

Spec: specs/warranty/design/06-agent-runtime.md §2-3 (REQ-601)
      docs/evidence/adk-api-probe-2026-08-19.log

⛔ **여기서 확인되는 것은 조립이지 호출이 아니다.** REQ-601의 수용 기준은 실물 모델 호출이고
   그것은 T2-1이 소유한다 — 그래서 이 파일에는 `Verifies:`가 없다. 붙이면 다음 사람이
   증명되지 않은 것을 근거로 상태를 올린다(T11-3 ④가 같은 판단을 적어 뒀다).

⚠️ **`google-adk`는 게이트에 안 깔린다**(cloud extra · REQ-801). 그러니 태우는 자리는
   라이브러리 위가 아니라 **아래**다: 생성자에 실릴 인자를 순수 함수가 값으로 낸다.
   묻는 것은 일곱이다:

  ① 설계 표 파서가 **실제로 읽는가** (공허 통과 방지)
  ② 명세의 이름·도구가 design 06§3과 **같은가** (사본이 따로 썩지 않는가)
  ③ ★ 모델이 **설정에서** 오는가 — 여기 적히면 그것이 배포 값을 이긴다
  ④ 명세와 다른 함수를 붙이면 **거부하는가** — ADK는 아무 `Callable`이나 받는다
  ⑤ ★ `Runner`에 `session_service`가 실리는가 — **기본값이 없는 인자**다(probe ②)
  ⑥ ★ 모듈이 `google`을 **최상위에서 임포트하지 않는가** — 그러면 게이트가 임포트만으로 깨진다
  ⑦ 지시가 선언한 도구를 **전부 이름으로 말하는가**

⚠️ ⑥은 두 방향을 함께 묻는다. *"최상위에 없다"*만 물으면 **지연 임포트가 아예 없어도**
   초록이다 — 그건 배선이 없다는 뜻이고, 이 태스크가 만들려던 것 자체가 사라진 상태다.

⚠️ **프롬프트 문구의 품질은 안 묻는다.** 실물 응답 없이는 판정이 안 되는 종류라 `[manual]`이다
   (T12-2가 같은 자리를 같은 이유로 남겼다). ⑦이 묻는 것은 취향이 아니라 **누락**이다:
   지시에 없는 도구는 모델이 부를 줄 모르고, 그 도구는 조용히 영영 안 불린다.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from warranty.adapters import adk_agent
from warranty.adapters.adk_agent import (
    AGENT_NAME,
    INSTRUCTION,
    SESSION_SERVICE,
    TOOL_NAMES,
    AgentWiringError,
    agent_kwargs,
    build_spec,
    runner_kwargs,
)
from warranty.config import Settings, load_settings

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "specs" / "warranty" / "design" / "06-agent-runtime.md"
MODULE = Path(adk_agent.__file__)

#: 설계의 도구 표가 사는 절.
TOOLS_HEADING = "## 3. 도구 (의도)"

#: 공허 통과 방지의 바닥. 설계 표에는 도구가 넷 있다 — 파서가 이보다 적게 읽으면 깨진 것이다.
MIN_TOOLS = 4

#: `       ├─ provision(spec)  …` 한 행에서 도구 이름.
DESIGN_TOOL_RE = re.compile(r"^\s*[├└]─ ([a-z_]+)\(", re.MULTILINE)

#: `   Agent "warranty"` — 설계가 부르는 에이전트 이름.
DESIGN_NAME_RE = re.compile(r'^\s*Agent "([\w-]+)"', re.MULTILINE)

BASE = {
    "WR_PROJECT_ID": "wr-test",
    "WR_REGION": "us-central1",
    "WR_MODEL": "test-model-1",
    "WR_ADAPTERS": "fake",
}


def _settings(model: str) -> Settings:
    return load_settings({**BASE, "WR_MODEL": model})


def _design_section() -> str:
    text = RUNTIME.read_text(encoding="utf-8")
    start = text.find(TOOLS_HEADING)
    if start < 0:
        raise AssertionError(
            f"{RUNTIME.name}에서 {TOOLS_HEADING!r} 절을 못 찾았다 — 표제가 바뀌었다. "
            "이 가드는 그 절 하나에 물린다."
        )
    end = text.find("\n## 4.", start)
    return text[start:] if end < 0 else text[start:end]


def _design_tools() -> tuple[str, ...]:
    """design 06§3이 선언한 도구 이름 — **순서 그대로**."""
    return tuple(DESIGN_TOOL_RE.findall(_design_section()))


def _module_tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))


def _tool_stub(name: str) -> Callable[[], None]:
    """이름만 맞는 도구 대역. ⚠️ ADK가 받는 것이 평범한 `Callable`이라 이것으로 충분하다."""

    def tool() -> None: ...

    tool.__name__ = name
    return tool


def _tools(names: tuple[str, ...]) -> list[Callable[[], None]]:
    return [_tool_stub(name) for name in names]


# ── ① 설계 표 파서가 실제로 읽는가 ────────────────────────────────────────────


def test_the_design_tool_table_is_actually_read() -> None:
    """① 바닥. ⚠️ 파서가 0개를 읽으면 ②는 **빈 것끼리 맞대고** 조용히 통과한다."""
    tools = _design_tools()
    assert len(tools) >= MIN_TOOLS, (
        f"design 06§3에서 도구를 {len(tools)}개만 읽었다 (최소 {MIN_TOOLS}) — "
        "표 모양이 바뀌었거나 절이 옮겨졌다. 이 수가 0이면 ②는 아무것도 안 맞댄다."
    )
    assert DESIGN_NAME_RE.search(_design_section()) is not None, (
        "설계 절에서 에이전트 이름을 못 읽었다 — 파서가 다른 절을 읽고 있다"
    )


# ── ② 명세가 설계와 같은가 ────────────────────────────────────────────────────


def test_the_spec_declares_exactly_the_tools_the_design_names() -> None:
    """② ⛔ **사본은 따로 썩는다.** `TOOL_NAMES`는 design 06§3의 사본이고, 여기가 그 둘을
    맞대는 유일한 자리다.

    ⚠️ 순서까지 묻는다. 설계의 표는 Day-1 → 조회 → Day-2 → 리포트 순이고, 그 순서가
       지시문과 데모 서사가 읽히는 순서다 — 어긋나면 사람이 읽는 것과 모델이 받는 것이 갈린다.
    ⚠️ 개수도 따로 묻는다: 설계의 문장은 *"도구는 4개로 고정한다"*이고, 그건 표와 같은
       주장이 아니라 **표에 대한 제약**이다.
    """
    declared = _design_tools()
    assert declared == TOOL_NAMES, (
        f"설계와 명세의 도구가 갈라졌다: 설계 {list(declared)} · 코드 {list(TOOL_NAMES)}"
    )
    assert len(TOOL_NAMES) == MIN_TOOLS, (
        f"도구가 {len(TOOL_NAMES)}개다 — 설계는 넷으로 고정한다고 적었다(design 06§3)"
    )

    name = DESIGN_NAME_RE.search(_design_section())
    assert name is not None and name.group(1) == AGENT_NAME, (
        f"설계는 에이전트를 {name.group(1) if name else '없음'!r}라 부르는데 "
        f"코드는 {AGENT_NAME!r}다"
    )


# ── ③ 모델의 출처 ─────────────────────────────────────────────────────────────


def test_the_model_comes_from_settings_and_is_not_written_here() -> None:
    """③ ★ ⛔ **여기 적히면 그것이 배포 값을 이긴다.** `WR_MODEL`을 바꿔 배포해도 에이전트는
    옛 모델을 부르고, 그 어긋남은 로그가 아니라 **청구서**에서 보인다.

    ⚠️ 문자열을 안 찾고 **값을 묻는다**: 서로 다른 설정 둘이 서로 다른 명세를 내는가.
       *"소스에 `gemini`가 없다"*는 구문 검사이고, 그건 다른 이름으로 박아 넣으면 통과한다.
    """
    first = build_spec(_settings("model-alpha"))
    second = build_spec(_settings("model-beta"))
    assert (first.model, second.model) == ("model-alpha", "model-beta"), (
        f"명세의 모델이 설정을 안 따라간다: {first.model!r} · {second.model!r} — "
        "값이 코드에 박혀 있다"
    )
    assert first.session_service == SESSION_SERVICE, "명세가 다른 세션 서비스를 말한다"


# ── ④ 명세와 실제로 붙는 함수가 같은가 ────────────────────────────────────────


def test_wiring_a_tool_the_spec_never_declared_is_refused() -> None:
    """④ ⛔ **ADK는 아무 `Callable`이나 받는다**(probe ①). 그러니 명세가 `inspect`를
    선언했는데 다른 함수가 붙어도 라이브러리는 **아무 말도 안 한다.**

    모델은 지시에 적힌 이름을 부르려 하고 그 도구는 없다. 그 실패는 배선이 아니라
    *"모델이 이상하다"*로 읽힌다 — 고칠 곳을 아무도 못 찾는다.
    """
    spec = build_spec(_settings("model-alpha"))
    kwargs = agent_kwargs(spec, _tools(TOOL_NAMES))
    assert [fn.__name__ for fn in kwargs["tools"]] == list(TOOL_NAMES)
    assert kwargs["model"] == "model-alpha", "생성자 인자가 명세의 모델을 안 싣는다"
    assert kwargs["name"] == AGENT_NAME

    # 이름이 하나 다르다 — 모델은 `report`를 부르려 하고 붙어 있는 것은 `summarize`다.
    swapped = TOOL_NAMES[:-1] + ("summarize",)
    with pytest.raises(AgentWiringError):
        agent_kwargs(spec, _tools(swapped))

    # 집합은 같은데 순서가 다르다. ⚠️ 이것도 거부한다 — 설계의 표가 순서까지 권위다.
    reordered = (TOOL_NAMES[1], TOOL_NAMES[0], *TOOL_NAMES[2:])
    with pytest.raises(AgentWiringError):
        agent_kwargs(spec, _tools(reordered))

    # 하나가 빠졌다. ⛔ 지시는 넷을 말하는데 셋만 붙어 있는 상태가 가장 조용하다.
    with pytest.raises(AgentWiringError):
        agent_kwargs(spec, _tools(TOOL_NAMES[:-1]))


# ── ⑤ Runner가 세션 서비스를 받는가 ───────────────────────────────────────────


def test_the_runner_arguments_carry_a_session_service() -> None:
    """⑤ ★ probe 로그 ②: `session_service`는 **기본값이 없는 키워드 인자**다.

    ⛔ 빠뜨리면 `TypeError`이고, 그 예외는 게이트에도 빌드에도 안 난다 — **첫 실물 호출**에서
       난다. 그때는 이미 이미지가 올라가 있고, 실패는 *"에이전트가 안 뜬다"*로만 보인다.
    ⚠️ `app_name`도 함께 묻는다: 명세와 다른 이름으로 돌면 세션이 다른 앱 아래에 쌓인다.
    """
    spec = build_spec(_settings("model-alpha"))
    kwargs = runner_kwargs(spec, agent=object(), session_service=object())
    assert kwargs.keys() == {"app_name", "agent", "session_service"}, (
        f"`Runner`에 실릴 인자가 기대와 다르다: {sorted(kwargs)}"
    )
    assert kwargs["app_name"] == spec.name

    with pytest.raises(AgentWiringError):
        runner_kwargs(spec, agent=object(), session_service=None)


# ── ⑥ 게이트가 google-adk 없이 도는가 ─────────────────────────────────────────


def test_the_module_does_not_import_the_cloud_stack_at_module_level() -> None:
    """⑥ ★ ⛔ **이것이 red면 게이트는 임포트만으로 깨진다.** `google-adk`는 cloud extra라
    게이트 venv에 없고(REQ-801), 최상위에서 부르면 수집 단계에서 전부 죽는다.

    ⚠️ 두 방향을 함께 묻는다 — *"최상위에 없다"*만 물으면 지연 임포트가 **아예 없어도**
       초록이고, 그건 이 태스크가 만들려던 배선이 사라졌다는 뜻이다.
    """
    tree = _module_tree()
    top_level = [
        alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names
    ] + [node.module or "" for node in tree.body if isinstance(node, ast.ImportFrom)]
    leaked = sorted(name for name in top_level if name.split(".", 1)[0] == "google")
    assert not leaked, (
        f"모듈 최상위가 클라우드 스택을 임포트한다: {leaked} — "
        "게이트에는 그 패키지가 없다. 지연 임포트여야 한다(REQ-801)"
    )

    nested = sorted(
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom) and node not in tree.body
        for name in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
        )
        if name.split(".", 1)[0] == "google"
    )
    assert nested, (
        "모듈 어디에도 `google` 임포트가 없다 — 최상위가 깨끗한 이유가 "
        "*지연 임포트라서*가 아니라 **배선이 없어서**다(REQ-601의 오프라인 절반이 사라졌다)"
    )


def test_importing_the_module_does_not_pull_in_the_cloud_stack() -> None:
    """⑥ 반대편 — 구문이 아니라 **실제로** 안 끌려오는가.

    ⚠️ 구문 검사만으로는 부족하다: 최상위가 깨끗해도 어떤 헬퍼가 임포트 시점에 불리면
       (기본 인자·모듈 상수 계산) 같은 일이 난다. 게이트 venv에는 `google-adk`가 없으니
       거기서는 그 경우 임포트가 통째로 깨지지만, **깔려 있는 기계에서는 조용히 통과한다** —
       그리고 배포 이미지는 정확히 그런 기계다.
    """
    assert adk_agent.AGENT_NAME, "모듈을 실제로 임포트하지 않았다"
    pulled = sorted(name for name in sys.modules if name.split(".", 1)[0] == "google")
    assert not pulled, f"모듈을 임포트했을 뿐인데 클라우드 스택이 딸려 왔다: {pulled}"


# ── ⑦ 지시가 도구를 전부 말하는가 ─────────────────────────────────────────────


def test_the_instruction_names_every_tool_the_agent_is_given() -> None:
    """⑦ 지시에 없는 도구는 모델이 부를 줄 모른다 — 그 도구는 **조용히 영영 안 불린다.**

    ⚠️ 문구의 품질은 여기서 안 묻는다(`[manual]`). 묻는 것은 **누락**이고, 그건 기계가 셀 수 있다.
    """
    missing = [name for name in TOOL_NAMES if name not in INSTRUCTION]
    assert not missing, (
        f"지시가 이름을 안 대는 도구: {missing} — 붙어 있지만 모델은 그것이 있는 줄 모른다"
    )
