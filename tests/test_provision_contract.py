"""REQ-103 — 계약이 **선언이 아니라 산출인가.**

Spec: specs/warranty/design/01-operational-contract.md (REQ-103)

⚠️ 이 질문은 값의 질문이 아니다. 계약의 네 자리에 **맞는 값이 들어 있는가**는
   손으로 적어도 통과한다 — 그리고 손으로 적은 계약은 리소스가 바뀌는 순간 틀린다.
   물어야 할 것은 **어디서 온 값인가**다 (T0-10 · M-44 계열의 같은 착각).

그래서 셋을 함께 묻는다:
  ① 유도된다는 자리가 **인자로 들어올 수 없는가** (시그니처를 구문으로 본다)
  ② 응답이 바뀌면 그 자리가 **전부 따라 바뀌는가** (값을 박아 두면 여기서 red다)
  ③ 프로덕션 코드에서 계약을 **조립하는 자리가 하나뿐인가** (`provision.py`)

⚠️ 유도되는 자리 목록을 여기 베껴 두지 않는다 — design 01§3의 표를 **파싱해서** 읽는다.
   베껴 두면 설계가 자리를 늘려도 사본은 안 늘고 게이트는 초록이다(T0-10의 교훈).

⚠️ ③의 스캔 범위는 `src/warranty/`뿐이다. 테스트는 자기 픽스처로 계약을 세울 수 있어야
   한다 — 그건 산재가 아니라 그 테스트가 무엇을 재는지의 일부다(test_tunables.py와 같은 규칙).
"""

from __future__ import annotations

import ast
import inspect
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

import warranty.demo as demo  # `from warranty import demo`는 재수출이 아니다(strict)
from warranty.domain.contract import (
    ContractError,
    Criterion,
    CriterionMode,
    Direction,
    OperationalContract,
    Reversibility,
)
from warranty.usecases.provision import ProvisionResponse, derive_contract

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "warranty"
PROVISION = SRC / "usecases" / "provision.py"
DESIGN = ROOT / "specs" / "warranty" / "design" / "01-operational-contract.md"

#: design 01§3의 유도 표를 여는 표제. ⚠️ 바뀌면 파서가 **못 찾고 예외를 낸다** —
#: 조용히 0행을 읽고 아래 검사를 공허하게 통과시키는 것보다 낫다.
DESIGN_SECTION = "## 3. ★ 계약은 선언이 아니라 산출이다"

#: 표의 첫 칸(백틱으로 감싼 필드 경로). `health_signal.resource_filter`처럼 점이 있다.
DESIGN_ROW_RE = re.compile(r"^\|\s*`([a-z_.]+)`\s*\|", re.MULTILINE)

#: 사람이 정하는 유일한 자리. **산문에서 읽는다** — 여기 적어 두면 설계가 바뀌어도 안 따라온다.
DESIGN_HUMAN_RE = re.compile(r"사람이 정하는 것은 `([a-z_]+)`")

#: 계약을 조립하는 생성자들. 프로덕션 코드에서 이것을 직접 부르는 자리는 유도 모듈뿐이다.
CONTRACT_CONSTRUCTORS = ("OperationalContract", "SignalSpec", "RollbackPlan")

#: 공허 통과 방지의 바닥. 표에서 행이 빠지면 금지 집합이 조용히 줄어든다.
#: ⚠️ 바닥은 공허 통과 방지지 **완전성이 아니다** — 표에 행이 늘면 금지 집합은 자동으로
#:    늘지만, 늘어난 자리가 실제로 유도되는지는 사람이 본다.
MIN_DERIVED_FIELDS = 4
MIN_SCANNED_FILES = 8

CRITERION = Criterion(
    direction=Direction.DECREASE,
    threshold=Decimal("0.5"),
    mode=CriterionMode.RELATIVE,
    tolerance=Decimal("0.1"),
)
PROVISIONED_AT = datetime.fromisoformat("2026-08-21T09:00:00+00:00")


