"""검증 — "실행됨 ≠ 나아졌음". 가드 G8."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from warranty.domain.attribution import Attribution, Method
from warranty.domain.contract import Criterion, CriterionMode, Direction
from warranty.domain.cost import Basis, CostFact
from warranty.domain.entry import LedgerEntry, Rollback, Status
from warranty.domain.verification import (
    DecidedBy,
    Measurement,
    Verdict,
    Verification,
    classify,
)

FROZEN = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
CRIT = Criterion(Direction.DECREASE, Decimal("0.5"), CriterionMode.RELATIVE, Decimal("0.1"))


def _m(value: str | None, points: int = 30) -> Measurement:
    return Measurement(Decimal(value) if value is not None else None, points)


def _entry(**over: Any) -> LedgerEntry:
    """⚠️ 기본값도 타입 검사를 받게 생성자로 만든다 — `dict[str, object]`로 쌓으면
    `LedgerEntry(**base)`의 억제가 **기본값의 오타까지** 함께 덮는다(T0-9).
    ⛔ 재정의 인자는 여전히 검사 밖이다(`Any`).
    """
    base = LedgerEntry(
        entry_id="01k2m9x7q3f4b8n0v6c1t5r2wz",
        agent_id="warranty",
        action_id="shift_traffic",
        status=Status.EXECUTED,
        started_at=FROZEN,
        attribution=Attribution(Method.NONE, reason="no billable resource"),
        assumed=CostFact(Decimal(0), FROZEN, Basis.PUBLISHED_RATE),
    )
    return replace(base, **over)


def _verification(verdict: Verdict) -> Verification:
    return Verification(
        verdict=verdict,
        decided_by=DecidedBy.RULE,
        baseline=_m("1.0"),
        after=_m("0.2"),
    )


# ── 판정 (REQ-203, REQ-205) ────────────────────────────────────────────


def test_req_203_clear_improvement_is_recovered() -> None:
    """Verifies: REQ-203"""
    assert classify(_m("1.0"), _m("0.2"), CRIT) is Verdict.RECOVERED


def test_req_203_clear_failure_is_not_recovered() -> None:
    """Verifies: REQ-203"""
    assert classify(_m("1.0"), _m("0.95"), CRIT) is Verdict.NOT_RECOVERED


def test_req_204_inside_tolerance_is_handed_to_the_model() -> None:
    """Verifies: REQ-204

    ★ 모델의 판단이 하중을 받는 자리. **명확한 경우는 모델을 안 부른다** —
    부르면 판정이 비결정적이 되고 REQ-802가 깨진다.
    """
    assert classify(_m("1.0"), _m("0.5"), CRIT) is Verdict.AMBIGUOUS


def test_req_205_empty_window_is_unverifiable_not_a_verdict() -> None:
    """Verifies: REQ-205

    ⚠️ 아직 안 온 데이터로 판정하면 `unverifiable`이 아니라 **거짓 판정**이다.
    """
    assert classify(_m("1.0"), _m(None, points=0), CRIT) is Verdict.UNVERIFIABLE
    assert classify(_m(None, points=0), _m("0.2"), CRIT) is Verdict.UNVERIFIABLE


def test_req_204_model_verdict_without_a_rationale_is_rejected() -> None:
    """Verifies: REQ-204

    근거 없는 모델 판정은 검증이 아니라 주사위다.
    """
    with pytest.raises(ValueError, match="근거가 없다"):
        Verification(Verdict.RECOVERED, DecidedBy.MODEL, _m("1.0"), _m("0.2"))


def test_req_204_ambiguous_cannot_be_a_final_verdict() -> None:
    """Verifies: REQ-204

    AMBIGUOUS는 **중간 상태**다. 모델이 recovered/not_recovered 중 하나로 닫아야 한다.
    """
    with pytest.raises(ValueError, match="최종 판정이 아니다"):
        Verification(Verdict.AMBIGUOUS, DecidedBy.RULE, _m("1.0"), _m("0.5"))


# ── ★ G8 — `improved`는 저장이 아니라 유도 (REQ-502) ────────────────────


def test_req_502_improved_is_derived_not_stored() -> None:
    """Verifies: REQ-502

    ★ G8 — 저장 필드로 두면 `verification.verdict`와 어긋날 수 있고,
    **어긋난 쪽이 리포트에 실린다.**
    """
    assert "improved" not in LedgerEntry.__slots__
    entry = _entry(verification=_verification(Verdict.RECOVERED))
    assert entry.improved is True


def test_req_502_executed_improved_rolled_back_are_three_values() -> None:
    """Verifies: REQ-502

    ★ 이 시스템이 말할 수 있고 대부분의 도구가 말할 수 없는 문장:
    **실행은 됐고, 나아지지는 않았고, 되돌렸다.**
    """
    entry = _entry(
        verification=_verification(Verdict.NOT_RECOVERED),
        rollback=Rollback(performed=True, verified_traffic={"svc-00007-abc": 100}),
    )
    assert entry.executed is True
    assert entry.improved is False
    assert entry.rolled_back is True


def test_req_502_no_verification_means_not_improved() -> None:
    """Verifies: REQ-502, REQ-205

    ⚠️ 검증이 없으면 **회복이 아니다.** 조용한 성공을 만들지 않는다.
    """
    assert _entry().improved is False


def test_req_205_unverifiable_is_not_improved() -> None:
    """Verifies: REQ-205

    ⚠️ 여기서 관대해지면 논지가 무너진다 — `unverifiable`을 성공으로 세면
    회복률이 거짓말이 된다.
    """
    entry = _entry(
        verification=Verification(Verdict.UNVERIFIABLE, DecidedBy.RULE, _m(None, 0), _m(None, 0))
    )
    assert entry.improved is False


# ── 계약 (REQ-102) ─────────────────────────────────────────────────────


def test_req_102_reversible_without_a_rollback_plan_is_refused() -> None:
    """Verifies: REQ-102, REQ-104

    되돌릴 방법 없이 가역일 수 없다. 조용한 기본값을 주면 **그 장식 위에서
    자동 조치가 돈다.**
    """
    from warranty.domain.contract import (
        ContractError,
        OperationalContract,
        ResourceRef,
        Reversibility,
        SignalSpec,
    )

    with pytest.raises(ContractError, match="롤백 계획이 없다"):
        OperationalContract(
            contract_id="c1",
            resource=ResourceRef("cloud_run_service", "svc", "us-central1"),
            health_signal=SignalSpec("m", "svc", "ALIGN_RATE", 120),
            recovery_criterion=CRIT,
            rollback_plan=None,
            reversibility=Reversibility.REVERSIBLE,
            provisioned_at=FROZEN,
            provisioned_by="e1",
        )


def test_req_105_retiring_a_contract_makes_it_inactive() -> None:
    """Verifies: REQ-105

    ⚠️ 없는 리소스를 가리키는 계약이 살아 있으면, 자동 조치가 **존재하지 않는 것을
    고치려 한다.** 조치는 '성공'하고 신호는 안 움직인다.
    """
    from warranty.domain.contract import (
        OperationalContract,
        ResourceRef,
        Reversibility,
        RollbackPlan,
        SignalSpec,
    )

    c = OperationalContract(
        contract_id="c1",
        resource=ResourceRef("cloud_run_service", "svc", "us-central1"),
        health_signal=SignalSpec("m", "svc", "ALIGN_RATE", 120),
        recovery_criterion=CRIT,
        rollback_plan=RollbackPlan("svc-00007-abc"),
        reversibility=Reversibility.REVERSIBLE,
        provisioned_at=FROZEN,
        provisioned_by="e1",
    )
    assert c.is_active
    assert not c.retired().is_active
