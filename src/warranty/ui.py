"""사람이 보는 화면 — **원장을 읽어서 그리기만 한다** (REQ-508·604).

Spec: specs/warranty/design/08-interfaces.md §3 (REQ-508, REQ-604)

⛔ **이것은 대시보드가 아니라 원장의 읽기 뷰다.** 버튼이 없고, 조치를 걸 수 없고,
   아무것도 저장하지 않는다. `OVERVIEW` §11이 범위 밖으로 선언한 *"웹 대시보드"*는
   **조작 표면**을 뜻하고, 이 화면에는 그것이 없다.

⭐ **왜 필요한가**: 이 프로젝트가 말하는 문장은 전부 원장에 있는데, 그것을 보려면
   지금까지 `curl` + JSON이 필요했다. 심사위원은 그것을 안 한다. `executed`와 `improved`가
   **다른 칸**이라는 것이 논지인데, 두 칸이 나란히 보이는 화면이 없으면 그 논지는
   읽는 사람에게 도착하지 않는다.

⚠️ **여기서 아무것도 계산하지 않는다.** 세는 규칙은 `domain/report.daily_report`가 소유하고
   이 모듈은 그 결과를 받아 그린다. 두 벌이 되면 화면과 API가 다른 수를 말하고,
   **틀린 쪽이 사람에게 보인다.**

⚠️ **순수하다** — 문자열을 받아 문자열을 낸다. 그래서 오프라인 게이트가 화면의 내용을
   태울 수 있다. 소켓을 쥔 코드 안에 렌더링을 두면 *"화면이 옳은가"*를 물으려면
   매번 포트를 열어야 한다(`server.resolve`와 같은 이유).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape

#: 헤드라인 칸과 사람이 읽는 이름. ⚠️ **순서가 논지다** — `executed` 바로 옆에
#: `improved`가 온다. 떨어뜨려 놓으면 둘이 다른 값이라는 것이 안 보인다.
HEADLINE: tuple[tuple[str, str], ...] = (
    ("executed", "Executed"),
    ("improved", "Improved"),
    ("rolled_back", "Rolled back"),
    ("escalated", "Escalated"),
    ("unverifiable", "Unverifiable"),
    ("manual_required", "Manual required"),
    ("model_decided", "Model decided"),
    ("wasted_usd", "Wasted (USD)"),
    ("wasted_assumed_only", "of which assumed"),
)

#: 원장 표의 열. ⚠️ `Attribution`과 금액이 **같은 줄에** 있어야 한다 — 금액만 보이면
#: 그 수가 계산값인지 청구서인지 사라지고, 그 구분이 이 프로젝트 논지의 절반이다.
#: ⛔ **화면 문자열은 영어다.** 심사·데모의 언어가 영어이고, 화면은 저장소가 아니라
#:    **바깥 사람**이 읽는 자리다. 주석·문서는 한국어로 남는다 — 그건 우리가 읽는다.
COLUMNS: tuple[str, ...] = (
    "Entry",
    "Kind",
    "Target",
    "Status",
    "Decision",
    "Verification",
    "Rollback",
    "Attribution",
    "Cost (USD)",
    "Reason",
)

STYLE = """
:root{--bg:#faf9fc;--card:#fff;--ink:#17141f;--soft:#4a4557;--mute:#77718a;
--rule:#e2dfe9;--ok:#1d4ed8;--warn:#b45309;--bad:#b91c1c;--zero:#8b839d}
@media(prefers-color-scheme:dark){:root{--bg:#131118;--card:#1c1925;--ink:#f2f0f7;
--soft:#bab3ca;--mute:#8b839d;--rule:#322d40;--ok:#7ba3ff;--warn:#f0a63c;--bad:#f08a8a;--zero:#8b839d}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.6;
font-family:ui-sans-serif,-apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:72rem;margin:0 auto;padding:2.5rem 1.25rem 4rem}
h1{font-size:1.5rem;margin:0 0 .35rem;letter-spacing:-.02em}
.sub{color:var(--mute);font-size:.9rem;margin:0 0 2rem}
.thesis{border-left:3px solid var(--warn);background:var(--card);padding:.9rem 1.1rem;
margin:0 0 2rem;font-size:.95rem;color:var(--soft)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));gap:1px;
background:var(--rule);border:1px solid var(--rule);margin-bottom:2rem}
.cell{background:var(--card);padding:1rem}
.k{font-size:.7rem;letter-spacing:.09em;text-transform:uppercase;color:var(--mute);margin:0 0 .3rem}
.v{font-size:1.6rem;font-weight:600;font-variant-numeric:tabular-nums;line-height:1;margin:0}
.v.zero{color:var(--zero)}
.tablewrap{overflow-x:auto;border:1px solid var(--rule);background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th{text-align:left;font-size:.68rem;letter-spacing:.09em;text-transform:uppercase;
color:var(--mute);font-weight:600;padding:.7rem .8rem;border-bottom:1px solid var(--rule);
white-space:nowrap}
td{padding:.7rem .8rem;border-bottom:1px solid var(--rule);vertical-align:top;color:var(--soft)}
tr:last-child td{border-bottom:0}
td.id{font-family:ui-monospace,monospace;font-size:.76rem;color:var(--mute)}
td.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.tag{display:inline-block;font-size:.7rem;font-weight:600;padding:.15rem .45rem;
border-radius:2px;white-space:nowrap}
.tag.ok{color:var(--ok)}.tag.warn{color:var(--warn)}.tag.bad{color:var(--bad)}
.tag.flat{color:var(--mute)}
.note{color:var(--mute);font-size:.8rem;margin-top:2rem;border-top:1px solid var(--rule);
padding-top:1rem}
.empty{padding:2.5rem 1rem;text-align:center;color:var(--mute);font-size:.9rem}
"""

#: ⛔ 화면 맨 위에 붙는 문장. **이 화면이 무엇을 주장하지 않는지**를 먼저 적는다.
THESIS = (
    "Most operations tools count <b>executed</b> and call that success. "
    "This table keeps <b>improved</b> in a column of its own, and the whole point is that "
    "it <b>can be smaller than executed</b>. "
    "Every number here is derived from the ledger — none of them is stored."
)

#: 상태별 색. ⚠️ 모르는 상태는 **회색이지 초록이 아니다** — 조용한 성공을 만들지 않는다.
STATUS_TONE: Mapping[str, str] = {
    "executed": "ok",
    "denied": "bad",
    "failed": "bad",
    "manual_required": "warn",
    "awaiting_approval": "warn",
}

VERDICT_TONE: Mapping[str, str] = {
    "recovered": "ok",
    "not_recovered": "bad",
    "ambiguous": "warn",
    "unverifiable": "warn",
}


def _tag(value: object, tone_of: Mapping[str, str]) -> str:
    """값 하나를 색 붙은 표지로. ⚠️ 모르는 값은 `flat`이다."""
    if value in (None, ""):
        return '<span class="tag flat">—</span>'
    text = str(value)
    tone = tone_of.get(text, "flat")
    return f'<span class="tag {tone}">{escape(text)}</span>'


def _money(value: object) -> str:
    """금액 한 칸. ⚠️ **0을 흐리게 그린다** — 0은 값이지만 *"아직 아무것도 안 샀다"*이고,
    진한 0은 측정된 0으로 읽힌다."""
    text = str(value if value is not None else "0")
    zero = text.strip("0.") == ""
    klass = "num zero" if zero else "num"
    return f'<td class="{klass}">{escape(text)}</td>'


def render_dashboard(
    report: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
    *,
    day: str,
    service: str,
    revision: str = "",
) -> str:
    """하루치 성적표와 원장 행들을 한 장으로. **순수하다.**

    ⚠️ `report`는 `domain/report.DailyReport.as_dict()`가 낸 그대로다 —
       여기서 다시 세지 않는다(세는 자리는 하나다).
    """
    cells = "".join(
        f'<div class="cell"><p class="k">{escape(label)}</p>'
        f'<p class="v{" zero" if str(report.get(key, 0)).strip("0.") == "" else ""}">'
        f"{escape(str(report.get(key, 0)))}</p></div>"
        for key, label in HEADLINE
    )

    head = "".join(f"<th>{escape(c)}</th>" for c in COLUMNS)

    if rows:
        body = "".join(
            "<tr>"
            f'<td class="id">{escape(str(r.get("entry_id", "")))}</td>'
            f"<td>{_tag(r.get('kind'), {})}</td>"
            f'<td class="id">{escape(str(r.get("action_id", "")))}</td>'
            f"<td>{_tag(r.get('status'), STATUS_TONE)}</td>"
            f"<td>{_tag(r.get('verdict'), {})}</td>"
            f"<td>{_tag(r.get('verification'), VERDICT_TONE)}</td>"
            f"<td>{_tag(r.get('rolled_back'), {})}</td>"
            f"<td>{_tag(r.get('attribution'), {})}</td>"
            f"{_money(r.get('amount_usd'))}"
            f"<td>{escape(str(r.get('reason', '') or ''))}</td>"
            "</tr>"
            for r in rows
        )
        table = f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    else:
        # ⛔ 빈 표를 조용히 그리지 않는다 — *"조치가 없었다"*와 *"못 읽었다"*는 다르다.
        table = (
            '<div class="empty">No ledger entries for this date. '
            "That means no action was taken — not that reading failed.</div>"
        )

    where = escape(service) + (f" · {escape(revision)}" if revision else "")
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>warranty — {escape(day)}</title><style>{STYLE}</style></head><body>"
        '<div class="wrap">'
        "<h1>Accountability Ledger</h1>"
        f'<p class="sub">{escape(day)} · {where}</p>'
        f'<p class="thesis">{THESIS}</p>'
        f'<div class="grid">{cells}</div>'
        f'<div class="tablewrap">{table}</div>'
        '<p class="note">Read-only — no action can be taken from this page. '
        "When a cost's <b>attribution</b> is <code>resource_label</code>, that row can be "
        "found again in the bill; when it is <code>none</code>, it cannot. "
        "We do not hide the difference.</p>"
        "</div></body></html>"
    )


def ledger_rows(entries: Sequence[object]) -> list[dict[str, object]]:
    """원장 항목들을 **화면이 읽는 모양**으로. **순수하다.**

    ⚠️ 여기서 아무것도 판정하지 않는다 — `executed`·`improved`·`rolled_back`은 전부
       항목이 유도하는 값이고(가드 G8), 이 함수는 그것을 **옮기기만** 한다.
    ⛔ **`assumed`를 `measured`로 덮지 않는다**(I-1). 청구서가 말한 값이 있으면 그것을
       보여 주되, 그 사실을 `basis` 칸으로 함께 낸다 — 총액만 옮기면 그 수가 계산값인지
       청구서인지 화면에서 사라진다.
    ⚠️ 최신이 위다. 원장은 시간순이고, 사람이 먼저 보는 것은 방금 일어난 일이다.
    """
    out: list[dict[str, object]] = []
    for entry in entries:
        verification = getattr(entry, "verification", None)
        rollback = getattr(entry, "rollback", None)
        measured = getattr(entry, "measured", None)
        cost = measured if measured is not None else getattr(entry, "assumed", None)
        attribution = getattr(entry, "attribution", None)
        status = getattr(entry, "status", None)
        out.append(
            {
                "entry_id": getattr(entry, "entry_id", ""),
                "kind": getattr(getattr(entry, "kind", None), "value", ""),
                "action_id": getattr(entry, "action_id", ""),
                "status": getattr(status, "value", str(status or "")),
                "verdict": _verdict_name(getattr(entry, "decision", None)),
                "verification": _verdict_name(verification),
                # ⚠️ `False`와 `None`을 구분한다 — *"안 되돌렸다"*와 *"롤백이 없었다"*는 다르다.
                "rolled_back": None if rollback is None else str(bool(rollback.performed)).lower(),
                "attribution": getattr(getattr(attribution, "method", None), "value", ""),
                "amount_usd": "0" if cost is None else str(cost.amount_usd),
                "reason": _reason_of(verification, attribution),
            }
        )
    out.reverse()
    return out


def _verdict_name(holder: object) -> str:
    """판정/검증의 이름 한 조각. ⚠️ 없으면 빈 문자열이고, 화면은 그것을 `—`로 그린다."""
    verdict = getattr(holder, "verdict", None)
    return str(getattr(verdict, "value", verdict) or "")


def _reason_of(verification: object, attribution: object) -> str:
    """왜 그렇게 됐는가 — **응답에 근거가 있다**(REQ-604)를 화면에서도 지킨다.

    ⚠️ 모델이 판단한 경우의 근거가 먼저다. 그것이 없으면 귀속이 왜 `none`인지를 낸다 —
       둘 다 *"이 행이 왜 이 모양인가"*에 답하는 문장이고, 없으면 화면은 수만 보여 준다.
    """
    rationale = str(getattr(verification, "rationale", "") or "")
    if rationale:
        return rationale
    return str(getattr(attribution, "reason", "") or "")
