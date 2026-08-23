"""설정 — 환경변수를 **검증해서** 읽는다.

Spec: specs/warranty/design/08-interfaces.md §5
      specs/warranty/design/10-deployment.md §1–2, §4 (REQ-602, REQ-805)

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

    project_id = _require(env, "WR_PROJECT_ID")

    # ADK/GenAI SDK가 직접 읽는 변수가 우리 설정과 어긋나면, 모델 호출이 우리가 믿는
    # 프로젝트가 아닌 곳에 청구된다. **그 어긋남은 조용하다** — 그래서 여기서 막는다.
    adk_project = env.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if adk_project and adk_project != project_id:
        raise ConfigError(
            f"GOOGLE_CLOUD_PROJECT({adk_project})가 WR_PROJECT_ID({project_id})와 다르다 "
            "— 모델 호출이 다른 프로젝트에 청구된다"
        )

    raw_adapters = env.get("WR_ADAPTERS", "live").strip()
    if raw_adapters not in Adapters.__members__.values():
        raise ConfigError(f"WR_ADAPTERS가 live/fake가 아니다: {raw_adapters!r}")

    raw_days = env.get("WR_RECONCILE_DEADLINE_DAYS", "3").strip()
    if not raw_days.isdigit() or int(raw_days) < 1:
        raise ConfigError(f"WR_RECONCILE_DEADLINE_DAYS가 양의 정수가 아니다: {raw_days!r}")

    billing_table = env.get("WR_BILLING_TABLE", "").strip() or None
    if billing_table is not None and billing_table.count(".") != 2:
        raise ConfigError(
            f"WR_BILLING_TABLE 형식이 <project>.<dataset>.<table>이 아니다: {billing_table!r}"
        )

    return Settings(
        project_id=project_id,
        region=_require(env, "WR_REGION"),
        model=_require(env, "WR_MODEL"),
        adapters=Adapters(raw_adapters),
        reconcile_deadline_days=int(raw_days),
        billing_table=billing_table,
    )


# ── 배포 산출물이 읽는 값 (T11-1 · design 10§1–2, §4) ─────────────────────────
#
# ⛔ **여기가 유일한 출처다.** `Dockerfile`도 `scripts/deploy.sh`도 이 값을 다시 적지 않는다.
#    다시 적는 순간 배포 산출물과 코드가 **따로 썩고**, 그 어긋남은 배포가 성공할 때까지
#    안 보인다 — 그리고 배포는 게이트에 없다. 게이트가 그것을 대신 묻는다
#    (tests/test_deploy_artifacts.py).
# ⚠️ **리전은 여기 없다.** 리전은 `Settings.region`(`WR_REGION`)이고, 배포도 앱과 **같은
#    설정 로더**가 검증한 값을 쓴다. 두 번째 리전 상수를 만드는 것이 첫 번째 어긋남이다.

#: Cloud Run 서비스명 — design 10§2.
SERVICE_NAME = "warranty-api"

#: ⛔ REQ-805 — 유휴 시 0으로 수렴한다. **0이 아니면 그 순간부터 상시 과금이다.**
MIN_INSTANCES = 0
MAX_INSTANCES = 2

#: 이미지가 사는 Artifact Registry 저장소 — design 10§2.
IMAGE_REPO = "warranty"

#: 인프라 라벨 — design 10§4. ⚠️ 귀속 라벨(`wr_entry`)과 **섞지 않는다**: 화해 질의가
#: 인프라 라벨로 매칭하면 인프라 비용이 조치에 귀속된다.
INFRA_LABELS: tuple[tuple[str, str], ...] = (("wr_project", "warranty"), ("wr_env", "hack"))

#: 컨테이너가 받아 가야 하는 설정 변수. ⚠️ `load_settings`가 **기본값을 안 주므로**
#: 이 목록이 빠지면 컨테이너는 부팅하다 `ConfigError`로 죽는다 — 조용한 실패가 아니라
#: 시끄러운 실패이고, 그게 설계다(design 08§5).
RUNTIME_ENV_KEYS = ("WR_PROJECT_ID", "WR_REGION", "WR_MODEL", "WR_ADAPTERS")

#: ⛔ **포트의 유일한 출처다** (T12-1). Cloud Run이 컨테이너에 주입하는 변수 이름이고,
#:    `Dockerfile`도 `scripts/deploy.sh`도 이 숫자를 다시 적지 않는다. 다시 적는 순간
#:    *이미지가 듣는 포트*와 *플랫폼이 프로브하는 포트*가 따로 썩고, 그 어긋남은
#:    **첫 배포의 포트 프로브 실패**로만 보인다 — 게이트에서는 안 보인다.
PORT_ENV_KEY = "PORT"

#: ⚠️ `WR_*`와 달리 여기엔 기본값이 있다. 규칙을 어기는 게 아니라 **주인이 다르다**:
#:    이 변수는 우리가 정의한 설정이 아니라 플랫폼이 주입하는 것이고, 이 값은 그 플랫폼이
#:    문서로 약속한 기본값이다. 로컬에서 `PORT` 없이 띄우는 것은 설정 누락이 아니다.
DEFAULT_PORT = 8080

MAX_PORT = 65535


def load_port(environ: Mapping[str, str] | None = None) -> int:
    """이미지가 들을 포트. **없으면 기본값, 있으면 검증한다.**

    ⚠️ 값이 있는데 숫자가 아닐 때 **조용히 기본값으로 접지 않는다.** 접으면 컨테이너는
       뜨고 프로브는 실패하며, 로그에는 아무 이유도 안 남는다 — `PORT=$PORT` 같은
       미치환 문자열이 정확히 그렇게 새어 들어온다.
    """
    env = os.environ if environ is None else environ
    raw = env.get(PORT_ENV_KEY, "").strip()
    if not raw:
        return DEFAULT_PORT
    if not raw.isdigit() or not 1 <= int(raw) <= MAX_PORT:
        raise ConfigError(f"{PORT_ENV_KEY}가 1~{MAX_PORT}의 정수가 아니다: {raw!r}")
    return int(raw)


def image_uri(settings: Settings, tag: str) -> str:
    """Artifact Registry 이미지 주소. 리전·프로젝트는 **설정에서** 온다.

    ⚠️ 태그를 강제하는 이유: `latest`는 *"어느 리비전이 도는가"*를 안 말한다. 롤백이
       리비전 전환인 시스템에서 그 침묵은 되돌릴 대상을 모르게 만든다(REQ-302).
    """
    if not tag.strip():
        raise ConfigError("이미지 태그가 비어 있다 — 어느 리비전인지 말하지 않는 배포는 안 한다")
    return (
        f"{settings.region}-docker.pkg.dev/{settings.project_id}/{IMAGE_REPO}/{SERVICE_NAME}:{tag}"
    )


def deploy_argv(settings: Settings, tag: str) -> tuple[str, ...]:
    """`gcloud`에 넘길 인자 전부. 배포 스크립트는 이것을 **받아서 실행만** 한다.

    ⛔ 이 함수가 배포의 **유일한 렌더러**다. 스크립트가 플래그를 하나라도 직접 적으면
       그 플래그는 코드가 안 보는 값이 되고, `min-instances`가 그 자리에 있으면
       REQ-805는 **아무도 안 읽는 문장**이 된다.
    """
    labels = ",".join(f"{key}={value}" for key, value in INFRA_LABELS)
    env_vars = ",".join(f"{key}={_runtime_env_value(settings, key)}" for key in RUNTIME_ENV_KEYS)
    return (
        "run",
        "deploy",
        SERVICE_NAME,
        f"--project={settings.project_id}",
        f"--region={settings.region}",
        f"--image={image_uri(settings, tag)}",
        f"--min-instances={MIN_INSTANCES}",
        f"--max-instances={MAX_INSTANCES}",
        f"--labels={labels}",
        f"--set-env-vars={env_vars}",
        "--no-allow-unauthenticated",
    )


def _runtime_env_value(settings: Settings, key: str) -> str:
    """컨테이너에 실릴 값 — **설정 객체에서** 읽는다(두 번째 사본을 안 만든다)."""
    match key:
        case "WR_PROJECT_ID":
            return settings.project_id
        case "WR_REGION":
            return settings.region
        case "WR_MODEL":
            return settings.model
        case "WR_ADAPTERS":
            return str(settings.adapters)
        case _:
            raise ConfigError(f"컨테이너에 실을 값을 모른다: {key}")
