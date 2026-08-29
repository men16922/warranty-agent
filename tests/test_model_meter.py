"""모델 호출 계량 — ★ **호출 1건 = 원장 1행** (REQ-603).

Spec: specs/warranty/design/06-agent-runtime.md (REQ-603)

⚠️ 전부 fake 모델 위다. 이 파일이 통과해도 REQ-601은 만족되지 않는다 —
   스텁은 인터페이스의 **존재**를 증명하지 않는다 (docs/PRINCIPLES.md #3).
⚠️ 이 파일이 지키는 것은 두 가지다: 원장을 만드는 경로가 **하나도 안 빠지는가**(#9),
   그리고 계량한 행이 **조치인 척하지 않는가**(REQ-508의 분모).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, get_protocol_members

import pytest

from warranty.adapters.fakes import (
    FAKE_MODEL,
    FakeBudget,
    FakeRun,
    FrozenClock,
    InMemoryContracts,
    RecordingExecutor,
    ScriptedModel,
    ScriptedSignal,
    SeededIdGen,
)
from warranty.domain.attribution import Attribution, Method, Verifiability
from warranty.domain.contract import (
    Criterion,
    CriterionMode,
    Direction,
    OperationalContract,
    ResourceRef,
    Reversibility,
    RollbackPlan,
    SignalSpec,
)
from warranty.domain.decision import decide
from warranty.domain.entry import EntryKind, InMemoryLedger, LedgerEntry, LedgerError, Status
from warranty.domain.report import daily_report
from warranty.domain.tokens import (
    ModelReply,
    Rate,
    TokenError,
    TokenPrices,
    TokenUsage,
    UnpricedModelError,
)
from warranty.domain.verification import Measurement, Verdict
from warranty.ports import ModelPort
from warranty.usecases.meter import MODEL_ACTION_PREFIX, MeteredModel
from warranty.usecases.provision import ProvisionResponse
from warranty.usecases.remediate import Remediator

FROZEN = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)  # REQ-802: 살아 있는 시계를 안 쓴다
AGENT = "warranty"
RESOURCE = ResourceRef("cloud_run_service", "demo-target", "us-central1")

#: 테스트용 단가표. ⚠️ 실물 공시 단가가 아니다 — 이 저장소는 아직 그것을 확인 못 했다
#: (design 06§2). 확인 못 한 값을 픽스처에 적으면 그 숫자가 사실처럼 굳는다(#1).
PRICES = TokenPrices(
    {FAKE_MODEL: Rate(Decimal("1.00"), Decimal("10.00"))},
    source_note="test fixture — not a published rate",
)


def _m(value: str, points: int = 30) -> Measurement:
    return Measurement(Decimal(value), points)


def _meter(
    model: ScriptedModel,
    ledger: InMemoryLedger | None = None,
    ids: SeededIdGen | None = None,
) -> MeteredModel:
    """⚠️ `ids`는 **주입된다.** 한 원장에 쓰는 경로 둘이 각자 id를 만들면 id가 겹치고,
    겹침은 `create`가 막는다 — 실제 조립에서도 id 생성기는 하나다 (I-5)."""
    return MeteredModel(
        model=model,
        ledger=ledger if ledger is not None else InMemoryLedger(),
        clock=FrozenClock(FROZEN.isoformat()),
        ids=ids if ids is not None else SeededIdGen(),
        prices=PRICES,
        agent_id=AGENT,
    )


# ── ★ 호출 1건 = 원장 1행 (REQ-603) ────────────────────────────────────


def test_req_603_one_model_call_is_one_ledger_row() -> None:
    """Verifies: REQ-603, REQ-503, REQ-504

    ★ 이 한 줄이 T5-3의 전부다. 판정은 **행 수**로 한다 — "기록했다"는 주장이고
    행을 세는 것은 측정이다.
    """
    ledger = InMemoryLedger()
    meter = _meter(ScriptedModel(Verdict.RECOVERED, "latency came back"), ledger)

    verdict, rationale = meter.judge_ambiguous(_m("1.0"), _m("0.2"), "criterion")

    assert (verdict, rationale) == (Verdict.RECOVERED, "latency came back")
    rows = ledger.all_entries()
    assert len(rows) == 1
    row = rows[0]
    assert row.kind is EntryKind.MODEL_CALL
    assert row.action_id == f"{MODEL_ACTION_PREFIX}judge_ambiguous"
    assert row.status is Status.EXECUTED
    assert row.attribution.method is Method.TOKEN_METER
    assert row.verifiability is Verifiability.ASSUMED_ONLY  # 청구 행에 라벨이 없다
    # 1000 * 1.00/1M + 200 * 10.00/1M
    assert row.assumed.amount_usd == Decimal("0.001") + Decimal("0.002")
    assert row.assumed.is_recomputable  # REQ-503 — 수량과 단가가 남아 있다


def test_req_603_two_calls_are_two_rows() -> None:
    """Verifies: REQ-603

    ⚠️ 한 번만 태우면 *"첫 호출에만 기록한다"*가 초록으로 지나간다 (REQ-501과 같은 계열).
    """
    ledger = InMemoryLedger()
    meter = _meter(ScriptedModel(), ledger)
    meter.judge_ambiguous(_m("1.0"), _m("0.5"), "c")
    meter.judge_ambiguous(_m("1.0"), _m("0.5"), "c")
    assert len(ledger.all_entries()) == 2
    assert len({row.entry_id for row in ledger.all_entries()}) == 2


def test_req_603_a_failed_call_still_leaves_a_row() -> None:
    """Verifies: REQ-603

    ⚠️ 호출이 예외로 끝나도 **토큰은 이미 나갔을 수 있다.** 성공 경로에만 기록하면
    그 지출은 원장에 영원히 없고, 없는 지출은 리포트에서 0으로 보인다.
    """
    ledger = InMemoryLedger()
    meter = _meter(ScriptedModel(raises=RuntimeError("vertex 503")), ledger)

    with pytest.raises(RuntimeError):
        meter.judge_ambiguous(_m("1.0"), _m("0.5"), "c")

    rows = ledger.all_entries()
    assert len(rows) == 1
    assert rows[0].status is Status.FAILED
    # 사용량을 못 받았으니 `token_meter`라고 적을 수 없다 — **사유가 남는다** (REQ-504).
    assert rows[0].attribution.method is Method.NONE
    assert rows[0].attribution.reason


def test_req_504_an_unpriced_model_is_not_recorded_as_token_metered() -> None:
    """Verifies: REQ-504, REQ-603

    ⚠️ 단가를 모르는 호출을 `token_meter` + 0원으로 적으면 그 행은 *"계량했는데
    공짜였다"*로 읽힌다. 그건 *"얼마인지 모른다"*와 **다른 문장이다**(#2).
    """
    ledger = InMemoryLedger()
    unknown = ScriptedModel(usage=TokenUsage("some-unlisted-model", 10, 10))
    _meter(unknown, ledger).judge_ambiguous(_m("1.0"), _m("0.5"), "c")

    row = ledger.all_entries()[0]
    assert row.attribution.method is Method.NONE
    assert "some-unlisted-model" in (row.attribution.reason or "")
    assert row.assumed.amount_usd == Decimal(0)


# ── ★ #9 — 원장을 만드는 경로를 **전부** 훑는다 ────────────────────────


#: 모델 포트의 메서드마다 그것을 **실제로 부르는** 한 줄. ⚠️ 포트에 메서드가 늘면
#: 아래 가드가 red다 — 계량을 빠뜨린 호출은 조용하고, 조용한 누락이 #9의 실패다.
MODEL_PORT_EXERCISES: dict[str, Callable[[MeteredModel], object]] = {
    "judge_ambiguous": lambda meter: meter.judge_ambiguous(_m("1.0"), _m("0.5"), "criterion"),
}


def test_req_603_every_model_port_method_is_metered() -> None:
    """Verifies: REQ-603

    ★ #9 — 형제 집합은 세는 순간 전부 센다. 산문이 *"모든 모델 호출은 포트를 지난다"*라고
    말해도, 가드가 메서드 하나만 태우면 나머지는 **안 물어진 채다.**
    """
    assert set(MODEL_PORT_EXERCISES) == get_protocol_members(ModelPort), (
        "ModelPort의 메서드와 계량 가드가 어긋났다 — 새 모델 호출이 원장을 안 남긴다"
    )
    for name, exercise in MODEL_PORT_EXERCISES.items():
        ledger = InMemoryLedger()
        exercise(_meter(ScriptedModel(), ledger))
        rows = ledger.all_entries()
        assert len(rows) == 1, f"{name}: 호출 1건인데 원장이 {len(rows)}행이다"
        assert rows[0].kind is EntryKind.MODEL_CALL


def _an_action_row(ledger: InMemoryLedger) -> None:
    """조치 경로로 행을 하나 만든다 (게이트 → 실행 → 검증).

    ⚠️ 판정 모델도 **같은 원장**에 계량된다 — 실제 조립이 그렇다. 여기서 원장을 갈라 놓으면
    "두 경로가 한 원장을 공유할 때 무슨 일이 나는가"를 이 파일이 영영 안 묻게 된다.
    """
    ids = SeededIdGen("action")
    contracts = InMemoryContracts()
    contracts.put(
        OperationalContract(
            contract_id="c1",
            resource=RESOURCE,
            health_signal=SignalSpec(
                "run.googleapis.com/request_latencies", "demo-target", "P95", 120
            ),
            recovery_criterion=Criterion(
                Direction.DECREASE, Decimal("0.5"), CriterionMode.RELATIVE, Decimal("0.1")
            ),
            rollback_plan=RollbackPlan("demo-target-00007-abc"),
            reversibility=Reversibility.REVERSIBLE,
            provisioned_at=FROZEN,
            provisioned_by="e0",
        )
    )
    Remediator(
        contracts=contracts,
        signals=ScriptedSignal([_m("1.0"), _m("0.2")]),
        executor=RecordingExecutor(),
        run=FakeRun(),
        budgets=FakeBudget(Decimal("0.50")),
        ledger=ledger,
        clock=FrozenClock(FROZEN.isoformat()),
        ids=ids,
        judge=_meter(ScriptedModel(), ledger, ids=ids),
    ).remediate(
        agent_id=AGENT,
        action_id="shift_traffic",
        resource=RESOURCE,
        projected_usd=Decimal("0.01"),
    )


def _a_model_call_row(ledger: InMemoryLedger, id_prefix: str = "model") -> None:
    meter = _meter(ScriptedModel(), ledger, ids=SeededIdGen(id_prefix))
    meter.judge_ambiguous(_m("1.0"), _m("0.5"), "criterion")


#: 원장을 만드는 **경로 전부**. ⚠️ `EntryKind`에 값이 늘면 여기도 늘어야 하고,
#: 안 늘면 아래 가드가 red다 (docs/PRINCIPLES.md #9).
def _a_provision_row(ledger: InMemoryLedger) -> None:
    """Day-1 프로비저닝 — **돈을 쓰는 리소스가 태어나는 순간**이 원장에 남는가 (REQ-504).

    ⚠️ 실물 어댑터를 안 부른다(G5 · REQ-801). 대역이 만들었다고 말하고, 우리가 보는 것은
       **그 응답에서 되읽은 라벨이 항목의 귀속이 되는가**다.
    """
    from warranty.adapters.fakes import InMemoryContracts
    from warranty.runtime import AgentTools

    AgentTools(
        remediator=None,  # type: ignore[arg-type]
        contracts=InMemoryContracts(),
        signals=None,  # type: ignore[arg-type]
        default_region=RESOURCE.region,
        provisioner=_LabellingProvisioner(),
        ledger=ledger,
        clock=FrozenClock(FROZEN.isoformat()),
        ids=SeededIdGen("prov"),
    ).provision("day1-swept")


class _LabellingProvisioner:
    """⚠️ 보낸 라벨을 **되돌려준다** — 실물 Cloud Run이 하는 일과 같은 모양이다."""

    def create(
        self, name: str, kind: str = "cloud_run_service", cost_label: str = ""
    ) -> ProvisionResponse:
        return ProvisionResponse(
            kind=kind,
            name=name,
            region=RESOURCE.region,
            previous_revision=None,
            cost_label=cost_label or None,
        )


#: 원장을 만드는 **경로 전부**. ⚠️ `EntryKind`에 값이 늘면 여기도 늘어야 하고,
#: 안 늘면 아래 가드가 red다 (docs/PRINCIPLES.md #9).
LEDGER_PRODUCERS: dict[EntryKind, Callable[[InMemoryLedger], None]] = {
    EntryKind.ACTION: _an_action_row,
    EntryKind.MODEL_CALL: _a_model_call_row,
    EntryKind.PROVISION: _a_provision_row,
}


def test_req_603_every_ledger_creating_path_is_swept() -> None:
    """Verifies: REQ-603

    ★ #9 — 원장을 만드는 경로가 여럿이면 가드는 **전부를** 훑는다. 새 경로가 생겼는데
    이 표가 안 늘면, 그 경로의 행은 아무도 안 물어본 채로 리포트에 실린다.
    """
    assert set(LEDGER_PRODUCERS) == set(EntryKind)
    for kind, produce in LEDGER_PRODUCERS.items():
        ledger = InMemoryLedger()
        produce(ledger)
        made = {row.kind for row in ledger.all_entries()}
        assert kind in made, f"{kind}: 이 경로가 그 종류의 행을 안 만든다"


def test_req_401_a_model_call_carries_no_decision() -> None:
    """Verifies: REQ-401, REQ-603

    ⚠️ 모델 호출은 게이트를 거치지 않는다. 판정을 붙이면 그 행은 *"게이트를 통과했다"*로
    읽히고, G4(모든 항목에 판정)는 그 거짓말을 **초록으로 확인해 준다.**
    """
    ledger = InMemoryLedger()
    _a_model_call_row(ledger)
    assert ledger.all_entries()[0].decision is None

    action = _an_action_row  # 조치 행은 반대로 판정을 **가져야** 한다
    other = InMemoryLedger()
    action(other)
    for row in other.all_entries():
        if row.kind is EntryKind.ACTION:
            assert row.decision is not None


# ── ★ 모델 호출 행이 조치인 척하지 않는다 (REQ-508의 분모) ─────────────


def test_req_508_model_calls_are_not_counted_as_remediation_actions() -> None:
    """Verifies: REQ-508, REQ-603

    ★ 이것이 이번 판에서 가장 조용한 실패다. 모델 호출 행을 조치로 세면 회복률의
    **분모만 늘고** 그 행들은 원리상 절대 `improved`가 되지 않는다 —
    ⇒ **모델을 쓸수록 헤드라인이 나빠진다.** 리포트를 봐서는 안 보인다.
    """
    ledger = InMemoryLedger()
    _an_action_row(ledger)  # 회복된 조치 1건
    _a_model_call_row(ledger, "m1")
    _a_model_call_row(ledger, "m2")

    assert len(ledger.all_entries()) >= 3  # 원장에는 **남아 있다** — 안 세는 것과 다르다
    report = daily_report(ledger.all_entries(), day=FROZEN.date(), agent_id=AGENT)
    assert report.executed == 1
    assert report.improved == 1
    assert report.improvement_rate == Decimal(1)


# ── 단가와 사용량 (REQ-503) ────────────────────────────────────────────


def test_req_503_token_cost_is_recomputable_from_quantities_and_unit_prices() -> None:
    """Verifies: REQ-503

    ⚠️ 총액만 남기면 **어느 가정이 총액을 지배하는지** 영원히 모른다.
    """
    fact = PRICES.cost_of(TokenUsage(FAKE_MODEL, 2000, 500), priced_at=FROZEN)
    assert fact.is_recomputable
    assert fact.recompute() == fact.amount_usd
    assert fact.amount_usd == Decimal("0.007")


def test_req_603_an_unpriced_model_is_an_error_not_a_zero() -> None:
    """Verifies: REQ-603

    ⚠️ 모르는 것을 0으로 돌려주면 그 구분은 **호출부에서 영원히 사라진다.**
    """
    with pytest.raises(UnpricedModelError):
        PRICES.cost_of(TokenUsage("some-unlisted-model", 1, 1), priced_at=FROZEN)


def test_req_603_negative_token_counts_are_rejected() -> None:
    """Verifies: REQ-603"""
    with pytest.raises(TokenError):
        TokenUsage(FAKE_MODEL, -1, 0)
    with pytest.raises(TokenError):
        TokenUsage("", 1, 1)


def test_req_603_a_model_row_with_a_decision_is_rejected_at_construction() -> None:
    """Verifies: REQ-603, REQ-401

    불변식을 **자료형 모양으로** 집행한다 — 관례로 두면 언젠가 깨진다 (design 08§2).
    """
    reply = ModelReply(Verdict.RECOVERED, "ok", TokenUsage(FAKE_MODEL, 1, 1))
    assert reply.usage.model == FAKE_MODEL  # 응답이 사용량을 **함께** 갖는다

    def _row(**over: Any) -> LedgerEntry:
        # ⚠️ 기본값을 생성자로 만든다 — dict로 쌓으면 그 기본값이 검사를 안 받는다(T0-9).
        base = LedgerEntry(
            entry_id="e1",
            agent_id=AGENT,
            action_id=f"{MODEL_ACTION_PREFIX}judge_ambiguous",
            status=Status.EXECUTED,
            started_at=FROZEN,
            attribution=Attribution(Method.TOKEN_METER),
            assumed=PRICES.cost_of(TokenUsage(FAKE_MODEL, 1, 1), priced_at=FROZEN),
            kind=EntryKind.MODEL_CALL,
        )
        return replace(base, **over)

    assert _row().decision is None
    with pytest.raises(LedgerError):
        _row(
            entry_id="e2",
            decision=decide(
                reversibility=Reversibility.REVERSIBLE,
                verifiable=True,
                projected_usd=Decimal("0.01"),
                headroom_usd=Decimal("0.50"),
            ),
        )
