"""조치 실행기 — **조치는 하나가 아니다** (P1).

Spec: specs/warranty/design/03-atomic-rollback.md (REQ-301, REQ-302)

⭐ **이 파일이 커진 이유는 능력이 아니라 논지다.** 조치가 *"트래픽 전환"* 하나뿐인 동안
   이 시스템은 카나리 롤백 도구(Flagger·Argo Rollouts·Kayenta)와 **구분되지 않는다.**
   그 도구들은 배포할 때만 움직인다. 동시성은 **배포와 무관하게 아무 때나** 바꿀 수 있고,
   바꾸면 **요청은 전부 200인데 절반이 SLO를 못 지킨다** — `executed ≠ improved`의
   가장 순수한 형태이고, 헬스체크가 원리적으로 못 잡는 자리다.

⭐ **롤백은 한 벌 그대로다.** 동시성을 바꾸면 Cloud Run이 새 리비전을 만들고, 되돌리기는
   이전 리비전으로의 트래픽 전환이다 — 이미 원자적이라고 **되읽어 증명한** 그 경로(REQ-303).
   조치를 하나 더한 대가로 검증·롤백 코드는 **한 줄도 안 늘었다.**
"""

from __future__ import annotations

from dataclasses import dataclass

from warranty.adapters.live_run import RunControlError, concurrency_value
from warranty.domain.contract import ResourceRef
from warranty.ports import RunControl

#: 조치 문법의 구분자. `<kind>:<value>` — 리비전 이름에는 이 글자가 없어서 옛 형태와 안 겹친다.
SEPARATOR = ":"

#: 트래픽을 특정 리비전으로 전부 옮긴다. 값은 리비전 이름.
TRAFFIC = "traffic"

#: 인스턴스당 동시 요청 수를 바꾼다. 값은 정수.
CONCURRENCY = "concurrency"

#: ⛔ **아는 조치만 실행한다.** 모르는 접두어에 기본값을 주면 오타 하나가 조용히
#: 트래픽 전환이 되고, 그 전환은 원장에 *"요청한 조치"*로 남는다.
KNOWN_ACTIONS = (TRAFFIC, CONCURRENCY)


class ActionError(ValueError):
    """실행할 조치가 이 어댑터의 안전한 범위 밖이다."""


@dataclass(frozen=True, slots=True)
class Action:
    """실행 전에 **이미 해석이 끝난** 조치 하나.

    ⚠️ 해석을 실행기 안에서 하지 않고 값으로 빼는 이유: 게이트는 실물을 못 부르지만
       *"무엇을 하겠다고 읽었는가"*는 태울 수 있다. 그 해석이 틀리면 실물에서 조용히 틀린다.
    """

    kind: str
    revision: str = ""
    concurrency: int = 0


def target_revision(action_id: str, resource: ResourceRef) -> str:
    """트래픽 조치가 가리키는 리비전. **순수하다.**

    ⛔ 다른 서비스의 리비전으로는 못 옮긴다. 이름만 보고 옮기면 **엉뚱한 서비스의
       트래픽이 움직이고**, 그 실패는 "권한 없음"이 아니라 조용한 오작동으로 온다.
    """
    revision = action_id.strip()
    if resource.kind != "cloud_run_service":
        raise ActionError(f"Cloud Run 서비스 조치가 아니다: {resource.kind!r}")
    if not revision.startswith(f"{resource.name}-"):
        raise ActionError(f"대상 리비전이 서비스 {resource.name!r}에 속하지 않는다: {revision!r}")
    return revision


def parse_action(action_id: str, resource: ResourceRef) -> Action:
    """`action_id` 한 줄을 조치로 읽는다. **순수하다.**

    문법은 `<kind>:<value>`다:
      `traffic:demo-target-00002-lss` · `concurrency:16`

    ⚠️ **구분자가 없으면 트래픽 전환으로 읽는다.** 배포된 에이전트와 08-28 원장이
       리비전 이름을 그대로 넘기고 있다 — 옛 형태를 깨면 이미 실물에서 참인 기록이
       재현 불가가 된다. 리비전 이름에 `:`가 못 들어가서 두 형태는 안 겹친다.
    """
    raw = action_id.strip()
    if not raw:
        raise ActionError("조치가 비었다 — 무엇을 할지 모른다")

    if SEPARATOR not in raw:
        return Action(kind=TRAFFIC, revision=target_revision(raw, resource))

    kind, _, value = raw.partition(SEPARATOR)
    kind, value = kind.strip(), value.strip()
    if kind not in KNOWN_ACTIONS:
        raise ActionError(f"모르는 조치다: {kind!r} — 아는 것은 {sorted(KNOWN_ACTIONS)}")

    if kind == TRAFFIC:
        return Action(kind=TRAFFIC, revision=target_revision(value, resource))

    if resource.kind != "cloud_run_service":
        raise ActionError(f"Cloud Run 서비스 조치가 아니다: {resource.kind!r}")
    try:
        requested = int(value)
    except ValueError as exc:
        raise ActionError(f"동시성이 정수가 아니다: {value!r}") from exc
    # ⚠️ 경계는 `live_run`이 소유한다 — Cloud Run이 받는 값이지 이 문법의 취향이 아니다.
    #    다만 **여기서 나가는 예외는 하나여야 한다**: 호출자가 `ActionError`만 잡는데
    #    범위 초과가 `RunControlError`로 새어 나가면 그 조치는 거절이 아니라 **크래시**다.
    try:
        return Action(kind=CONCURRENCY, concurrency=concurrency_value(requested))
    except RunControlError as exc:
        raise ActionError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class LiveActionExecutor:
    run: RunControl

    def execute(self, action_id: str, resource: ResourceRef) -> bool:
        """조치를 실행한다. ⛔ 반환은 **API가 성공했는가**이지 나아졌는가가 아니다.

        ⚠️ 해석은 **실행 전에** 끝난다 — 모르는 조치는 여기서 예외이지, 절반쯤 실행된
           상태가 아니다.
        """
        action = parse_action(action_id, resource)
        if action.kind == TRAFFIC:
            self.run.shift_all_traffic(resource, action.revision)
            return True
        self.run.set_concurrency(resource, action.concurrency)
        return True
