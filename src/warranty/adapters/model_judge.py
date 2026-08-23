"""애매한 판정을 모델에 넘기는 어댑터 — **프롬프트 · 파싱 · 폴백** (T12-2 · REQ-204).

Spec: specs/warranty/design/06-agent-runtime.md §4 (REQ-204, REQ-604)
      specs/warranty/design/02-verification.md §3.1 (REQ-204)

★ **"이거 어디가 에이전트냐"에 답하는 자리다.** 여기까지 이 저장소의 `ModelPort` 구현은
  대역 하나뿐이었고(`ScriptedModel`), 원장은 늘 `decided_by: rule`이었다. 규칙이 못 닫는
  판정을 모델이 닫고 **그 문장이 근거로 남는 것**이 REQ-204이고, 이 파일이 그 절반이다.

⛔ **오프라인 절반이다.** 전송(`Transport`)은 포트 뒤에 있고 게이트는 그 자리를 절대
   실물로 안 채운다(REQ-801). 여기서 태울 수 있는 것은 셋이다 — 무엇을 물었나(프롬프트),
   답을 어떻게 읽나(파싱), **못 읽으면 무엇으로 적나(폴백).**
   실물 호출은 REQ-601이고 그것은 여전히 `TODO`다 (docs/PRINCIPLES.md #3).

⚠️ **파싱 실패를 조용히 `recovered`로 접지 않는다.** 접으면 못 읽은 응답 하나가
   *"나아졌다"*가 되고, 그 조치는 롤백 없이 남으며 리포트의 회복률만 올라간다 —
   이 프로젝트가 겨냥하는 실패(조용한 성공) **그 자체**다. 보수적인 값은
   `not_recovered`다: 그것은 롤백을 열고(REQ-302), 원장에 `improved=false`로 남는다.

⚠️ **전송 실패는 안 삼킨다.** 폴백은 *"답은 왔는데 못 읽었다"* 전용이다. 호출이 예외로
   끝나면 **얼마 썼는지 모른다** — 거기서 사용량 0을 지어내면 원장에 *"계량했는데
   공짜였다"*는 행이 남고, 그건 *"얼마인지 모른다"*와 다른 문장이다(#2). 예외는 그대로
   올라가고 `MeteredModel`의 `finally`가 사용량 없는 `FAILED` 행을 남긴다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from warranty.domain.tokens import ModelReply, TokenUsage
from warranty.domain.verification import Measurement, Verdict

#: ⛔ 모델이 낼 수 있는 판정 **전부**. REQ-204의 `Then`이 이 둘을 적는다.
#: `AMBIGUOUS`는 규칙이 이미 낸 답이라 되돌려받으면 판정이 안 닫히고(`Verification`이
#: 거부한다), `UNVERIFIABLE`은 신호를 못 읽었다는 뜻인데 모델은 정의상 **읽힌 값 둘을
#: 받아서** 불린다 — 넷 중 둘은 답이 아니라 **호출이 성립하지 않았다는 뜻**이다.
ALLOWED_VERDICTS: tuple[Verdict, ...] = (Verdict.RECOVERED, Verdict.NOT_RECOVERED)

#: ⛔ 못 읽은 응답이 받는 판정. **보수적이라는 것은 롤백을 연다는 뜻이다** (REQ-302).
FALLBACK_VERDICT = Verdict.NOT_RECOVERED

#: 폴백 근거의 머리. ⚠️ 원장에서 *"모델이 그렇게 판단했다"*와 *"모델 답을 못 읽었다"*가
#: 구별돼야 한다 — 둘 다 `decided_by: model`로 남기 때문이다.
FALLBACK_PREFIX = "model reply unreadable"

#: 폴백 근거에 싣는 원문 발췌 길이. ⚠️ 발췌가 없으면 원장은 *"못 읽었다"*고만 말하고
#: **무엇을 못 읽었는지는 사라진다** — 그러면 고칠 곳을 아무도 못 찾는다.
#: 길이를 두는 이유는 반대편이다: 모델 응답 전체가 원장 행에 실리면 안 된다.
RAW_EXCERPT_CHARS = 200

FENCE = "```"

PROMPT_TEMPLATE = """\
A remediation action ran against a service. Decide whether the service recovered.

recovery criterion : {criterion}
baseline           : {baseline}
after              : {after}

The rule-based classifier could not close this: the change landed inside the
criterion's tolerance. That is why you were called.

Answer with one JSON object and nothing else:

  {{"verdict": "<{verdicts}>", "rationale": "<one sentence, why>"}}

