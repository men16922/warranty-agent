"""Gemini 전송의 실물 절반. 프롬프트/파싱은 ``model_judge``가 소유한다."""

from __future__ import annotations

from typing import Any

from warranty.adapters import live_guard
from warranty.adapters.model_judge import RawReply
from warranty.domain.tokens import TokenUsage


class GenaiTransportError(RuntimeError):
    """Gemini 응답에 판정 또는 계량에 필요한 값이 없다."""


class VertexGenaiTransport:
    def __init__(self, project: str, location: str, model: str) -> None:
        if not project or not location or not model:
            raise GenaiTransportError("Vertex project/location/model이 모두 필요하다")
        self._project = project
        self._location = location
        self._model = model
        self._client: Any | None = None

    def _models(self) -> Any:
        live_guard.note("genai_transport.VertexGenaiTransport._models")
        if self._client is None:
            from google import genai  # type: ignore[import-not-found]

            self._client = genai.Client(
                vertexai=True, project=self._project, location=self._location
            )
        return self._client.models

    def complete(self, prompt: str) -> RawReply:
        live_guard.note("genai_transport.VertexGenaiTransport.complete")
        response = self._models().generate_content(model=self._model, contents=prompt)
        text = getattr(response, "text", None)
        usage = getattr(response, "usage_metadata", None)
        if not isinstance(text, str) or usage is None:
            raise GenaiTransportError("Gemini 응답에 text 또는 usage_metadata가 없다")
        return RawReply(
            text=text,
            usage=TokenUsage(
                model=self._model,
                input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
                output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
            ),
        )


class AIStudioGenaiTransport:
    """Google AI Studio (Gemini API) 클라이언트 전송 실물 어댑터.

    대회 요건: Gemini API in Google AI Studio via API Key.
    """

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key or not model:
            raise GenaiTransportError("AI Studio api_key와 model이 모두 필요하다")
        self._api_key = api_key
        self._model = model
        self._client: Any | None = None

    def _models(self) -> Any:
        live_guard.note("genai_transport.AIStudioGenaiTransport._models")
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client.models

    def complete(self, prompt: str) -> RawReply:
        live_guard.note("genai_transport.AIStudioGenaiTransport.complete")
        response = self._models().generate_content(model=self._model, contents=prompt)
        text = getattr(response, "text", None)
        usage = getattr(response, "usage_metadata", None)
        if not isinstance(text, str) or usage is None:
            raise GenaiTransportError("Gemini 응답에 text 또는 usage_metadata가 없다")
        return RawReply(
            text=text,
            usage=TokenUsage(
                model=self._model,
                input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
                output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
            ),
        )
