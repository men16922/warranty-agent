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
