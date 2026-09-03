"""Google Cloud Secret Manager 어댑터 — 런타임에 안전하게 비밀을 조회한다.

Spec: specs/warranty/design/08-interfaces.md §3.A, specs/warranty/design/10-deployment.md §4
대회 요건: Secure API key retrieval via Google Cloud Secret Manager.

⚠️ 라이브러리는 지연 임포트한다. 게이트는 Secret Manager 클라이언트를 직접 만들지 않고
   fake 또는 환경변수로 검증한다 (G5 가드 준수).
"""

from __future__ import annotations

import os
from typing import Any

from warranty.adapters import live_guard


class SecretManagerError(RuntimeError):
    """Secret Manager에서 비밀을 읽지 못했다."""


class SecretManagerKeyProvider:
    """Google Cloud Secret Manager에서 비밀의 페이로드를 가져오는 실물 어댑터."""

    def __init__(self, project_id: str) -> None:
        if not project_id:
            raise SecretManagerError("project_id가 비었다")
        self._project_id = project_id
        self._client: Any | None = None

    def _get_client(self) -> Any:
        live_guard.note("live_secret.SecretManagerKeyProvider._get_client")
        if self._client is None:
            from google.cloud import secretmanager  # type: ignore[import-not-found]

            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def get_secret(self, secret_name: str, version: str = "latest") -> str:
        """Secret Manager에서 지정된 비밀 버전의 UTF-8 문자열 페이로드를 반환한다."""
        live_guard.note("live_secret.SecretManagerKeyProvider.get_secret")
        if not secret_name:
            raise SecretManagerError("secret_name이 비었다")
        client = self._get_client()
        name = f"projects/{self._project_id}/secrets/{secret_name}/versions/{version}"
        try:
            response = client.access_secret_version(request={"name": name})
            payload: bytes = response.payload.data
            result = payload.decode("utf-8").strip()
            if not result:
                raise SecretManagerError(f"비밀 {secret_name}의 값이 비어 있다")
            return result
        except Exception as exc:
            if isinstance(exc, SecretManagerError):
                raise
            raise SecretManagerError(f"Secret Manager 비밀 {secret_name} 읽기 실패: {exc}") from exc


def resolve_api_key(
    project_id: str | None = None,
    secret_name: str = "gemini-api-key",
    env_var: str = "GEMINI_API_KEY",
    provider: SecretManagerKeyProvider | None = None,
) -> str | None:
    """환경변수 우선, 없으면 Secret Manager에서 Gemini API 키를 조회한다.

    1. 지정된 환경변수에 유효한 값이 있으면 그것을 쓴다.
    2. 환경변수가 없고 provider나 project_id가 주어지면 Secret Manager 조회를 시도한다.
    3. 둘 다 없거나 조회 실패 시 None을 반환한다.
    """
    live_guard.note("live_secret.resolve_api_key")
    env_val = os.environ.get(env_var, "").strip()
    if env_val:
        return env_val
    if provider is not None:
        try:
            return provider.get_secret(secret_name)
        except SecretManagerError:
            return None
    if project_id:
        try:
            p = SecretManagerKeyProvider(project_id)
            return p.get_secret(secret_name)
        except Exception:
            return None
    return None
