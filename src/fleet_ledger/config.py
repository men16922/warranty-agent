"""설정 — 환경변수를 **검증해서** 읽는다.

Spec: specs/fleet-ledger/design/06-interfaces.md §6

⚠️ 이 모듈은 클라우드 SDK를 임포트하지 않는다. 게이트가 오프라인이려면(REQ-701)
   설정 계층이 라이브 클라이언트를 만들 수 없어야 한다.
⚠️ 조용한 기본값을 두지 않는다 — 빠진 설정은 **거부**한다. 기본값이 있으면
   설정이 안 된 채로 배포가 성공하고, 그 실패는 조용하다 (REFERENCE_FROM_PARENT #4).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Adapters(StrEnum):
    LIVE = "live"
    FAKE = "fake"


class ConfigError(ValueError):
    """설정이 성립하지 않는다."""


def load_env_file(path: Path = ENV_FILE) -> dict[str, str]:
    """`.env`를 읽는다. 의존성 없이 — 이 형식에 라이브러리가 필요하지 않다.

    ⚠️ 이미 프로세스 환경에 있는 값을 덮지 않는다. 배포 환경(Cloud Run)이 권위이고
       `.env`는 로컬 편의다. 반대로 하면 배포에서 로컬 값이 이긴다.
    """
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


@dataclass(frozen=True, slots=True)
class Settings:
    project_id: str
    region: str
    model: str
    adapters: Adapters
    reconcile_deadline_days: int
    billing_table: str | None

    @property
    def can_reconcile(self) -> bool:
        """화해가 가능한가. **비어 있음을 조용히 넘기지 않고 물을 수 있게 한다.**"""
        return self.billing_table is not None


def _require(source: Mapping[str, str], key: str) -> str:
    value = source.get(key, "").strip()
    if not value:
        raise ConfigError(f"{key}가 비어 있다 — .env.example을 보고 채울 것")
    return value


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """설정을 읽는다.

    - `environ`을 주면 **그것만** 본다. 디스크를 안 읽는다.
    - 안 주면 `.env`를 읽고 그 위에 프로세스 환경을 덮는다(배포 환경이 권위).

    ⚠️ 이 구분이 REQ-702(결정론)다. 첫 판은 `environ`을 줘도 `.env`를 함께 읽었고,
       그래서 **테스트 결과가 로컬 `.env` 내용에 따라 달라졌다** — 게이트가
       레포에 없는 파일에 의존하면 그 초록은 이 기계에서만 참이다.
    """
    if environ is not None:
        env = {k: v for k, v in environ.items() if v}
    else:
        env = dict(load_env_file())
        env.update({k: v for k, v in os.environ.items() if v})

    project_id = _require(env, "FL_PROJECT_ID")

    # ADK/GenAI SDK가 직접 읽는 변수가 우리 설정과 어긋나면, 모델 호출이 우리가 믿는
    # 프로젝트가 아닌 곳에 청구된다. **그 어긋남은 조용하다** — 그래서 여기서 막는다.
    adk_project = env.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if adk_project and adk_project != project_id:
        raise ConfigError(
            f"GOOGLE_CLOUD_PROJECT({adk_project})가 FL_PROJECT_ID({project_id})와 다르다 "
            "— 모델 호출이 다른 프로젝트에 청구된다"
        )

    raw_adapters = env.get("FL_ADAPTERS", "live").strip()
    if raw_adapters not in Adapters.__members__.values():
        raise ConfigError(f"FL_ADAPTERS가 live/fake가 아니다: {raw_adapters!r}")

    raw_days = env.get("FL_RECONCILE_DEADLINE_DAYS", "3").strip()
    if not raw_days.isdigit() or int(raw_days) < 1:
        raise ConfigError(f"FL_RECONCILE_DEADLINE_DAYS가 양의 정수가 아니다: {raw_days!r}")

    billing_table = env.get("FL_BILLING_TABLE", "").strip() or None
    if billing_table is not None and billing_table.count(".") != 2:
        raise ConfigError(
            f"FL_BILLING_TABLE 형식이 <project>.<dataset>.<table>이 아니다: {billing_table!r}"
        )

    return Settings(
        project_id=project_id,
        region=_require(env, "FL_REGION"),
        model=_require(env, "FL_MODEL"),
        adapters=Adapters(raw_adapters),
        reconcile_deadline_days=int(raw_days),
        billing_table=billing_table,
    )
