"""D15 앱 인증 — 공개 URL이 과금 권한으로 번지지 않는가.

Spec: specs/warranty/design/08-interfaces.md §3.A
"""

from __future__ import annotations

import pytest

from warranty import auth
from warranty.auth import AUTH_SCHEME, AuthVerdict, authenticate

TOKEN = "a" * auth.MIN_TOKEN_BYTES


@pytest.mark.parametrize("configured", [None, "", " ", "short", f" {TOKEN}", f"{TOKEN} "])
def test_missing_or_weak_server_secret_fails_closed(configured: str | None) -> None:
    assert authenticate(f"{AUTH_SCHEME} {TOKEN}", configured) is AuthVerdict.NOT_CONFIGURED


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, AuthVerdict.MISSING),
        ("", AuthVerdict.MALFORMED),
        (TOKEN, AuthVerdict.MALFORMED),
        (f"Basic {TOKEN}", AuthVerdict.MALFORMED),
        (f"{AUTH_SCHEME} ", AuthVerdict.MALFORMED),
        (f"{AUTH_SCHEME} wrong", AuthVerdict.INVALID),
    ],
)
def test_missing_malformed_and_wrong_credentials_are_not_authorized(
    header: str | None, expected: AuthVerdict
) -> None:
    assert authenticate(header, TOKEN) is expected


def test_a_valid_bearer_token_is_authorized_and_the_scheme_is_case_insensitive() -> None:
    assert authenticate(f"{AUTH_SCHEME} {TOKEN}", TOKEN) is AuthVerdict.AUTHORIZED
    assert authenticate(f"bearer {TOKEN}", TOKEN) is AuthVerdict.AUTHORIZED

    v_stat, u_stat = auth.authenticate_bearer_or_firebase(f"Bearer {TOKEN}", TOKEN)
    assert v_stat is AuthVerdict.AUTHORIZED and u_stat is not None and u_stat.uid == "api"

    def _fb_verifier(id_token: str) -> auth.AuthenticatedUser | None:
        if id_token == "valid-fb":
            return auth.AuthenticatedUser(uid="u42", email="u@test.com", provider="firebase")
        return None

    v_fb, u_fb = auth.authenticate_bearer_or_firebase(
        "Bearer valid-fb", TOKEN, firebase_verifier=_fb_verifier
    )
    assert v_fb is AuthVerdict.AUTHORIZED and u_fb is not None and u_fb.uid == "u42"

    v_fail, u_fail = auth.authenticate_bearer_or_firebase("Bearer whatever", None)
    assert v_fail is AuthVerdict.NOT_CONFIGURED and u_fail is None


def test_secret_comparison_uses_compare_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[bytes, bytes]] = []

    def _spy(provided: bytes, expected: bytes) -> bool:
        calls.append((provided, expected))
        return False

    monkeypatch.setattr(auth, "compare_digest", _spy)
    assert authenticate(f"{AUTH_SCHEME} wrong", TOKEN) is AuthVerdict.INVALID
    assert calls == [(b"wrong", TOKEN.encode("utf-8"))]
