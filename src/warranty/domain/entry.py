"""원장 항목과 그것을 담는 저장소 — **불변식을 API 모양으로 집행한다.**

Spec: specs/warranty/design/05-accountability-ledger.md §1
      specs/warranty/design/08-interfaces.md §2
      (REQ-501, REQ-502, REQ-505, REQ-507)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from warranty.domain.attribution import Attribution, Verifiability
from warranty.domain.cost import Basis, CostFact, Delta, delta_of
from warranty.domain.decision import Decision
from warranty.domain.verification import Verdict, Verification


class EntryKind(StrEnum):
    """원장을 만드는 **경로**의 집합.

    Spec: specs/warranty/design/06-agent-runtime.md (REQ-603)

    ⚠️ 이 열거형은 장식이 아니다 — 리포트가 읽는다(design 05§5). 모델 호출 행을
       조치와 섞으면 회복률의 **분모가 늘고**, 그 행들은 원리상 절대 `improved`가
       되지 않으므로 **모델을 쓸수록 헤드라인이 나빠진다.** 그 오차는 리포트를
       봐서는 안 보인다.
    ⚠️ 값이 늘면 가드가 자동으로 그것도 훑는다 (docs/PRINCIPLES.md #9).
    """

    ACTION = "action"  # 조치 — 게이트를 거친다
    MODEL_CALL = "model_call"  # 모델 호출 — 게이트를 거치지 않는다 (REQ-603)


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
class Approval:
    """기록된 승인 — 누가, 언제, 그리고 **그때 다시 판정한 결과** (REQ-404).

    Spec: specs/warranty/design/04-decision-gate.md (REQ-404)

    ⚠️ `reevaluated`가 원래 `decision`을 **덮지 않는다.** 덮으면 *"무엇에 동의했는가"*가
       사라지고, 남는 건 승인 후의 판정뿐이라 승인이 정당했는지 물을 수 없다.
    """

    approver: str
    approved_at: datetime
    reevaluated: Decision


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
    approval: Approval | None = None
    verification: Verification | None = None
    rollback: Rollback | None = None
    measured: CostFact | None = None
    delta: Delta | None = None
    reconcile_state: ReconcileState = ReconcileState.PENDING
    #: `unreconciled`로 닫은 **사유** (REQ-506). ⚠️ 상태만 남기면 *"라벨이 없었다"*와
    #: *"내보내기가 아직 안 왔다"*가 같은 칸이 되고, 그 둘은 고치는 방법이 다르다.
    unreconciled_reason: str = ""
    retry_of: str | None = None
    kind: EntryKind = EntryKind.ACTION

    def __post_init__(self) -> None:
        if self.kind is EntryKind.MODEL_CALL and self.decision is not None:
            # ⚠️ 모델 호출은 판정 게이트를 거치지 않는다 (REQ-603). 판정을 붙이면 그 행은
            #    *"게이트를 통과했다"*로 읽히고, G4(모든 항목에 판정)는 그 거짓말을
            #    오히려 **초록으로 확인해 준다.**
            raise LedgerError(f"모델 호출에 판정이 붙었다: {self.entry_id}")

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

    @property
    def escalated(self) -> bool:
        """롤백을 **시도했는데 못 했다** — 사람에게 넘어간 것이다 (REQ-305).

        ⚠️ `rolled_back`의 부정이 아니다. 애초에 롤백이 필요 없었던 조치(회복됨)는
        여기 안 든다. 부정으로 세면 **성공한 조치가 전부 에스컬레이션이 되고**,
        리포트의 `escalated` 칸이 성공 건수를 세게 된다.
        """
        return self.rollback is not None and not self.rollback.performed


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

    def give_up_reconcile(
        self, entry_id: str, *, at: datetime, deadline_days: int, reason: str
    ) -> LedgerEntry:
        """기한이 지나도록 청구 행을 못 맞춘 항목을 **사유와 함께** `unreconciled`로 닫는다.

        Spec: specs/warranty/design/05-accountability-ledger.md §4 (REQ-506)

        ⚠️ **기한이 지났는지를 여기서 묻는다.** 호출자가 판단하게 두면 *"기한 내"*는
        약속이 아니라 관례가 되고, 아직 도착할 수 있는 청구서를 기다리다 말고
        `unreconciled`로 닫아 버린 행이 생긴다 — 그 행의 비용은 영원히 추정으로 남는다.
        ⚠️ **사유가 없으면 안 받는다** (`Attribution(none)`과 같은 규칙). 사유 없는
        `unreconciled`는 *"라벨이 안 붙어 있었다"*와 *"내보내기가 아직 안 왔다"*를
        같은 칸에 넣고, 그 둘은 고치는 방법이 다르다.
        ⚠️ 이미 화해된 행은 **안 뒤집는다** — 청구서가 말한 값이 기한보다 세다.
        """
        current = self._rows.get(entry_id)
        if current is None:
            raise LedgerError(f"없는 항목이다: {entry_id}")
        if not reason.strip():
            raise LedgerError(f"unreconciled에 사유가 없다: {entry_id}")
        if current.reconcile_state is not ReconcileState.PENDING:
            return current  # 멱등 — 이미 화해됐거나 이미 포기한 행이다 (REQ-506)
        if at - current.started_at < timedelta(days=deadline_days):
            raise LedgerError(
                f"기한이 아직 안 지났다: {entry_id} "
                f"({current.started_at.isoformat()} + {deadline_days}일 > {at.isoformat()})"
            )
        updated = replace(
            current,
            reconcile_state=ReconcileState.UNRECONCILED,
            unreconciled_reason=reason,
        )
        self._rows[entry_id] = updated
        return updated

    def approve(self, entry_id: str, approval: Approval) -> LedgerEntry:
        """승인을 **기록한다.** 만질 수 있는 것은 `approval`뿐이다 (REQ-404).

        ⚠️ 승인은 `awaiting_approval`인 항목에만, **한 번만** 붙는다. 상태를 안 보면
        이미 거부된(`denied`) 항목이나 이미 실행된 항목에 승인이 사후에 붙고,
        원장은 *"승인받고 실행했다"*로 읽힌다 — 순서가 반대였는데도.
        """
        current = self._rows.get(entry_id)
        if current is None:
            raise LedgerError(f"없는 항목이다: {entry_id}")
        if current.status is not Status.AWAITING_APPROVAL:
            raise LedgerError(f"승인 대기 중이 아닌 항목이다: {entry_id} ({current.status})")
        if current.approval is not None:
            raise LedgerError(f"이미 승인된 항목이다: {entry_id}")
        updated = replace(current, approval=approval)
        self._rows[entry_id] = updated
        return updated

    def complete(
        self,
        entry_id: str,
        *,
        status: Status,
        verification: Verification | None = None,
        rollback: Rollback | None = None,
    ) -> LedgerEntry:
        """조치의 결과를 채운다.

        ⚠️ 만질 수 있는 것은 `status`·`verification`·`rollback`뿐이다.
        `assumed`·`decision`은 손대지 못한다 — 범용 쓰기가 있으면 불변식이 관례가 되고,
        관례는 언젠가 깨진다 (design/08-interfaces.md §2).
        """
        current = self._rows.get(entry_id)
        if current is None:
            raise LedgerError(f"없는 항목이다: {entry_id}")
        updated = replace(current, status=status, verification=verification, rollback=rollback)
        self._rows[entry_id] = updated
        return updated

    def all_entries(self) -> tuple[LedgerEntry, ...]:
        return tuple(self._rows.values())
