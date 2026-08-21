"""Day-1 — 계약은 선언이 아니라 **산출**이다 (REQ-103).

Spec: specs/warranty/design/01-operational-contract.md (REQ-102, REQ-103)

**손으로 적는 계약은 낡는다.** 리소스는 바뀌는데 문서는 안 바뀌고, Day-2는 그 낡은
선언을 읽어 **추측한 신호**로 검증한다. 추측한 신호로 하는 검증은 검증이 아니다.

그래서 여기서 하는 일은 값을 잘 고르는 것이 아니라 **값의 출처를 고정하는 것**이다.
design 01§3의 표가 유도되는 자리를 못 박고, 사람이 정하는 것은 `recovery_criterion`
하나뿐이다 — *"무엇을 회복이라 부를지"*는 **정책이지 사실이 아니기** 때문이다.

⛔ **이 모듈은 실물 응답을 본 적이 없다.** `ProvisionResponse`는 Cloud Run 생성 API의
   응답을 이 저장소가 **어떻게 읽을 작정인지**이고, 실제 JSON이 이 모양으로 오는지는
   실물 프로비저닝(T3-1)에서만 확인된다. 스텁 위의 초록은 *"우리가 이 인터페이스를
   이렇게 부른다"*를 말할 뿐이다 (docs/PRINCIPLES.md #3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from warranty.domain.contract import (
    ContractError,
    Criterion,
    OperationalContract,
    ResourceRef,
    Reversibility,
    RollbackPlan,
    SignalSpec,
)
from warranty.tunables import VERIFY_WINDOW_S


@dataclass(frozen=True, slots=True)
class ProvisionResponse:
    """생성 API가 **실제로 만든 것**. 계약의 유도는 전부 여기서 출발한다.

    ⚠️ `previous_revision`은 배포 **직전에** 서빙하던 리비전이다 — 새로 만든 서비스에는
       없다(`None`). 그 없음이 가역성을 정한다(`derive_contract` 참조).
    """

    kind: str
    name: str
    region: str
    previous_revision: str | None = None

    def __post_init__(self) -> None:
        # ⚠️ 빈 응답을 통과시키면 계약이 **아무것도 안 가리키는 채로** 성립한다.
        #    그 계약은 Day-2에서 조용히 틀린다 — 신호는 안 읽히고 조치는 "성공"한다.
        if not self.name:
            raise ContractError("생성 응답에 리소스 이름이 없다 — 유도할 것이 없다")
        if not self.region:
            raise ContractError(f"생성 응답에 리전이 없다: {self.name!r}")
        if self.previous_revision is not None and not self.previous_revision:
            raise ContractError(
                f"직전 리비전이 빈 문자열이다: {self.name!r} — "
                "없으면 `None`이어야 한다. 빈 문자열은 '있다'로 읽힌다"
            )


@dataclass(frozen=True, slots=True)
class KindProfile:
    """**리소스 타입**이 정하는 것 — 계약마다 사람이 고르는 값이 아니다.

    ⚠️ 여기 있는 것은 *"이 타입의 건강을 무엇으로 재는가"*이지 *"얼마면 건강한가"*가
       아니다. 후자는 `recovery_criterion`이고 그것만이 사람의 몫이다.
    """

    metric_type: str
    aggregation: str
    rollback_kind: str


#: 아는 리소스 타입. ⚠️ **표에 없는 타입은 기본값이 아니라 거부다**(REQ-102와 같은 규칙) —
#: 조용한 기본값은 선언을 장식으로 만들고, 그 장식 위에서 자동 조치가 돈다.
KNOWN_KINDS: dict[str, KindProfile] = {
    "cloud_run_service": KindProfile(
        metric_type="run.googleapis.com/request_latencies",
        aggregation="P95",
        rollback_kind="cloud_run_traffic",
    ),
}


def derive_contract(
    response: ProvisionResponse,
    *,
    recovery_criterion: Criterion,
    contract_id: str,
    provisioned_at: datetime,
    provisioned_by: str,
) -> OperationalContract:
    """생성 응답 하나에서 운영 계약을 **유도한다** (REQ-103).

    Spec: specs/warranty/design/01-operational-contract.md (REQ-103)

    유도되는 자리는 design 01§3의 표가 정한다 — `resource` ·
    `health_signal.resource_filter` · `rollback_plan.previous_revision` ·
    `reversibility`. ⛔ **그 넷은 인자로 들어올 수 없다.** 하나라도 인자로 열어 두면
    *"계약은 유도된다"*는 문장이 관례가 되고, 관례는 언젠가 깨진다 —
    `tests/test_provision_contract.py`가 이 시그니처를 **구문으로** 묻는다.

    ⚠️ **리소스 타입은 가역의 필요조건이지 충분조건이 아니다.** design 01§3의 표는
       *"reversibility ← 리소스 타입에서 유도 (Cloud Run 서비스 = 가역)"*라고 적지만,
       타입만 보고 `REVERSIBLE`을 쓰면 **되돌아갈 리비전이 없는 첫 배포**에서 계약이
       아예 성립하지 않는다(REQ-102 — 가역인데 롤백 계획이 없는 계약은 거부된다).
       그래서 둘을 함께 묻는다: 타입이 트래픽 전환을 아는가 **그리고** 돌아갈 자리가
       응답에 있는가. 없으면 `IRREVERSIBLE`이고, 그 리소스는 자동 대상이 아니다.
       ⛔ 이 차이는 설계 문서에 아직 안 적혀 있다 — 적는 것은 설계 변경이라 범위 밖이다.
    """
    profile = KNOWN_KINDS.get(response.kind)
    if profile is None:
        raise ContractError(
            f"어떻게 재고 어떻게 되돌리는지 모르는 리소스 타입이다: {response.kind!r} — "
            f"아는 타입은 {sorted(KNOWN_KINDS)}. 모르는 타입에 기본값을 주면 그 계약은 장식이다"
        )
    rollback_plan = (
        None
        if response.previous_revision is None
        else RollbackPlan(
            previous_revision=response.previous_revision,  # ★ 배포 직전의 현재 리비전
            kind=profile.rollback_kind,
        )
    )
    return OperationalContract(
        contract_id=contract_id,
        resource=ResourceRef(kind=response.kind, name=response.name, region=response.region),
        health_signal=SignalSpec(
            metric_type=profile.metric_type,
            resource_filter=response.name,  # ★ 그 이름 — 손으로 적는 자리가 아니다
            aggregation=profile.aggregation,
            window_s=VERIFY_WINDOW_S,
        ),
        recovery_criterion=recovery_criterion,  # 사람이 정하는 유일한 것
        rollback_plan=rollback_plan,
        reversibility=(
            Reversibility.IRREVERSIBLE if rollback_plan is None else Reversibility.REVERSIBLE
        ),
        provisioned_at=provisioned_at,
        provisioned_by=provisioned_by,
    )
