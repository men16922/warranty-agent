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
