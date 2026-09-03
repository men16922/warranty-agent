"""D15 앱 인증 — 공개 Hosted URL과 과금 가능한 호출을 가른다.

Spec: specs/warranty/design/08-interfaces.md §3.A

Cloud Run invoker는 공개다. 심사위원이 Hosted URL과 ``/livez``를 열 수 있어야 한다.
그 공개 범위가 곧 Gemini 토큰을 쓸 권한은 아니므로 ``/agent:chat``은 별도의 bearer
token을 요구한다. 이 모듈은 토큰 값을 저장하거나 로그에 남기지 않고 판정만 돌려준다.
"""

from __future__ import annotations

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
