from __future__ import annotations

import pytest

from warranty.adapters.fakes import FakeRun
from warranty.adapters.live_action import ActionError, LiveActionExecutor, target_revision
from warranty.domain.contract import ResourceRef

RESOURCE = ResourceRef("cloud_run_service", "demo-target", "us-central1")


def test_the_action_targets_only_a_revision_of_the_requested_service() -> None:
    assert target_revision("demo-target-00002-lss", RESOURCE) == "demo-target-00002-lss"
    with pytest.raises(ActionError):
        target_revision("other-service-00002-lss", RESOURCE)


def test_the_executor_uses_the_same_atomic_traffic_port_as_rollback() -> None:
    run = FakeRun()
    executor = LiveActionExecutor(run)
    assert executor.execute("demo-target-00002-lss", RESOURCE) is True
    assert run.shifts == ["demo-target-00002-lss"]
