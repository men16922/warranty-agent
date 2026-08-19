"""원장 항목과 그것을 담는 저장소 — **불변식을 API 모양으로 집행한다.**

Spec: specs/fleet-ledger/design/01-domain-model.md §2 · design/06-interfaces.md §3
      (REQ-201, REQ-204, REQ-207)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from warranty.domain.attribution import Attribution, Verifiability
from warranty.domain.cost import Basis, CostFact, Delta, delta_of
from warranty.domain.decision import Decision
from warranty.domain.verification import Verdict, Verification


class Status(StrEnum):
    EXECUTED = "executed"
    DENIED = "denied"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    MANUAL_REQUIRED = "manual_required"  # 계약이 없어 자동 대상이 아니다 (REQ-104)


class ReconcileState(StrEnum):
    PENDING = "pending"
    RECONCILED = "reconciled"
    UNRECONCILED = "unreconciled"
    NOT_APPLICABLE = "not_applicable"


class LedgerError(Exception):
    """원장 불변식이 깨졌다."""


@dataclass(frozen=True, slots=True)
class Rollback:
    """되돌림의 기록. **주장이 아니라 측정이다** (REQ-303, REQ-304)."""

    performed: bool
    verified_traffic: Mapping[str, int] | None = None
    signal_restored: bool | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    entry_id: str
    agent_id: str
    action_id: str
    status: Status
    started_at: datetime
    attribution: Attribution
    assumed: CostFact
    decision: Decision | None = None
    contract_id: str | None = None
    verification: Verification | None = None
    rollback: Rollback | None = None
    measured: CostFact | None = None
    delta: Delta | None = None
    reconcile_state: ReconcileState = ReconcileState.PENDING
    retry_of: str | None = None

    @property
    def verifiability(self) -> Verifiability:
        """⚠️ 저장하지 않고 귀속 방법에서 **유도한다.** 저장하면 둘이 어긋날 수 있다."""
        return self.attribution.verifiability

    # ── ★ 셋을 따로 갖는다 (REQ-502) ────────────────────────────────────
    # 이 셋을 하나의 `success`로 합치는 순간 이 프로젝트의 논지가 사라진다.

    @property
    def executed(self) -> bool:
        """조치 API가 성공했는가."""
        return self.status is Status.EXECUTED

    @property
    def improved(self) -> bool:
        """신호가 회복됐는가.

        ⚠️ **저장하지 않고 검증 결과에서 유도한다**(가드 G8). 저장 필드로 두면
        `verification.verdict`와 어긋날 수 있고, 어긋난 쪽이 리포트에 실린다.
        ⚠️ 검증이 없거나 `unverifiable`이면 **False다** — 조용한 성공을 만들지 않는다.
        """
        return self.verification is not None and self.verification.verdict is Verdict.RECOVERED

    @property
    def rolled_back(self) -> bool:
        return self.rollback is not None and self.rollback.performed


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
