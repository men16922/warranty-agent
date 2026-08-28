from __future__ import annotations

from decimal import Decimal

import pytest

from warranty.adapters.live_budget import (
    BudgetState,
    BudgetStoreError,
    budget_document,
    parse_budget,
    reserve_state,
    settle_state,
)
from warranty.domain.budget import Reservation, ReservationError


def test_budget_money_round_trips_as_text_and_open_reservations_reduce_headroom() -> None:
    state = BudgetState(Decimal("0.50"), Decimal("0.10"), {"r1": Decimal("0.20")})
    document = budget_document(state)
    assert document["limit_usd"] == "0.50"
    assert parse_budget(document, Decimal("0.50")) == state
    assert state.headroom == Decimal("0.20")


def test_reserve_and_settle_are_pure_atomic_transitions() -> None:
    initial = parse_budget(None, Decimal("0.50"))
    made = reserve_state(initial, "r1", "warranty", Decimal("0.30"))
    assert made is not None
    reserved, reservation = made
    assert reserved.headroom == Decimal("0.20")
    assert reserve_state(reserved, "r2", "warranty", Decimal("0.21")) is None
    settled = settle_state(reserved, reservation, Decimal("0.10"))
    assert settled.spent == Decimal("0.10")
    assert settled.headroom == Decimal("0.40")


def test_budget_refuses_drift_and_double_settlement() -> None:
    with pytest.raises(BudgetStoreError):
        parse_budget(budget_document(BudgetState(Decimal("1"), Decimal(0), {})), Decimal("0.5"))
    state = BudgetState(Decimal("0.50"), Decimal(0), {})
    with pytest.raises(ReservationError):
        settle_state(state, reserve_state(state, "r1", "warranty", Decimal("0.1"))[1], Decimal(0))  # type: ignore[index]


def test_actual_spend_cannot_exceed_the_amount_that_was_reserved() -> None:
    state = BudgetState(Decimal("0.50"), Decimal(0), {"r1": Decimal("0.10")})
    with pytest.raises(ReservationError):
        settle_state(state, Reservation("r1", "warranty", Decimal("0.10")), Decimal("0.11"))
