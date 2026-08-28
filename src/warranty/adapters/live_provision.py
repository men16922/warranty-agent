"""Day-1 실물 절반 — **만드는 호출과 계약이 같은 순간에 난다** (T3-1 · REQ-101).

Spec: specs/warranty/design/01-operational-contract.md §1, §3 (REQ-101, REQ-103)
      specs/warranty/design/10-deployment.md §2 (REQ-602)

⛔ **여기까지가 논지의 절반이다.** 첫 화면이 *"만든 에이전트가 어떻게 확인하고 어떻게
   되돌리는지도 함께 적어 둔다"*라고 말하는데, 08-29까지 실물 `provision`은
   `not_implemented`를 돌려주고 있었다 — Day-2만 실물이었다.

⚠️ **이 어댑터는 계약을 만들지 않는다.** 계약은 `usecases/provision.derive_contract`가
   생성 응답에서 **유도한다**(REQ-103). 여기서 하는 일은 *"실제로 무엇이 만들어졌는가"*를
   그 함수가 읽을 수 있는 모양(`ProvisionResponse`)으로 옮기는 것뿐이다.
   ⇒ 어댑터가 계약 필드를 하나라도 직접 채우면 유도는 관례가 되고, 관례는 언젠가 깨진다.

⚠️ **새로 만든 서비스에는 돌아갈 리비전이 없다.** `previous_revision=None`이고, 그래서
   유도된 계약은 `IRREVERSIBLE`이 되며 그 리소스는 **자동 조치 대상이 아니다**.
   이것은 결함이 아니라 design 01§3이 적어 둔 결과다 — 되돌아갈 자리가 없는데
   `REVERSIBLE`을 쓰면 그 계약은 필요한 날 틀린다.

⚠️ **이미지는 자기가 도는 것을 쓴다.** 새 이미지 주소를 설정으로 받으면 값의 출처가
   둘이 되고(config와 그 설정), 둘이면 한쪽만 낡는다. 이 서비스가 지금 무엇으로 도는지는
   Cloud Run이 안다 — 그것을 읽어서 쓴다. ⇒ 만들어진 리소스는 **이 커밋과 같은 이미지**다.

⛔ **모듈 임포트만으로 클라이언트를 만들지 않는다** — G5가 집행한다(T12-5 · REQ-801).
"""

from __future__ import annotations

from typing import Any

from warranty.adapters import live_guard
from warranty.usecases.provision import ProvisionResponse

#: Admin v2에서 서비스를 **만들** 때 부모가 되는 경로. ⚠️ 서비스 하나를 가리키는
#: `live_run.SERVICE_PATH`와 다른 모양이다 — 섞으면 생성이 404로 죽는다.
PARENT_PATH = "projects/{project}/locations/{region}"

#: 만들어지는 서비스가 뜰 때 쓰는 진입점. ⚠️ 이미지는 `warranty-api`와 같은 것을 쓰고
#: **진입점만 바꾼다**(design 10§2와 같은 수법) — 두 번째 Dockerfile이 따로 썩지 않는다.
PROVISIONED_COMMAND = ("python", "-m", "warranty.demo_target_server")

#: 만들어지는 서비스가 **건강한 쪽으로** 뜬다. ⛔ 기본값은 없다(demo_target_server) —
#: 안 주면 컨테이너가 뜨지 않고, 그 편이 조용히 건강한 척하는 것보다 낫다.
PROVISIONED_ENV = {"WR_DEMO_REVISION": "healthy"}

#: 유휴 0으로 수렴한다 — 만든 것도 REQ-805를 지킨다. 만드는 자리가 예외면 규칙이 아니다.
PROVISIONED_MIN_INSTANCES = 0
PROVISIONED_MAX_INSTANCES = 1


class ProvisionError(RuntimeError):
    """실물 프로비저닝이 성립하지 않는다."""


def parent_path(project: str, region: str) -> str:
    """생성 호출의 부모 경로. **순수하다.**

    ⚠️ 빈 값을 통과시키면 `projects//locations/`가 만들어지고, 그 요청은 **다른 곳**을
       가리킨다. 여기서 죽는 편이 낫다.
    """
    if not project.strip():
        raise ProvisionError("프로젝트가 비었다 — 어디에 만들지 모른다")
    if not region.strip():
        raise ProvisionError("리전이 비었다 — 어디에 만들지 모른다")
    return PARENT_PATH.format(project=project.strip(), region=region.strip())


def service_name(name: str) -> str:
    """만들 서비스의 이름. **순수하다.**

    ⚠️ Cloud Run 서비스 이름 규칙(소문자·숫자·하이픈)을 여기서 태운다 — 안 태우면
       실패가 **생성 호출까지 가서** 나고, 그때는 이미 부분적으로 만들어진 뒤일 수 있다.
    """
    trimmed = name.strip()
    if not trimmed:
        raise ProvisionError("서비스 이름이 비었다")
    if not all(char.islower() or char.isdigit() or char == "-" for char in trimmed):
        raise ProvisionError(
            f"Cloud Run 서비스 이름으로 못 쓴다: {trimmed!r} — 소문자·숫자·하이픈만 된다"
        )
    if trimmed[0] == "-" or trimmed[-1] == "-":
        raise ProvisionError(f"이름이 하이픈으로 시작하거나 끝난다: {trimmed!r}")
    return trimmed


