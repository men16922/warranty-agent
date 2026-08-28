from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from warranty.adapters.fakes import FrozenClock, SeededIdGen
from warranty.agent_chat import AgentChatError, adk_token_usages, final_text, record_adk_events
from warranty.domain.entry import InMemoryLedger, Status
from warranty.domain.tokens import TokenPrices
from warranty.usecases.meter import ModelCallMeter


class Event:
    def __init__(self, text: str | None, final: bool, usage: object | None = None) -> None:
        self.content = SimpleNamespace(parts=[SimpleNamespace(text=text)])
        self.usage_metadata = usage
        self._final = final

    def is_final_response(self) -> bool:
        return self._final


def test_only_the_final_adk_response_leaves_the_http_boundary() -> None:
    assert final_text([Event("tool chatter", False), Event("recovered", True)]) == "recovered"


def test_an_adk_run_without_final_text_fails_loudly() -> None:
    with pytest.raises(AgentChatError):
        final_text([Event(None, True)])


def _usage(prompt: int, candidates: int, tool: int = 0, thoughts: int = 0) -> object:
    return SimpleNamespace(
        prompt_token_count=prompt,
        candidates_token_count=candidates,
        tool_use_prompt_token_count=tool,
        thoughts_token_count=thoughts,
    )


def _meter(ledger: InMemoryLedger) -> ModelCallMeter:
    return ModelCallMeter(
        ledger=ledger,
        clock=FrozenClock(datetime(2026, 8, 28, tzinfo=UTC).isoformat()),
        ids=SeededIdGen("adk"),
        prices=TokenPrices({}, source_note="test has no published price"),
        agent_id="warranty",
    )


def test_adk_usage_preserves_tool_prompts_and_thoughts_in_billable_sides() -> None:
    usages = adk_token_usages(
        [Event("tool", False, _usage(100, 30, tool=20, thoughts=5))], "gemini-3.7-flash"
    )
    assert [(usage.input_tokens, usage.output_tokens) for usage in usages] == [(120, 35)]


def test_each_adk_model_response_becomes_one_model_call_row() -> None:
    ledger = InMemoryLedger()
    record_adk_events(
        [
            Event("tool", False, _usage(100, 10)),
            Event("final", True, _usage(200, 20, tool=30)),
        ],
        model="gemini-3.7-flash",
        session_id="request-7",
        meter=_meter(ledger),
    )
    rows = ledger.all_entries()
    assert len(rows) == 2
    assert [row.action_id for row in rows] == [
        "model:adk:request-7:1",
        "model:adk:request-7:2",
    ]
    assert all(row.status is Status.EXECUTED for row in rows)


def test_missing_adk_usage_is_a_failed_row_not_silent_zero() -> None:
    ledger = InMemoryLedger()
    record_adk_events(
        [Event("final", True)],
        model="gemini-3.7-flash",
        session_id="request-8",
        meter=_meter(ledger),
    )
    row = ledger.all_entries()[0]
    assert row.action_id == "model:adk:request-8:unreported"
    assert row.status is Status.FAILED
    assert row.attribution.reason
