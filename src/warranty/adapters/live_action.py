"""Cloud Run 트래픽 전환을 조치 실행 포트에 붙인다."""

from __future__ import annotations

from dataclasses import dataclass

from warranty.domain.contract import ResourceRef
from warranty.ports import RunControl


class ActionError(ValueError):
    """실행할 조치가 이 어댑터의 안전한 범위 밖이다."""


def target_revision(action_id: str, resource: ResourceRef) -> str:
    """현재 라이브 조치는 `action_id`가 가리키는 같은 서비스 리비전으로의 전환 하나다."""
    revision = action_id.strip()
    if resource.kind != "cloud_run_service":
        raise ActionError(f"Cloud Run 서비스 조치가 아니다: {resource.kind!r}")
    if not revision.startswith(f"{resource.name}-"):
        raise ActionError(f"대상 리비전이 서비스 {resource.name!r}에 속하지 않는다: {revision!r}")
    return revision


@dataclass(frozen=True, slots=True)
class LiveActionExecutor:
    run: RunControl

    def execute(self, action_id: str, resource: ResourceRef) -> bool:
        self.run.shift_all_traffic(resource, target_revision(action_id, resource))
        return True
