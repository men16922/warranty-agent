from __future__ import annotations

from datetime import datetime

from warranty.adapters.system import SystemClock, UlidGen


def test_live_ids_fit_the_lowercase_ulid_contract() -> None:
    made = UlidGen().new_entry_id()
    assert len(made) == 26
    assert made == made.lower()
    assert set(made) <= set("0123456789abcdefghjkmnpqrstvwxyz")


def test_live_clock_returns_an_aware_iso_timestamp() -> None:
    value = datetime.fromisoformat(SystemClock(lambda _seconds: None).now_iso())
    assert value.utcoffset() is not None


def test_live_clock_uses_the_pause_injected_by_the_deployment_entrypoint() -> None:
    slept: list[float] = []
    SystemClock(slept.append).sleep(45)
    assert slept == [45]
