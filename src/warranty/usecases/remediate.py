"""조치 → 검증 → 롤백 — 이 프로젝트의 루프 전체.

Spec: specs/warranty/design/02-verification.md · 03-atomic-rollback.md · 04-decision-gate.md
      (REQ-104, REQ-201~205, REQ-301~305, REQ-401~403)

    ⛔ 검증할 수 없는 조치는 자동으로 실행하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from warranty.domain.attribution import Attribution, Method
from warranty.domain.contract import (
    OperationalContract,
    ResourceRef,
    Reversibility,
    RollbackPlan,
)
from warranty.domain.cost import Basis, CostFact
from warranty.domain.decision import BLOCKING, Gate, decide
from warranty.domain.entry import LedgerEntry, Rollback, Status
from warranty.domain.verification import (
    DecidedBy,
    Measurement,
    Verdict,
    Verification,
    classify,
)
from warranty.ports import (
    ActionExecutor,
    BudgetStore,
    Clock,
    ContractStore,
    IdGen,
    LedgerWriter,
    ModelJudge,
    RunControl,
    SignalSource,
)

#: 재측정 타이밍. ⚠️ 상수는 **한 곳에만** 있다 (REQ-206, REQ-804).
VERIFY_DELAY_S = 45
VERIFY_WINDOW_S = 120


@dataclass(frozen=True, slots=True)
class Remediator:
    contracts: ContractStore
    signals: SignalSource
    executor: ActionExecutor
    run: RunControl
    budgets: BudgetStore
    ledger: LedgerWriter
    clock: Clock
    ids: IdGen
    judge: ModelJudge

    def remediate(
        self,
        *,
        agent_id: str,
        action_id: str,
        resource: ResourceRef,
        projected_usd: Decimal,
        destructive: bool = False,
    ) -> LedgerEntry:
        entry_id = self.ids.new_entry_id()
        started = datetime.fromisoformat(self.clock.now_iso())
        zero = CostFact(Decimal(0), started, Basis.PUBLISHED_RATE)

        contract = self.contracts.active_for(resource)

        # ── 검증 가능성은 **유도된다.** 조치가 주장하지 않는다 (REQ-402).
        verifiable = contract is not None and self.signals.readable(contract.health_signal)
        reversibility = (
            contract.reversibility if contract is not None else Reversibility.IRREVERSIBLE
        )

        decision = decide(
            reversibility=reversibility,
            verifiable=verifiable,
            projected_usd=projected_usd,
            headroom_usd=self.budgets.headroom(agent_id),
            destructive=destructive,
        )

        # REQ-104 — 계약이 없으면 자동 대상이 아니다.
        status = Status.MANUAL_REQUIRED if contract is None else _status_for(decision.verdict)

        entry = LedgerEntry(
            entry_id=entry_id,
            agent_id=agent_id,
            action_id=action_id,
            status=status,
            started_at=started,
            attribution=Attribution(Method.NONE, reason="no billable resource created"),
            assumed=zero,
            decision=decision,  # I-4 — 모든 항목이 판정을 갖는다
            contract_id=contract.contract_id if contract is not None else None,
        )
        self.ledger.create(entry)

        # ── I-1 — 막는 판정이면 **실행기를 부르지 않는다** (REQ-403).
        if contract is None or decision.verdict in BLOCKING or decision.verdict is Gate.APPROVE:
            return entry

        # ── ① 기준선 (REQ-201)
        baseline = self.signals.read(contract.health_signal)

        # ── I-9 — 롤백 계획은 조치 **전에** 고정된다 (REQ-301).
        plan = contract.rollback_plan

        # ── ② 실행
        ok = self.executor.execute(action_id, resource)
        self.budgets.commit(agent_id, projected_usd)
        if not ok:
            return self.ledger.complete(entry_id, status=Status.FAILED)

        # ── ③ 대기 후 ④ **같은 스펙으로** 재측정 (REQ-202)
        self.clock.sleep(VERIFY_DELAY_S)
        after = self.signals.read(contract.health_signal)

        verdict = classify(baseline, after, contract.recovery_criterion)
        decided_by = DecidedBy.RULE
        rationale = ""
        if verdict is Verdict.AMBIGUOUS:
            # ★ 모델은 **애매할 때만** 불린다 (REQ-204).
            verdict, rationale = self.judge.judge_ambiguous(
                baseline, after, str(contract.recovery_criterion)
            )
            decided_by = DecidedBy.MODEL

        verification = Verification(
            verdict=verdict,
            decided_by=decided_by,
            baseline=baseline,
            after=after,
            rationale=rationale,
        )

        if verdict is Verdict.RECOVERED:
            return self.ledger.complete(entry_id, status=Status.EXECUTED, verification=verification)

        # ── ⑤ 회복 실패 → 롤백 (REQ-302)
        rollback = self._rollback(contract, resource, plan, baseline, verification)
        return self.ledger.complete(
            entry_id, status=Status.EXECUTED, verification=verification, rollback=rollback
        )

    def _rollback(
        self,
        contract: OperationalContract,
        resource: ResourceRef,
        plan: RollbackPlan | None,
        baseline: Measurement,
        verification: Verification,
    ) -> Rollback:
        # REQ-305 — 되돌릴 수 없으면 에스컬레이션하고 **더 조치하지 않는다.**
        if plan is None:
            return Rollback(performed=False, reason="irreversible or no rollback plan — escalated")

        self.run.shift_all_traffic(resource, plan.previous_revision)

        # REQ-303 — **다시 읽어 확인한다.** '롤백했다'는 주장이고 이건 측정이다.
        traffic = dict(self.run.read_traffic(resource))
        atomic = traffic.get(plan.previous_revision) == 100

        # REQ-304 — 롤백 후에도 재측정한다. 안 돌아오면 **원인이 조치가 아니었다.**
        self.clock.sleep(VERIFY_DELAY_S)
        restored_m = self.signals.read(contract.health_signal)
        restored = (
            None if restored_m.is_empty or baseline.is_empty else _within(restored_m, baseline)
        )

        return Rollback(
            performed=atomic,
            verified_traffic=traffic,
            signal_restored=restored,
            reason="" if atomic else "traffic split did not reach the previous revision",
        )


def _status_for(verdict: Gate) -> Status:
    if verdict is Gate.DENY:
        return Status.DENIED
    if verdict is Gate.MANUAL:
        return Status.MANUAL_REQUIRED
    if verdict is Gate.APPROVE:
        return Status.AWAITING_APPROVAL
    return Status.EXECUTED


def _within(a: Measurement, b: Measurement, tol: Decimal = Decimal("0.15")) -> bool:
    assert a.value is not None and b.value is not None
    if b.value == 0:
        return a.value == 0
    return abs(a.value - b.value) / b.value <= tol
