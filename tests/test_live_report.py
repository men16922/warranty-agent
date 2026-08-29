"""회복률 리포트의 실물 절반 — **하루를 어떻게 긁어 오는가** (T5-4 · REQ-508).

Spec: specs/warranty/design/05-accountability-ledger.md §5 (REQ-508)

⛔ **세는 규칙은 여기 없다.** `domain/report.daily_report`가 소유한다. 이 파일이 태우는
   것은 *"그 함수에 무엇을 넘기는가"*뿐이다 — 넘기는 집합이 틀리면 세는 규칙이 옳아도
   리포트는 틀리고, 그 틀림은 **비어 있으면서 초록**으로 보인다.

묻는 것은 셋이다:
  ① 하루 창이 **닫힘–열림**인가 — 자정 정각 행이 이틀에 실리지 않는가
  ② 질의가 **에이전트로 좁히지 않는가** — 좁히면 Firestore가 복합 색인을 요구한다
  ③ ⛔ **본체**: 리포트 도구가 `executed`와 `improved`를 **따로** 내는가
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from warranty.adapters.live_store import STARTED_AT_FIELD, day_window_conditions
from warranty.domain.attribution import Attribution, Method
from warranty.domain.cost import Basis, CostFact
from warranty.domain.entry import EntryKind, InMemoryLedger, LedgerEntry, Status
from warranty.domain.verification import DecidedBy, Measurement, Verdict, Verification
from warranty.runtime import AgentTools
from warranty.runtime import RuntimeError as ToolError

DAY = date(2026, 8, 29)
NOON = datetime(2026, 8, 29, 12, tzinfo=UTC)
AGENT = "warranty"


def test_the_day_window_is_closed_open() -> None:
    """① 자정 정각 행이 **이틀에 실리지 않는가**.

    ⚠️ 끝을 `<=`로 잡으면 다음 날 00:00:00 행이 양쪽에 세어지고, 그 오차는 리포트를
       봐서는 안 보인다 — 두 날의 합이 전체보다 커질 뿐이다.
    """
    conditions = day_window_conditions(DAY)
    assert [op for _, op, _ in conditions] == [">=", "<"], f"창이 닫힘–열림이 아니다: {conditions}"
    start = datetime(2026, 8, 29, tzinfo=UTC)
    assert [value for _, _, value in conditions] == [
        start.isoformat(),
        (start + timedelta(days=1)).isoformat(),
    ]


def test_the_query_does_not_narrow_by_agent() -> None:
    """② 에이전트로 좁히면 Firestore가 **복합 색인**을 요구한다.

    ⛔ 색인이 없는 날 리포트는 예외로 죽는다. 좁히는 일은 도메인이 이미 한다 —
       질의는 넉넉히 긁고, 판정은 한 곳에서 한다.
    """
    fields = {path for path, _, _ in day_window_conditions(DAY)}
    assert fields == {STARTED_AT_FIELD}, (
        f"질의가 시각 말고 다른 필드를 건다: {fields} — 복합 색인이 필요해진다"
    )


def _entry(entry_id: str, **over: object) -> LedgerEntry:
    base = LedgerEntry(
        entry_id=entry_id,
        agent_id=AGENT,
        action_id="shift_traffic",
        status=Status.EXECUTED,
        started_at=NOON,
        attribution=Attribution(Method.RESOURCE_LABEL, label_value=entry_id),
        assumed=CostFact(
            amount_usd=Decimal("0.10"),
            priced_at=NOON,
            basis=Basis.PUBLISHED_RATE,
            inputs={"cpu_seconds": Decimal(60)},
            unit_prices={"cpu_seconds": Decimal("0.10") / Decimal(60)},
        ),
    )
    return replace(base, **over)  # type: ignore[arg-type]


def _verified(verdict: Verdict) -> Verification:
    return Verification(
        verdict=verdict,
        decided_by=DecidedBy.RULE,
        baseline=Measurement(Decimal("100"), 30),
        after=Measurement(Decimal("30"), 30),
    )


def _tools(ledger: InMemoryLedger) -> AgentTools:
    return AgentTools(
        remediator=None,  # type: ignore[arg-type]
        contracts=None,  # type: ignore[arg-type]
        signals=None,  # type: ignore[arg-type]
        default_region="us-central1",
        ledger=ledger,
    )


def test_req_508_the_report_counts_improved_separately_from_executed() -> None:
    """③ ⛔ **이 가드의 본체다.** `executed`만 세고 성공이라 부르지 않는가.

    Verifies: REQ-508

    ⚠️ 모델 호출 행을 섞으면 분모가 늘고, 그 행들은 원리상 절대 `improved`가 되지
       않는다 — **모델을 쓸수록 헤드라인이 나빠진다.**
    ⚠️ 어제 행이 섞이면 하루 창이 무의미해진다. 셋을 한 자리에서 함께 태운다.
    """
    ledger = InMemoryLedger()
    ledger.create(_entry("a1", verification=_verified(Verdict.RECOVERED)))
    ledger.create(_entry("a2", verification=_verified(Verdict.NOT_RECOVERED)))
    ledger.create(_entry("m1", kind=EntryKind.MODEL_CALL))
    ledger.create(_entry("old", started_at=NOON - timedelta(days=1)))

    report = _tools(ledger).report("2026-08-29")
    assert report["executed"] == 2, (
        f"조치 수가 {report['executed']}다 — 모델 호출이나 어제 행이 섞였다: {report}"
    )
    # ⛔ 여기서 **둘이 다른 값**인 것이 요점이다. 같아지면 이 프로젝트가 말하는 문장이
    #    사라진다 — 실행했다와 나아졌다가 같은 칸이 되는 순간 논지가 없다.
    assert report["improved"] == 1, f"improved가 executed와 같은 칸이 됐다: {report}"
    assert report["rolled_back"] == 0, "롤백 안 한 조치가 롤백으로 세어졌다"
    assert report["wasted_usd"] == "0.10", (
        f"회복 못 한 조치가 쓴 돈이 안 세어졌다: {report['wasted_usd']} — "
        "롤백해도 그 조치가 쓴 돈은 이미 나갔다"
    )


def test_a_date_that_is_not_a_date_is_refused() -> None:
    """⚠️ 날짜가 아닌 것을 넘기면 **여기서 죽는다** — 조용히 빈 리포트를 내지 않는다.

    빈 리포트는 *"그 날 아무 일도 없었다"*로 읽히고, 그것은 거짓이다.
    """
    with pytest.raises(ToolError):
        _tools(InMemoryLedger()).report("어제")
