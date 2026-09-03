"""Firebase Authentication 어댑터 — Firebase ID 토큰을 검증한다.

Spec: specs/warranty/design/08-interfaces.md §3.A
대회 요건: User authentication via Firebase.

⚠️ 라이브러리는 지연 임포트한다. 게이트에는 `firebase-admin`이 없거나
   오프라인 테스트 중이므로, 게이트에서는 fake verifier를 쓴다 (G5 가드 준수).
"""

from __future__ import annotations

from typing import Any

from warranty.adapters import live_guard
from warranty.auth import AuthenticatedUser


class FirebaseAuthError(RuntimeError):
    """Firebase ID 토큰 검증 실패 또는 설정 누락."""


class LiveFirebaseVerifier:
    """Firebase Admin SDK를 사용하여 Firebase ID Token을 검증하는 실물 어댑터."""

    def __init__(self, project_id: str | None = None) -> None:
        self._project_id = project_id
        self._app: Any | None = None

    def _ensure_app(self) -> Any:
        live_guard.note("live_firebase_auth.LiveFirebaseVerifier._ensure_app")
        if self._app is None:
            import firebase_admin  # type: ignore[import-not-found]
            from firebase_admin import credentials

            try:
                self._app = firebase_admin.get_app()
            except ValueError:
                options = {"projectId": self._project_id} if self._project_id else None
                self._app = firebase_admin.initialize_app(
                    credentials.ApplicationDefault(), options=options
                )
        return self._app

    def verify(self, id_token: str) -> AuthenticatedUser | None:
        """Firebase ID 토큰의 서명과 만료를 검증하고 AuthenticatedUser를 반환한다."""
        live_guard.note("live_firebase_auth.LiveFirebaseVerifier.verify")
        if not id_token or not id_token.strip():
            return None
        self._ensure_app()
        from firebase_admin import auth as fb_auth

        try:
            decoded = fb_auth.verify_id_token(id_token)
            uid = decoded.get("uid") or decoded.get("sub") or ""
            if not uid:
                return None
            email = decoded.get("email")
            return AuthenticatedUser(uid=str(uid), email=email, provider="firebase")
        except Exception:
            return None
