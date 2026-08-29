"""사람이 보는 원장 화면 — **게이트가 화면의 내용을 태운다** (REQ-508·604·901).

Spec: specs/warranty/design/08-interfaces.md §3

⛔ **화면이 없던 동안 이 프로젝트의 문장은 `curl`을 아는 사람에게만 도착했다.**
   `executed`와 `improved`가 다른 칸이라는 것이 논지인데, 두 칸이 나란히 보이는 화면이
   없으면 그 논지는 읽는 사람에게 도착하지 않는다.

⚠️ **렌더러가 순수해서 여기서 태울 수 있다.** 소켓을 쥔 코드 안에 그리기를 두면
   *"화면이 옳은가"*를 물으려면 매번 포트를 열어야 한다.

여섯을 묻는다:
  ① 헤드라인에 `executed`와 `improved`가 **둘 다** 있고 서로 다른 값을 그리는가
  ② 비용의 **귀속**이 화면에 있는가 — 금액만 보이면 계산값인지 청구서인지 사라진다
  ③ 원장이 비었을 때 **빈 표를 조용히 그리지 않는가**
  ④ 사용자 문자열이 **이스케이프**되는가 (원장 값은 모델·API가 채운다)
  ⑤ `measured`가 있으면 그것을 보여 주되 `assumed`를 **덮지 않는가**
  ⑥ 롤백의 `False`와 **없음**이 구분되는가
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from warranty.ui import HEADLINE, ledger_rows, render_dashboard

REPORT = {
    "executed": 2,
    "improved": 0,
    "rolled_back": 1,
    "escalated": 0,
    "unverifiable": 1,
    "manual_required": 1,
    "model_decided": 1,
    "wasted_usd": "0.00150",
    "wasted_assumed_only": 2,
}


@dataclass(frozen=True)
class _Cost:
    amount_usd: Decimal


@dataclass(frozen=True)
class _Verdict:
    value: str


@dataclass(frozen=True)
class _Verification:
    verdict: _Verdict
    rationale: str = ""


@dataclass(frozen=True)
class _Rollback:
    performed: bool


@dataclass(frozen=True)
class _Method:
    value: str


@dataclass(frozen=True)
class _Attribution:
    method: _Method
    reason: str = ""


@dataclass(frozen=True)
class _Kind:
    value: str


@dataclass(frozen=True)
class _Status:
    value: str


@dataclass(frozen=True)
class _Entry:
    entry_id: str
    action_id: str
    kind: _Kind
    status: _Status
    attribution: _Attribution
    assumed: _Cost
    measured: _Cost | None = None
    verification: _Verification | None = None
    rollback: _Rollback | None = None
    decision: _Verification | None = None


def _entry(**over: object) -> _Entry:
    base: dict[str, object] = {
        "entry_id": "01m1abc",
        "action_id": "demo-target-00002-lss",
        "kind": _Kind("action"),
        "status": _Status("executed"),
        "attribution": _Attribution(_Method("resource_label")),
        "assumed": _Cost(Decimal("0.00150")),
    }
    base.update(over)
    return _Entry(**base)  # type: ignore[arg-type]


def _page(rows: list[dict[str, object]] | None = None) -> str:
    return render_dashboard(
        REPORT,
        rows if rows is not None else ledger_rows([_entry()]),
        day="2026-08-29",
        service="warranty-hack",
    )


def test_the_headline_puts_improved_next_to_executed() -> None:
    """① ★ **순서가 논지다.** 떨어뜨려 놓으면 둘이 다른 값이라는 것이 안 보인다.

    Verifies: REQ-508
    """
    keys = [key for key, _ in HEADLINE]
    assert keys.index("improved") == keys.index("executed") + 1

    page = _page()
    assert "Executed" in page and "Improved" in page
    # ⛔ 두 값이 실제로 화면에 다르게 그려진다 — 2와 0.
    assert ">2</p>" in page
    assert 'class="v zero">0</p>' in page


def test_the_page_shows_how_the_cost_is_attributed() -> None:
    """② ⛔ 금액만 보이면 그 수가 **계산값인지 청구서인지** 화면에서 사라진다.

    Verifies: REQ-504
    """
    page = _page()
    # ⛔ **표의 머리에서** 찾는다. 페이지 어디에나 있는지 물으면 아래 각주의
    #    "…<b>attribution</b>…" 문장이 그 단언을 **공짜로 통과시킨다** — 실제로 그랬고
    #    M-276이 그것을 잡았다(열을 지워도 초록이었다).
    header = page.split("<thead>")[1].split("</thead>")[0]
    assert "Attribution" in header, "비용의 귀속이 표의 열에 없다"
    assert "resource_label" in page
    assert "0.00150" in page


def test_an_empty_ledger_is_not_drawn_as_an_empty_table() -> None:
    """③ ⛔ *"조치가 없었다"*와 *"못 읽었다"*는 다르다.

    Verifies: REQ-508
    """
    page = _page(rows=[])
    assert "No ledger entries for this date" in page
    assert "<tbody>" not in page


def test_ledger_values_are_escaped() -> None:
    """④ ⚠️ 원장 값은 **모델과 GCP API가 채운다** — 우리가 쓴 문자열이 아니다.

    Verifies: REQ-604
    """
    rows = ledger_rows([_entry(action_id="<script>alert(1)</script>")])
    page = _page(rows)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page

    # ⚠️ **표지(`_tag`)를 지나는 값도 따로 태운다.** 위 단언은 `action_id` 칸만 태운다 —
    #    상태·판정·귀속은 다른 경로(`_tag`)로 그려지고, M-277이 그 경로의 이스케이프를
    #    지워도 **초록이었다.** 경로가 둘이면 가드도 둘이어야 한다.
    tagged = _page(ledger_rows([_entry(status=_Status("<img src=x onerror=1>"))]))
    assert "<img src=x" not in tagged
    assert "&lt;img src=x" in tagged


def test_a_measured_cost_is_shown_without_erasing_that_it_was_measured() -> None:
    """⑤ ⛔ **`assumed`를 덮지 않는다**(I-1). 청구서가 말한 값이 있으면 그것을 보여 준다.

    Verifies: REQ-505
    """
    rows = ledger_rows([_entry(measured=_Cost(Decimal("0.00220")))])
    assert rows[0]["amount_usd"] == "0.00220"
    # 원장의 `assumed`는 그대로다 — 화면이 고른 것이지 덮은 것이 아니다.
    assert _entry(measured=_Cost(Decimal("0.00220"))).assumed.amount_usd == Decimal("0.00150")


def test_a_rollback_that_did_not_happen_differs_from_no_rollback() -> None:
    """⑥ ⚠️ *"안 되돌렸다"*와 *"롤백이 없었다"*는 다르다 — 하나로 그리면 실패가 숨는다.

    Verifies: REQ-303
    """
    none_row = ledger_rows([_entry()])[0]
    false_row = ledger_rows([_entry(rollback=_Rollback(performed=False))])[0]
    true_row = ledger_rows([_entry(rollback=_Rollback(performed=True))])[0]
    assert none_row["rolled_back"] is None
    assert false_row["rolled_back"] == "false"
    assert true_row["rolled_back"] == "true"


def test_the_newest_entry_is_first() -> None:
    """⚠️ 원장은 시간순이고, 사람이 먼저 보는 것은 **방금 일어난 일**이다."""
    rows = ledger_rows([_entry(entry_id="old"), _entry(entry_id="new")])
    assert [r["entry_id"] for r in rows] == ["new", "old"]


def test_the_reason_reaches_the_screen() -> None:
    """⚠️ *"판단 근거는 로그가 아니라 응답에 있다"*(REQ-604)를 화면에서도 지킨다.

    Verifies: REQ-604
    """
    judged = ledger_rows(
        [_entry(verification=_Verification(_Verdict("not_recovered"), "latency traded for errors"))]
    )
    assert judged[0]["reason"] == "latency traded for errors"

    # 근거가 없으면 **귀속이 왜 `none`인지**가 그 자리에 온다 — 빈 칸으로 두지 않는다.
    unlabelled = ledger_rows(
        [_entry(attribution=_Attribution(_Method("none"), reason="no billable resource created"))]
    )
    assert unlabelled[0]["reason"] == "no billable resource created"
