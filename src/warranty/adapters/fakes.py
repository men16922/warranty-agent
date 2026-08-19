"""테스트 어댑터.

⚠️ 이것들은 게이트가 오프라인이게 만드는 장치이지, REQ-601·602를 만족시키지 못한다.
   스텁 위에서 통과하는 테스트는 *"우리가 이 인터페이스를 이렇게 부른다"*를 말할 뿐
   *"그 인터페이스가 존재한다"*를 말하지 않는다 (docs/PRINCIPLES.md #3).
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from warranty.domain.contract import OperationalContract, ResourceRef, SignalSpec
from warranty.domain.verification import Measurement, Verdict


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

    def shift_all_traffic(self, resource: ResourceRef, revision: str) -> None:
        self.shifts.append(revision)
        self._traffic = {revision: 100} if self._honors else {revision: 50, self._current: 50}

    def read_traffic(self, resource: ResourceRef) -> Mapping[str, int]:
        return dict(self._traffic)


class FakeBudget:
    def __init__(self, headroom: Decimal = Decimal("0.50")) -> None:
        self._headroom = headroom
        self.committed: list[Decimal] = []

    def headroom(self, agent_id: str) -> Decimal:
        return self._headroom

    def commit(self, agent_id: str, amount: Decimal) -> None:
        self.committed.append(amount)
        self._headroom -= amount


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
