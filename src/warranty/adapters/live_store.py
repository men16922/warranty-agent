"""Firestore 어댑터 — 계약과 원장의 **실물 절반** (REQ-102·501·505).

Spec: specs/warranty/design/08-interfaces.md §2, §2.1
      specs/warranty/design/10-deployment.md §2 (Firestore Native)

⛔ **불변식은 여기 없다.** 무엇이 허용되는지는 `warranty.domain.entry`의 전이 함수들이
   알고, 이 모듈은 **읽고 쓰기만** 한다. 저장소가 둘이 된 순간(인메모리 · Firestore)
   규칙을 두 벌 적으면 한쪽만 고쳐지는 날이 오고, 그날 원장은 **저장소에 따라 다른 것을
   허용한다** (design 08§2 · docs/PRINCIPLES.md #10).

⚠️ **라이브러리는 지연 임포트한다.** `google-cloud-firestore`는 게이트에 안 깔린다
   (cloud extra · REQ-801). 그래서 게이트가 태우는 것은 호출이 아니라 **문서의 모양**이다 —
   `live_signal.py`(T13-1)·`live_run.py`와 같은 수법이다.

⛔ **모듈 임포트만으로 클라이언트를 만들지 않는다.** G5가 그것을 집행한다.
"""

from __future__ import annotations

import types
import typing
from collections.abc import Callable, Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, cast, get_args, get_origin

from warranty.adapters import live_guard
from warranty.domain.contract import ContractState, OperationalContract, ResourceRef
from warranty.domain.cost import CostFact
from warranty.domain.entry import (
    Approval,
    LedgerEntry,
    LedgerError,
    Rollback,
    Status,
    apply_approval,
    apply_completion,
    apply_give_up_reconcile,
    apply_reconcile,
)
from warranty.domain.verification import Verification

#: 컬렉션 이름. ⚠️ 여기 한 곳에만 적는다 — 두 곳에 적으면 배포마다 다른 곳을 읽는다.
CONTRACTS = "contracts"
LEDGER = "ledger"

#: `active_for`가 거는 조건. **값이다** — 게이트가 SDK 없이 이 모양을 태울 수 있다.
STATE_FIELD = "state"
RESOURCE_FIELDS = ("resource.kind", "resource.name", "resource.region")


class StoreError(RuntimeError):
    """Firestore 문서를 신뢰할 수 없다."""


# ── 문서 매핑 — **필드가 늘면 자동으로 따라간다** ─────────────────────────────────
#
# ⛔ 필드마다 손으로 옮기지 않는 이유는 게으름이 아니다. 손으로 적으면 도메인에 필드가
#    하나 느는 날 **그 필드만 조용히 저장 안 된다** — 원장은 여전히 읽히고, 빠진 값은
#    기본값으로 채워지며, 그 행은 거짓말을 하기 시작한다. 그 실패는 예외가 아니라 침묵이다.
# ⚠️ `init=False` 필드는 안 싣는다 — 생성자가 안 받는 값은 문서가 말할 것이 아니다.


