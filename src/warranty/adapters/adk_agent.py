"""ADK 에이전트 배선 — **무엇을 어떻게 조립하는가의 명세** (T12-3 · REQ-601의 오프라인 절반).

Spec: specs/warranty/design/06-agent-runtime.md §2-3 (REQ-601)
      docs/evidence/adk-api-probe-2026-08-19.log (실물 introspect 결과)

⛔ **오프라인 절반이다.** `google-adk`는 게이트에 안 깔린다(cloud extra · REQ-801).
   그래서 라이브러리를 부르는 두 함수는 **지연 임포트**하고, 게이트는 그 위가 아니라
   **아래**를 태운다: 생성자에 실릴 인자를 순수 함수가 **값으로** 낸다.
   `tools/deploy_plan.py`가 `gcloud` 인자에 대해 한 것과 같은 수법이다(T11-1).

⚠️ 이 모듈의 오프라인 테스트가 확인하는 것은 *"우리가 이렇게 조립한다"*까지다.
   *"Gemini가 답했다"*는 별도 실물 증거가 소유한다 — 둘을 합치지 않는다
   (`docs/evidence/live-adk-remediate-2026-08-28.log`).

⚠️ **인자를 값으로 내는 것이 취향이 아닌 이유**는 probe 로그 ②다: `Runner`의
   `session_service`는 **기본값이 없는 키워드 인자**다. 안 넘기면 그 실패는 임포트에서도
   빌드에서도 안 보이고 **첫 실물 호출**에서 `TypeError`로 난다. 값으로 내면 게이트가
   `google-adk` 없이도 *"우리가 그 자리를 채우는가"*를 물을 수 있다.

⚠️ **모델 id를 여기 안 적는다.** `Settings.model`(`WR_MODEL`)에서 온다 — 적는 순간
   이 저장소에 그 문자열의 다섯 번째 사본이 생기고, 사본은 따로 썩는다.
   (사본들이 서로 안 어긋나는지 집행하는 자리는 T12-6이고, 여기가 아니다.)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from warranty.adapters import live_guard
from warranty.config import Settings

#: 에이전트 이름 — design 06§3의 사본이다. ⚠️ `SERVICE_NAME`(`warranty-api`)과 **다른 값**이다:
#: 하나는 Cloud Run 서비스, 하나는 ADK 에이전트다. 게이트가 설계와 맞댄다.
AGENT_NAME = "warranty"

#: ⛔ **도구는 넷으로 고정한다** (design 06§3). 늘리면 4분 안에 설명이 안 된다는 것이
#: 설계의 문장이고, 그 문장을 지키는 자리가 여기다. 순서도 설계와 같다.
TOOL_NAMES: tuple[str, ...] = ("provision", "inspect", "remediate", "report")

#: ⚠️ probe 로그 ②의 권고. `min-instances=0`이라 **유휴 후 첫 요청은 언제나 새 세션**이고,
#: 데모는 단발 요청이라 그것으로 충분하다(REQ-805). 대화 연속성을 가정하면 안 된다.
SESSION_SERVICE = "InMemorySessionService"

#: 에이전트가 받는 지시. ⚠️ **문구의 품질은 게이트가 못 묻는다** — 실물 응답 없이는 판정이
#: 안 되는 종류라 `[manual]`이다. 게이트가 묻는 것은 하나뿐이다: **선언한 도구를 전부
#: 이름으로 말하는가.** 안 말하면 모델이 쓸 줄 모르는 도구가 붙어 있는 것이고,
#: 그 실패는 조용하다 — 에이전트는 그냥 그 도구를 영영 안 부른다.
INSTRUCTION = """\
You operate GCP resources under an operational warranty.

An action did not succeed because its API returned success. It succeeded only if the
health signal named by the resource's operational contract recovered when re-measured.

Do not automate what you cannot verify: when no live contract makes the signal
readable, escalate instead of executing.

