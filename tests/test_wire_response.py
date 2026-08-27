"""`remediate` 응답 — ★ **판정·검증 근거·트래픽 배분이 화면에 있는가** (T5-1).

Spec: specs/warranty/design/08-interfaces.md §3.1

Verifies: REQ-604
Verifies: REQ-502
Verifies: REQ-503

⚠️ 이 파일이 묻는 것은 *"응답에 값이 있는가"*가 아니라 **어떤 값이 반드시 있는가**다.
   `rule`·`rationale`·`verified_traffic`은 4분 안에 논지를 전달하는 세 문장이고,
   로그에만 있으면 없는 것과 같다.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from warranty.domain.attribution import Attribution, Method
from warranty.domain.contract import Reversibility
from warranty.domain.cost import Basis, CostFact
from warranty.domain.decision import decide
from warranty.domain.entry import LedgerEntry, Rollback, Status
from warranty.domain.verification import DecidedBy, Measurement, Verdict, Verification
from warranty.wire import (
    REQUIRED_KEYS,
    SEPARATE_OUTCOMES,
    remediate_response,
)

FROZEN = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)  # REQ-802: 살아 있는 시계를 안 쓴다
ENTRY_ID = "01k2m9x7q3f4b8n0v6c1t5r2wz"
PREVIOUS = "demo-target-00001-abc"


def _entry(**over: Any) -> LedgerEntry:
    base = LedgerEntry(
        entry_id=ENTRY_ID,
        agent_id="fleet-steward",
        action_id="rollout_revision",
        status=Status.EXECUTED,
        started_at=FROZEN,
        attribution=Attribution(Method.RESOURCE_LABEL, label_value=ENTRY_ID),
        assumed=CostFact(
            amount_usd=Decimal("0.0021"),
            priced_at=FROZEN,
            basis=Basis.PUBLISHED_RATE,
            inputs={"cpu_seconds": Decimal(60)},
            unit_prices={"cpu_seconds": Decimal("0.000333")},
        ),
        decision=decide(
            reversibility=Reversibility.REVERSIBLE,
            verifiable=True,
            projected_usd=Decimal("0.0021"),
            headroom_usd=Decimal("0.42"),
        ),
        contract_id="c1",
        verification=Verification(
            verdict=Verdict.NOT_RECOVERED,
            decided_by=DecidedBy.MODEL,
            baseline=Measurement(Decimal("674.2"), 30),
            after=Measurement(Decimal("988.6"), 30),
            rationale="오류율은 60% 나아졌지만 p95가 기준선의 2.3배로 올랐다 — "
            "증상 하나를 다른 증상과 맞바꿨다.",
        ),
        rollback=Rollback(
            performed=True,
            verified_traffic={PREVIOUS: 100},
            signal_restored=True,
        ),
    )
    return replace(base, **over)


# ── ★ 화면에 보여야 하는 세 문장 (REQ-604) ───────────────────────────────────────


def test_the_decision_carries_the_rule_that_produced_it() -> None:
    """★ 데모에서 *"왜 막혔죠?"*에 답하는 칸이다. 없으면 판정은 신탁이 된다."""
    body = remediate_response(_entry())
    assert body["decision"]["rule"], "판정에 근거 문장이 없다 — 로그에만 있으면 없는 것과 같다"


def test_the_verification_carries_the_model_rationale() -> None:
    """★ 애매한 판정을 모델이 했다면 **그 문장이 응답에 있다** (REQ-204)."""
    body = remediate_response(_entry())
    assert body["verification"]["decided_by"] == DecidedBy.MODEL.value
    assert "p95" in body["verification"]["rationale"]


def test_the_rollback_carries_the_traffic_it_read_back() -> None:
    """★ *"되돌렸다"*는 주장이고 배분은 측정이다 (REQ-302). 응답에 있는 것은 측정이어야 한다."""
    body = remediate_response(_entry())
    assert body["rollback"]["verified_traffic"] == {PREVIOUS: 100}


# ── ★ 셋이 따로 있다 (REQ-502) ──────────────────────────────────────────────────


def test_executed_improved_and_rolled_back_are_three_separate_fields() -> None:
    """⛔ 하나로 뭉치면 *"실행했다"*가 *"나아졌다"*로 읽힌다 — 이 프로젝트가 반대하는 문장이다."""
    body = remediate_response(_entry())
    for key in SEPARATE_OUTCOMES:
        assert key in body, f"{key}가 응답에 없다"
    assert (body["executed"], body["improved"], body["rolled_back"]) == (True, False, True)


def test_a_recovered_action_says_improved_without_a_rollback() -> None:
    entry = _entry(
        verification=Verification(
            verdict=Verdict.RECOVERED,
            decided_by=DecidedBy.RULE,
            baseline=Measurement(Decimal("988.6"), 30),
            after=Measurement(Decimal("674.2"), 30),
        ),
        rollback=None,
    )
    body = remediate_response(entry)
    assert (body["executed"], body["improved"], body["rolled_back"]) == (True, True, False)


def test_a_denied_action_never_says_executed() -> None:
    """⛔ 게이트가 막은 조치는 실행자가 안 불린 것이다 (G1). 응답이 그것을 뒤집으면 안 된다."""
    body = remediate_response(_entry(status=Status.DENIED, verification=None, rollback=None))
    assert body["executed"] is False
    assert body["improved"] is False


# ── 돈 — JSON의 수치는 double이다 ───────────────────────────────────────────────


def test_money_leaves_as_text_not_as_a_number() -> None:
    body = remediate_response(_entry())
    assert body["assumed"]["amount_usd"] == "0.0021"
    assert body["decision"]["headroom_usd"] == "0.42"
    assert body["assumed"]["unit_prices"]["cpu_seconds"] == "0.000333"


def test_the_cost_shows_the_quantities_and_unit_prices_it_came_from() -> None:
    """⚠️ 총액만 내면 그 숫자가 어떻게 나왔는지 아무도 못 묻는다 (REQ-503)."""
    body = remediate_response(_entry())
    assert body["assumed"]["inputs"] == {"cpu_seconds": "60"}


def test_measured_arrives_beside_assumed_and_never_on_top_of_it() -> None:
    """⛔ 추정은 절대 덮이지 않는다 (REQ-505 · I-1) — 응답에서도 두 칸이다."""
    measured = CostFact(Decimal("0.0034"), FROZEN, Basis.BILLING_EXPORT)
    body = remediate_response(_entry(measured=measured))
    assert body["assumed"]["amount_usd"] == "0.0021"
    assert body["measured"]["amount_usd"] == "0.0034"


# ── 모양 ────────────────────────────────────────────────────────────────────────


def test_every_required_key_is_present_even_when_the_value_is_null() -> None:
    """⛔ 키째 빼면 *"검증을 안 했다"*와 *"검증 칸이 없는 모양"*이 구분되지 않는다."""
    body = remediate_response(_entry(decision=None, verification=None, rollback=None))
    for key in REQUIRED_KEYS:
        assert key in body, f"{key}가 빠졌다"
    assert body["verification"] is None


def test_the_measurement_says_how_many_points_it_saw() -> None:
    """⚠️ 값 하나만 보이면 빈 창(`points=0`)이 *"0ms"*로 읽힌다 (REQ-205)."""
    body = remediate_response(_entry())
    assert body["verification"]["baseline"] == {"value": "674.2", "points": 30}


def test_an_empty_window_reads_as_null_not_as_zero() -> None:
    entry = _entry(
        verification=Verification(
            verdict=Verdict.UNVERIFIABLE,
            decided_by=DecidedBy.RULE,
            baseline=Measurement(None, 0),
            after=Measurement(None, 0),
        )
    )
    body = remediate_response(entry)
    assert body["verification"]["baseline"] == {"value": None, "points": 0}


def test_the_body_is_json_serialisable_and_deterministic() -> None:
    """⚠️ 같은 행이 프로세스마다 다른 바이트를 내면 안 된다 (REQ-802)."""
    body = remediate_response(_entry())
    first = json.dumps(body, ensure_ascii=False, sort_keys=True)
    second = json.dumps(remediate_response(_entry()), ensure_ascii=False, sort_keys=True)
    assert first == second


def test_no_decimal_survives_into_the_body() -> None:
    """⛔ `Decimal`은 JSON이 못 싣는다. 하나라도 남으면 응답은 **직렬화에서** 죽는다."""

    def walk(value: Any) -> None:
        assert not isinstance(value, Decimal), f"응답에 Decimal이 남았다: {value}"
        if isinstance(value, dict):
            for item in value.values():
                walk(item)

    walk(remediate_response(_entry(measured=CostFact(Decimal("1"), FROZEN, Basis.BILLING_EXPORT))))


def test_the_required_list_is_not_empty() -> None:
    """① 공허 통과 방지 — 목록이 비면 위의 검사들은 **아무것도 안 보고** 초록이다."""
    assert len(REQUIRED_KEYS) >= 9
    assert set(SEPARATE_OUTCOMES) <= set(REQUIRED_KEYS)


def test_a_body_missing_a_required_key_is_refused() -> None:
    """⚠️ 목록과 본문이 어긋나면 **모양이 아니라 목록이 거짓말한 것**이다."""
    import warranty.wire as wire

    original = wire.REQUIRED_KEYS
    try:
        wire.REQUIRED_KEYS = (*original, "traffic_after_action")
        with pytest.raises(wire.WireError, match="traffic_after_action"):
            remediate_response(_entry())
    finally:
        wire.REQUIRED_KEYS = original