def _design_section() -> str:
    text = DESIGN.read_text(encoding="utf-8")
    start = text.find(DESIGN_SECTION)
    if start < 0:
        raise AssertionError(f"design 01의 유도 절을 못 찾았다: {DESIGN_SECTION!r}")
    end = text.find("\n## ", start + 1)
    return text[start:] if end < 0 else text[start:end]


def _derived_fields() -> set[str]:
    """design 01§3의 표가 **유도된다고 선언한** 필드 경로들."""
    return set(DESIGN_ROW_RE.findall(_design_section()))


def _human_field() -> str:
    match = DESIGN_HUMAN_RE.search(_design_section())
    if match is None:
        raise AssertionError("design 01§3이 '사람이 정하는 것'을 말하지 않는다 — 파서가 깨졌다")
    return match.group(1)


def _forbidden_parameter_names() -> set[str]:
    """유도되는 자리가 **인자로 다시 들어올 수 있는 이름들.**

    ⚠️ 뿌리와 잎을 둘 다 막는다 — `rollback_plan.previous_revision`을 막는 것은
       `rollback_plan=`이든 `previous_revision=`이든 열리면 같은 것이 깨지기 때문이다.
    """
    names: set[str] = set()
    for path in _derived_fields():
        names.update(path.split("."))
    return names


