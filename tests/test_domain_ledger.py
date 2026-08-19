"""T1 도메인 — 원장 행의 불변식.

가드 G2(assumed 불변) · G3(method↔verifiability) · G7(1회=1행)이 여기 있다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from fleet_ledger.domain.attribution import (
    Attribution,
    AttributionError,
    Method,
    Verifiability,
)
from fleet_ledger.domain.cost import Basis, CostFact, CostFactError, delta_of
from fleet_ledger.domain.entry import (
    InMemoryLedger,
    LedgerEntry,
    LedgerError,
    ReconcileState,
    Status,
)

FROZEN = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)  # REQ-702: 살아 있는 시계를 안 쓴다
ENTRY_ID = "01k2m9x7q3f4b8n0v6c1t5r2wz"


def _assumed(amount: str = "0.0200") -> CostFact:
    return CostFact(
        amount_usd=Decimal(amount),
        priced_at=FROZEN,
        basis=Basis.PUBLISHED_RATE,
        inputs={"cpu_seconds": Decimal(60)},
        unit_prices={"cpu_seconds": Decimal("0.000333")},
    )


def _measured(amount: str = "1.9000") -> CostFact:
    return CostFact(amount_usd=Decimal(amount), priced_at=FROZEN, basis=Basis.BILLING_EXPORT)


def _entry(**over: object) -> LedgerEntry:
    base: dict[str, object] = {
        "entry_id": ENTRY_ID,
        "agent_id": "fleet-steward",
        "action_id": "restart_service",
        "status": Status.EXECUTED,
        "started_at": FROZEN,
        "attribution": Attribution(Method.RESOURCE_LABEL, label_value=ENTRY_ID),
        "assumed": _assumed(),
    }
    base.update(over)
    return LedgerEntry(**base)  # type: ignore[arg-type]


# ── REQ-202 ────────────────────────────────────────────────────────────────


def test_req_202_cost_fact_keeps_the_quantities_that_made_the_total() -> None:
    """Verifies: REQ-202

    총액만이 아니라 **수량·단가·가격 기준 시각**을 함께 갖는다. 그래야 나중에
    "왜 틀렸나"를 총액이 아니라 어느 가정이 틀렸는지로 답할 수 있다.
    """
    fact = _assumed()
    assert fact.inputs["cpu_seconds"] == Decimal(60)
    assert fact.unit_prices["cpu_seconds"] == Decimal("0.000333")
    assert fact.priced_at == FROZEN
    assert fact.is_recomputable
    assert fact.recompute() == Decimal("0.019980")


def test_req_202_rejects_a_computed_fact_without_matching_prices() -> None:
    """Verifies: REQ-202

    수량과 단가의 키가 어긋나면 재계산이 불가능하고, 재계산 불가능한 추정은
    왜 틀렸는지 물을 수 없다.
    """
    with pytest.raises(CostFactError, match="키가 다르다"):
        CostFact(
            amount_usd=Decimal("1"),
            priced_at=FROZEN,
            basis=Basis.PUBLISHED_RATE,
            inputs={"cpu_seconds": Decimal(60)},
            unit_prices={"gb_seconds": Decimal("0.1")},
        )


def test_req_202_inputs_are_not_mutable_after_construction() -> None:
    """Verifies: REQ-202"""
    fact = _assumed()
    with pytest.raises(TypeError):
        fact.inputs["cpu_seconds"] = Decimal(999)  # type: ignore[index]


# ── REQ-203 (가드 G3) ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        (Method.RESOURCE_LABEL, Verifiability.RECONCILABLE),
        (Method.TOKEN_METER, Verifiability.ASSUMED_ONLY),
        (Method.NONE, Verifiability.ASSUMED_ONLY),
    ],
)
def test_req_203_verifiability_is_derived_from_method(
    method: Method, expected: Verifiability
) -> None:
    """Verifies: REQ-203

    G3 — 매핑은 코드에 한 벌만 있고, 셋 **전부**를 값으로 명시해 태운다.
    형제 중 하나만 순회하면 나머지는 안 물어진 채다 (REFERENCE_FROM_PARENT #10).
    """
    kwargs: dict[str, str] = {}
    if method is Method.RESOURCE_LABEL:
        kwargs["label_value"] = ENTRY_ID
    elif method is Method.NONE:
        kwargs["reason"] = "read-only action"
    assert Attribution(method, **kwargs).verifiability is expected  # type: ignore[arg-type]


def test_req_203_entry_derives_verifiability_and_does_not_store_it() -> None:
    """Verifies: REQ-203

    저장하면 귀속 방법과 어긋날 수 있다. 유도하면 어긋날 수 없다.
    """
    entry = _entry(attribution=Attribution(Method.TOKEN_METER))
    assert entry.verifiability is Verifiability.ASSUMED_ONLY
    assert not hasattr(entry, "_verifiability")


def test_req_206_none_without_a_reason_is_rejected() -> None:
    """Verifies: REQ-206

    조용한 `none`을 만들면 화해가 영원히 못 찾는데 **원인이 안 보인다.**
    """
    with pytest.raises(AttributionError, match="사유가 없다"):
        Attribution(Method.NONE)


def test_req_205_label_value_must_satisfy_gcp_label_constraints() -> None:
    """Verifies: REQ-205

    id 형식은 GCP 라벨 제약(소문자·≤63자)에서 **유도된 것**이다.
    """
    with pytest.raises(AttributionError, match="라벨 제약"):
        Attribution(Method.RESOURCE_LABEL, label_value="UPPER-CASE-NOT-ALLOWED")


# ── REQ-204 (가드 G2) ──────────────────────────────────────────────────────


def test_req_204_reconcile_does_not_touch_assumed() -> None:
    """Verifies: REQ-204, REQ-402

    ★ 이 시스템의 최상위 불변식. 추정을 실측으로 덮으면 "추정이 얼마나 틀렸나"를
    영원히 못 본다 — 그게 이 프로젝트의 존재 이유다.
    """
    ledger = InMemoryLedger()
    ledger.create(_entry())
    before = _assumed()

    after = ledger.reconcile(ENTRY_ID, _measured("1.9000"))

    assert after.assumed == before
    assert after.assumed.amount_usd == Decimal("0.0200")
    assert after.measured is not None
    assert after.measured.amount_usd == Decimal("1.9000")
    assert after.delta is not None
    assert after.delta.amount_usd == Decimal("1.8800")
    assert after.delta.ratio == Decimal("95")


def test_req_204_store_offers_no_general_update_path() -> None:
    """Verifies: REQ-204

    불변식을 문서가 아니라 **API 모양으로** 집행한다. 범용 쓰기가 있으면
    I-1은 관례가 되고, 관례는 언젠가 깨진다.
    """
    forbidden = {"update", "put", "save", "set", "replace", "write"}
    assert forbidden.isdisjoint(dir(InMemoryLedger))


def test_req_403_reconcile_is_idempotent() -> None:
    """Verifies: REQ-403"""
    ledger = InMemoryLedger()
    ledger.create(_entry())
    first = ledger.reconcile(ENTRY_ID, _measured("1.9000"))
    second = ledger.reconcile(ENTRY_ID, _measured("2.5000"))
    assert second == first
    assert second.measured is not None
    assert second.measured.amount_usd == Decimal("1.9000")


def test_req_402_delta_ratio_is_undefined_when_assumed_is_zero() -> None:
    """Verifies: REQ-402

    거부된 항목은 `assumed == 0`이다. 배율을 0으로 나누지 않고, **사유를 남긴다.**
    """
    zero = CostFact(amount_usd=Decimal(0), priced_at=FROZEN, basis=Basis.PUBLISHED_RATE)
    delta = delta_of(zero, _measured("0.5000"))
    assert delta.ratio is None
    assert "정의되지 않는다" in delta.note


# ── REQ-201 / REQ-207 (가드 G7) ────────────────────────────────────────────


def test_req_201_one_action_is_one_row_and_retry_does_not_overwrite() -> None:
    """Verifies: REQ-201

    G7 — 재시도는 **새 id**를 만들고 `retry_of`로 원래를 가리킨다.
    같은 id로 덮으면 원장이 사건을 잃는다.
    """
    ledger = InMemoryLedger()
    ledger.create(_entry())
    with pytest.raises(LedgerError, match="이미 있는 항목"):
        ledger.create(_entry())

    retry = _entry(entry_id="01k2m9x7q3f4b8n0v6c1t5r300", retry_of=ENTRY_ID)
    ledger.create(retry)
    assert len(ledger.all_entries()) == 2


def test_req_207_denied_entries_are_recorded_with_zero_assumed() -> None:
    """Verifies: REQ-207

    거부를 기록하지 않으면 "게이트가 얼마를 막았는가"를 못 답한다 —
    그게 게이트의 유일한 실적 지표다.
    """
    ledger = InMemoryLedger()
    denied = _entry(
        status=Status.DENIED,
        attribution=Attribution(Method.NONE, reason="action not executed"),
        assumed=CostFact(amount_usd=Decimal(0), priced_at=FROZEN, basis=Basis.PUBLISHED_RATE),
        reconcile_state=ReconcileState.NOT_APPLICABLE,
    )
    ledger.create(denied)
    stored = ledger.get(ENTRY_ID)
    assert stored is not None
    assert stored.status is Status.DENIED
    assert stored.assumed.amount_usd == Decimal(0)
    assert stored.verifiability is Verifiability.ASSUMED_ONLY
