"""모델 호출 계량 — ★ **호출 1건 = 원장 1행** (REQ-603).

Spec: specs/warranty/design/06-agent-runtime.md (REQ-603)
      specs/warranty/design/05-accountability-ledger.md (REQ-503, REQ-504)

⚠️ 계량이 **여기 한 겹에만** 있는 것이 요점이다. 호출부마다 기록을 시키면 언젠가 한 곳이
   빠지고, 그 빠짐은 조용하다 (design 06§5). `MeteredModel`은 `ModelPort`를 감싸
   `ModelJudge`인 척한다 — 그래서 `Remediator`는 계량을 **모른다.**
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from warranty.domain.attribution import Attribution, Method
from warranty.domain.cost import Basis, CostFact
from warranty.domain.entry import EntryKind, LedgerEntry, Status
from warranty.domain.tokens import ModelReply, TokenPrices, TokenUsage, UnpricedModelError
from warranty.domain.verification import Measurement, Verdict
from warranty.ports import Clock, IdGen, LedgerWriter, ModelPort

#: 원장의 `action_id`에 붙는 접두사. 모델 호출은 조치가 아니므로 **이름에서부터 구분된다.**
MODEL_ACTION_PREFIX = "model:"


@dataclass(frozen=True, slots=True)
class MeteredModel:
    """`ModelPort`를 감싸 **호출마다 원장 1행**을 남긴다 (REQ-603).

    Spec: specs/warranty/design/06-agent-runtime.md (REQ-603)

    ⚠️ 이 객체는 `ModelJudge`(REQ-204)의 자리에 그대로 꽂힌다. 계량을 `Remediator`
       안에 넣으면 모델을 부르는 **다음 자리**가 계량을 빠뜨리게 된다.
    """

    model: ModelPort
    ledger: LedgerWriter
    clock: Clock
    ids: IdGen
    prices: TokenPrices
    agent_id: str

    def judge_ambiguous(
        self, baseline: Measurement, after: Measurement, criterion_note: str
    ) -> tuple[Verdict, str]:
        """REQ-204의 그 호출. 계량은 `_call`이 한다."""
        reply = self._call(
            "judge_ambiguous",
            lambda: self.model.judge_ambiguous(baseline, after, criterion_note),
        )
        return reply.verdict, reply.rationale

    def _call(self, action_id: str, invoke: Callable[[], ModelReply]) -> ModelReply:
        """★ 계량은 **여기 한 곳**에만 있다 (design 06§5).

        ⚠️ 기록이 `finally`에 있다. 호출이 예외로 끝나도 **토큰은 이미 나갔을 수 있고**,
           행을 안 남기면 그 지출은 원장에 영원히 없다 — 예산 정산을 `finally`에 둔 것과
           같은 이유다 (design 04§3).
        """
        usage: TokenUsage | None = None
        try:
            reply = invoke()
            usage = reply.usage
        finally:
            self._record(action_id, usage)
        return reply

    def _record(self, action_id: str, usage: TokenUsage | None) -> None:
        started = datetime.fromisoformat(self.clock.now_iso())
        attribution, assumed = self._attribute(usage, started)
        self.ledger.create(
            LedgerEntry(
                entry_id=self.ids.new_entry_id(),
                agent_id=self.agent_id,
                action_id=f"{MODEL_ACTION_PREFIX}{action_id}",
                # 사용량을 못 받았다 = 호출이 응답을 못 냈다. 성공으로 적을 수 없다.
                status=Status.EXECUTED if usage is not None else Status.FAILED,
                started_at=started,
                attribution=attribution,
                assumed=assumed,
                # ⚠️ 모델 호출은 게이트를 거치지 않는다 → `decision`을 붙이지 않는다.
                kind=EntryKind.MODEL_CALL,
            )
        )

    def _attribute(
        self, usage: TokenUsage | None, priced_at: datetime
    ) -> tuple[Attribution, CostFact]:
        """귀속 방법과 추정 비용 (REQ-504).

        ⚠️ 셋 중 무엇도 **조용한 0**을 만들지 않는다. `token_meter`라고 적고 0을 넣으면
           그 행은 *"계량했는데 공짜였다"*로 읽히고, 그건 *"얼마인지 모른다"*와 다르다.
        """
        zero = CostFact(Decimal(0), priced_at, Basis.PUBLISHED_RATE)
        if usage is None:
            return Attribution(Method.NONE, reason="model call reported no usage"), zero
        try:
            return Attribution(Method.TOKEN_METER), self.prices.cost_of(usage, priced_at=priced_at)
        except UnpricedModelError as exc:
            return Attribution(Method.NONE, reason=str(exc)), zero
