"""실물 시계와 식별자 — 도메인에는 주입하고, 게이트에서는 대역으로 바꾼다."""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from datetime import UTC, datetime

_CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz"
_ULID_LENGTH = 26


def _base32(value: int, length: int = _ULID_LENGTH) -> str:
    chars = ["0"] * length
    for index in range(length - 1, -1, -1):
        chars[index] = _CROCKFORD[value & 31]
        value >>= 5
    return "".join(chars)


class SystemClock:
    def __init__(self, pause: Callable[[float], None]) -> None:
        self._pause = pause

    def now_iso(self) -> str:
        return datetime.now(UTC).isoformat()

    def sleep(self, seconds: int) -> None:
        self._pause(seconds)


class UlidGen:
    """48비트 밀리초 + 80비트 난수인 소문자 ULID."""

    def new_entry_id(self) -> str:
        milliseconds = time.time_ns() // 1_000_000
        return _base32((milliseconds << 80) | secrets.randbits(80))