Tools:
- provision — Day-1 requests. It creates the resource and emits its operational contract.
- inspect   — read a resource's contract and its recent signal. No side effects.
- remediate — Day-2 actions. It runs the decision gate, the verification and the rollback
              itself; do not try to sequence those steps yourself.
- report    — recovery rates for a day. No side effects.
"""


class AdkUnavailable(RuntimeError):
    """`google-adk`가 없다. ⚠️ **게이트에서는 정상이다** — 여기서 이 예외를 삼키고 대역으로
    넘어가면, 배포가 프레임워크 없이 뜨고 그 사실이 첫 요청까지 안 보인다."""


class AgentWiringError(ValueError):
    """명세와 실제로 붙이는 것이 어긋난다."""


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """조립될 에이전트 하나의 선언 전부. **값이다** — 그래서 게이트가 태울 수 있다."""

    name: str
    model: str
    instruction: str
    tools: tuple[str, ...]
    session_service: str


def build_spec(settings: Settings) -> AgentSpec:
    """설정 하나에서 명세 하나. ⚠️ **모델은 설정에서 온다** — 여기서 문자열을 적으면
    그것이 배포 값을 이기고, 그 어긋남은 청구서에서만 보인다."""
    return AgentSpec(
        name=AGENT_NAME,
        model=settings.model,
        instruction=INSTRUCTION,
        tools=TOOL_NAMES,
        session_service=SESSION_SERVICE,
    )


def vertex_env(settings: Settings) -> dict[str, str]:
    """ADK·google-genai가 **환경변수로** 읽는 Vertex 설정. 라이브러리를 안 부른다.

    ⛔ **`settings.region`이 아니라 `settings.vertex_location`이다.** 실물이 그 둘을 갈랐다
       (2026-08-23 · `docs/evidence/adk-live-call-2026-08-23.log`): Gemini 3.x는 Vertex에서
       **`global`에만 있고** `us-central1`은 404다. 하나로 묶으면 Cloud Run 리전을 고르는
       순간 모델이 사라지고, **그 사실은 배포 후 첫 모델 호출에서야 보인다** — 빌드도
       게이트도 조용하다. T11-1(배포 값의 사본)·T11-3(선언과 설치)과 같은 계열이고,
       다른 점은 **이것이 실물에서 이미 한 번 터졌다**는 것뿐이다.

    ⚠️ 값을 여기서 적지 않는다. `"global"`을 여기 쓰면 그것이 설정을 이기고, 모델이
       리전을 늘리는 날 아무도 이 줄을 못 찾는다.
    """
    return {
        "GOOGLE_GENAI_USE_VERTEXAI": "1",
        "GOOGLE_CLOUD_PROJECT": settings.project_id,
        "GOOGLE_CLOUD_LOCATION": settings.vertex_location,
    }


def agent_kwargs(spec: AgentSpec, tools: Sequence[Callable[..., Any]]) -> dict[str, Any]:
    """`Agent(**...)`에 실릴 것 전부. **순수하다** — 라이브러리를 안 부른다.

    ⛔ 이름을 맞대는 것이 이 함수의 본체다. probe 로그 ①대로 `tools`는 평범한 `Callable`을
       받으므로 **아무 함수나 들어간다** — 명세가 `inspect`를 선언했는데 다른 함수가 붙어도
       라이브러리는 아무 말도 안 한다. 모델은 지시에 적힌 도구를 부르려 하고, 그 도구는
       없다. 그 실패는 배선이 아니라 **모델이 이상하다**로 읽힌다.
    """
    given = tuple(getattr(fn, "__name__", "?") for fn in tools)
    if given != spec.tools:
        raise AgentWiringError(
            f"명세가 선언한 도구와 붙이려는 함수가 다르다: 명세 {list(spec.tools)} · "
            f"실제 {list(given)} — 순서까지 같아야 한다(design 06§3의 표가 권위다)"
        )
    return {
        "name": spec.name,
        "model": spec.model,
        "instruction": spec.instruction,
        "tools": list(tools),
    }


def runner_kwargs(spec: AgentSpec, agent: Any, session_service: Any) -> dict[str, Any]:
    """`Runner(**...)`에 실릴 것 전부. **순수하다.**

    ⚠️ probe 로그 ②: `session_service`는 **기본값이 없다.** 빠뜨리면 `TypeError`이고,
       그 예외는 게이트에도 빌드에도 안 나타난다 — 첫 실물 호출에서만 난다.
       그래서 여기서 **없음을 거부한다**: 게이트가 물을 수 있는 유일한 자리다.
    """
    if session_service is None:
        raise AgentWiringError(
            f"`Runner`에 세션 서비스가 없다 — 기본값이 없는 인자다(design 06§2). "
            f"명세가 말하는 것은 {spec.session_service}다"
        )
    return {"app_name": spec.name, "agent": agent, "session_service": session_service}


def _load_adk() -> tuple[Any, Any]:
    """⛔ **이 저장소에서 네트워크에 가장 가까운 두 줄이다.** 지연 임포트인 이유는 REQ-801:
    게이트는 `google-adk` 없이 통과해야 하고, 최상위에서 부르면 **임포트만으로** 깨진다.

    ⚠️ `sessions`를 따로 임포트한다 — probe 로그 2절이 적은 최상위 export에 그 이름이 없다.
       `google.adk`만 임포트하고 `adk.sessions`를 읽으면 `AttributeError`가 날 수 있고,
       그 예외는 *"세션 서비스를 못 만들었다"*가 아니라 *"에이전트가 깨졌다"*로 읽힌다.

    ⚠️ 첫 줄이 tripwire인 이유는 G5다 — 이 함수가 게이트에서 **불렸다는 사실 자체**가
       REQ-801의 위반이고, 위반은 임포트가 실패해서가 아니라 **여기 온 것**으로 성립한다.
    """
    live_guard.note("adk_agent._load_adk")
    try:
        # ⚠️ 억제가 첫 줄에만 붙는다: 이 줄이 `google.adk`를 `Any`로 만들면 아래 줄은
        #    mypy에게 이미 해결된 이름이다. 둘째 줄에도 붙이면 `warn_unused_ignores`가
        #    운다 — 게이트에 없는 패키지의 억제는 **정확히 한 줄**이어야 한다.
        import google.adk as adk  # type: ignore[import-not-found]
        from google.adk import sessions
    except ImportError as exc:  # pragma: no cover - 게이트에는 이 패키지가 없다
        raise AdkUnavailable(
            'google-adk가 없다 — 이미지는 `pip install ".[cloud]"`로 얻는다. '
            "게이트에는 없는 것이 정상이다(REQ-801)"
        ) from exc
    return adk, sessions


def build_agent(spec: AgentSpec, tools: Sequence[Callable[..., Any]]) -> Any:
    """★ 실제 `Agent`를 만든다. ⛔ **게이트는 이것을 안 부른다** (REQ-801).

    ⚠️ 인자 검증은 임포트 **앞**이다 — 그래야 배선이 틀렸을 때 나는 말이
       *"google-adk가 없다"*가 아니라 *"명세와 도구가 다르다"*가 된다.
    ⚠️ **tripwire는 그보다도 앞이다** — 인자 검증은 *"우리가 옳게 조립하는가"*를 묻고,
       G5는 *"게이트가 여기 왔는가"*를 묻는다. 후자는 인자가 옳아도 위반이다(REQ-801).
    """
    live_guard.note("adk_agent.build_agent")
    kwargs = agent_kwargs(spec, tools)
    adk, _ = _load_adk()
    return adk.Agent(**kwargs)


def build_runner(spec: AgentSpec, tools: Sequence[Callable[..., Any]]) -> Any:
    """★ 실제 `Runner`를 만든다. ⛔ **게이트는 이것을 안 부른다** (REQ-801 · G5가 집행한다)."""
    live_guard.note("adk_agent.build_runner")
    agent = build_agent(spec, tools)
    adk, sessions = _load_adk()
    session_service = getattr(sessions, spec.session_service)()
    return adk.Runner(**runner_kwargs(spec, agent, session_service))
