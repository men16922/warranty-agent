"""원장 행 하나를 응답 한 덩어리로 — ★ **화면에 안 보이면 없는 것과 같다** (REQ-604).

Spec: specs/warranty/design/08-interfaces.md §3.1

⛔ **이 모듈이 존재하는 이유는 4분이다.** 판정의 근거(`rule`), 검증의 근거(`rationale`),
   되돌렸다는 **증거**(`verified_traffic`)가 로그에만 있으면 심사자는 그것을 못 본다.
   그래서 셋은 응답의 필수 칸이고, 빠지면 게이트가 red다.

⚠️ **`executed`·`improved`·`rolled_back`은 셋이 따로 나간다** (REQ-502). 하나로 뭉치면
   *"실행했다"*가 *"나아졌다"*로 읽히고, 그 오해가 이 프로젝트가 반대하는 그 문장이다.
   셋은 원장 행에서 **유도된다** — 여기서 다시 계산하지 않는다(가드 G8과 같은 계열).

⚠️ 돈은 **문자열로** 낸다. JSON의 수치는 double이고, `0.0021`을 그 타입으로 내보내면
   화면에 뜨는 값이 청구서와 달라진다 (REQ-503·505 · design 08§2.1과 같은 규칙).
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from warranty.domain.cost import CostFact
from warranty.domain.entry import LedgerEntry
from warranty.domain.verification import Measurement

#: 응답이 반드시 갖는 칸. ⚠️ **값이다** — 게이트가 이 목록으로 묻는다. 여기서 이름을
#: 지우면 그 칸은 조용히 사라지고, 사라진 것은 심사자에게 *"없는 기능"*으로 보인다.
REQUIRED_KEYS: tuple[str, ...] = (
    "entry_id",
    "status",
    "decision",
    "verification",
    "rollback",
    "executed",
    "improved",
    "rolled_back",
    "assumed",
)

#: ★ 따로 나가야 하는 셋 (REQ-502).
SEPARATE_OUTCOMES: tuple[str, ...] = ("executed", "improved", "rolled_back")


class WireError(ValueError):
    """응답으로 낼 수 없는 값이다."""


def _money(value: Decimal) -> str:
    """돈 하나. **문자열이다** — 자릿수까지 그대로 보인다."""
    return str(value)


def _amounts(values: Mapping[str, Decimal]) -> dict[str, str]:
    return {name: _money(amount) for name, amount in values.items()}


def _measurement(measured: Measurement | None) -> dict[str, Any] | None:
    """측정 하나. ⚠️ **`points`를 함께 낸다** — 값 하나만 보이면 그 값이 30개 점의 p95인지
    한 점인지 구분이 안 되고, 빈 창(`points=0`)이 *"0ms"*로 읽힌다 (REQ-205)."""
    if measured is None:
        return None
    return {
        "value": None if measured.value is None else _money(measured.value),
        "points": measured.points,
    }


def _cost(fact: CostFact) -> dict[str, Any]:
    """비용 사실 하나 — **수량과 단가와 함께** 낸다 (REQ-503).

    ⚠️ 총액만 내면 그 숫자가 어떻게 나왔는지 아무도 못 묻는다. 못 묻는 숫자는
       청구서와 어긋나도 어긋난 줄을 모른다.
    """
    return {
        "amount_usd": _money(fact.amount_usd),
        "basis": fact.basis.value,
        "priced_at": fact.priced_at.isoformat(),
        "inputs": _amounts(fact.inputs),
        "unit_prices": _amounts(fact.unit_prices),
    }


def remediate_response(entry: LedgerEntry) -> dict[str, Any]:
    """원장 행 하나 → design 08§3.1의 응답.

    ⛔ 없는 것은 **`null`로 낸다, 키째 빼지 않는다.** 키가 사라지면 *"검증을 안 했다"*와
       *"검증 칸이 없는 응답 모양"*이 구분되지 않고, 후자로 읽히는 순간 REQ-604는
       *"어떤 때는 보이는"* 약속이 된다.
    """
    decision = entry.decision
    verification = entry.verification
    rollback = entry.rollback

    body: dict[str, Any] = {
        "entry_id": entry.entry_id,
        "status": entry.status.value,
        "decision": None
        if decision is None
        else {
            "verdict": decision.verdict.value,
            # ★ 판정의 이유. 데모에서 *"왜 막혔죠?"*에 답하는 칸이다.
            "rule": decision.rule,
            "reversibility": decision.reversibility.value,
            "verifiable": decision.verifiable,
            "destructive": decision.destructive,
            "projected_usd": _money(decision.projected_usd),
            "headroom_usd": _money(decision.headroom_usd),
        },
        "verification": None
        if verification is None
        else {
            "verdict": verification.verdict.value,
            "decided_by": verification.decided_by.value,
            # ★ 모델이 판정했으면 **그 문장이 여기 있다** (REQ-204).
            "rationale": verification.rationale,
            "baseline": _measurement(verification.baseline),
            "after": _measurement(verification.after),
        },
        "rollback": None
        if rollback is None
        else {
            "performed": rollback.performed,
            # ★ 주장이 아니라 **측정이다** — 전환 후 다시 읽은 배분이다 (REQ-302).
            "verified_traffic": None
            if rollback.verified_traffic is None
            else dict(rollback.verified_traffic),
            "signal_restored": rollback.signal_restored,
            "reason": rollback.reason,
        },
        # ★ 셋이 따로 있다 (REQ-502). 유도값이고, 여기서 다시 계산하지 않는다.
        "executed": entry.executed,
        "improved": entry.improved,
        "rolled_back": entry.rolled_back,
        "assumed": _cost(entry.assumed),
        # ⚠️ 실측은 **`assumed`를 덮지 않고 옆칸으로** 나간다 (REQ-505 · I-1).
        "measured": None if entry.measured is None else _cost(entry.measured),
        "contract_id": entry.contract_id,
    }

    missing = [key for key in REQUIRED_KEYS if key not in body]
    if missing:
        raise WireError(f"응답에 빠진 칸이 있다: {missing} — 화면에 안 보이면 없는 것과 같다")
    return body
