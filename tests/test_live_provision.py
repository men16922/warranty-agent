"""Day-1 실물 절반 — **만든 것과 계약이 같은 순간에 나는가** (T3-1 · REQ-101).

Spec: specs/warranty/design/01-operational-contract.md §1, §3 (REQ-101, REQ-103)

⚠️ **실물 호출은 안 한다.** 게이트는 네트워크가 없다(REQ-801). 여기서 태우는 것은
   *"요청의 모양"*과 *"응답을 어떻게 읽는가"*이고, 실제 JSON이 이 모양으로 오는지는
   실물 프로비저닝에서만 확인된다 — 그 증거는 `docs/evidence/`가 갖는다.

묻는 것은 넷이다:
  ① 부모 경로·서비스 이름이 **빈 값과 못 쓰는 글자에서 죽는가** (생성 호출까지 안 가고)
  ② 생성 응답을 **되읽는가** — 다른 것을 가리키면 거절하는가
  ③ 갓 만든 서비스는 **돌아갈 자리가 없다**는 것이 계약의 가역성으로 나오는가
  ④ ⛔ **본체**: 만드는 호출과 계약 기록이 **한 번에** 나는가 (REQ-101)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from warranty.adapters.fakes import InMemoryContracts
from warranty.adapters.live_provision import (
    ProvisionError,
    parent_path,
    response_from_service,
    service_name,
)
from warranty.domain.contract import ResourceRef, Reversibility
from warranty.runtime import AgentTools
from warranty.usecases.provision import ProvisionResponse

REGION = "us-central1"
PROJECT = "warranty-hack"


@dataclass(frozen=True, slots=True)
class _CreatedService:
    """생성 API가 돌려주는 것 중 이 저장소가 **읽는 부분만**."""

    name: str


def test_req_101_the_parent_path_refuses_empty_project_or_region() -> None:
    """① 빈 값이 `projects//locations/`가 되어 **다른 곳**을 가리키지 않는가.

    Verifies: REQ-101
    """
    assert parent_path(PROJECT, REGION) == f"projects/{PROJECT}/locations/{REGION}"
    with pytest.raises(ProvisionError):
        parent_path("", REGION)
    with pytest.raises(ProvisionError):
        parent_path(PROJECT, "  ")


def test_the_service_name_is_burned_before_the_create_call() -> None:
    """① 못 쓰는 이름이 **생성 호출까지 가서** 죽지 않는가.

    ⚠️ 거기서 죽으면 이미 부분적으로 만들어진 뒤일 수 있다 — 그 리소스는 계약이 없다.
    """
    assert service_name("  day1-svc ") == "day1-svc"
    for bad in ("", "Day1", "svc_1", "-svc", "svc-"):
        with pytest.raises(ProvisionError):
            service_name(bad)


def test_the_created_service_is_read_back_rather_than_assumed() -> None:
    """② 서버가 말하는 것을 읽는가 — 우리가 보낸 값을 그대로 믿지 않는가.

    ⛔ `read_traffic`이 롤백에 대해 하는 일을 생성에 대해 한다(REQ-303의 같은 원리).
    """
    created = _CreatedService(name=f"{parent_path(PROJECT, REGION)}/services/day1-svc")
    response = response_from_service(
        created, kind="cloud_run_service", name="day1-svc", region=REGION
    )
    assert response == ProvisionResponse("cloud_run_service", "day1-svc", REGION, None)

    with pytest.raises(ProvisionError):
        response_from_service(
            _CreatedService(name=""), kind="cloud_run_service", name="x", region=REGION
        )
    other = _CreatedService(name=f"{parent_path(PROJECT, REGION)}/services/somebody-else")
    with pytest.raises(ProvisionError):
        response_from_service(other, kind="cloud_run_service", name="day1-svc", region=REGION)


@dataclass
class _FakeProvisioner:
    """만들었다고 **말만 하는** 프로비저너. 실물 호출 없이 ④를 태운다."""

    calls: list[str]

    def create(self, name: str, kind: str = "cloud_run_service") -> ProvisionResponse:
        self.calls.append(name)
        return ProvisionResponse(kind=kind, name=name, region=REGION, previous_revision=None)


class _FixedClock:
    def now_iso(self) -> str:
        return datetime(2026, 8, 29, tzinfo=UTC).isoformat()

    def sleep(self, seconds: int) -> None: ...


class _FixedIds:
    def new_entry_id(self) -> str:
        return "ct-day1-0001"


def _tools(contracts: InMemoryContracts, provisioner: _FakeProvisioner) -> AgentTools:
    return AgentTools(
        remediator=None,  # type: ignore[arg-type]
        contracts=contracts,
        signals=None,  # type: ignore[arg-type]
        default_region=REGION,
        provisioner=provisioner,
        clock=_FixedClock(),
        ids=_FixedIds(),
    )


def test_req_101_provisioning_records_a_contract_in_the_same_step() -> None:
    """④ ⛔ **이 가드의 본체다.** 만든 뒤 계약 문서가 **존재하는가** (REQ-101의 Then).

    Verifies: REQ-101

    ⚠️ 둘을 나눠 두면 사이에 실패가 들어갈 자리가 생기고, 거기서 만들어진 리소스는
       **계약 없는 리소스**가 된다 — 자동 조치 대상이 아니고(REQ-104) 아무도 그것을 모른다.
    """
    contracts = InMemoryContracts()
    provisioner = _FakeProvisioner(calls=[])
    result = _tools(contracts, provisioner).provision("day1-svc")

    assert provisioner.calls == ["day1-svc"], "리소스를 안 만들고 계약만 쓰면 그 계약은 장식이다"
    stored = contracts.active_for(ResourceRef("cloud_run_service", "day1-svc", REGION))
    assert stored is not None, "만들었는데 계약 문서가 없다 — REQ-101의 Then이 성립하지 않는다"
    assert stored.contract_id == result["contract"] == "ct-day1-0001"
    assert stored.health_signal.resource_filter == "day1-svc", (
        "신호가 만든 리소스를 안 가리킨다 — 손으로 적는 자리가 아니라 유도되는 자리다(REQ-103)"
    )


def test_a_freshly_made_service_has_nowhere_to_roll_back_to() -> None:
    """③ 돌아갈 자리가 없으면 **가역이라고 하지 않는다**.

    ⛔ 타입만 보고 `REVERSIBLE`을 쓰면 그 계약은 필요한 날 틀린다 — design 01§3이
       적어 둔 결과이지 결함이 아니다. 그 리소스는 자동 조치 대상이 아니다.
    """
    contracts = InMemoryContracts()
    result = _tools(contracts, _FakeProvisioner(calls=[])).provision("day1-svc")
    assert result["reversibility"] == Reversibility.IRREVERSIBLE.value
    assert result["rollback_revision"] is None
