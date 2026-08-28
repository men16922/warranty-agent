"""인증된 HTTP 요청 하나를 ADK Runner의 단발 세션 하나로 옮긴다."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from threading import Lock
from typing import Any

from warranty.adapters import live_guard
from warranty.adapters.adk_agent import build_runner, build_spec, vertex_env
from warranty.config import load_settings
from warranty.domain.tokens import TokenUsage
from warranty.runtime import build_live_tools
from warranty.usecases.meter import ModelCallMeter


class AgentChatError(RuntimeError):
    """ADK가 최종 텍스트 응답을 만들지 못했다."""


def final_text(events: Iterable[Any]) -> str:
    chunks: list[str] = []
    for event in events:
        is_final = getattr(event, "is_final_response", None)
        if not callable(is_final) or not is_final():
            continue
        content = getattr(event, "content", None)
        for part in getattr(content, "parts", ()) if content is not None else ():
            value = getattr(part, "text", None)
            if isinstance(value, str):
                chunks.append(value)
    answer = "".join(chunks).strip()
    if not answer:
        raise AgentChatError("ADK가 최종 텍스트 응답을 내지 않았다")
    return answer


def adk_token_usages(events: Iterable[Any], model: str) -> tuple[TokenUsage, ...]:
    """ADK 모델 응답 이벤트마다 과금 가능한 입력·출력 토큰을 보존한다."""
    usages: list[TokenUsage] = []
    for event in events:
        metadata = getattr(event, "usage_metadata", None)
        if metadata is None:
            continue
        prompt = int(getattr(metadata, "prompt_token_count", 0) or 0)
        tool_prompt = int(getattr(metadata, "tool_use_prompt_token_count", 0) or 0)
        candidates = int(getattr(metadata, "candidates_token_count", 0) or 0)
        thoughts = int(getattr(metadata, "thoughts_token_count", 0) or 0)
        usages.append(TokenUsage(model, prompt + tool_prompt, candidates + thoughts))
    return tuple(usages)


def record_adk_events(
    events: Iterable[Any],
    *,
    model: str,
    session_id: str,
    meter: ModelCallMeter,
    failed: bool = False,
) -> None:
    """ADK가 실행한 모델 호출을 응답 이벤트 수만큼 원장에 남긴다."""
    usages = adk_token_usages(events, model)
    for index, usage in enumerate(usages, start=1):
        meter.record(f"adk:{session_id}:{index}", usage)
    if failed or not usages:
        meter.record(f"adk:{session_id}:unreported", None)


class LiveAgentChat:
    """첫 인증 요청에서만 클라우드 런타임을 만든다."""

    def __init__(self, pause: Callable[[float], None]) -> None:
        self._lock = Lock()
        self._pause = pause
        self._runner: Any | None = None
        self._spec: Any | None = None
        self._model_calls: ModelCallMeter | None = None
        self._session_number = 0

    def _runtime(self) -> tuple[Any, Any, ModelCallMeter]:
        if self._runner is None or self._spec is None or self._model_calls is None:
            settings = load_settings()
            for key, value in vertex_env(settings).items():
                import os

                os.environ[key] = value
            spec = build_spec(settings)
            tools = build_live_tools(settings, self._pause)
            if tools.model_calls is None:
                raise AgentChatError("실물 런타임에 모델 호출 계량기가 없다")
            self._runner = build_runner(spec, tools.callables())
            self._spec = spec
            self._model_calls = tools.model_calls
        return self._runner, self._spec, self._model_calls

    def __call__(self, body: Mapping[str, object]) -> Mapping[str, object]:
        live_guard.note("agent_chat.LiveAgentChat.__call__")
        message = body.get("message")
        if not isinstance(message, str) or not message.strip():
            raise AgentChatError("message가 없거나 비었다")
        with self._lock:
            runner, spec, model_calls = self._runtime()
            self._session_number += 1
            session_id = f"request-{self._session_number}"
            runner.session_service.create_session_sync(
                app_name=spec.name, user_id="api", session_id=session_id
            )
            from google.genai import types  # type: ignore[import-not-found]

            events: list[Any] = []
            try:
                events.extend(
                    runner.run(
                        user_id="api",
                        session_id=session_id,
                        new_message=types.Content(
                            role="user", parts=[types.Part.from_text(text=message.strip())]
                        ),
                    )
                )
            except Exception:
                record_adk_events(
                    events,
                    model=spec.model,
                    session_id=session_id,
                    meter=model_calls,
                    failed=True,
                )
                raise
            record_adk_events(events, model=spec.model, session_id=session_id, meter=model_calls)
            return {"message": final_text(events), "session_id": session_id}


def lazy_live_agent_chat(
    pause: Callable[[float], None],
) -> Callable[[Mapping[str, object]], Mapping[str, object]]:
    return LiveAgentChat(pause)