def encode(value: Any) -> Any:
    """도메인 값 하나를 Firestore가 담을 수 있는 값으로. **순수하다.**

    ⛔ `Decimal`을 **문자열로** 싣는다. Firestore의 수치 타입은 double이고, 돈을 double로
       왕복시키면 `0.84`가 `0.8400000000000001`이 되어 돌아온다 — 그 값은 청구서와 안 맞고,
       안 맞는 이유는 코드 어디에도 안 적혀 있다 (REQ-503·505).
    ⚠️ 모르는 타입은 **거절한다.** `str()`로 뭉개면 저장은 성공하고 복원이 깨진다.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: encode(getattr(value, f.name)) for f in fields(value) if f.init}
    if isinstance(value, Mapping):
        return {str(key): encode(item) for key, item in value.items()}
    if isinstance(value, str | int | float):
        return value
    raise StoreError(f"문서에 실을 수 없는 값이다: {type(value).__name__}")


def _unwrap_optional(kind: Any) -> tuple[Any, bool]:
    """`X | None` → `(X, True)`. 아니면 `(kind, False)`."""
    if get_origin(kind) in (types.UnionType, typing.Union):
        args = [arg for arg in get_args(kind) if arg is not type(None)]
        if len(args) != 1:
            raise StoreError(f"복원할 수 없는 합타입이다: {kind}")
        return args[0], True
    return kind, False


def decode(kind: Any, raw: Any) -> Any:
    """문서의 값 하나를 도메인 값으로. **순수하다.** 타입이 복원을 이끈다.

    ⚠️ `Decimal` 자리에 수치가 오면 **거절한다.** double로 저장된 돈은 이미 값이 바뀐
       뒤이고, 여기서 받아 주면 그 손실이 도메인 안까지 들어온다.
    """
    kind, optional = _unwrap_optional(kind)
    if raw is None:
        if not optional:
            raise StoreError(f"{kind}이(가) 아닌 None이 왔다")
        return None

    if isinstance(kind, type) and issubclass(kind, StrEnum):
        try:
            return kind(raw)
        except ValueError as exc:
            raise StoreError(f"{kind.__name__}에 없는 값이다: {raw!r}") from exc
    if kind is Decimal:
        if not isinstance(raw, str):
            raise StoreError(f"Decimal은 문자열로만 복원한다 — {type(raw).__name__}이 왔다")
        try:
            return Decimal(raw)
        except InvalidOperation as exc:
            raise StoreError(f"Decimal이 아니다: {raw!r}") from exc
    if kind is datetime:
        if not isinstance(raw, str):
            raise StoreError(f"시각은 ISO 문자열로만 복원한다 — {type(raw).__name__}이 왔다")
        return datetime.fromisoformat(raw)
    if get_origin(kind) in (Mapping, dict):
        if not isinstance(raw, Mapping):
            raise StoreError(f"매핑이 아니다: {type(raw).__name__}")
        _, value_kind = get_args(kind)
        return {str(key): decode(value_kind, item) for key, item in raw.items()}
    if isinstance(kind, type) and is_dataclass(kind):
        return decode_dataclass(kind, raw)
    if kind in (str, int, float, bool):
        if not isinstance(raw, kind) or (kind is not bool and isinstance(raw, bool)):
            raise StoreError(f"{kind.__name__}이 아니다: {type(raw).__name__}")
        return raw
    raise StoreError(f"복원할 수 없는 타입이다: {kind}")


def decode_dataclass[T](kind: type[T], raw: Any) -> T:
    """문서 하나를 데이터클래스 하나로. **키가 정확히 맞아야 한다.**

    ⛔ 빠진 키를 기본값으로 채우지 않는다. 채우면 **옛 배포가 쓴 문서**가 새 필드에 대해
       조용히 기본값을 갖고 돌아오고, 그 행은 자기가 무엇을 모르는지 말하지 않는다.
       마이그레이션은 소리를 내야 한다.
    ⛔ 남는 키도 거절한다 — 우리가 안 읽는 필드가 문서에 있다는 것은 이 코드와 그 문서를
       쓴 코드가 **다른 것을 말하고 있다**는 뜻이다.
    """
    if not isinstance(raw, Mapping):
        raise StoreError(f"{kind.__name__} 문서가 매핑이 아니다: {type(raw).__name__}")
    hints = typing.get_type_hints(kind)
    expected = {f.name for f in fields(cast(Any, kind)) if f.init}
    given = set(raw.keys())
    if missing := expected - given:
        raise StoreError(f"{kind.__name__} 문서에 없는 필드다: {sorted(missing)}")
    if extra := given - expected:
        raise StoreError(f"{kind.__name__}이 모르는 필드다: {sorted(extra)}")
    return kind(**{name: decode(hints[name], raw[name]) for name in expected})


def contract_document(contract: OperationalContract) -> dict[str, Any]:
    """계약 하나의 문서. **순수하다.**"""
    document = encode(contract)
    if not isinstance(document, dict):  # pragma: no cover - 데이터클래스는 항상 dict다
        raise StoreError("계약 문서가 매핑이 아니다")
    return document


def entry_document(entry: LedgerEntry) -> dict[str, Any]:
    """원장 행 하나의 문서. **순수하다.**"""
    document = encode(entry)
    if not isinstance(document, dict):  # pragma: no cover - 데이터클래스는 항상 dict다
        raise StoreError("원장 문서가 매핑이 아니다")
    return document


def active_contract_conditions(resource: ResourceRef) -> tuple[tuple[str, str, str], ...]:
    """`active_for`가 거는 조건 전부. **순수하다** — SDK 없이 게이트가 태운다.

    ⚠️ `state`를 조건에 **넣는다.** 빼고 파이썬에서 거르면 `retired`된 계약이 한 번은
       메모리에 올라오고, 그것을 거르는 줄이 사라지는 날 자동 조치가 **없는 리소스를
       고치려 든다** (REQ-105).
    """
    if not resource.name:
        raise StoreError("리소스 이름이 비었다 — 계약을 찾을 수 없다")
    return (
        (RESOURCE_FIELDS[0], "==", resource.kind),
        (RESOURCE_FIELDS[1], "==", resource.name),
        (RESOURCE_FIELDS[2], "==", resource.region),
        (STATE_FIELD, "==", ContractState.ACTIVE.value),
    )


def one_active(documents: list[Any], resource: ResourceRef) -> OperationalContract | None:
    """질의 결과에서 **살아 있는 계약 하나**를 고른다. **순수하다.**

    ⛔ 둘 이상이면 거절한다. 한 리소스에 계약이 둘이면 *"어느 기준으로 회복을 판정하는가"*에
       답이 둘이고, 아무거나 고르면 그 판정은 **고른 사람에 따라 달라진다** (REQ-102).
    """
    if not documents:
        return None
    if len(documents) > 1:
        raise StoreError(
            f"살아 있는 계약이 둘 이상이다: {resource.name} ({len(documents)}건) — "
            "어느 기준으로 검증할지 모른다"
        )
    return decode_dataclass(OperationalContract, documents[0])


class LiveContractStore:
    """실물 Firestore 계약 저장소. ⛔ 클라이언트는 첫 조회에서 만든다 (G5 · REQ-801)."""

    def __init__(self, project: str) -> None:
        if not project:
            raise StoreError("프로젝트가 비었다 — Firestore를 열 수 없다")
        self._project = project
        self._client: Any | None = None

    def _db(self) -> Any:
        live_guard.note("live_store.LiveContractStore._db")
        if self._client is None:
            # 지연 임포트 — 게이트에는 이 패키지가 없다(REQ-801).
            from google.cloud import firestore  # type: ignore[import-not-found]

            self._client = firestore.Client(project=self._project)
        return self._client

    def put(self, contract: OperationalContract) -> None:
        """계약 하나를 Firestore에 **한 번만** 쓴다 (REQ-101).

        ⛔ `create`다 — `set`이 아니다. 같은 `contract_id`로 두 번 오면 Firestore가
           `AlreadyExists`로 거절하고, 그 거절이 *"계약은 산출물이지 갱신 대상이 아니다"*를
           집행한다. `set`을 쓰면 두 번째 프로비저닝이 첫 계약을 **조용히 덮는다**.

        ⛔ 첫 줄이 tripwire다(G5) — `_db`가 캐시되어 있으면 그쪽 관측 지점을 안 지난다.
        """
        live_guard.note("live_store.LiveContractStore.put")
        self._db().collection(CONTRACTS).document(contract.contract_id).create(
            contract_document(contract)
        )

    def active_for(self, resource: ResourceRef) -> OperationalContract | None:
        live_guard.note("live_store.LiveContractStore.active_for")
        query: Any = self._db().collection(CONTRACTS)
        for path, op, value in active_contract_conditions(resource):
            query = query.where(path, op, value)
        return one_active([snapshot.to_dict() for snapshot in query.stream()], resource)


class LiveLedger:
    """실물 Firestore 원장. ⛔ 클라이언트는 첫 쓰기에서 만든다 (G5 · REQ-801).

    ⚠️ 전이는 **읽고-바꾸고-쓰기**라 트랜잭션 안에서 돈다. 밖에서 하면 두 요청이 같은 행을
       같은 시점의 사본으로 고치고, 나중 쓰기가 앞선 쓰기를 **말없이 덮는다** — 승인 한 번,
       화해 한 번 같은 규칙이 그 창에서 무너진다.
    """

    def __init__(self, project: str) -> None:
        if not project:
            raise StoreError("프로젝트가 비었다 — Firestore를 열 수 없다")
        self._project = project
        self._client: Any | None = None

    def _db(self) -> Any:
        live_guard.note("live_store.LiveLedger._db")
        if self._client is None:
            # 억제는 이 파일의 **첫 지연 임포트에만** 붙는다 — 또 붙이면
            # `warn_unused_ignores`가 운다(live_run.py와 같은 규칙).
            from google.cloud import firestore

            self._client = firestore.Client(project=self._project)
        return self._client

    def _doc(self, entry_id: str) -> Any:
        live_guard.note("live_store.LiveLedger._doc")
        if not entry_id:
            raise LedgerError("항목 id가 비었다")
        return self._db().collection(LEDGER).document(entry_id)

    def create(self, entry: LedgerEntry) -> None:
        """⛔ `create()`다, `set()`이 아니다. **Firestore가 I-5를 집행한다** — 읽어 보고
        없으면 쓰면 그 사이에 다른 요청이 같은 id로 쓴다 (REQ-501: 1회 = 1행)."""
        live_guard.note("live_store.LiveLedger.create")
        from google.api_core import exceptions  # type: ignore[import-not-found]

        try:
            self._doc(entry.entry_id).create(entry_document(entry))
        except exceptions.AlreadyExists as exc:
            raise LedgerError(f"이미 있는 항목이다: {entry.entry_id}") from exc

    def get(self, entry_id: str) -> LedgerEntry | None:
        live_guard.note("live_store.LiveLedger.get")
        snapshot = self._doc(entry_id).get()
        if not snapshot.exists:
            return None
        return decode_dataclass(LedgerEntry, snapshot.to_dict())

    def _mutate(self, entry_id: str, change: Callable[[LedgerEntry], LedgerEntry]) -> LedgerEntry:
        """한 행을 트랜잭션 안에서 읽고 → 도메인 전이를 태우고 → 되쓴다."""
        live_guard.note("live_store.LiveLedger._mutate")
        from google.cloud import firestore

        reference = self._doc(entry_id)
        transaction = self._db().transaction()

        @firestore.transactional  # type: ignore[untyped-decorator]
        def run(tx: Any) -> LedgerEntry:
            live_guard.note("live_store.LiveLedger._mutate.run")
            snapshot = reference.get(transaction=tx)
            if not snapshot.exists:
                raise LedgerError(f"없는 항목이다: {entry_id}")
            updated = change(decode_dataclass(LedgerEntry, snapshot.to_dict()))
            tx.set(reference, entry_document(updated))
            return updated

        return cast(LedgerEntry, run(transaction))

    def approve(self, entry_id: str, approval: Approval) -> LedgerEntry:
        live_guard.note("live_store.LiveLedger.approve")
        return self._mutate(entry_id, lambda current: apply_approval(current, approval))

    def complete(
        self,
        entry_id: str,
        *,
        status: Status,
        verification: Verification | None = None,
        rollback: Rollback | None = None,
    ) -> LedgerEntry:
        live_guard.note("live_store.LiveLedger.complete")
        return self._mutate(
            entry_id,
            lambda current: apply_completion(
                current, status=status, verification=verification, rollback=rollback
            ),
        )

    def reconcile(self, entry_id: str, measured: CostFact) -> LedgerEntry:
        live_guard.note("live_store.LiveLedger.reconcile")
        return self._mutate(entry_id, lambda current: apply_reconcile(current, measured))

    def give_up_reconcile(
        self, entry_id: str, *, at: datetime, deadline_days: int, reason: str
    ) -> LedgerEntry:
        live_guard.note("live_store.LiveLedger.give_up_reconcile")
        return self._mutate(
            entry_id,
            lambda current: apply_give_up_reconcile(
                current, at=at, deadline_days=deadline_days, reason=reason
            ),
        )
