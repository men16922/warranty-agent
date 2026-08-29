"""Cloud Run Admin 어댑터 — **게이트가 태울 수 있는 것은 요청의 모양까지다** (T2-4 · REQ-301·302).

Spec: specs/warranty/design/03-atomic-rollback.md (REQ-301, REQ-302)

⛔ 이 열은 *"Cloud Run이 우리 말을 듣는가"*를 안 묻는다 — 그건 실물의 질문이고 오프라인
   게이트가 판정할 수 없다(docs/PRINCIPLES.md #3). 묻는 것은 **우리가 무엇을 보내고
   무엇을 읽는가**이고, 그것이 틀리면 실물에서 조용히 틀린다.

넷을 묻는다:
  ① 경로가 **계약이 가리키는 리전**에서 오는가 (설정의 리전이 아니다)
  ② 전환 요청이 **항목 하나 · 100%**인가 — 부분 전환은 롤백의 근거가 못 된다
  ③ 배분 되읽기가 응답을 **잃지 않고** 옮기는가
  ④ 만질 수 없는 것을 **거부하는가** (빈 프로젝트 · 다른 kind · 빈 리비전)

⚠️ ②가 이 파일의 본체다. 여러 항목을 내면 남은 비율이 다른 리비전에 남고, 그때
   *"되돌렸다"*는 **부분적으로만** 참이다 — REQ-302가 약속한 원자성이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from warranty.adapters.live_run import (
    FULL_TRAFFIC,
    MAX_CONCURRENCY,
    MIN_CONCURRENCY,
    RunControlError,
    concurrency_value,
    latest_traffic_spec,
    parse_traffic,
    service_path,
    traffic_spec,
)
from warranty.domain.contract import ResourceRef

RESOURCE = ResourceRef(kind="cloud_run_service", name="demo-target", region="us-central1")


@dataclass(frozen=True)
class _Status:
    """Admin API 응답 항목의 **모양만** 흉내낸다 — 라이브러리를 안 부른다."""

    revision: str
    percent: int


def test_the_path_comes_from_the_resource_not_the_settings() -> None:
    """① ⛔ 리전은 **계약이 가리키는 리소스**의 것이다.

    ⚠️ 설정에서 가져오면 리전이 둘인 날 갈라지고, 그때 우리는 **다른 서비스의 트래픽을
       옮긴다.** 그 실패는 "권한 없음"이 아니라 "엉뚱한 것이 되돌아갔다"로 온다.
    """
    other = ResourceRef(kind="cloud_run_service", name="demo-target", region="europe-west4")
    assert service_path(RESOURCE, "p1") == (
        "projects/p1/locations/us-central1/services/demo-target"
    )
    assert service_path(other, "p1").endswith("/locations/europe-west4/services/demo-target")
    assert service_path(RESOURCE, "p1") != service_path(other, "p1")


def test_the_shift_asks_for_one_target_at_full_traffic() -> None:
    """② ★ **부분 전환은 롤백이 아니다** (REQ-302)."""
    spec = traffic_spec("demo-target-00007-abc")
    assert len(spec) == 1, f"항목이 하나가 아니다: {spec} — 남은 비율이 다른 리비전에 남는다"
    assert spec[0]["percent"] == FULL_TRAFFIC == 100
    assert spec[0]["revision"] == "demo-target-00007-abc"


def test_reading_the_split_back_loses_nothing() -> None:
    """③ 되읽기가 응답을 **잃지 않는다** — 잃으면 합이 100이 아닌 것을 아무도 못 본다."""
    assert parse_traffic([_Status("r1", 100)]) == {"r1": 100}
    assert parse_traffic([_Status("r1", 50), _Status("r2", 50)]) == {"r1": 50, "r2": 50}
    assert parse_traffic([]) == {}
    assert parse_traffic(None) == {}
    # ⚠️ 이름 없는 항목을 **버리지 않는다.** 조용히 사라지면 합이 100이 아닌 것이 안 보인다.
    assert parse_traffic([_Status("", 30), _Status("r1", 70)]) == {"": 30, "r1": 70}


@pytest.mark.parametrize(
    ("resource", "project", "why"),
    [
        (RESOURCE, "", "프로젝트가 비었다"),
        (ResourceRef(kind="gke_cluster", name="c", region="us-central1"), "p", "다른 kind"),
    ],
)
def test_it_refuses_what_it_cannot_touch(resource: ResourceRef, project: str, why: str) -> None:
    """④ ⛔ **거부가 조용하면 엉뚱한 것을 만진다.**"""
    with pytest.raises(RunControlError):
        service_path(resource, project)


def test_an_empty_revision_is_refused() -> None:
    """④ 어디로 옮길지 모르는 전환은 **보내지 않는다.**"""
    with pytest.raises(RunControlError):
        traffic_spec("")


# ── 두 번째 조치: 동시성 변경 (P1) ────────────────────────────────────


def test_the_concurrency_change_points_traffic_at_the_new_revision() -> None:
    """⑤ ★ **이것이 없으면 동시성 조치는 조용한 무해동작이다.**

    Spec: specs/warranty/design/03-atomic-rollback.md (REQ-302)

    롤백이 한 번이라도 돌면 `service.traffic`은 특정 리비전에 **고정**된다
    (`traffic_spec`이 그렇게 만든다 — 그게 원자성의 근거다). 그 상태에서 템플릿만
    바꾸면 Cloud Run은 새 리비전을 만들지만 **트래픽은 옛 리비전에 남는다.**

    ⛔ 그때 조치는 200을 받고 아무것도 안 바꾼다. 검증은 `not_recovered`를 내고 롤백이
       돌고 원장은 *"고쳤는데 안 나아졌다"*고 적지만 **고친 적이 없다** — 이 저장소가
       세는 `improved`가 그 순간 거짓말이 된다.
    """
    spec = latest_traffic_spec()
    assert len(spec) == 1
    assert spec[0]["percent"] == FULL_TRAFFIC
    assert spec[0]["type_"].endswith("_LATEST")
    # ⛔ 리비전을 못 박으면 **방금 만든 리비전이 아닌 곳**으로 갈 수 있다.
    assert "revision" not in spec[0]
    # 두 조각은 서로 다른 것을 뜻한다 — 같아지면 한쪽이 다른 쪽을 덮은 것이다.
    assert spec != traffic_spec("demo-target-00007-abc")


@pytest.mark.parametrize("good", [MIN_CONCURRENCY, 8, 16, MAX_CONCURRENCY])
def test_the_concurrency_range_accepts_what_cloud_run_accepts(good: int) -> None:
    """⑥ 공허 통과 방지 — 전부 거절이면 아래 테스트는 아무것도 안 묻는다."""
    assert concurrency_value(good) == good


@pytest.mark.parametrize("bad", [0, -1, MAX_CONCURRENCY + 1, True, "16"])
def test_the_concurrency_range_refuses_what_it_cannot_send(bad: object) -> None:
    """⑥ ⛔ 여기서 안 막으면 잘못된 값이 **실행 단계까지 가서** API 오류로 돌아온다.

    ⚠️ 그러면 원장에 `FAILED`가 남고, 그것은 *"조치가 효과 없었다"*와 구분이 안 된다 —
       우리 요청이 애초에 틀렸다는 사실이 사라진다.
    ⚠️ `True`를 함께 태우는 이유: 파이썬에서 `bool`은 `int`이고, 안 막으면
       `concurrency_value(True)`가 **1을 돌려주며 통과한다.**
    """
    with pytest.raises(RunControlError):
        concurrency_value(bad)  # type: ignore[arg-type]