- "verdict" must be one of: {verdicts}. Nothing else is a legal answer.
- "rationale" must not be empty. A verdict with no reason is not a verification.
"""


class JudgeParseError(ValueError):
    """모델의 답을 판정으로 읽을 수 없다. **호출이 실패한 것과 다르다.**"""


@dataclass(frozen=True, slots=True)
class RawReply:
    """전송이 돌려주는 것 — **본문과 사용량이 함께 온다** (REQ-603).

    ⚠️ 사용량을 선택 값으로 두면 계량이 추정의 추정이 된다(`ModelReply`와 같은 이유).
    """

    text: str
    usage: TokenUsage


class Transport(Protocol):
    """★ 모델 **전송**. ⛔ 이 뒤가 네트워크다.

    ⚠️ 이 자리가 포트인 이유는 계층 취향이 아니라 REQ-801이다 — 게이트가 오프라인이려면
       프롬프트·파싱·폴백을 태우는 동안 **아무것도 안 나가야** 한다.
    """

    def complete(self, prompt: str) -> RawReply: ...


def _render(measurement: Measurement) -> str:
    """측정 하나를 모델이 읽을 한 줄로. ⚠️ 빈 창을 `0`으로 적지 않는다 — *"0이었다"*와
    *"안 왔다"*는 다른 문장이고, 후자는 애초에 `unverifiable`이다 (design 02§4)."""
    value = "none" if measurement.value is None else f"{measurement.value}"
    return f"value={value} points={measurement.points}"


def build_prompt(baseline: Measurement, after: Measurement, criterion_note: str) -> str:
    """모델에게 실제로 물어보는 문장.

    ⚠️ **결정론적이다** (REQ-802) — 시각도, 난수도, 환경도 안 들어간다. 같은 판정 요청은
       같은 프롬프트를 만든다. 그래야 다르게 나온 답이 모델의 답인지 우리 입력의 차이인지
       구별된다.
    ⚠️ 프롬프트는 `AMBIGUOUS`를 **선택지로 적지 않는다.** 적으면 모델이 그대로 되돌려줄 수
       있고, 그 값은 `Verification`이 거부한다 — 판정이 영영 안 닫힌다.
    """
    return PROMPT_TEMPLATE.format(
        criterion=criterion_note,
        baseline=_render(baseline),
        after=_render(after),
        verdicts=" | ".join(str(verdict) for verdict in ALLOWED_VERDICTS),
    )


def _strip_fence(text: str) -> str:
    """```json … ``` 을 벗긴다.

    ⚠️ 지어낸 방어가 아니다 — 모델은 JSON을 코드펜스로 감싸 답하는 쪽이 흔하다. 안 벗기면
       **정상 응답이 전부 폴백으로 떨어지고**, 원장은 모델이 판단한 적 없다고 말한다.
       그 실패는 조용하다: 루프는 계속 돌고 판정은 늘 보수적으로 옳아 보인다.
    """
    stripped = text.strip()
    if not stripped.startswith(FENCE) or not stripped.endswith(FENCE):
        return stripped
    inner = stripped[len(FENCE) : -len(FENCE)]
    head, _, rest = inner.partition("\n")
    # ```json 처럼 언어 표지가 첫 줄에 붙는다. 첫 줄이 표지가 아니면 본문이므로 안 버린다.
    return (rest if head.strip().isalpha() else inner).strip()


def parse_reply(text: str) -> tuple[Verdict, str]:
    """모델의 답을 `(verdict, rationale)`로 읽는다. 못 읽으면 `JudgeParseError`.

    ⛔ **관대하게 읽지 않는다.** 여기서 관대해지면 애매한 응답이 판정이 되고, 그 판정은
       `decided_by: model`을 달고 원장에 남아 **모델이 그렇게 말한 것처럼** 읽힌다.
    """
    payload = _load(_strip_fence(text))
    if not isinstance(payload, dict):
        raise JudgeParseError(f"JSON 객체가 아니다: {type(payload).__name__}")

    raw_verdict = payload.get("verdict")
    if not isinstance(raw_verdict, str):
        raise JudgeParseError("verdict가 없거나 문자열이 아니다")
    allowed = {str(verdict) for verdict in ALLOWED_VERDICTS}
    if raw_verdict.strip().lower() not in allowed:
        raise JudgeParseError(f"허용되지 않는 verdict다: {raw_verdict!r} (허용: {sorted(allowed)})")

    rationale = payload.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise JudgeParseError("rationale이 없거나 비었다 — 근거 없는 판정은 판정이 아니다")

    return Verdict(raw_verdict.strip().lower()), rationale.strip()


def _load(text: str) -> object:
    try:
        return json.loads(text)
    except ValueError as exc:
        raise JudgeParseError(f"JSON이 아니다: {exc}") from exc


def fallback_rationale(reason: str, raw: str) -> str:
    """못 읽은 응답이 원장에 남기는 문장. **절대 비지 않는다.**

    ⚠️ 비면 `Verification`이 *"모델이 판정했는데 근거가 없다"*로 예외를 낸다 — 그 예외는
       조치 한 건을 통째로 날리고, 원인은 **모델 답이 이상했다**는 것뿐이다.
    """
    excerpt = raw.strip()[:RAW_EXCERPT_CHARS]
    return f"{FALLBACK_PREFIX}: {reason} · raw[:{RAW_EXCERPT_CHARS}]={excerpt!r}"


@dataclass(frozen=True, slots=True)
class PromptedJudge:
    """`ModelPort`의 **실물 절반** — 묻고, 읽고, 못 읽으면 보수적으로 적는다.

    Spec: specs/warranty/design/06-agent-runtime.md §4 (REQ-204)

    ⚠️ 계량은 여기 없다. `MeteredModel`이 이것을 감싸고, 그래야 모델을 부르는 **다음
       자리**가 계량을 빠뜨리지 않는다 (design 06§5).
    """

    transport: Transport

    def judge_ambiguous(
        self, baseline: Measurement, after: Measurement, criterion_note: str
    ) -> ModelReply:
        raw = self.transport.complete(build_prompt(baseline, after, criterion_note))
        try:
            verdict, rationale = parse_reply(raw.text)
        except JudgeParseError as exc:
            # ⛔ 못 읽은 것도 **판정으로 닫는다** — 여기서 예외를 올리면 조치 한 건이
            #    검증 없이 끝나고, 그건 `unverifiable`도 아니고 그냥 구멍이다.
            verdict, rationale = FALLBACK_VERDICT, fallback_rationale(str(exc), raw.text)
        # ⚠️ 사용량은 **양쪽 경로에서 같이** 실린다. 답을 못 읽었어도 토큰은 나갔다.
        return ModelReply(verdict, rationale, raw.usage)
