"""Firestore 예산 예약 — 판정과 지출 사이의 창을 트랜잭션으로 닫는다."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from warranty.adapters import live_guard
from warranty.domain.budget import Reservation, ReservationError
from warranty.ports import IdGen

BUDGETS = "budgets"


class BudgetStoreError(RuntimeError):
    """Firestore 예산 문서가 성립하지 않는다."""


@dataclass(frozen=True, slots=True)
class BudgetState:
    limit: Decimal
    spent: Decimal
    reservations: dict[str, Decimal]

    @property
    def headroom(self) -> Decimal:
        return self.limit - self.spent - sum(self.reservations.values(), Decimal(0))


def budget_document(state: BudgetState) -> dict[str, object]:
    return {
        "limit_usd": str(state.limit),
        "spent_usd": str(state.spent),
        "reservations": {key: str(value) for key, value in state.reservations.items()},
    }


def parse_budget(document: dict[str, Any] | None, limit: Decimal) -> BudgetState:
    if document is None:
        return BudgetState(limit=limit, spent=Decimal(0), reservations={})
    try:
        stored_limit = Decimal(document["limit_usd"])
        spent = Decimal(document["spent_usd"])
        raw_reservations = document["reservations"]
        if not isinstance(raw_reservations, dict):
            raise TypeError("reservations is not a mapping")
        reservations = {str(key): Decimal(value) for key, value in raw_reservations.items()}
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise BudgetStoreError("예산 문서를 읽을 수 없다") from exc
    if stored_limit != limit:
        raise BudgetStoreError(f"예산 한도가 배포 값과 다르다: {stored_limit} != {limit}")
    if spent < 0 or any(amount < 0 for amount in reservations.values()):
        raise BudgetStoreError("예산 문서에 음수 지출 또는 예약이 있다")
    return BudgetState(stored_limit, spent, reservations)


def reserve_state(
    state: BudgetState, reservation_id: str, agent_id: str, amount: Decimal
) -> tuple[BudgetState, Reservation] | None:
    if amount < 0:
        raise ReservationError(f"예약 금액이 음수다: {amount}")
    if amount > state.headroom:
        return None
    reservation = Reservation(reservation_id, agent_id, amount)
    opened = dict(state.reservations)
    opened[reservation_id] = amount
    return BudgetState(state.limit, state.spent, opened), reservation


def settle_state(state: BudgetState, reservation: Reservation, actual: Decimal) -> BudgetState:
    expected = state.reservations.get(reservation.reservation_id)
    if expected is None or expected != reservation.amount:
        raise ReservationError(f"열려 있지 않은 예약이다: {reservation.reservation_id}")
    if actual < 0 or actual > reservation.amount:
        raise ReservationError(f"실제 지출이 예약 범위를 벗어났다: {actual} > {reservation.amount}")
    opened = dict(state.reservations)
    del opened[reservation.reservation_id]
    return BudgetState(state.limit, state.spent + actual, opened)


class LiveBudgetStore:
    def __init__(self, project: str, limit: Decimal, ids: IdGen) -> None:
        if not project or limit <= 0:
            raise BudgetStoreError("프로젝트와 양의 예산 한도가 필요하다")
        self._project = project
        self._limit = limit
        self._ids = ids
        self._client: Any | None = None

    def _db(self) -> Any:
        live_guard.note("live_budget.LiveBudgetStore._db")
        if self._client is None:
            from google.cloud import firestore  # type: ignore[import-not-found]

            self._client = firestore.Client(project=self._project)
        return self._client

    def _doc(self, agent_id: str) -> Any:
        live_guard.note("live_budget.LiveBudgetStore._doc")
        if not agent_id or "/" in agent_id:
            raise BudgetStoreError(f"예산 주체 id가 성립하지 않는다: {agent_id!r}")
        return self._db().collection(BUDGETS).document(agent_id)

    def headroom(self, agent_id: str) -> Decimal:
        live_guard.note("live_budget.LiveBudgetStore.headroom")
        snapshot = self._doc(agent_id).get()
        state = parse_budget(snapshot.to_dict() if snapshot.exists else None, self._limit)
        return state.headroom

    def reserve(self, agent_id: str, amount: Decimal) -> Reservation | None:
        live_guard.note("live_budget.LiveBudgetStore.reserve")
        from google.cloud import firestore

        reference = self._doc(agent_id)
        transaction = self._db().transaction()
        reservation_id = self._ids.new_entry_id()

        @firestore.transactional  # type: ignore[untyped-decorator]
        def run(tx: Any) -> Reservation | None:
            snapshot = reference.get(transaction=tx)
            state = parse_budget(snapshot.to_dict() if snapshot.exists else None, self._limit)
            made = reserve_state(state, reservation_id, agent_id, amount)
            if made is None:
                return None
            updated, reservation = made
            tx.set(reference, budget_document(updated))
            return reservation

        return cast(Reservation | None, run(transaction))

    def settle(self, reservation: Reservation, actual: Decimal) -> None:
        live_guard.note("live_budget.LiveBudgetStore.settle")
        from google.cloud import firestore

        reference = self._doc(reservation.agent_id)
        transaction = self._db().transaction()

        @firestore.transactional  # type: ignore[untyped-decorator]
        def run(tx: Any) -> None:
            snapshot = reference.get(transaction=tx)
            state = parse_budget(snapshot.to_dict() if snapshot.exists else None, self._limit)
            tx.set(reference, budget_document(settle_state(state, reservation, actual)))

        run(transaction)

    def unsettled(self) -> int:
        live_guard.note("live_budget.LiveBudgetStore.unsettled")
        total = 0
        for snapshot in self._db().collection(BUDGETS).stream():
            total += len(parse_budget(snapshot.to_dict(), self._limit).reservations)
        return total
