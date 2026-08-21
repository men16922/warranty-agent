"""포트 — 게이트가 오프라인이려면 여기서 경계가 서야 한다.

Spec: specs/warranty/design/08-interfaces.md (REQ-801, REQ-802)

⚠️ 포트는 설계 취향이 아니다. **이 경계가 없으면 REQ-801은 만족 불가능하다** —
   이 시스템은 Vertex·Firestore·Cloud Monitoring·Cloud Run을 쓴다.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from warranty.domain.budget import Reservation
from warranty.domain.contract import OperationalContract, ResourceRef, SignalSpec
from warranty.domain.cost import CostFact
from warranty.domain.entry import Approval, LedgerEntry, Rollback, Status
from warranty.domain.tokens import ModelReply
from warranty.domain.verification import Measurement, Verdict, Verification


class Clock(Protocol):
    def now_iso(self) -> str: ...
    def sleep(self, seconds: int) -> None:
        """⚠️ 테스트에서는 실제로 안 잔다. 게이트가 결정론적이려면 시간도 주입돼야 한다."""


class IdGen(Protocol):
    def new_entry_id(self) -> str: ...


class ContractStore(Protocol):
    def active_for(self, resource: ResourceRef) -> OperationalContract | None:
        """⚠️ `retired`된 계약은 돌려주지 않는다 — 없는 리소스를 고치려 들면 안 된다."""


class SignalSource(Protocol):
    def read(self, spec: SignalSpec) -> Measurement: ...
    def readable(self, spec: SignalSpec) -> bool:
        """지금 이 신호를 읽을 수 있는가. **판정 게이트의 검증 가능성 축이 여기서 온다.**"""


class ActionExecutor(Protocol):
    def execute(self, action_id: str, resource: ResourceRef) -> bool:
        """조치를 실행한다. 반환은 **API가 성공했는가**이지 나아졌는가가 아니다."""


class RunControl(Protocol):
    """Cloud Run 리비전/트래픽. **원자적 롤백이 GCP 전용을 정당화하는 이유다.**"""

    def shift_all_traffic(self, resource: ResourceRef, revision: str) -> None: ...
    def read_traffic(self, resource: ResourceRef) -> Mapping[str, int]:
        """⚠️ 전환 후 **다시 읽는다.** '롤백했다'는 주장이고 이건 측정이다."""


class BudgetStore(Protocol):
    """★ 예약 프로토콜 — `reserve` → 실행 → `settle` (REQ-405).

    Spec: specs/warranty/design/04-decision-gate.md (REQ-405)

    ⚠️ **`commit` 하나로는 동시 초과를 못 막는다.** 실행 뒤에 청구하면 판정과 지출
       사이가 비고, 그 창에서 두 조치가 같은 여유를 본다.
    """

    def headroom(self, agent_id: str) -> Decimal:
        """쓸 수 있는 여유. ⚠️ **미정산 예약은 이미 빠져 있다** — 안 빼면 예약이 장식이다."""

    def reserve(self, agent_id: str, amount: Decimal) -> Reservation | None:
        """여유를 붙잡는다. 부족하면 `None`.

        ⚠️ **권위는 이 확인이지 앞선 `headroom` 읽기가 아니다.** 읽은 값으로 판정하고
           예약 없이 실행하면 그 판정은 이미 낡았을 수 있다.
        """

    def settle(self, reservation: Reservation, actual: Decimal) -> None:
        """예약을 실제 지출로 확정하고 차액을 되돌린다.

        ⚠️ 안 돌면 예산이 **조용히 잠긴다** — 잠긴 예산은 "예산 없음"과 구분이 안 된다.
           그래서 호출자는 예외 경로에서도 이것을 부른다 (design 04§3).
        """

    def unsettled(self) -> int:
        """미정산 예약 수. **잠긴 예산을 보이게 하는 지표다** (design 04§3)."""


class ModelJudge(Protocol):
    """★ 판정이 애매할 때만 불린다 (REQ-204)."""

    def judge_ambiguous(
        self, baseline: Measurement, after: Measurement, criterion_note: str
    ) -> tuple[Verdict, str]:
        """`(verdict, rationale)`. **근거 없는 판정은 허용되지 않는다.**"""


class ModelPort(Protocol):
    """★ 모든 모델 호출이 지나는 **단 하나의 문** (REQ-603).

    Spec: specs/warranty/design/06-agent-runtime.md (REQ-603)

    ⚠️ 호출부마다 원장 기록을 시키면 **언젠가 한 곳이 빠지고, 그 빠짐은 조용하다.**
       그래서 계량은 이 포트를 감싸는 한 겹(`MeteredModel`)에만 있고, 여기 메서드가
       늘면 가드가 **그 메서드도 훑는다** (docs/PRINCIPLES.md #9).
    ⚠️ 응답이 사용량을 **함께** 낸다. 안 그러면 얼마 썼는지는 호출부의 추측이 된다.
    """

    def judge_ambiguous(
        self, baseline: Measurement, after: Measurement, criterion_note: str
    ) -> ModelReply: ...


class LedgerWriter(Protocol):
    """원장 쓰기.

    ⚠️ **범용 `update()`가 없다.** 범용 쓰기가 있으면 `assumed` 불변이 *관례*가 되고,
    관례는 언젠가 깨진다. 각 메서드가 만질 수 있는 필드가 정해져 있다
    (design/08-interfaces.md §2).
    """

    def create(self, entry: LedgerEntry) -> None: ...
    def approve(self, entry_id: str, approval: Approval) -> LedgerEntry:
        """승인을 기록한다. **승인만 만진다** (REQ-404)."""

    def complete(
        self,
        entry_id: str,
        *,
        status: Status,
        verification: Verification | None = None,
        rollback: Rollback | None = None,
    ) -> LedgerEntry: ...
    def reconcile(self, entry_id: str, measured: CostFact) -> LedgerEntry: ...
    def give_up_reconcile(
        self, entry_id: str, *, at: datetime, deadline_days: int, reason: str
    ) -> LedgerEntry:
        """기한이 지나 못 맞춘 행을 **사유와 함께** `unreconciled`로 닫는다 (REQ-506)."""


class LedgerReader(Protocol):
    def get(self, entry_id: str) -> LedgerEntry | None:
        """⚠️ 승인 경로는 **기록된 항목**에서 시작한다 — 호출자가 들고 온 사본이 아니라.
        사본을 믿으면 대기 중에 바뀐 상태(이미 거부됨·이미 실행됨)를 못 본다.
        """


class Ledger(LedgerWriter, LedgerReader, Protocol):
    """읽고 쓰는 원장. 승인은 **기록을 읽어서** 시작하므로 둘 다 필요하다 (REQ-404)."""
