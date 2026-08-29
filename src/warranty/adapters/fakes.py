"""테스트 어댑터.

⚠️ 이것들은 게이트가 오프라인이게 만드는 장치이지, REQ-601·602를 만족시키지 못한다.
   스텁 위에서 통과하는 테스트는 *"우리가 이 인터페이스를 이렇게 부른다"*를 말할 뿐
   *"그 인터페이스가 존재한다"*를 말하지 않는다 (docs/PRINCIPLES.md #3).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal

from warranty.domain.budget import Reservation, ReservationError
from warranty.domain.contract import OperationalContract, ResourceRef, SignalSpec
from warranty.domain.tokens import ModelReply, TokenUsage
from warranty.domain.verification import Measurement, Verdict

#: 대역이 자칭하는 모델 id. ⚠️ 실물 id를 쓰지 않는다 — 이 저장소는 아직 실물 모델을
#: 호출해 본 적이 없고(design 06§2), 대역에 실물 이름을 적으면 테스트가 그 이름을
#: **확인된 것처럼** 만든다.
FAKE_MODEL = "fake-model"


class FrozenClock:
    def __init__(self, iso: str = "2026-08-19T12:00:00+00:00") -> None:
        self._iso = iso
        self.slept: list[int] = []

    def now_iso(self) -> str:
        return self._iso

    def sleep(self, seconds: int) -> None:
        self.slept.append(seconds)  # 실제로 안 잔다


class SeededIdGen:
    def __init__(self, prefix: str = "01k2m9x7q3f4b8n0v6c1t5r") -> None:
        self._prefix, self._n = prefix, 0

    def new_entry_id(self) -> str:
        self._n += 1
        return f"{self._prefix}{self._n:03d}"


class InMemoryContracts:
    def __init__(self) -> None:
        self._by_resource: dict[tuple[str, str], OperationalContract] = {}
        self.lookups = 0

    def put(self, contract: OperationalContract) -> None:
        key = (contract.resource.kind, contract.resource.name)
        self._by_resource[key] = contract

    def active_for(self, resource: ResourceRef) -> OperationalContract | None:
        self.lookups += 1
        found = self._by_resource.get((resource.kind, resource.name))
        return found if found is not None and found.is_active else None


class ScriptedSignal:
    """읽을 때마다 **미리 정한 순서대로** 값을 돌려준다.

    ⚠️ 회복·미회복·애매·빈 창 네 경우를 **값으로 명시**해 태우기 위한 장치다.
    행복 경로만 태운 가드는 하중을 안 받는다.
    """

    def __init__(self, series: list[Measurement], readable: bool = True) -> None:
        self._series, self._i, self._readable = series, 0, readable
        self.reads: list[SignalSpec] = []

    def read(self, spec: SignalSpec) -> Measurement:
        self.reads.append(spec)
        value = self._series[min(self._i, len(self._series) - 1)]
        self._i += 1
        return value

    def readable(self, spec: SignalSpec) -> bool:
        return self._readable


class RecordingExecutor:
    """★ 호출 횟수를 센다 — **가드 G1의 전부다.**

    판정만 확인하는 테스트는 *"판정은 했는데 실행은 됐다"*를 못 잡는다.
    """

    def __init__(self, succeeds: bool = True) -> None:
        self.calls: list[tuple[str, str]] = []
        self._succeeds = succeeds

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def execute(self, action_id: str, resource: ResourceRef) -> bool:
        self.calls.append((action_id, resource.name))
        return self._succeeds


class ReentrantExecutor(RecordingExecutor):
    """★ 조치가 도는 **도중에** 또 하나의 조치가 들어온다 (REQ-405).

    Spec: specs/warranty/design/04-decision-gate.md (REQ-405)

    ⚠️ 게이트는 오프라인·결정론이라 스레드가 없다(REQ-802). 그래서 *"판정과 지출 사이의
       창"*을 값으로 태우는 방법이 **재진입뿐이다.** 이 창을 안 만들면 예약은 `commit`의
       다른 이름일 뿐이고, 예약을 지워도 테스트는 초록이다.
    """

    def __init__(self, succeeds: bool = True) -> None:
        super().__init__(succeeds)
        self.during: Callable[[], None] | None = None

    def execute(self, action_id: str, resource: ResourceRef) -> bool:
        ok = super().execute(action_id, resource)
        if self.during is not None:
            # 한 번만 — 안 비우면 안쪽 조치가 또 재진입해 무한히 내려간다.
            during, self.during = self.during, None
            during()
        return ok


class FakeRun:
    """Cloud Run 트래픽의 대역.

    ⚠️ `honors_shift=False`는 **API는 성공했는데 배분이 안 옮겨진** 경우다.
    이 경우가 없으면 "전환 후 다시 읽는다"는 가드가 하중을 못 받는다 —
    픽스처가 늘 완벽하면 읽기와 가정의 결과가 같아진다 (docs/PRINCIPLES.md #8).
    """

    def __init__(self, current: str = "svc-00008-def", honors_shift: bool = True) -> None:
        self._current = current
        self._traffic: dict[str, int] = {current: 100}
        self._honors = honors_shift
        self.shifts: list[str] = []
        self.concurrencies: list[int] = []

    def shift_all_traffic(self, resource: ResourceRef, revision: str) -> None:
        self.shifts.append(revision)
        self._traffic = {revision: 100} if self._honors else {revision: 50, self._current: 50}

    def read_traffic(self, resource: ResourceRef) -> Mapping[str, int]:
        return dict(self._traffic)

    def set_concurrency(self, resource: ResourceRef, value: int) -> None:
        """동시성 변경의 대역. ⚠️ **새 리비전이 생기는 것까지 흉내낸다.**

        실물 Cloud Run은 템플릿이 바뀌면 리비전을 새로 만들고 트래픽을 그리로 보낸다.
        대역이 그걸 안 하면 *"조치 뒤 배분이 옮겨져 있다"*가 픽스처에서만 거짓이 되고,
        롤백 테스트는 **자기가 무엇을 되돌리는지 모른 채** 초록이 된다
        (docs/PRINCIPLES.md #8).
        """
        self.concurrencies.append(value)
        self._current = f"{resource.name}-c{value}"
        self._traffic = {self._current: 100}


class FakeBudget:
    """예약을 **실제로 붙잡는** 대역 (REQ-405).

    Spec: specs/warranty/design/04-decision-gate.md (REQ-405)

    ⚠️ 예약분을 `headroom`에서 빼지 않으면 이 fake는 예약을 **흉내만 낸다** —
       그러면 "동시 초과를 막는가"를 묻는 테스트가 통과해도 아무것도 증명하지 않는다
       (docs/PRINCIPLES.md #8 — 픽스처가 늘 완벽하면 가드가 하중을 못 받는다).
    """

    def __init__(self, headroom: Decimal = Decimal("0.50")) -> None:
        self._available = headroom
        self._open: dict[str, Reservation] = {}
        self.settled: list[Decimal] = []
        self._n = 0

    def headroom(self, agent_id: str) -> Decimal:
        return self._available  # 미정산 예약은 이미 빠져 있다

    def reserve(self, agent_id: str, amount: Decimal) -> Reservation | None:
        if amount > self._available:
            return None
        self._n += 1
        made = Reservation(f"rsv-{self._n:03d}", agent_id, amount)
        self._available -= amount
        self._open[made.reservation_id] = made
        return made

    def settle(self, reservation: Reservation, actual: Decimal) -> None:
        if self._open.pop(reservation.reservation_id, None) is None:
            # 두 번 정산하면 차액이 두 번 돌아와 **예산이 늘어난다.**
            raise ReservationError(f"열려 있지 않은 예약이다: {reservation.reservation_id}")
        self._available += reservation.amount - actual
        self.settled.append(actual)

    def unsettled(self) -> int:
        return len(self._open)


class ScriptedModel:
    """★ `ModelPort`의 대역 — **사용량을 함께 낸다** (REQ-603).

    Spec: specs/warranty/design/06-agent-runtime.md (REQ-603)

    ⚠️ 사용량 없는 대역을 쓰면 계량 테스트가 계량을 안 태운다. 그리고 `raises`가 없으면
       *"호출은 실패했는데 토큰은 나갔다"*는 경우가 값으로 안 실리고, 그러면 기록을
       `finally`에 둔 이유가 가드에서 사라진다 (docs/PRINCIPLES.md #8).
    """

    def __init__(
        self,
        verdict: Verdict = Verdict.NOT_RECOVERED,
        rationale: str = "fake",
        usage: TokenUsage | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._reply = ModelReply(verdict, rationale, usage or TokenUsage(FAKE_MODEL, 1000, 200))
        self._raises = raises
        self.calls = 0

    def judge_ambiguous(
        self, baseline: Measurement, after: Measurement, criterion_note: str
    ) -> ModelReply:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._reply


class FakeJudge:
    """★ 모델 자리의 대역. **불렸는지 세는 것이 요점이다** — 명확한 경우엔 안 불려야 한다."""

    def __init__(self, verdict: Verdict = Verdict.NOT_RECOVERED, rationale: str = "fake") -> None:
        self._verdict, self._rationale = verdict, rationale
        self.calls = 0

    def judge_ambiguous(
        self, baseline: Measurement, after: Measurement, criterion_note: str
    ) -> tuple[Verdict, str]:
        self.calls += 1
        return self._verdict, self._rationale
