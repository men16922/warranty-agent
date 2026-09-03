"""Firestore 문서 매핑 — 실물 없이 **무엇을 쓰고 무엇을 되읽는지**를 태운다.

Spec: specs/warranty/design/08-interfaces.md §2, §2.1 (REQ-102, REQ-501, REQ-505)

이 파일은 SDK를 임포트하거나 클라이언트를 만들지 않는다. 묻는 것은 문서의 모양,
왕복의 정확성, 그리고 **불변식이 이 어댑터에 두 번째 사본으로 생기지 않았는가**다.
실제로 Firestore가 답하는지는 라이브 수용 기준이다.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from warranty.adapters.live_store import (
    CONTRACTS,
    LEDGER,
    RESOURCE_FIELDS,
    STATE_FIELD,
    StoreError,
    active_contract_conditions,
    contract_document,
    contracts_collection_path,
    decode,
    decode_dataclass,
    encode,
    entry_document,
    ledger_collection_path,
    one_active,
)
from warranty.domain.attribution import Attribution, Method
from warranty.domain.contract import (
    ContractState,
    Criterion,
    CriterionMode,
    Direction,
    OperationalContract,
    ResourceRef,
    Reversibility,
    RollbackPlan,
    SignalSpec,
)
from warranty.domain.cost import Basis, CostFact, delta_of
from warranty.domain.decision import Gate, decide
from warranty.domain.entry import (
    Approval,
    EntryKind,
    LedgerEntry,
    ReconcileState,
    Rollback,
    Status,
)
from warranty.domain.verification import DecidedBy, Measurement, Verdict, Verification

FROZEN = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)  # REQ-802: 살아 있는 시계를 안 쓴다
ENTRY_ID = "01k2m9x7q3f4b8n0v6c1t5r2wz"
RESOURCE = ResourceRef(kind="cloud_run_service", name="demo-target", region="us-central1")
SOURCE = Path("src/warranty/adapters/live_store.py")


def _contract(**over: Any) -> OperationalContract:
    base = OperationalContract(
        contract_id="c1",
        resource=RESOURCE,
        health_signal=SignalSpec("run.googleapis.com/request_latencies", "demo-target", "P95", 120),
        recovery_criterion=Criterion(
            direction=Direction.DECREASE,
            threshold=Decimal("700.0"),
            mode=CriterionMode.ABSOLUTE,
            tolerance=Decimal("0.10"),
        ),
        rollback_plan=RollbackPlan("demo-target-00001-abc"),
        reversibility=Reversibility.REVERSIBLE,
        provisioned_at=FROZEN,
        provisioned_by="e0",
        cost_model="cpu_seconds",
    )
    return replace(base, **over)


def _assumed() -> CostFact:
    return CostFact(
        amount_usd=Decimal("0.0200"),
        priced_at=FROZEN,
        basis=Basis.PUBLISHED_RATE,
        inputs={"cpu_seconds": Decimal(60)},
        unit_prices={"cpu_seconds": Decimal("0.000333")},
        source_note="published rate",
    )


def _measured() -> CostFact:
    return CostFact(amount_usd=Decimal("1.9000"), priced_at=FROZEN, basis=Basis.BILLING_EXPORT)


def _entry(**over: Any) -> LedgerEntry:
    """⚠️ 생성자로 만들고 `replace`로 덮는다 — 기본값도 타입 검사를 받게 하려는 것이다."""
    decision = decide(
        reversibility=Reversibility.REVERSIBLE,
        verifiable=True,
        projected_usd=Decimal("0.0200"),
        headroom_usd=Decimal("0.5000"),
    )
    base = LedgerEntry(
        entry_id=ENTRY_ID,
        agent_id="fleet-steward",
        action_id="rollout_revision",
        status=Status.EXECUTED,
        started_at=FROZEN,
        attribution=Attribution(Method.RESOURCE_LABEL, label_value=ENTRY_ID),
        assumed=_assumed(),
        decision=decision,
        contract_id="c1",
        verification=Verification(
            verdict=Verdict.NOT_RECOVERED,
            decided_by=DecidedBy.RULE,
            baseline=Measurement(Decimal("674.2"), 30),
            after=Measurement(Decimal("988.6"), 30),
            rationale="p95가 기준을 넘었다",
        ),
        rollback=Rollback(
            performed=True,
            verified_traffic={"demo-target-00001-abc": 100},
            signal_restored=True,
            reason="",
        ),
    )
    return replace(base, **over)


# ── 왕복 — 문서가 도메인 값을 **잃지 않는가** ─────────────────────────────────────


def test_contract_round_trips_through_a_document() -> None:
    contract = _contract()
    assert decode_dataclass(OperationalContract, contract_document(contract)) == contract


def test_ledger_entry_round_trips_with_every_optional_filled() -> None:
    """⚠️ 선택 필드가 **채워진** 행으로 태운다 — 비어 있으면 `None`만 왕복하고,
    중첩된 판정·검증·롤백이 안 실려도 초록이다."""
    entry = _entry(
        approval=Approval(
            approver="operator",
            approved_at=FROZEN,
            reevaluated=decide(
                reversibility=Reversibility.REVERSIBLE,
                verifiable=True,
                projected_usd=Decimal("0.0200"),
                headroom_usd=Decimal("0.5000"),
            ),
        ),
        status=Status.AWAITING_APPROVAL,
        measured=_measured(),
        delta=delta_of(_assumed(), _measured()),
        reconcile_state=ReconcileState.RECONCILED,
        retry_of="01k2m9x7q3f4b8n0v6c1t5r2wy",
        kind=EntryKind.ACTION,
    )
    assert decode_dataclass(LedgerEntry, entry_document(entry)) == entry


def test_a_row_that_was_never_reconciled_round_trips_too() -> None:
    entry = _entry(decision=None, verification=None, rollback=None, contract_id=None)
    assert decode_dataclass(LedgerEntry, entry_document(entry)) == entry


# ── 돈 — **double로 왕복시키지 않는다** (REQ-503·505) ────────────────────────────


def test_money_is_stored_as_text_not_as_a_number() -> None:
    """⛔ Firestore의 수치는 double이다. `0.0200`을 그 타입으로 보내면 돌아오는 값은
    청구서와 안 맞고, 안 맞는 이유는 코드 어디에도 안 적혀 있다."""
    document = entry_document(_entry())
    assert document["assumed"]["amount_usd"] == "0.0200"
    assert document["assumed"]["inputs"]["cpu_seconds"] == "60"
    assert document["decision"]["projected_usd"] == "0.0200"


def test_a_number_in_a_money_field_is_refused() -> None:
    """⛔ double로 저장된 돈은 이미 값이 바뀐 뒤다 — 받아 주면 그 손실이 도메인에 들어온다."""
    document = entry_document(_entry())
    document["assumed"]["amount_usd"] = 0.02
    with pytest.raises(StoreError, match="Decimal"):
        decode_dataclass(LedgerEntry, document)


def test_money_keeps_its_scale_across_the_round_trip() -> None:
    """⚠️ `0.0200`과 `0.02`는 같은 수지만 **같은 사실이 아니다** — 자릿수는 단가가 몇 자리로
    계산됐는지를 말한다. 문자열로 실으면 그 자릿수가 보존된다."""
    entry = decode_dataclass(LedgerEntry, entry_document(_entry()))
    assert str(entry.assumed.amount_usd) == "0.0200"


# ── 문서의 모양 ─────────────────────────────────────────────────────────────────


def test_document_carries_only_values_firestore_can_hold() -> None:
    allowed = (str, int, float, bool, type(None))

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
            return
        assert isinstance(value, allowed), f"문서에 실릴 수 없는 값이다: {type(value).__name__}"

    walk(entry_document(_entry()))
    walk(contract_document(_contract()))


def test_enums_are_stored_as_their_declared_value() -> None:
    document = contract_document(_contract())
    assert document["state"] == ContractState.ACTIVE.value
    assert document["reversibility"] == Reversibility.REVERSIBLE.value
    assert entry_document(_entry())["decision"]["verdict"] == Gate.AUTO.value


def test_fields_the_constructor_does_not_take_are_not_stored() -> None:
    """⚠️ `_required`는 파생된 선언이다. 문서에 실으면 그것이 **저장된 사실**이 되고,
    도메인이 그 목록을 고치는 날 옛 문서가 새 코드와 다른 것을 말한다."""
    assert "_required" not in contract_document(_contract())


# ── 복원 — **마이그레이션은 소리를 내야 한다** ───────────────────────────────────


def test_a_missing_field_is_refused_instead_of_defaulted() -> None:
    document = entry_document(_entry())
    del document["kind"]
    with pytest.raises(StoreError, match="kind"):
        decode_dataclass(LedgerEntry, document)


def test_an_unknown_field_is_refused() -> None:
    document = entry_document(_entry())
    document["improved"] = True
    with pytest.raises(StoreError, match="improved"):
        decode_dataclass(LedgerEntry, document)


def test_an_enum_value_we_do_not_know_is_refused() -> None:
    document = entry_document(_entry())
    document["status"] = "probably_fine"
    with pytest.raises(StoreError, match="Status"):
        decode_dataclass(LedgerEntry, document)


def test_a_boolean_is_not_accepted_where_a_number_belongs() -> None:
    """⚠️ 파이썬에서 `True`는 `1`이다. 그냥 `isinstance`로 물으면 `points=True`가 통과한다."""
    document = entry_document(_entry())
    document["verification"]["baseline"]["points"] = True
    with pytest.raises(StoreError, match="int"):
        decode_dataclass(LedgerEntry, document)


def test_null_where_the_field_cannot_be_null_is_refused() -> None:
    document = entry_document(_entry())
    document["started_at"] = None
    with pytest.raises(StoreError):
        decode_dataclass(LedgerEntry, document)


def test_a_document_that_is_not_a_mapping_is_refused() -> None:
    with pytest.raises(StoreError, match="LedgerEntry"):
        decode_dataclass(LedgerEntry, ["not", "a", "document"])


def test_a_value_we_cannot_store_is_refused_instead_of_stringified() -> None:
    """⛔ `str()`로 뭉개면 **저장은 성공하고 복원이 깨진다** — 그 실패는 쓰는 날이 아니라
    읽는 날에 난다."""
    with pytest.raises(StoreError, match="set"):
        encode({"seen"})


def test_a_type_we_cannot_restore_is_refused() -> None:
    with pytest.raises(StoreError, match="복원할 수 없는"):
        decode(complex, "1+2j")


# ── 계약 조회 — `retired`를 **질의에서** 거른다 (REQ-105) ────────────────────────


def test_the_query_filters_on_state_not_in_python() -> None:
    conditions = active_contract_conditions(RESOURCE)
    assert (STATE_FIELD, "==", ContractState.ACTIVE.value) in conditions


def test_the_query_pins_all_three_parts_of_the_resource() -> None:
    """⚠️ 이름만 걸면 리전이 둘인 날 **다른 리전의 같은 이름**이 걸린다."""
    conditions = active_contract_conditions(RESOURCE)
    assert tuple(path for path, _, _ in conditions)[:3] == RESOURCE_FIELDS
    assert [value for _, _, value in conditions][:3] == [
        RESOURCE.kind,
        RESOURCE.name,
        RESOURCE.region,
    ]


def test_a_resource_without_a_name_cannot_be_looked_up() -> None:
    with pytest.raises(StoreError, match="이름"):
        active_contract_conditions(ResourceRef(kind="cloud_run_service", name="", region="us"))


def test_no_active_contract_reads_as_none_not_as_an_error() -> None:
    """⚠️ 계약 없음은 고장이 아니라 **MANUAL로 가는 정상 경로**다 (REQ-104)."""
    assert one_active([], RESOURCE) is None


def test_two_active_contracts_are_refused_rather_than_picked_from() -> None:
    """⛔ 아무거나 고르면 *"어느 기준으로 회복을 판정했는가"*의 답이 실행할 때마다 달라진다."""
    document = contract_document(_contract())
    with pytest.raises(StoreError, match="둘 이상"):
        one_active([document, contract_document(_contract(contract_id="c2"))], RESOURCE)


def test_one_active_contract_comes_back_as_the_contract() -> None:
    contract = _contract()
    assert one_active([contract_document(contract)], RESOURCE) == contract


def test_collections_are_named_in_exactly_one_place() -> None:
    assert (CONTRACTS, LEDGER) == ("contracts", "ledger")
    assert contracts_collection_path(None) == "contracts"
    assert ledger_collection_path(None) == "ledger"
    assert contracts_collection_path("devops-uid-42") == "users/devops-uid-42/contracts"
    assert ledger_collection_path("devops-uid-42") == "users/devops-uid-42/ledger"


# ── ⛔ 불변식의 두 번째 사본이 여기 생기지 않았는가 ──────────────────────────────


def test_the_adapter_does_not_edit_entry_fields_itself() -> None:
    """⛔ 이 어댑터가 `replace(...)`로 필드를 직접 고치기 시작하면 원장의 규칙은
    **저장소마다 한 벌씩** 생긴다. 그러면 `assumed` 불변도, "승인은 한 번"도
    한쪽에서만 참인 날이 온다 (design 08§2).

    ⚠️ 문서를 읽어서 판정하지 않고 **소스를 읽어서** 판정한다 — 규칙이 문장으로만
    남으면 그것은 지켜지지 않는다.
    """
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "replace" not in called


def test_every_transition_goes_through_the_domain_functions() -> None:
    """⚠️ 네 전이 전부가 도메인 함수를 부르는가. 하나라도 빠지면 그 전이만 규칙 밖이다."""
    source = SOURCE.read_text(encoding="utf-8")
    for name in (
        "apply_approval",
        "apply_completion",
        "apply_reconcile",
        "apply_give_up_reconcile",
    ):
        assert f"{name}(" in source, f"{name}을 안 부른다 — 그 전이는 규칙 밖이다"
