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
    cost_labels,
    label_of,
    parent_path,
    response_from_service,
    service_name,
)
from warranty.domain.attribution import Method
from warranty.domain.contract import ResourceRef, Reversibility
from warranty.domain.entry import EntryKind, InMemoryLedger
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
    labels: list[str]

    #: ⚠️ **라벨이 조용히 안 붙는 경우를 값으로 태운다.** 실물에서 그것은 권한·정책으로
    #:    일어나고, 대역이 늘 완벽하면 `Method.NONE` 경로가 하중을 못 받는다
    #:    (docs/PRINCIPLES.md #8).
    echoes_label: bool = True

    def create(
        self, name: str, kind: str = "cloud_run_service", cost_label: str = ""
    ) -> ProvisionResponse:
        self.calls.append(name)
        self.labels.append(cost_label)
        return ProvisionResponse(
            kind=kind,
            name=name,
            region=REGION,
            previous_revision=None,
            cost_label=(cost_label or None) if self.echoes_label else None,
        )


class _FixedClock:
    def now_iso(self) -> str:
        return datetime(2026, 8, 29, tzinfo=UTC).isoformat()

    def sleep(self, seconds: int) -> None: ...


class _FixedIds:
    """⚠️ **부를 때마다 다른 값을 준다.** `provision`은 원장 id와 계약 id를 각각 만들고,
    같은 값을 돌려주면 *"라벨이 계약을 가리킨다"*와 *"항목을 가리킨다"*가 구분되지 않는다.
    """

    def __init__(self) -> None:
        self._n = 0

    def new_entry_id(self) -> str:
        self._n += 1
        return f"ct-day1-{self._n:04d}"


