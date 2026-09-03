"""D15 앱 인증 — 공개 Hosted URL과 과금 가능한 호출을 가른다.

Spec: specs/warranty/design/08-interfaces.md §3.A

Cloud Run invoker는 공개다. 심사위원이 Hosted URL과 ``/livez``를 열 수 있어야 한다.
그 공개 범위가 곧 Gemini 토큰을 쓸 권한은 아니므로 ``/agent:chat``은 별도의 bearer
token을 요구한다. 이 모듈은 토큰 값을 저장하거나 로그에 남기지 않고 판정만 돌려준다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from hmac import compare_digest

AUTH_SCHEME = "Bearer"
AUTH_ENV_KEY = "WR_AGENT_AUTH_TOKEN"

#: 256-bit 무작위 토큰을 바닥으로 둔다. 문자 수가 아니라 UTF-8 바이트 수를 본다.
MIN_TOKEN_BYTES = 32


class AuthVerdict(StrEnum):
    """인증 판정. 실패 이유는 서버 내부 판정이고 응답은 하나로 뭉친다."""

    AUTHORIZED = "authorized"
    NOT_CONFIGURED = "not_configured"
    MISSING = "missing"
    MALFORMED = "malformed"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """인증된 주체 정보 (Firebase 사용자 또는 서비스 계정)."""

    uid: str
    email: str | None = None
    provider: str = "bearer"


FirebaseTokenVerifier = Callable[[str], AuthenticatedUser | None]


def authenticate(authorization: str | None, expected_token: str | None) -> AuthVerdict:
    """Bearer 헤더를 판정한다.

    기대 토큰이 없거나 약하면 인증을 끄지 않고 **설정 실패**로 돌려준다. 호출자는 이를
    ``503``으로 내서 fail-close한다. 사용자 입력과 비밀 비교는 길이가 같아도 내용에 따른
    단락 평가가 없는 ``compare_digest``를 쓴다.
    """
    if expected_token is None or expected_token != expected_token.strip():
        return AuthVerdict.NOT_CONFIGURED
    expected = expected_token.encode("utf-8")
    if len(expected) < MIN_TOKEN_BYTES:
        return AuthVerdict.NOT_CONFIGURED

    if authorization is None:
        return AuthVerdict.MISSING
    scheme, separator, credential = authorization.partition(" ")
    if (
        not separator
        or scheme.casefold() != AUTH_SCHEME.casefold()
        or not credential
        or credential != credential.strip()
    ):
        return AuthVerdict.MALFORMED

    if not compare_digest(credential.encode("utf-8"), expected):
        return AuthVerdict.INVALID
    return AuthVerdict.AUTHORIZED


def authenticate_bearer_or_firebase(
    authorization: str | None,
    expected_token: str | None,
    *,
    firebase_verifier: FirebaseTokenVerifier | None = None,
) -> tuple[AuthVerdict, AuthenticatedUser | None]:
    """Bearer 토큰 또는 Firebase ID 토큰을 판정한다.

    1. 기본 Bearer 토큰이 일치하면 서비스 계정 신원(uid='api')으로 승인한다.
    2. Bearer 토큰이 불일치하더라도 firebase_verifier가 제공되어 ID 토큰 검증에 성공하면
       사용자 신원을 반환한다.
    3. 둘 다 불만족 시 적절한 AuthVerdict 실패 사유를 반환한다.
    """
    if authorization is None:
        return AuthVerdict.MISSING, None

    scheme, separator, credential = authorization.partition(" ")
    if (
        not separator
        or scheme.casefold() != AUTH_SCHEME.casefold()
        or not credential
        or credential != credential.strip()
    ):
        return AuthVerdict.MALFORMED, None

    # 1. 정적 기대 토큰 확인
    has_expected = (
        expected_token is not None
        and expected_token == expected_token.strip()
        and len(expected_token.encode("utf-8")) >= MIN_TOKEN_BYTES
    )
    if has_expected:
        assert expected_token is not None
        if compare_digest(credential.encode("utf-8"), expected_token.encode("utf-8")):
            return AuthVerdict.AUTHORIZED, AuthenticatedUser(uid="api", provider="bearer")

    # 2. Firebase ID 토큰 검증 시도
    if firebase_verifier is not None:
        try:
            user = firebase_verifier(credential)
            if user is not None:
                return AuthVerdict.AUTHORIZED, user
        except Exception:
            pass

    # 기대 토큰도 올바르게 설정되어 있지 않고 Firebase 검증기도 없으면 설정 실패
    if not has_expected and firebase_verifier is None:
        return AuthVerdict.NOT_CONFIGURED, None

    return AuthVerdict.INVALID, None
