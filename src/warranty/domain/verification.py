"""검증 — "실행됨 ≠ 나아졌음".

Spec: specs/warranty/design/02-verification.md (REQ-201~206)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from warranty.domain.contract import Criterion, CriterionMode, Direction


class Verdict(StrEnum):
    RECOVERED = "recovered"
    NOT_RECOVERED = "not_recovered"
    AMBIGUOUS = "ambiguous"  # ★ 모델에 위임되는 유일한 경우 (REQ-204)
    UNVERIFIABLE = "unverifiable"  # ⚠️ 성공이 아니다 (REQ-205)


class DecidedBy(StrEnum):
    RULE = "rule"
    MODEL = "model"


@dataclass(frozen=True, slots=True)
class Measurement:
    """한 번의 신호 읽기. 기준선과 재측정이 **같은 타입**이어야 비교가 성립한다."""

    value: Decimal | None  # None = 창에 데이터 포인트가 없었다
    points: int

    @property
    def is_empty(self) -> bool:
        return self.points == 0 or self.value is None


@dataclass(frozen=True, slots=True)
class Verification:
    verdict: Verdict
    decided_by: DecidedBy
    baseline: Measurement | None
    after: Measurement | None
    rationale: str = ""

    def __post_init__(self) -> None:
        if self.decided_by is DecidedBy.MODEL and not self.rationale:
            # ⚠️ 모델이 판단했으면 근거가 있어야 한다. 근거 없는 모델 판정은
            #    검증이 아니라 주사위다 (REQ-204).
            raise ValueError("모델이 판정했는데 근거가 없다")
        if self.verdict is Verdict.AMBIGUOUS:
            # AMBIGUOUS는 **중간 상태**다. 최종 검증 결과로 저장될 수 없다 —
            # 모델이 recovered/not_recovered 중 하나로 닫아야 한다.
            raise ValueError("AMBIGUOUS는 최종 판정이 아니다 — 모델이 닫아야 한다")


def classify(baseline: Measurement, after: Measurement, criterion: Criterion) -> Verdict:
    """규칙으로 판정한다. 애매하면 `AMBIGUOUS`를 돌려 **모델에 넘긴다.**

    ⚠️ 명확한 경우까지 모델에 맡기면 판정이 비결정적이 되고 REQ-802가 깨진다.
    """
    if baseline.is_empty or after.is_empty:
        # ⚠️ 아직 안 온 데이터로 판정하면 그건 unverifiable이 아니라 **거짓 판정**이다.
        return Verdict.UNVERIFIABLE

    assert baseline.value is not None and after.value is not None
    if criterion.mode is CriterionMode.RELATIVE:
        if baseline.value == 0:
            return Verdict.UNVERIFIABLE
        change = (baseline.value - after.value) / baseline.value
        if criterion.direction is Direction.INCREASE:
            change = -change
        target = criterion.threshold
    else:
        change = baseline.value - after.value
        if criterion.direction is Direction.INCREASE:
            change = -change
        target = criterion.threshold

    if change >= target + criterion.tolerance:
        return Verdict.RECOVERED
    if change <= target - criterion.tolerance:
        return Verdict.NOT_RECOVERED
    # tolerance 안쪽 — ★ 여기가 모델의 판단이 하중을 받는 자리다
    return Verdict.AMBIGUOUS
