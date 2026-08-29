from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from warranty.adapters.fakes import (
    FakeBudget,
    FakeJudge,
    FakeRun,
    FrozenClock,
    InMemoryContracts,
    RecordingExecutor,
    ScriptedSignal,
    SeededIdGen,
)
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
from warranty.domain.entry import InMemoryLedger
from warranty.domain.verification import Measurement
from warranty.runtime import AgentTools
from warranty.usecases.remediate import Remediator

RESOURCE = ResourceRef("cloud_run_service", "demo-target", "us-central1")


def _tools() -> AgentTools:
    contracts = InMemoryContracts()
    contracts.put(
        OperationalContract(
            contract_id="c1",
            resource=RESOURCE,
            health_signal=SignalSpec("latency", RESOURCE.name, "P95", 120),
            recovery_criterion=Criterion(
                Direction.DECREASE, Decimal("0.5"), CriterionMode.RELATIVE, Decimal("0.1")
            ),
            rollback_plan=RollbackPlan("demo-target-00001-swl"),
            reversibility=Reversibility.REVERSIBLE,
            provisioned_at=datetime(2026, 8, 28, tzinfo=UTC),
            provisioned_by="demo",
        )
    )
    signals = ScriptedSignal(
        [
            Measurement(Decimal("674.2"), 30),
            Measurement(Decimal("988.6"), 30),
            Measurement(Decimal("674.2"), 30),
        ]
    )
    remediator = Remediator(
        contracts=contracts,
        signals=signals,
        executor=RecordingExecutor(),
        run=FakeRun(),
        budgets=FakeBudget(),
        ledger=InMemoryLedger(),
        clock=FrozenClock(),
        ids=SeededIdGen(),
        judge=FakeJudge(),
    )
    return AgentTools(remediator, contracts, signals, RESOURCE.region)


def test_adk_receives_exactly_the_four_declared_tools() -> None:
    assert tuple(tool.__name__ for tool in _tools().callables()) == (
        "provision",
        "inspect",
        "remediate",
        "report",
    )


def test_the_remediate_tool_returns_the_argument_in_one_visible_response() -> None:
    body = _tools().remediate(RESOURCE.name, "demo-target-00002-lss")
    assert (body["executed"], body["improved"], body["rolled_back"]) == (True, False, True)
    assert body["rollback"]["verified_traffic"] == {"demo-target-00001-swl": 100}


def test_the_agent_can_ask_for_the_second_action_not_just_a_revision() -> None:
    """★ **조치를 어댑터에만 더하면 에이전트는 그것을 못 부른다** (P1).

    ⛔ 이 인자가 `target_revision`이던 동안 도구 표면은 *"조치 = 트래픽 전환"*을 이름으로
       못 박고 있었다. 그 상태의 `concurrency:16`은 **코드에는 있고 데모에는 없는 능력**이다.

    ⚠️ 여기서 실행기는 `RecordingExecutor`다 — 이 테스트가 묻는 것은 *"동시성이 실제로
       바뀌는가"*가 아니라 **에이전트가 넘긴 문자열이 조치로 그대로 도달하는가**다.
       실제 분기는 `test_live_action.py`가 소유한다.
    """
    tools = _tools()
    body = tools.remediate(RESOURCE.name, "concurrency:16")
    assert (body["executed"], body["improved"], body["rolled_back"]) == (True, False, True)

    executor = tools.remediator.executor
    assert isinstance(executor, RecordingExecutor)
    assert executor.calls[-1] == ("concurrency:16", RESOURCE.name)
