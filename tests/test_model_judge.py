"""판정 어댑터 — 프롬프트 · 파싱 · **폴백** (T12-2 · REQ-204).

Spec: specs/warranty/design/06-agent-runtime.md §4 (REQ-204)

⚠️ 전부 오프라인이다. 이 파일이 통과해도 REQ-601은 만족되지 않는다 — 전송은 대역이고,
   스텁 위의 초록은 *"우리가 이 인터페이스를 이렇게 부른다"*까지만 말한다 (PRINCIPLES #3).

⛔ **이 파일이 지키는 문장은 하나다**: *못 읽은 모델 응답이 조용히 `recovered`가 되지
   않는다.* 그 반대편이 이 프로젝트가 겨냥하는 실패(조용한 성공) 그 자체이고, 하필
   모델이 불리는 구간은 정의상 **판단이 어려운 구간**(tolerance 안쪽)이다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import get_protocol_members

import pytest

from warranty.adapters.fakes import (
    FAKE_MODEL,
    FakeBudget,
    FakeRun,
    FrozenClock,
    InMemoryContracts,
    RecordingExecutor,
    ScriptedSignal,
    SeededIdGen,
)
from warranty.adapters.model_judge import (
    ALLOWED_VERDICTS,
    FALLBACK_PREFIX,
    FALLBACK_VERDICT,
    RAW_EXCERPT_CHARS,
    JudgeParseError,
    PromptedJudge,
    RawReply,
    Transport,
    build_prompt,
    fallback_rationale,
    parse_reply,
)
from warranty.domain.contract import (
    Criterion,
    CriterionMode,
    Direction,
    OperationalContract,
    ResourceRef,
    Reversibility,
    RollbackPlan,
    SignalSpec,
)
from warranty.domain.entry import EntryKind, InMemoryLedger, LedgerEntry
from warranty.domain.tokens import Rate, TokenPrices, TokenUsage
from warranty.domain.verification import DecidedBy, Measurement, Verdict, Verification
from warranty.ports import ModelPort
from warranty.usecases.meter import MeteredModel
from warranty.usecases.remediate import Remediator

FROZEN = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)  # REQ-802: 살아 있는 시계를 안 쓴다
AGENT = "warranty"
RESOURCE = ResourceRef("cloud_run_service", "demo-target", "us-central1")
PREVIOUS = "demo-target-00007-abc"

#: 테스트용 단가표. ⚠️ 실물 공시 단가가 아니다 (design 06§2 · PRINCIPLES #1).
PRICES = TokenPrices(
    {FAKE_MODEL: Rate(Decimal("1.00"), Decimal("10.00"))},
    source_note="test fixture — not a published rate",
)
USAGE = TokenUsage(FAKE_MODEL, 1000, 200)


def _m(value: str, points: int = 30) -> Measurement:
    return Measurement(Decimal(value), points)


class ScriptedTransport:
    """전송의 대역 — **본문을 정해 준다.** 실제 모델이 무엇을 낼지는 이 저장소가 모른다.

    ⚠️ `raises`가 있는 이유는 폴백의 **경계**를 태우기 위해서다: 못 읽은 답과 못 한 호출은
       다른 사건이고, 어댑터는 앞의 것만 판정으로 닫는다.
    """

    def __init__(
        self,
        text: str = '{"verdict": "recovered", "rationale": "latency came back"}',
        usage: TokenUsage | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._reply = RawReply(text, usage if usage is not None else USAGE)
        self._raises = raises
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> RawReply:
        self.prompts.append(prompt)
        if self._raises is not None:
            raise self._raises
        return self._reply


# ── ① 무엇을 물었나 (프롬프트) ─────────────────────────────────────────────


def test_req_204_the_prompt_carries_both_measurements_and_the_criterion() -> None:
    """Verifies: REQ-204

    바닥이자 본체다. ⚠️ 재측정이 프롬프트에 안 실리면 모델은 **기준선만 보고** 답하고,
    그 답은 여전히 문장으로 그럴듯하다 — 원장에서 구별이 안 된다.
    """
    prompt = build_prompt(_m("1.0", 30), _m("0.5", 12), "p95 must drop 50% ±10%")

    assert "value=1.0 points=30" in prompt, f"기준선이 프롬프트에 없다: {prompt!r}"
    assert "value=0.5 points=12" in prompt, f"재측정이 프롬프트에 없다: {prompt!r}"
    assert "p95 must drop 50% ±10%" in prompt, (
        "판정 기준이 프롬프트에 없다 — 조치가 아니라 계약이 성공 기준을 정한다(REQ-203)"
    )


def test_req_204_the_prompt_offers_only_the_two_verdicts_that_close_the_call() -> None:
    """Verifies: REQ-204

    ⛔ `ambiguous`를 선택지로 적으면 모델이 그대로 되돌려줄 수 있고, 그 값은
    `Verification`이 거부한다 — 판정이 **영영 안 닫힌다.** `unverifiable`도 마찬가지로
    답이 아니다: 모델은 정의상 **읽힌 값 둘을 받아서** 불린다.
    """
    assert ALLOWED_VERDICTS == (Verdict.RECOVERED, Verdict.NOT_RECOVERED)

    prompt = build_prompt(_m("1.0"), _m("0.5"), "criterion")
    assert str(Verdict.AMBIGUOUS) not in prompt, "프롬프트가 닫히지 않는 답을 선택지로 준다"
    assert str(Verdict.UNVERIFIABLE) not in prompt


def test_req_802_the_same_call_builds_the_same_prompt() -> None:
    """Verifies: REQ-802

    ⚠️ 프롬프트에 시각·난수·환경이 섞이면, 다르게 나온 답이 **모델의 답인지 우리 입력의
    차이인지** 구별되지 않는다.
    """
    args = (_m("1.0"), _m("0.5"), "criterion")
    assert build_prompt(*args) == build_prompt(*args)


# ── ② 답을 어떻게 읽나 (파싱) ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"verdict": "recovered", "rationale": "signal returned"}', Verdict.RECOVERED),
        ('{"verdict": "not_recovered", "rationale": "p95 rose 2.3x"}', Verdict.NOT_RECOVERED),
        ('{"verdict": "  RECOVERED ", "rationale": " padded "}', Verdict.RECOVERED),
    ],
)
def test_req_204_a_well_formed_reply_is_read_as_a_verdict(text: str, expected: Verdict) -> None:
    """Verifies: REQ-204"""
    verdict, rationale = parse_reply(text)
    assert verdict is expected
    assert rationale.strip() == rationale and rationale, "근거가 다듬어지지 않았다"


def test_req_204_a_fenced_reply_is_read_too() -> None:
    """Verifies: REQ-204

    ⛔ **지어낸 방어가 아니다** — 모델은 JSON을 코드펜스로 감싸는 쪽이 흔하다. 안 벗기면
    *정상 응답이 전부 폴백*으로 떨어지고, 원장은 모델이 판단한 적 없다고 말한다.
    그 실패는 조용하다: 루프는 계속 돌고 판정은 늘 보수적으로 옳아 보인다.
    """
    fenced = '```json\n{"verdict": "not_recovered", "rationale": "traded one symptom"}\n```'
    assert parse_reply(fenced) == (Verdict.NOT_RECOVERED, "traded one symptom")


#: 읽으면 안 되는 답들. ⚠️ 표로 두는 이유는 #9다 — 거절 사유가 늘면 **여기도 는다.**
BAD_REPLIES: dict[str, str] = {
    "JSON이 아니다": "recovered, because latency came back",
    "객체가 아니다": '["recovered", "reason"]',
    "verdict가 없다": '{"rationale": "no verdict here"}',
    "verdict가 문자열이 아니다": '{"verdict": 1, "rationale": "why"}',
    "★ ambiguous로 되돌려준다": '{"verdict": "ambiguous", "rationale": "hard to say"}',
    "unverifiable로 되돌려준다": '{"verdict": "unverifiable", "rationale": "no signal"}',
    "모르는 값이다": '{"verdict": "improved", "rationale": "why"}',
    "rationale이 없다": '{"verdict": "recovered"}',
    "★ rationale이 비었다": '{"verdict": "recovered", "rationale": "   "}',
}


@pytest.mark.parametrize("case", sorted(BAD_REPLIES), ids=lambda name: name)
def test_req_204_an_unreadable_reply_is_refused_not_guessed(case: str) -> None:
    """Verifies: REQ-204

    ⛔ **관대하게 읽으면** 애매한 응답이 판정이 되고, 그 판정은 `decided_by: model`을 달고
    원장에 남아 **모델이 그렇게 말한 것처럼** 읽힌다.
    ⚠️ 빈 근거를 통과시키면 `Verification`이 예외를 내고 조치 한 건이 통째로 날아간다.
    """
    with pytest.raises(JudgeParseError):
        parse_reply(BAD_REPLIES[case])


# ── ③ 못 읽으면 무엇으로 적나 (폴백) ───────────────────────────────────────


def test_req_204_a_parse_failure_falls_back_to_the_verdict_that_rolls_back() -> None:
    """Verifies: REQ-204, REQ-302

    ★ **이 파일의 본체다.** 파싱 실패가 `recovered`가 되면 못 읽은 응답 하나가 *"나아졌다"*가
    되고, 그 조치는 롤백 없이 남으며 리포트의 회복률만 오른다 — 조용한 성공 그 자체다.
    보수적인 값은 롤백을 여는 쪽이다.
    """
    assert FALLBACK_VERDICT is Verdict.NOT_RECOVERED

    judge = PromptedJudge(ScriptedTransport("not json at all"))
    reply = judge.judge_ambiguous(_m("1.0"), _m("0.5"), "criterion")

    assert reply.verdict is Verdict.NOT_RECOVERED
    assert reply.rationale.startswith(FALLBACK_PREFIX), (
        f"폴백이 모델의 판단과 구별되지 않는다: {reply.rationale!r}"
    )
    assert "not json at all" in reply.rationale, (
        "원장이 *무엇을* 못 읽었는지 안 말한다 — 그러면 고칠 곳을 아무도 못 찾는다"
    )


def test_req_204_the_fallback_rationale_is_never_empty_and_never_unbounded() -> None:
    """Verifies: REQ-204

    ⚠️ 비면 `Verification`이 *"모델이 판정했는데 근거가 없다"*로 예외를 낸다 — 그 예외는
    조치 한 건을 통째로 날린다. 반대편도 있다: 응답 전체가 원장 행에 실리면 안 된다.
    """
    assert fallback_rationale("reason", "")

    long_raw = "x" * (RAW_EXCERPT_CHARS * 3)
    excerpt = fallback_rationale("reason", long_raw)
    assert "x" * RAW_EXCERPT_CHARS in excerpt
    assert "x" * (RAW_EXCERPT_CHARS + 1) not in excerpt

    # ⛔ 값으로 태운다: 폴백 근거는 `Verification`이 받아 준다.
    Verification(
        verdict=FALLBACK_VERDICT,
        decided_by=DecidedBy.MODEL,
        baseline=_m("1.0"),
        after=_m("0.5"),
        rationale=fallback_rationale("reason", ""),
    )


def test_req_603_a_parse_failure_still_reports_what_the_call_spent() -> None:
    """Verifies: REQ-603

    ⚠️ 답을 못 읽었어도 **토큰은 나갔다.** 여기서 사용량을 버리거나 0으로 지어내면 원장에
    *"계량했는데 공짜였다"*는 행이 남고, 그건 *"얼마인지 모른다"*와 다른 문장이다(#2).
    """
    judge = PromptedJudge(ScriptedTransport("not json at all", usage=USAGE))
    assert judge.judge_ambiguous(_m("1.0"), _m("0.5"), "criterion").usage == USAGE


def test_req_603_a_transport_failure_is_not_swallowed() -> None:
    """Verifies: REQ-603

    ⛔ 폴백은 *"답은 왔는데 못 읽었다"* 전용이다. 호출이 예외로 끝나면 **얼마 썼는지
    모른다** — 그것을 판정으로 닫으면 사용량을 지어내야 하고, 그 지어냄이 #2가 금지하는
    조용한 0이다. 예외는 올라가고 `MeteredModel`의 `finally`가 `FAILED` 행을 남긴다.
    """
    boom = TimeoutError("transport died")
    judge = PromptedJudge(ScriptedTransport(raises=boom))
    with pytest.raises(TimeoutError):
        judge.judge_ambiguous(_m("1.0"), _m("0.5"), "criterion")


#: `ModelPort`의 메서드마다 이 어댑터를 태우는 자리. ⚠️ 포트에 메서드가 늘면 **여기도
#: 늘어야 한다** — 안 늘면 새 호출은 프롬프트도 폴백도 없이 실물로 나간다 (#9).
PORT_EXERCISES: frozenset[str] = frozenset({"judge_ambiguous"})


def test_req_603_the_adapter_answers_every_method_the_port_declares() -> None:
    """Verifies: REQ-603

    ★ #9 — 형제 집합은 세는 순간 전부 센다. `MeteredModel`이 같은 규칙을 이미 쓴다.
    """
    assert get_protocol_members(ModelPort) == PORT_EXERCISES, (
        "`ModelPort`의 메서드와 이 어댑터의 태우는 자리가 어긋났다"
    )
    for name in PORT_EXERCISES:
        assert callable(getattr(PromptedJudge(ScriptedTransport()), name))


def test_the_adapter_is_a_model_port() -> None:
    """⚠️ 판정은 mypy가 한다 — 아래 한 줄이 구조적 적합성을 게이트에 건다."""

    def _accepts(port: ModelPort) -> ModelPort:
        return port

    assert _accepts(PromptedJudge(ScriptedTransport())) is not None


# ── ④ 근거가 **원장 항목에** 실리는가 (T12-2의 done 기준) ──────────────────


def _contract() -> OperationalContract:
    return OperationalContract(
        contract_id="c1",
        resource=RESOURCE,
        health_signal=SignalSpec("run.googleapis.com/request_latencies", "demo-target", "P95", 120),
        recovery_criterion=Criterion(
            Direction.DECREASE, Decimal("0.5"), CriterionMode.RELATIVE, Decimal("0.1")
        ),
        rollback_plan=RollbackPlan(PREVIOUS),
        reversibility=Reversibility.REVERSIBLE,
        provisioned_at=FROZEN,
        provisioned_by="e0",
    )


def _remediate(transport: ScriptedTransport) -> tuple[LedgerEntry, InMemoryLedger]:
    """★ **실제 조립대로** 물린다: 전송 → `PromptedJudge` → `MeteredModel` → `Remediator`.

    ⚠️ 신호 셋은 애매한 경우다(0.5 감소 · 기준 0.5 · tolerance 0.1) — 여기서만 모델이 불린다.
    ⚠️ id 생성기는 **하나다.** 한 원장에 쓰는 경로 둘이 각자 만들면 id가 겹친다 (I-5).
    """
    ledger = InMemoryLedger()
    ids = SeededIdGen("judge")
    contracts = InMemoryContracts()
    contracts.put(_contract())
    entry = Remediator(
        contracts=contracts,
        signals=ScriptedSignal([_m("1.0"), _m("0.5"), _m("1.0")]),
        executor=RecordingExecutor(),
        run=FakeRun(),
        budgets=FakeBudget(Decimal("0.50")),
        ledger=ledger,
        clock=FrozenClock(FROZEN.isoformat()),
        ids=ids,
        judge=MeteredModel(
            model=PromptedJudge(transport),
            ledger=ledger,
            clock=FrozenClock(FROZEN.isoformat()),
            ids=ids,
            prices=PRICES,
            agent_id=AGENT,
        ),
    ).remediate(
        agent_id=AGENT,
        action_id="shift_traffic",
        resource=RESOURCE,
        projected_usd=Decimal("0.01"),
    )
    return entry, ledger


def test_req_204_the_model_rationale_lands_in_the_ledger_entry() -> None:
    """Verifies: REQ-204, REQ-604

    ★ T12-2의 done 기준이다. **근거가 원장에 안 남으면 그 판정은 없는 것과 같다.**
    ⚠️ 프롬프트가 실제로 나갔는지도 함께 묻는다 — 안 나갔는데 근거가 있으면 그건 우리가
    지어낸 문장이다.
    """
    transport = ScriptedTransport(
        '{"verdict": "not_recovered", "rationale": "error rate fell but p95 rose 2.3x"}'
    )
    entry, ledger = _remediate(transport)

    assert len(transport.prompts) == 1, "모델이 안 불렸다 — 이 테스트는 아무것도 안 묻고 있다"
    assert entry.verification is not None
    assert entry.verification.decided_by is DecidedBy.MODEL
    assert entry.verification.rationale == "error rate fell but p95 rose 2.3x"
    assert entry.improved is False
    assert entry.rolled_back is True

    calls = [row for row in ledger.all_entries() if row.kind is EntryKind.MODEL_CALL]
    assert len(calls) == 1, "모델 호출이 원장에 안 남았다 (REQ-603)"
    assert calls[0].assumed.amount_usd > 0, "계량한 행이 조용한 0을 적었다"


def test_req_204_an_unreadable_reply_lands_a_rationale_too_and_rolls_back() -> None:
    """Verifies: REQ-204, REQ-302

    ⛔ 폴백 경로도 **원장에 문장을 남긴다.** 남기지 않으면 `Verification`이 예외를 내고
    조치가 통째로 날아가며, 남기더라도 모델의 판단과 구별되지 않으면 그 원장은 *"모델이
    그렇게 판단했다"*고 거짓말한다.
    """
    entry, _ = _remediate(ScriptedTransport("I think it got better?"))

    assert entry.verification is not None
    assert entry.verification.decided_by is DecidedBy.MODEL
    assert entry.verification.verdict is Verdict.NOT_RECOVERED
    assert entry.verification.rationale.startswith(FALLBACK_PREFIX)
    assert entry.rolled_back is True, "못 읽은 응답이 롤백을 건너뛰었다"


def test_a_transport_wired_into_the_gate_is_always_a_double() -> None:
    """⛔ REQ-801 — 게이트가 오프라인이려면 이 자리가 실물로 안 채워져야 한다.

    ⚠️ 이 파일은 `Transport`를 **프로토콜로만** 안다. 실물 구현이 생기면 그것은
    `google-*`를 임포트할 것이고, 그 임포트는 게이트에 없다(T2-1이 소유한다).
    """
    assert isinstance(PromptedJudge(ScriptedTransport()).transport, ScriptedTransport)
    assert get_protocol_members(Transport) == {"complete"}