def response_from_service(service: Any, *, kind: str, name: str, region: str) -> ProvisionResponse:
    """만들어진 것을 **되읽어** 유도의 입력으로 옮긴다. **순수하다.**

    ⛔ **우리가 보낸 값이 아니라 서버가 말하는 값이다** — `read_traffic`이 롤백에 대해
       하는 일을 생성에 대해 한다(REQ-303의 같은 원리). 보낸 것을 그대로 계약에 넣으면
       *"만들어졌다"*는 주장이지 측정이 아니다.

    ⚠️ `traffic_statuses`가 **비어 있지 않아도** `previous_revision`은 `None`이다 —
       갓 만든 서비스의 배분은 방금 만든 리비전 하나를 가리키고, 그것은 **돌아갈 자리가
       아니라 지금 자리**다. 그 둘을 섞으면 롤백이 자기 자신으로 간다.
    """
    served = str(getattr(service, "name", "") or "")
    if not served:
        raise ProvisionError("생성 응답이 이름을 안 준다 — 무엇이 만들어졌는지 모른다")
    if not served.endswith(f"/{name}"):
        raise ProvisionError(
            f"생성 응답이 다른 것을 가리킨다: {served!r} — 기대한 이름은 {name!r}이다"
        )
    return ProvisionResponse(kind=kind, name=name, region=region, previous_revision=None)


class LiveProvisioner:
    """실물 Cloud Run 생성. ⛔ **클라이언트는 첫 호출에서 만든다** (G5 · REQ-801)."""

    def __init__(self, project: str, region: str, template_service: str) -> None:
        self._project = project
        self._region = region
        self._template = template_service
        self._client: Any | None = None

    def _services(self) -> Any:
        """⛔ **G5의 관측 지점이다.** 게이트가 여기 온 것 자체가 REQ-801 위반이다."""
        if self._client is None:
            live_guard.note("live_provision.LiveProvisioner._services")
            # ⚠️ 지연 임포트 — 게이트에는 이 패키지가 없다(REQ-801).
            from google.cloud import run_v2  # type: ignore[import-not-found]

            self._client = run_v2.ServicesClient()
        return self._client

    def _template_image(self) -> str:
        """지금 이 서비스가 **무엇으로 도는지** Cloud Run에게 묻는다.

        ⛔ 이미지 주소를 설정으로 받지 않는 이유다 — 받으면 값의 출처가 둘이 되고,
           둘이면 한쪽만 낡는다. 만들어진 리소스는 이 커밋과 **같은 이미지**여야 한다.
        """
        live_guard.note("live_provision.LiveProvisioner._template_image")
        name = f"{parent_path(self._project, self._region)}/services/{self._template}"
        service = self._services().get_service(name=name)
        containers = list(getattr(getattr(service, "template", None), "containers", []) or [])
        if not containers:
            raise ProvisionError(f"본보기 서비스에 컨테이너가 없다: {name}")
        image = str(getattr(containers[0], "image", "") or "")
        if not image:
            raise ProvisionError(f"본보기 서비스가 이미지를 안 말한다: {name}")
        return image

    def create(self, name: str, kind: str = "cloud_run_service") -> ProvisionResponse:
        """서비스 하나를 **실제로 만들고**, 만들어진 것을 되읽어 돌려준다.

        ⛔ 첫 줄이 tripwire다(G5). 게이트가 여기 온 것 자체가 REQ-801 위반이다.
        ⚠️ 계약은 여기서 안 만든다 — 부르는 쪽이 `derive_contract`에 넘긴다(REQ-103).
        """
        live_guard.note("live_provision.LiveProvisioner.create")
        if kind != "cloud_run_service":
            raise ProvisionError(f"이 어댑터가 만들 수 있는 것이 아니다: {kind!r}")
        target = service_name(name)
        image = self._template_image()
        client = self._services()
        from google.cloud import run_v2

        service = run_v2.Service(
            template=run_v2.RevisionTemplate(
                scaling=run_v2.RevisionScaling(
                    min_instance_count=PROVISIONED_MIN_INSTANCES,
                    max_instance_count=PROVISIONED_MAX_INSTANCES,
                ),
                containers=[
                    run_v2.Container(
                        image=image,
                        command=list(PROVISIONED_COMMAND),
                        env=[
                            run_v2.EnvVar(name=key, value=value)
                            for key, value in PROVISIONED_ENV.items()
                        ],
                    )
                ],
            )
        )
        created = client.create_service(
            parent=parent_path(self._project, self._region),
            service=service,
            service_id=target,
        ).result()
        return response_from_service(created, kind=kind, name=target, region=self._region.strip())