def _source_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _construction_sites(path: Path) -> list[str]:
    """이 파일에서 계약 자료형을 **직접 조립하는** 자리."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        f"{path.relative_to(ROOT)}:{node.lineno} {node.func.id}("
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in CONTRACT_CONSTRUCTORS
    ]


def _response(
    name: str = "demo-target", previous: str | None = "demo-target-00007-abc"
) -> ProvisionResponse:
    return ProvisionResponse(
        kind="cloud_run_service",
        name=name,
        region="us-central1",
        previous_revision=previous,
    )


def _derive(response: ProvisionResponse) -> OperationalContract:
    return derive_contract(
        response,
        recovery_criterion=CRITERION,
        contract_id="ct-0001",
        provisioned_at=PROVISIONED_AT,
        provisioned_by="entry-0001",
    )


# ── ⓪ 공허 통과 방지 ───────────────────────────────────────────────────────


def test_req_103_the_design_table_is_actually_read() -> None:
    """Verifies: REQ-103

    파서가 0행을 읽으면 아래 시그니처 검사가 **아무것도 안 금지하고 초록**이다.
    이 저장소는 같은 방식으로 두 번 속았다 (M-03·M-25·M-45).
    """
    derived = _derived_fields()
    assert len(derived) >= MIN_DERIVED_FIELDS, (
        f"design 01§3의 유도 표에서 {len(derived)}행만 읽었다 (최소 {MIN_DERIVED_FIELDS}): "
        f"{sorted(derived)} — 표가 줄었거나 파서가 깨졌다"
    )
    assert _human_field() == "recovery_criterion", (
        f"design 01§3이 말하는 '사람이 정하는 것'이 {_human_field()!r}이다 — "
        "이 테스트가 아는 것과 다르다"
    )
    assert len(_source_files()) >= MIN_SCANNED_FILES, "src/warranty 스캔 경로가 틀렸다"


# ── ① 유도되는 자리는 인자로 들어올 수 없다 ───────────────────────────────


def test_req_103_no_derived_field_can_be_handed_in_as_an_argument() -> None:
    """Verifies: REQ-103

    ★ **이 태스크의 한 줄 수용 기준이다.** 값이 맞는지가 아니라 *"어디서 왔는가"*를 묻는다.
    `previous_revision=`을 인자로 열어 두면 호출부가 손으로 적은 리비전이 계약에 실리고,
    그 계약은 **리소스와 함께 늙지 않는다** — 그리고 그 어긋남은 조용하다.

    ⚠️ 금지 목록을 여기 베끼지 않고 design 01§3의 표에서 읽는다. 설계가 자리를 늘리면
       금지도 함께 는다 — 사본이면 안 는다(T0-10).
    """
    parameters = set(inspect.signature(derive_contract).parameters)
    leaked = sorted(parameters & _forbidden_parameter_names())
    assert not leaked, (
        f"design 01§3이 유도된다고 말한 자리가 `derive_contract`의 인자로 열려 있다: {leaked} — "
        "인자로 열리면 '유도된다'는 문장은 관례일 뿐이다"
    )
    assert _human_field() in parameters, (
        f"사람이 정하는 유일한 자리({_human_field()})가 인자가 아니다 — "
        "회복의 기준은 정책이지 사실이 아니라 유도될 수 없다"
    )


def test_req_103_production_code_assembles_a_contract_in_exactly_one_place() -> None:
    """Verifies: REQ-103

    ⚠️ 유도 함수를 만들어 놔도 **옆에서 손으로 조립하면** 아무것도 안 바뀐다.
    실제로 데모가 그랬다 — `OperationalContract(...)`를 직접 세우고 있었고, 그 계약의
    `resource_filter`는 리소스 이름과 **우연히** 같았다.
    """
    sites = {path: found for path in _source_files() if (found := _construction_sites(path))}
    outside = sorted(hit for path, found in sites.items() if path != PROVISION for hit in found)
    assert not outside, (
        f"유도 모듈 밖에서 계약을 조립한다: {outside} — 그 자리는 응답이 바뀌어도 안 바뀐다"
    )
    assert sites.get(PROVISION), (
        "유도 모듈이 계약을 조립하지 않는다 — 스캐너가 아무 자리도 못 찾았다(공허 통과)"
    )


# ── ② 응답이 바뀌면 유도된 자리가 따라 바뀐다 ─────────────────────────────


def test_req_103_the_health_signal_points_at_the_resource_the_response_named() -> None:
    """Verifies: REQ-103, REQ-102

    `health_signal.resource_filter`는 **실제로 만들어진 이름**이다 (design 01§3).
    추측한 필터로 재는 신호는 그 리소스의 신호가 아니다.
    """
    contract = _derive(_response(name="svc-alpha"))
    assert contract.resource.name == "svc-alpha"
    assert contract.health_signal.resource_filter == "svc-alpha"


def test_req_103_the_rollback_plan_holds_the_revision_that_was_serving_before() -> None:
    """Verifies: REQ-103, REQ-301

    롤백 계획의 목적지는 **배포 직전에 서빙하던 리비전**이다. 손으로 적으면 다음 배포
    때 낡고, 낡은 롤백 계획은 **필요할 때** 틀린다.
    """
    contract = _derive(_response(previous="svc-alpha-00042-xyz"))
    assert contract.rollback_plan is not None
    assert contract.rollback_plan.previous_revision == "svc-alpha-00042-xyz"
    assert contract.reversibility is Reversibility.REVERSIBLE


def test_req_103_every_derived_field_follows_the_response() -> None:
    """Verifies: REQ-103

    ★ **값을 박아 두면 여기서 red다.** 두 개의 다른 응답에서 유도한 계약이 유도된
    자리마다 달라야 한다 — 하나라도 같으면 그 자리는 응답을 안 읽은 것이다.

    ⚠️ 그리고 사람이 정한 자리(`recovery_criterion`)는 **안 바뀐다.** 유도가 정책까지
       건드리면 계약은 리소스를 따라 회복 기준까지 바꾸게 된다.
    """
    first = _derive(_response(name="svc-alpha", previous="svc-alpha-00007-abc"))
    second = _derive(_response(name="svc-beta", previous="svc-beta-00009-def"))
    assert first.rollback_plan is not None and second.rollback_plan is not None

    same = [
        label
        for label, left, right in (
            ("resource.name", first.resource.name, second.resource.name),
            (
                "health_signal.resource_filter",
                first.health_signal.resource_filter,
                second.health_signal.resource_filter,
            ),
            (
                "rollback_plan.previous_revision",
                first.rollback_plan.previous_revision,
                second.rollback_plan.previous_revision,
            ),
        )
        if left == right
    ]
    assert not same, f"응답이 달라졌는데 안 따라 바뀐 자리: {same} — 그 값은 박혀 있다"
    assert first.recovery_criterion == second.recovery_criterion, (
        "회복 기준이 응답을 따라 바뀌었다 — 그건 정책이지 사실이 아니다"
    )


# ── ③ 유도가 모르는 것을 아는 척하지 않는다 ───────────────────────────────


def test_req_103_a_response_without_a_rollback_target_is_not_called_reversible() -> None:
    """Verifies: REQ-103, REQ-102

    ⚠️ design 01§3은 가역성을 *"리소스 타입에서 유도"*라고 적지만, **타입은 필요조건이지
    충분조건이 아니다** — 되돌아갈 리비전이 없는 첫 배포를 타입만 보고 가역이라 부르면
    REQ-102가 그 계약을 거부한다(가역인데 롤백 계획이 없다). 그래서 돌아갈 자리가 없으면
    `IRREVERSIBLE`이고, 그 리소스는 자동 조치 대상이 아니다.
    """
    contract = _derive(_response(previous=None))
    assert contract.rollback_plan is None
    assert contract.reversibility is Reversibility.IRREVERSIBLE


def test_req_103_an_unknown_resource_kind_is_refused_instead_of_defaulted() -> None:
    """Verifies: REQ-103, REQ-102

    ⛔ 모르는 타입에 기본 신호를 주면 계약은 성립하고 **아무것도 안 가리킨다.**
    조용한 기본값은 선언을 장식으로 만들고, 그 장식 위에서 자동 조치가 돈다.
    """
    with pytest.raises(ContractError, match="리소스 타입"):
        _derive(
            ProvisionResponse(
                kind="cloud_sql_instance",
                name="db-1",
                region="us-central1",
                previous_revision=None,
            )
        )


def test_req_103_an_empty_response_field_is_refused() -> None:
    """Verifies: REQ-103

    ⚠️ 빈 이름을 통과시키면 계약은 **아무 리소스도 안 가리킨 채** 성립한다.
    빈 문자열 리비전은 더 나쁘다 — `None`과 달리 *"돌아갈 자리가 있다"*로 읽힌다.
    """
    with pytest.raises(ContractError, match="리소스 이름"):
        _response(name="")
    with pytest.raises(ContractError, match="직전 리비전"):
        _response(previous="")


# ── ④ 데모가 그 경로를 탄다 ───────────────────────────────────────────────


def test_req_103_the_demo_contract_is_derived_from_its_provision_response() -> None:
    """Verifies: REQ-103, REQ-803

    ⚠️ 데모는 이 저장소가 **화면에 내는 주장**이다. 거기서 계약을 손으로 조립하면
    ①단계가 보여 주는 것은 유도가 아니라 우리가 적어 둔 값이다.
    """
    contract = demo.demo_contract(PROVISIONED_AT)
    response = demo.DEMO_PROVISION_RESPONSE
    assert contract.resource.name == response.name
    assert contract.resource.region == response.region
    assert contract.health_signal.resource_filter == response.name
    assert contract.rollback_plan is not None
    assert contract.rollback_plan.previous_revision == response.previous_revision


def test_req_103_the_demo_says_the_response_shape_is_not_verified_yet() -> None:
    """Verifies: REQ-103, REQ-601

    ⛔ 유도는 됐지만 **응답이 각본이다.** 실물 Cloud Run 응답이 이 모양으로 오는지는
    T3-1에서만 확인된다. 그 문장이 빠지면 다음 사람이 이 초록을 실물 왕복으로 읽는다
    (docs/PRINCIPLES.md #3).
    """
    assert any("T3-1" in caveat for caveat in demo.run_demo().caveats)
