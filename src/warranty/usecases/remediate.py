"""조치 → 검증 → 롤백 — 이 프로젝트의 루프 전체.

Spec: specs/warranty/design/02-verification.md
      specs/warranty/design/03-atomic-rollback.md
      specs/warranty/design/04-decision-gate.md
      (REQ-104, REQ-201~205, REQ-301~305, REQ-401~405)

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
from warranty.domain.entry import Approval, LedgerEntry, LedgerError, Rollback, Status
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
    Ledger,
    ModelJudge,
    RunControl,
    SignalSource,
)

# ⚠️ 재측정 타이밍의 값은 `warranty.tunables`에만 있다 (REQ-206, REQ-804).
#    여기서 다시 적으면 재촬영 때 한쪽만 바뀌고, 그 어긋남은 조용하다.
from warranty.tunables import VERIFY_DELAY_S


@dataclass(frozen=True, slots=True)
class Remediator:
    contracts: ContractStore
    signals: SignalSource
    executor: ActionExecutor
    run: RunControl
    budgets: BudgetStore
    ledger: Ledger
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
        # ⚠️ `APPROVE`도 여기서 멈춘다 — 기록된 승인 없이는 진행하지 않는다 (REQ-404).
        if contract is None or decision.verdict in BLOCKING or decision.verdict is Gate.APPROVE:
            return entry

        return self._execute_and_verify(
            entry_id=entry_id,
            agent_id=agent_id,
            action_id=action_id,
            resource=resource,
            contract=contract,
            projected_usd=projected_usd,
        )

    def approve(self, *, entry_id: str, resource: ResourceRef, approver: str) -> LedgerEntry:
        """기록된 승인. ★ **승인은 게이트 면제가 아니다** (REQ-404).

        Spec: specs/warranty/design/04-decision-gate.md (REQ-404, REQ-105)

        승인은 *"비가역성 / 검증 불가에 동의한다"*는 뜻이지 **예산 면제나 계약 면제가
        아니다.** 그래서 승인 시점에 **게이트를 다시 평가한다** — 대기하는 동안 예산이
        마르거나 계약이 `retired`가 됐을 수 있고, 그때 원래 판정은 이미 낡았다.
        """
        entry = self.ledger.get(entry_id)
        if entry is None:
            raise LedgerError(f"없는 항목이다: {entry_id}")
        prior = entry.decision
        if prior is None:
            # 판정 없는 항목은 무엇에 동의하는지가 없다 (I-4).
            raise LedgerError(f"판정 없는 항목은 승인할 수 없다: {entry_id}")

        # ── ★ 재판정. 원래 판정의 **예상 비용과 파괴성은 그대로 쓴다** — 승인 대상은
        #    같은 조치여야 한다. 다시 읽는 것은 계약·신호·예산, 즉 **세상 쪽**이다.
        contract = self.contracts.active_for(resource)
        verifiable = contract is not None and self.signals.readable(contract.health_signal)
        reversibility = (
            contract.reversibility if contract is not None else Reversibility.IRREVERSIBLE
        )
        redecision = decide(
            reversibility=reversibility,
            verifiable=verifiable,
            projected_usd=prior.projected_usd,
            headroom_usd=self.budgets.headroom(entry.agent_id),
            destructive=prior.destructive,
        )

        # 승인은 **먼저 기록된다.** 막힌 승인도 기록이다 — 누가 언제 눌렀는지가 사라지면
        # 나중에 "아무도 승인 안 했다"와 구분이 안 된다.
        self.ledger.approve(
            entry_id,
            Approval(
                approver=approver,
                approved_at=datetime.fromisoformat(self.clock.now_iso()),
                reevaluated=redecision,
            ),
        )

        # REQ-105 — 계약이 사라졌거나 **다른 계약으로 바뀌었으면** 그 승인은 이 계약에
        # 대한 동의가 아니었다. 리소스가 재프로비저닝되면 계약 id가 바뀐다.
        if contract is None or contract.contract_id != entry.contract_id:
            return self.ledger.complete(entry_id, status=Status.MANUAL_REQUIRED)
        if redecision.verdict in BLOCKING:
            return self.ledger.complete(entry_id, status=_status_for(redecision.verdict))

        return self._execute_and_verify(
            entry_id=entry_id,
            agent_id=entry.agent_id,
            action_id=entry.action_id,
            resource=resource,
            contract=contract,
            projected_usd=prior.projected_usd,
        )

    def _execute_and_verify(
        self,
        *,
        entry_id: str,
        agent_id: str,
        action_id: str,
        resource: ResourceRef,
        contract: OperationalContract,
        projected_usd: Decimal,
    ) -> LedgerEntry:
        """게이트를 통과한 뒤의 전부 — 예약 → 기준선 → 실행 → 재측정 → (필요하면) 롤백.

        Spec: specs/warranty/design/04-decision-gate.md (REQ-405)

        ⚠️ `AUTO`와 **승인된 조치가 같은 경로를 탄다.** 승인 경로를 따로 배선하면
        그 경로만 검증·롤백을 빠뜨리게 되고, 그 누락은 조용하다. **예약도 마찬가지다** —
        여기 한 곳에서만 예약하니 승인 경로가 예약을 건너뛸 자리가 없다.
        """
        # ── ⓪ 예약 (REQ-405). ★ **실행 전에** 여유를 붙잡는다. 게이트가 `headroom`을
        #    읽은 시점과 돈이 나가는 시점 사이에 다른 조치가 들어오면 **같은 여유를 다시
        #    본다** — 둘 다 판정을 통과하고 합계는 한도를 넘는다.
        #    ⚠️ 예약 실패는 **지금 예산이 막는다**는 뜻이다. 판정은 낡았고 예약이 권위다.
        reservation = self.budgets.reserve(agent_id, projected_usd)
        if reservation is None:
            return self.ledger.complete(entry_id, status=Status.DENIED)

        # 실행 전에 죽으면 쓴 게 없다. 아래 `finally`가 이 값으로 정산한다.
        actual = Decimal(0)
        try:
            # ── ① 기준선 (REQ-201)
            baseline = self.signals.read(contract.health_signal)

            # ── I-9 — 롤백 계획은 조치 **전에** 고정된다 (REQ-301).
            plan = contract.rollback_plan

            # ── ② 실행
            ok = self.executor.execute(action_id, resource)
            if not ok:
                return self.ledger.complete(entry_id, status=Status.FAILED)
            # ⚠️ 공시 단가지 청구서가 아니다. 실측은 `reconcile`로 따로 온다 (REQ-506) —
            #    `assumed`를 덮지 않는 이유와 같다 (I-1).
            actual = projected_usd

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
                return self.ledger.complete(
                    entry_id, status=Status.EXECUTED, verification=verification
                )

            # ── ⑤ 회복 실패 → 롤백 (REQ-302)
            rollback = self._rollback(contract, resource, plan, baseline, verification)
            return self.ledger.complete(
                entry_id, status=Status.EXECUTED, verification=verification, rollback=rollback
            )
        finally:
            # ── ⑥ 정산 (REQ-405). ⚠️ **예외 경로에서도 돈다** — 안 풀린 예약은 여유를
            #    조용히 잠그고, 잠긴 예산은 "예산 없음"과 구분이 안 된다 (design 04§3).
            self.budgets.settle(reservation, actual)

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
