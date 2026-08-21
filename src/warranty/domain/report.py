"""일간 리포트 — ★ `improvement_rate`가 이 시스템의 헤드라인이다.

Spec: specs/warranty/design/05-accountability-ledger.md §5 (REQ-508)

대부분의 운영 도구는 `executed`만 세고 그것을 성공이라 부른다. 이 리포트가 내는 것은
**실행한 것 중 실제로 나아진 비율**이고, 그 옆에 `unverifiable`(확인조차 못 한 건수)과
`wasted_usd`(회복 실패 조치가 쓴 돈)를 나란히 놓는다.

⚠️ **여기 있는 숫자는 전부 원장에서 유도된다. 하나도 저장하지 않는다** — `improved`를
   유도로 뽑은 것과 같은 계열이다(가드 G8). 저장하면 원장과 리포트가 어긋날 수 있고,
   **어긋난 쪽이 사람에게 보인다.**
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, date
from decimal import Decimal
from typing import Any

from warranty.domain.entry import EntryKind, LedgerEntry, Status
from warranty.domain.verification import DecidedBy, Verdict

#: 하루의 경계는 **UTC**다. 신호도 청구도 UTC로 오고, 경계를 지역 시간으로 잡으면
#: 같은 원장이 리포트를 부르는 곳마다 다른 회복률을 낸다 (REQ-802 — 결정론).
REPORT_TZ = UTC

#: 헤드라인을 사람에게 보일 때의 자릿수. 계산은 자르지 않고 **표시할 때만** 자른다.
RATE_PLACES = Decimal("0.01")


class ReportError(ValueError):
    """리포트를 낼 수 없다."""


@dataclass(frozen=True, slots=True)
class DailyReport:
    """하루치 한 에이전트의 성적표.

    Spec: specs/warranty/design/05-accountability-ledger.md §5 (REQ-508)
    """

    day: date
    agent_id: str
    executed: int
    improved: int
    rolled_back: int
    escalated: int
    unverifiable: int
    manual_required: int
    model_decided: int
    wasted_usd: Decimal
    #: `wasted_usd` 중 **아직 청구서로 확인 안 된** 건수. 총액만 내면 그 총액을
    #: 지배하는 것이 추정인지 실측인지 영원히 모른다 (design 05§2와 같은 이유).
    wasted_assumed_only: int

    @property
    def improvement_rate(self) -> Decimal | None:
        """★ 이 시스템의 헤드라인. **분모는 `executed`다.**

        ⚠️ 분모를 전체 건수로 잡으면 거부·수동 필요가 회복률을 희석해서, 게이트가
           잘 막을수록 성적이 나빠 보인다. 게이트가 막은 것은 *조치가 아니다.*
        ⚠️ 실행이 0이면 **`None`이지 0이 아니다.** 0은 *"해 봤는데 하나도 못 고쳤다"*로
           읽히고, 그건 *"할 게 없었다"*와 전혀 다른 문장이다.
        """
        if self.executed == 0:
            return None
        return Decimal(self.improved) / Decimal(self.executed)

    def as_dict(self) -> dict[str, Any]:
        """design 05§5의 문서 모양 그대로.

        ⚠️ 금액은 **문자열**로 낸다 — float로 실으면 십진 정확도가 직렬화에서 사라진다.
        ⚠️ `unverifiable`을 빼지 않는다. 구조적으로 드러나는 한계는 감점이 아니라
           신뢰의 근거다(design 05§5). 감추면 회복률이 좋아 보이는 방향으로만 틀린다.
        """
        rate = self.improvement_rate
        return {
            "date": self.day.isoformat(),
            "agent_id": self.agent_id,
            "executed": self.executed,
            "improved": self.improved,
            "improvement_rate": None if rate is None else float(rate.quantize(RATE_PLACES)),
            "rolled_back": self.rolled_back,
            "escalated": self.escalated,
            "unverifiable": self.unverifiable,
            "manual_required": self.manual_required,
            "wasted_usd": str(self.wasted_usd),
            "wasted_assumed_only": self.wasted_assumed_only,
            "model_decided": self.model_decided,
        }


def daily_report(entries: Iterable[LedgerEntry], *, day: date, agent_id: str) -> DailyReport:
    """원장에서 하루치 성적표를 **유도한다** (REQ-508).

    Spec: specs/warranty/design/05-accountability-ledger.md §5 (REQ-508)
    """
    # ★ 이 리포트가 세는 것은 **조치**다 (REQ-508). 모델 호출 행(REQ-603)을 섞으면
    #   회복률의 분모가 늘고, 그 행들은 원리상 절대 `improved`가 되지 않는다 —
    #   ⇒ **모델을 쓸수록 헤드라인이 나빠지고**, 그 오차는 리포트를 봐서는 안 보인다.
    rows = tuple(
        row for row in _scoped(entries, day=day, agent_id=agent_id) if row.kind is EntryKind.ACTION
    )
    executed = tuple(row for row in rows if row.executed)
    # ★ 회복 실패 조치 — **실행됐는데 나아지지 않은 것**이다. 롤백으로 되돌렸어도
    #   그 조치가 쓴 돈은 이미 나갔다.
    wasted = tuple(row for row in executed if not row.improved)
    return DailyReport(
        day=day,
        agent_id=agent_id,
        executed=len(executed),
        improved=sum(1 for row in executed if row.improved),
        rolled_back=sum(1 for row in rows if row.rolled_back),
        escalated=sum(1 for row in rows if row.escalated),
        unverifiable=sum(1 for row in rows if _verdict_of(row) is Verdict.UNVERIFIABLE),
        manual_required=sum(1 for row in rows if row.status is Status.MANUAL_REQUIRED),
        model_decided=sum(1 for row in rows if _decided_by(row) is DecidedBy.MODEL),
        wasted_usd=sum((_spent(row) for row in wasted), start=Decimal(0)),
        wasted_assumed_only=sum(1 for row in wasted if row.measured is None),
    )


def _scoped(entries: Iterable[LedgerEntry], *, day: date, agent_id: str) -> Iterator[LedgerEntry]:
    """한 에이전트의 하루로 좁힌다.

    ⚠️ 시간대 없는 시각은 **어느 날인지 정할 수 없다.** UTC로 가정하고 넘어가면
       경계 근처 항목이 조용히 다른 날에 실리고, 그 오차는 리포트를 봐서는 안 보인다.
    """
    for entry in entries:
        if entry.agent_id != agent_id:
            continue
        if entry.started_at.tzinfo is None:
            raise ReportError(f"시각에 시간대가 없어 어느 날인지 정할 수 없다: {entry.entry_id}")
        if entry.started_at.astimezone(REPORT_TZ).date() == day:
            yield entry


def _spent(entry: LedgerEntry) -> Decimal:
    """이 조치가 쓴 돈. **청구서가 말한 값이 있으면 그것이 이긴다.**

    ⚠️ `assumed`를 덮는 것이 아니다 — 원장의 `assumed`는 그대로 있고, 여기서 **읽을 때**
       실측을 고를 뿐이다(I-1). 실측이 아직 없는 건수는 `wasted_assumed_only`로 함께 낸다.
    """
    return entry.assumed.amount_usd if entry.measured is None else entry.measured.amount_usd


def _verdict_of(entry: LedgerEntry) -> Verdict | None:
    return entry.verification.verdict if entry.verification is not None else None


def _decided_by(entry: LedgerEntry) -> DecidedBy | None:
    return entry.verification.decided_by if entry.verification is not None else None
