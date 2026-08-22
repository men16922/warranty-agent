# warranty — 배포 이미지 (design 10§2 · REQ-602)
#
# ⛔ **이 이미지는 아직 HTTP를 서비스하지 않는다.** design 08§3이 적은 엔드포인트는
#    REQ-602이고 그것은 T2-2가 소유한다. 지금 `CMD`가 도는 것은 **오프라인 데모**다.
#    ⇒ 이대로 Cloud Run에 올리면 포트 프로브에서 실패한다. 그 실패를 잡는 자리는
#    design 10§5의 `deploy-check`이고, 그것도 아직 없다(T2-4).
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

# ⛔ 서비스 진입점이 아니다 — 위 상자를 볼 것. T2-2가 이 줄을 바꾼다.
CMD ["python", "-m", "warranty.demo"]
