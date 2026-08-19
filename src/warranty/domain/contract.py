"""운영 계약 — Day-1이 Day-2에 넘기는 것.

Spec: specs/warranty/design/01-operational-contract.md (REQ-101~105)

⚠️ 계약의 값은 **프로비저닝이 실제로 만든 것에서 유도된다**. 손으로 적는 계약은 낡는다 —
   리소스는 바뀌는데 문서는 안 바뀐다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class Reversibility(StrEnum):
    REVERSIBLE = "reversible"
    IRREVERSIBLE = "irreversible"


class ContractState(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class Direction(StrEnum):
    DECREASE = "decrease"
    INCREASE = "increase"


class CriterionMode(StrEnum):
    RELATIVE = "relative"
    ABSOLUTE = "absolute"


class ContractError(ValueError):
    """계약이 성립하지 않는다."""


@dataclass(frozen=True, slots=True)
class ResourceRef:
    kind: str  # 지금은 "cloud_run_service" 하나
    name: str
    region: str


@dataclass(frozen=True, slots=True)
class SignalSpec:
    """무엇을 재면 건강한지 아는가.

    ⚠️ **기준선과 재측정이 이 스펙 하나를 공유한다**(REQ-202).
    두 곳에 두면 언젠가 다른 걸 재고, 그 어긋남은 조용하다.
    """

    metric_type: str
    resource_filter: str
    aggregation: str
    window_s: int
    kind: str = "cloud_monitoring"

    def __post_init__(self) -> None:
        if self.window_s <= 0:
            raise ContractError(f"신호 창이 양수가 아니다: {self.window_s}")
        if not self.resource_filter:
            # 실제 만들어진 리소스 이름에서 유도돼야 한다 (REQ-103)
            raise ContractError("resource_filter가 비어 있다 — 무엇을 재는지 특정되지 않는다")


@dataclass(frozen=True, slots=True)
class Criterion:
    """무엇을 회복이라 부르는가. **사람이 정하는 유일한 필드다** — 정책이지 사실이 아니다."""

    direction: Direction
    threshold: Decimal
    mode: CriterionMode
    tolerance: Decimal

    def __post_init__(self) -> None:
        if self.tolerance < 0:
            raise ContractError(f"tolerance가 음수다: {self.tolerance}")
        if self.mode is CriterionMode.RELATIVE and not (0 < self.threshold <= 1):
            raise ContractError(f"relative threshold는 (0, 1] 이어야 한다: {self.threshold}")


@dataclass(frozen=True, slots=True)
class RollbackPlan:
    """어떻게 되돌리는가. **조치 전에 확보된다**(REQ-301)."""

    previous_revision: str
    kind: str = "cloud_run_traffic"
    verify_traffic: bool = True

    def __post_init__(self) -> None:
        if not self.previous_revision:
            raise ContractError("되돌릴 리비전이 비어 있다 — 롤백 계획이 아니다")


@dataclass(frozen=True, slots=True)
class OperationalContract:
    contract_id: str
    resource: ResourceRef
    health_signal: SignalSpec
    recovery_criterion: Criterion
    rollback_plan: RollbackPlan | None
    reversibility: Reversibility
    provisioned_at: datetime
    provisioned_by: str
    state: ContractState = ContractState.ACTIVE
    cost_model: str | None = None
    _required: tuple[str, ...] = field(
        default=("health_signal", "recovery_criterion", "rollback_plan", "reversibility"),
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        # REQ-102 — 넷은 기본값이 없다. 조용한 기본값은 선언을 장식으로 만들고,
        # 그 장식 위에서 자동 조치가 돈다.
        if self.reversibility is Reversibility.REVERSIBLE and self.rollback_plan is None:
            raise ContractError(
                "가역이라 선언했는데 롤백 계획이 없다 — 되돌릴 방법 없이 가역일 수 없다"
            )
        if self.reversibility is Reversibility.IRREVERSIBLE and self.rollback_plan is not None:
            raise ContractError("비가역이라 선언했는데 롤백 계획이 있다 — 둘 중 하나가 틀렸다")

    @property
    def is_active(self) -> bool:
        return self.state is ContractState.ACTIVE

    def retired(self) -> OperationalContract:
        """리소스가 사라지면 계약도 종료된다 (REQ-105).

        ⚠️ 없는 리소스를 가리키는 계약이 살아 있으면, 자동 조치가 **존재하지 않는 것을
        고치려 한다.** 그 실패는 조용하다 — 조치는 '성공'하고 신호는 안 움직인다.
        """
        from dataclasses import replace

        return replace(self, state=ContractState.RETIRED)
