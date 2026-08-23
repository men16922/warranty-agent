# warranty — 배포 이미지 (design 10§2 · REQ-602)
#
# ⚠️ **이 이미지는 이제 포트를 연다**(T12-1). 직전까지 `CMD`가 돌린 것은 오프라인 데모였고,
#    데모는 끝나면 종료한다 — 포트를 한 번도 안 열어서 **포트 프로브에서 죽는 함정**이었다.
#    ⛔ 열리는 것은 포트와 헬스 경로까지다. design 08§3의 나머지 엔드포인트는 선언만 돼
#    있고 `501`을 낸다 — 실물 어댑터가 아직 없다(REQ-601·602는 TODO). 그 배선은 T2-2다.
#    ⚠️ 배포 전 검사는 **생겼다**(T12-4) — `tools/deploy_preflight.py`가 이 `CMD`의 진입점이
#    실제로 서비스하는지(포트를 config에서 읽고 · 소켓을 열고 · 안 끝나는지) 올리기 전에 묻고,
#    `scripts/deploy.sh`가 빌드보다 **먼저** 그것을 부른다. 올린 뒤의 절반은 아직 없다.
#    ⚠️ 실물로 확인된 것이 하나도 없다 — 빌드조차 여기서 돌려 본 적 없다(PRINCIPLES #3).
#
# ⚠️ 서비스명·리전·`min-instances`를 **여기 안 적는다.** 그 값들은
#    `src/warranty/config.py`에서 오고 `scripts/deploy.sh`가 받아 간다.
#    이미지가 그 값을 알아야 할 이유가 없고, 알면 두 번째 사본이 된다.

# ⚠️ 베이스의 파이썬은 pyproject의 `requires-python`과 같아야 한다 — 게이트가 묻는다.
FROM python:3.13-slim

# ⚠️ `PYTHONDONTWRITEBYTECODE`는 취향이 아니다. 읽기 전용 파일시스템에서 .pyc 쓰기가
#    실패하면 그 실패는 첫 요청에서야 보인다.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 의존성 선언을 먼저 복사한다 — 소스만 바뀔 때 설치 층을 다시 안 쌓는다.
COPY pyproject.toml ./
COPY src ./src

# ⚠️ `[cloud]`를 넣는 이유: 실물 어댑터는 이 extra 없이는 임포트되지 않는다.
#    게이트는 반대로 이것 **없이** 통과해야 한다 — 그것이 fake 어댑터의 전제다(REQ-801).
RUN pip install --no-cache-dir ".[cloud]"

# ⚠️ 포트 번호를 **여기 안 적는다.** 플랫폼이 `PORT`로 주입하고, 그 이름과 기본값은
#    `src/warranty/config.py` 한 곳에 있다. 여기 적으면 이미지가 듣는 포트와 프로브가
#    두드리는 포트가 따로 썩고, 그 어긋남은 첫 배포에서만 보인다.
CMD ["python", "-m", "warranty.server"]
