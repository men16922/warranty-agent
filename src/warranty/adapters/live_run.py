"""Cloud Run Admin 어댑터 — **트래픽 전환이 원자적이라는 주장의 실물 절반** (REQ-301·302).

Spec: specs/warranty/design/03-atomic-rollback.md (REQ-301, REQ-302, REQ-304)
      specs/warranty/design/10-deployment.md §2 (REQ-602)

⛔ **이 저장소가 GCP 전용인 이유가 여기 있다**(OVERVIEW §2). 트래픽 배분을 한 번의 호출로
   바꾸고, 바꿨다고 **주장하지 않고 다시 읽어** 증명한다. 점진적 롤아웃만 되는 곳에서는
   자동 롤백을 믿을 근거가 없다.

⚠️ **라이브러리는 지연 임포트한다.** `google-cloud-run`은 게이트에 안 깔린다(cloud extra ·
   REQ-801). 그래서 게이트가 태우는 것은 **호출이 아니라 요청의 모양**이다 —
   `tools/deploy_plan.py`(T11-1)·`adapters/adk_agent.py`(T12-3)와 같은 수법이다.

⛔ **모듈 임포트만으로 클라이언트를 만들지 않는다.** G5가 그것을 집행한다(T12-5):
   게이트가 도는 동안 실물 어댑터는 **하나도 생성되지 않아야** 한다.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from warranty.adapters import live_guard
from warranty.domain.contract import ResourceRef

#: Cloud Run Admin v2의 서비스 경로 모양. ⚠️ 여기서 프로젝트를 안 적는다 — 주입받는다.
SERVICE_PATH = "projects/{project}/locations/{region}/services/{name}"

#: 전환 후 배분에서 **기대하는 값**. ⛔ 100이 아니면 그것은 전환이 아니라 카나리아이고,
#: 그 위에서 "되돌렸다"는 문장은 참이 아니다(REQ-302).
FULL_TRAFFIC = 100

#: Cloud Run이 받는 인스턴스당 동시 요청 수의 경계. ⛔ 0은 "무제한"이 아니라 **거부**다 —
#: 여기서 안 막으면 API가 막고, 그때 실패는 조치가 아니라 우리 요청의 결함이다.
MIN_CONCURRENCY = 1
MAX_CONCURRENCY = 1000


class RunControlError(RuntimeError):
    """실물 Cloud Run 호출이 성립하지 않는다."""


def service_path(resource: ResourceRef, project: str) -> str:
    """리소스 하나의 Admin API 경로. **순수하다.**

    ⚠️ `resource.region`을 쓴다 — 설정의 리전이 아니다. 계약이 가리키는 리소스가
       어디 있는지는 그 계약이 안다(REQ-102). 설정에서 가져오면 리전이 둘인 날 갈라진다.
    """
    if not project:
        raise RunControlError("프로젝트가 비었다 — 경로를 만들 수 없다")
    if resource.kind != "cloud_run_service":
        raise RunControlError(
            f"Cloud Run 서비스가 아니다: {resource.kind!r} — 이 어댑터는 그것만 만진다"
        )
    return SERVICE_PATH.format(project=project, region=resource.region, name=resource.name)


def traffic_spec(revision: str) -> list[dict[str, Any]]:
    """*"이 리비전에 100%"*를 뜻하는 요청 조각. **순수하다.**

    ⛔ **한 항목만 낸다.** 여러 항목을 내면 남은 비율이 다른 리비전에 남고, 그 순간
       *"되돌렸다"*는 **부분적으로만** 참이다 — 그런 롤백은 검증의 근거가 못 된다.
    """
    if not revision:
        raise RunControlError("리비전 이름이 비었다 — 어디로 옮길지 모른다")
    return [
        {
            "type_": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
            "revision": revision,
            "percent": FULL_TRAFFIC,
        }
    ]


def latest_traffic_spec() -> list[dict[str, Any]]:
    """*"방금 만든 리비전에 100%"*를 뜻하는 요청 조각. **순수하다.**

    ⛔ **이 함수가 없으면 동시성 조치는 조용한 무해동작이다.** 롤백이 한 번이라도 돌면
       `service.traffic`은 **특정 리비전에 고정**된다(`traffic_spec`이 그렇게 만든다).
       그 상태에서 동시성만 바꾸면 Cloud Run은 새 리비전을 만들지만 트래픽은 **옛 리비전에
       그대로 남는다** — API는 200이고, 새 설정은 아무 요청도 못 받는다.

    ⚠️ 그 실패가 위험한 이유는 실패로 안 보이기 때문이다: 실행은 성공하고, 신호는 안 변하고,
       검증은 `not_recovered`를 내고, 롤백이 돈다. 원장은 *"고쳤는데 안 나아졌다"*고
       적지만 **사실은 고친 적이 없다.** 이 저장소가 세는 `improved`가 그 순간 거짓말이 된다.
    """
    return [
        {
            "type_": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST",
            "percent": FULL_TRAFFIC,
        }
    ]


def concurrency_value(raw: int) -> int:
    """조치가 요구한 동시성이 Cloud Run이 받는 값인가. **순수하다.**

    ⚠️ 경계를 어댑터에서 막는 이유: 여기서 안 막으면 잘못된 값이 **실행 단계까지 가서**
       API 오류로 돌아온다. 그러면 원장에는 `FAILED`가 남고, 그것은 *"조치가 효과 없었다"*와
       구분이 안 된다 — 우리 요청이 애초에 틀렸다는 사실이 사라진다.
    """
    ok = isinstance(raw, int) and not isinstance(raw, bool)
    if ok and MIN_CONCURRENCY <= raw <= MAX_CONCURRENCY:
        return raw
    raise RunControlError(
        f"동시성이 범위 밖이다: {raw!r} — {MIN_CONCURRENCY}~{MAX_CONCURRENCY}만 받는다"
    )


def parse_traffic(statuses: Iterable[Any] | None) -> dict[str, int]:
    """Admin API의 `traffic_statuses`를 `{리비전: 퍼센트}`로. **순수하다.**

    ⚠️ 이 함수가 존재하는 이유는 편의가 아니라 **되읽기**다(REQ-302). 응답 모양이 바뀌면
       배분을 잘못 읽고, 그러면 *"돌아갔다"*가 아무 근거 없이 참이 된다.
    ⚠️ 리비전 이름이 없는 항목은 **버리지 않고 빈 키로 남긴다** — 조용히 사라지면
       합이 100이 아닌 것을 아무도 못 본다.
    """
    out: dict[str, int] = {}
    for item in statuses or []:
        revision = str(getattr(item, "revision", "") or "")
        percent = int(getattr(item, "percent", 0) or 0)
        out[revision] = out.get(revision, 0) + percent
    return out


class LiveRunControl:
    """실물 Cloud Run Admin. ⛔ **클라이언트는 첫 호출에서 만든다** (G5 · REQ-801)."""

    def __init__(self, project: str) -> None:
        self._project = project
        self._client: Any | None = None

    def _services(self) -> Any:
        """⛔ **G5의 관측 지점이다.** 게이트가 여기 온 것 자체가 REQ-801 위반이다 —
        임포트가 실패해서가 아니라 **생성 경로에 들어온 것**으로 성립한다."""
        if self._client is None:
            live_guard.note("live_run.LiveRunControl._services")
            # ⚠️ 지연 임포트 — 게이트에는 이 패키지가 없다(REQ-801).
            #    억제는 **첫 줄에만** 붙인다: 이 줄이 이름을 `Any`로 만들면 아래는
            #    이미 해결된 이름이고, 또 붙이면 `warn_unused_ignores`가 운다.
            from google.cloud import run_v2  # type: ignore[import-not-found]

            self._client = run_v2.ServicesClient()
        return self._client

    def shift_all_traffic(self, resource: ResourceRef, revision: str) -> None:
        """트래픽 전부를 한 리비전으로. **한 번의 호출이다** — 그것이 원자성의 근거다.

        ⛔ 첫 줄이 tripwire다(G5). 게이트가 여기 온 것 자체가 REQ-801 위반이다.
        """
        live_guard.note("live_run.LiveRunControl.shift_all_traffic")
        client = self._services()
        from google.cloud import run_v2

        name = service_path(resource, self._project)
        service = client.get_service(name=name)
        service.traffic = [
            run_v2.TrafficTarget(
                type_=run_v2.TrafficTargetAllocationType.TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION,
                revision=revision,
                percent=FULL_TRAFFIC,
            )
        ]
        client.update_service(service=service).result()

    def read_traffic(self, resource: ResourceRef) -> Mapping[str, int]:
        """지금 배분을 **다시 읽는다**. ⛔ 우리가 방금 보낸 값이 아니라 서버가 말하는 값이다.

        ⛔ 첫 줄이 tripwire다(G5) — `_services`가 캐시되어 있으면 그쪽 관측 지점을 안 지난다.
        """
        live_guard.note("live_run.LiveRunControl.read_traffic")
        service = self._services().get_service(name=service_path(resource, self._project))
        return parse_traffic(getattr(service, "traffic_statuses", []))

    def set_concurrency(self, resource: ResourceRef, value: int) -> None:
        """인스턴스당 동시 요청 수를 바꾼다 — **두 번째 조치** (P1).

        ⭐ Cloud Run은 템플릿이 바뀌면 **새 리비전을 만든다.** 그래서 이 조치의 롤백은
           새로 만들 것이 없다 — 이전 리비전으로의 트래픽 전환, 즉 이미 원자적이라고
           증명한 그 경로다(REQ-301·302·303).

        ⛔ **트래픽을 LATEST로 함께 돌린다.** 롤백이 한 번이라도 돌았으면 배분은 특정
           리비전에 고정되어 있고, 그 상태에서 템플릿만 바꾸면 새 리비전은 **아무 요청도
           안 받는다.** 그러면 조치는 200을 받고 아무것도 안 바꾼다 —
           `latest_traffic_spec` 도크스트링이 그 함정을 적어 둔 자리다.

        ⛔ 첫 줄이 tripwire다(G5). 게이트가 여기 온 것 자체가 REQ-801 위반이다.
        """
        live_guard.note("live_run.LiveRunControl.set_concurrency")
        client = self._services()
        from google.cloud import run_v2

        name = service_path(resource, self._project)
        service = client.get_service(name=name)
        service.template.max_instance_request_concurrency = concurrency_value(value)
        service.traffic = [
            run_v2.TrafficTarget(
                type_=run_v2.TrafficTargetAllocationType.TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST,
                percent=FULL_TRAFFIC,
            )
        ]
        client.update_service(service=service).result()