def _tools(
    contracts: InMemoryContracts,
    provisioner: _FakeProvisioner,
    ledger: InMemoryLedger | None = None,
) -> AgentTools:
    return AgentTools(
        remediator=None,  # type: ignore[arg-type]
        contracts=contracts,
        signals=None,  # type: ignore[arg-type]
        default_region=REGION,
        provisioner=provisioner,
        ledger=ledger if ledger is not None else InMemoryLedger(),
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
    provisioner = _FakeProvisioner(calls=[], labels=[])
    result = _tools(contracts, provisioner).provision("day1-svc")

    assert provisioner.calls == ["day1-svc"], "리소스를 안 만들고 계약만 쓰면 그 계약은 장식이다"
    stored = contracts.active_for(ResourceRef("cloud_run_service", "day1-svc", REGION))
    assert stored is not None, "만들었는데 계약 문서가 없다 — REQ-101의 Then이 성립하지 않는다"
    assert stored.contract_id == result["contract"] == "ct-day1-0002"
    assert stored.health_signal.resource_filter == "day1-svc", (
        "신호가 만든 리소스를 안 가리킨다 — 손으로 적는 자리가 아니라 유도되는 자리다(REQ-103)"
    )


def test_a_freshly_made_service_has_nowhere_to_roll_back_to() -> None:
    """③ 돌아갈 자리가 없으면 **가역이라고 하지 않는다**.

    ⛔ 타입만 보고 `REVERSIBLE`을 쓰면 그 계약은 필요한 날 틀린다 — design 01§3이
       적어 둔 결과이지 결함이 아니다. 그 리소스는 자동 조치 대상이 아니다.
    """
    contracts = InMemoryContracts()
    result = _tools(contracts, _FakeProvisioner(calls=[], labels=[])).provision("day1-svc")
    assert result["reversibility"] == Reversibility.IRREVERSIBLE.value
    assert result["rollback_revision"] is None


# ── 비용 라벨 — 청구 행을 원장으로 되돌리는 실 (C2·C3 · REQ-504) ──────


def test_the_created_resource_carries_the_ledger_id_as_its_cost_label() -> None:
    """★ **이 라벨이 없으면 그 리소스의 청구 행은 영원히 원장으로 못 돌아온다.**

    Verifies: REQ-504

    ⛔ `Method.RESOURCE_LABEL`은 *"청구 행에서 되찾는다"*고 약속한다. 그 약속이 참이려면
       **원장 항목의 id가 리소스에 실제로 박혀 있어야** 한다. 이 저장소는 그 라벨을
       2026-08-29까지 **한 번도 안 붙였다** — `RESOURCE_LABEL`은 테스트에만 있었다.
    ⚠️ 라벨 값은 **원장 id**이지 계약 id가 아니다. 계약을 가리키면 재프로비저닝 후
       두 리소스가 같은 라벨을 갖고, 청구 행이 어느 항목의 것인지 갈라지지 않는다.
    """
    contracts = InMemoryContracts()
    provisioner = _FakeProvisioner(calls=[], labels=[])
    ledger = InMemoryLedger()

    body = _tools(contracts, provisioner, ledger).provision("day1-svc")

    entry_id = body["ledger_entry"]
    assert provisioner.labels == [entry_id], "리소스에 박은 라벨이 원장 id가 아니다"
    assert body["cost_label"] == entry_id
    assert body["attribution"] == Method.RESOURCE_LABEL.value
    assert body["reconcilable"] == "reconcilable"

    (row,) = ledger.all_entries()
    assert row.entry_id == entry_id
    assert row.attribution.method is Method.RESOURCE_LABEL
    assert row.attribution.label_value == entry_id
    # ⛔ 계약 id와 **다른** 값이다 — 같으면 위 ⚠️의 갈라짐이 안 잡힌다.
    assert row.contract_id != entry_id


def test_a_provision_row_is_not_an_action_row() -> None:
    """⛔ **`ACTION`으로 적으면 회복률이 조용히 무너진다.**

    Verifies: REQ-508

    프로비저닝 항목은 `EXECUTED`인데 검증이 없어 **원리상 절대 `improved`가 되지 않는다.**
    조치로 세면 분모만 늘고 분자는 안 늘어서 **프로비저닝할수록 성적이 나빠진다** —
    모델 호출을 섞을 때와 똑같은 오염이고, 리포트를 봐서는 안 보인다.
    """
    ledger = InMemoryLedger()
    _tools(InMemoryContracts(), _FakeProvisioner(calls=[], labels=[]), ledger).provision("day1-svc")
    (row,) = ledger.all_entries()
    assert row.kind is EntryKind.PROVISION
    # ⚠️ 리포트가 실제로 쓰는 필터로 묻는다 — `is not ACTION`은 mypy가 상수로 접어
    #    **아무것도 안 묻는 단언**이 된다. 여기서 묻는 것은 "리포트가 이 행을 뺀다"이다.
    assert [r for r in ledger.all_entries() if r.kind is EntryKind.ACTION] == []


def test_a_label_that_did_not_stick_is_recorded_as_such() -> None:
    """⛔ **붙였다는 것과 붙었다는 것은 다르다.**

    Verifies: REQ-504

    라벨은 조용히 안 붙을 수 있다(권한·정책·형식). 그때 `RESOURCE_LABEL`을 적으면
    화해는 **원리상 못 찾는데 원인이 안 보인다** — 그 침묵이 `Method.NONE`이 사유를
    요구하는 이유다.
    ⚠️ 그러므로 귀속은 **보낸 값이 아니라 되읽은 값**으로 정한다.
    """
    ledger = InMemoryLedger()
    silent = _FakeProvisioner(calls=[], labels=[], echoes_label=False)

    body = _tools(InMemoryContracts(), silent, ledger).provision("day1-svc")

    # 보내기는 보냈다 — 그런데도 귀속은 `none`이다.
    assert silent.labels == [body["ledger_entry"]]
    assert body["cost_label"] is None
    assert body["attribution"] == Method.NONE.value
    assert body["reconcilable"] == "assumed_only"

    (row,) = ledger.all_entries()
    assert row.attribution.method is Method.NONE
    assert row.attribution.reason  # ⛔ 조용한 `none`을 만들지 않는다


def test_the_create_request_carries_the_cost_label() -> None:
    """⛔ **게이트가 태울 수 있는 것은 호출이 아니라 요청의 모양이다.**

    Verifies: REQ-504

    라벨을 실제로 다는 줄은 실물 어댑터 안이라 오프라인 게이트가 못 지난다 —
    그 줄에 변이를 걸었더니 **초록이었다**(M-270). 그래서 모양을 여기서 태운다.

    ⚠️ 빈 라벨은 **빈 사전**이어야 한다. `{fl_entry: ""}`를 보내면 GCP는 라벨이 있다고
       받아들이고 되읽기는 *"없음"*으로 읽어서, 두 사실이 갈라진다.
    """
    assert cost_labels("ct-day1-0001") == {"fl_entry": "ct-day1-0001"}
    assert cost_labels("") == {}
    # 되읽기와 짝이 맞는가 — 보낸 모양을 그대로 돌려받으면 같은 값이 나와야 한다.
    assert label_of(_Service(labels=cost_labels("ct-day1-0001"))) == "ct-day1-0001"
    assert label_of(_Service(labels=cost_labels(""))) is None


@dataclass(frozen=True)
class _Service:
    """Admin API 응답의 **모양만** 흉내낸다 — 라이브러리를 안 부른다."""

    labels: dict[str, str]
