"""귀속 — 어떻게 청구서에 닿는가, 그리고 **닿을 수 없다면 그 사실**.

Spec: specs/fleet-ledger/design/02-attribution.md (REQ-203, REQ-205, REQ-206)
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

#: GCP 라벨 값 제약에서 유도된 형식. id를 바꾸려면 이 제약을 먼저 확인해야 한다.
LABEL_KEY = "fl_entry"
ENTRY_ID_RE = re.compile(r"^[a-z0-9_-]{1,63}$")


class Method(StrEnum):
    RESOURCE_LABEL = "resource_label"  # 리소스에 라벨을 박았다 → 청구 행에서 되찾는다
    TOKEN_METER = "token_meter"  # 모델 호출. 라벨 붙일 리소스가 없다
    NONE = "none"  # 과금 리소스를 안 만들었거나, 라벨 부착이 실패했다


class Verifiability(StrEnum):
    RECONCILABLE = "reconcilable"
    ASSUMED_ONLY = "assumed_only"


#: ★ 이 표는 **코드에 한 벌만** 존재한다 (design/01-domain-model.md §2.2).
#: 복사본 둘은 다음 고침이 한쪽에만 닿는 방식이다.
VERIFIABILITY_OF: Mapping[Method, Verifiability] = MappingProxyType(
    {
        Method.RESOURCE_LABEL: Verifiability.RECONCILABLE,
        Method.TOKEN_METER: Verifiability.ASSUMED_ONLY,
        Method.NONE: Verifiability.ASSUMED_ONLY,
    }
)


class AttributionError(ValueError):
    """귀속이 성립하지 않는다."""


@dataclass(frozen=True, slots=True)
class Attribution:
    method: Method
    label_value: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.method is Method.RESOURCE_LABEL:
            if not self.label_value:
                raise AttributionError(
                    "resource_label인데 라벨 값이 없다 — 화해가 원리상 불가능하다"
                )
            if not ENTRY_ID_RE.match(self.label_value):
                raise AttributionError(
                    "라벨 값이 GCP 라벨 제약을 어긴다 "
                    f"(소문자·숫자·-·_ · ≤63자): {self.label_value!r}"
                )
        elif self.method is Method.NONE and not self.reason:
            # ⚠️ 조용한 `none`을 만들면 화해가 영원히 못 찾는데 원인이 안 보인다 (REQ-206).
            raise AttributionError("method=none인데 사유가 없다")

    @property
    def verifiability(self) -> Verifiability:
        return VERIFIABILITY_OF[self.method]
