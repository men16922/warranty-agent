"""원장 항목과 그것을 담는 저장소 — **불변식을 API 모양으로 집행한다.**

Spec: specs/fleet-ledger/design/01-domain-model.md §2 · design/06-interfaces.md §3
      (REQ-201, REQ-204, REQ-207)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from warranty.domain.attribution import Attribution, Verifiability
from warranty.domain.cost import Basis, CostFact, Delta, delta_of


class Status(StrEnum):
    EXECUTED = "executed"
    DENIED = "denied"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"


class ReconcileState(StrEnum):
    PENDING = "pending"
    RECONCILED = "reconciled"
    UNRECONCILED = "unreconciled"
    NOT_APPLICABLE = "not_applicable"


class LedgerError(Exception):
    """원장 불변식이 깨졌다."""


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    entry_id: str
    agent_id: str
    action_id: str
    status: Status
    started_at: datetime
    attribution: Attribution
    assumed: CostFact
    measured: CostFact | None = None
    delta: Delta | None = None
    reconcile_state: ReconcileState = ReconcileState.PENDING
    retry_of: str | None = None

    @property
    def verifiability(self) -> Verifiability:
        """⚠️ 저장하지 않고 귀속 방법에서 **유도한다.** 저장하면 둘이 어긋날 수 있다."""
        return self.attribution.verifiability


class InMemoryLedger:
    """원장 저장소.

    ⚠️ **범용 `update()`가 없다.** 범용 쓰기가 있으면 I-1(`assumed` 불변)이 *관례*가 되고,
    관례는 언젠가 깨진다. 화해는 `reconcile()`만 할 수 있고 그것이 만질 수 있는 것은
    `measured`·`delta`·`reconcile_state`뿐이다 (design/06-interfaces.md §3).
    """

    def __init__(self) -> None:
        self._rows: dict[str, LedgerEntry] = {}

    def create(self, entry: LedgerEntry) -> None:
        if entry.entry_id in self._rows:
            # I-5: 액션 1회 = 원장 1행. 재시도는 새 id를 만들고 retry_of로 가리킨다.
            raise LedgerError(f"이미 있는 항목이다: {entry.entry_id}")
        self._rows[entry.entry_id] = entry

    def get(self, entry_id: str) -> LedgerEntry | None:
        return self._rows.get(entry_id)

    def reconcile(self, entry_id: str, measured: CostFact) -> LedgerEntry:
        """`measured`를 채우고 `delta`를 파생한다. **`assumed`는 건드리지 않는다** (I-1)."""
        current = self._rows.get(entry_id)
        if current is None:
            raise LedgerError(f"없는 항목이다: {entry_id}")
        if measured.basis is not Basis.BILLING_EXPORT:
            raise LedgerError(f"measured의 근거가 청구서가 아니다: {measured.basis}")
        if current.reconcile_state is ReconcileState.RECONCILED:
            return current  # REQ-403 멱등 — reconciled_at도 갱신하지 않는다
        updated = replace(
            current,
            measured=measured,
            delta=delta_of(current.assumed, measured),
            reconcile_state=ReconcileState.RECONCILED,
        )
        self._rows[entry_id] = updated
        return updated

    def all_entries(self) -> tuple[LedgerEntry, ...]:
        return tuple(self._rows.values())
