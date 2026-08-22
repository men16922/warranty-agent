#!/usr/bin/env bash
# 배포 — 이미지 빌드 → Artifact Registry → Cloud Run (design 10§5)
#
# ⛔ **게이트가 아니다.** 과금하고, 되돌리기 어렵고, 네트워크를 연다.
#    무인 루프의 deny 목록에 있다(scripts/overnight/overnight-settings.json).
#    ⇒ 이 스크립트는 **사람이** 부른다.
# ⛔ 이 스크립트는 **한 번도 실행된 적이 없다**(T11-1은 산출물만 만든다). 전용 GCP
#    프로젝트가 없어서 실행할 수도 없었다(T0-3). 첫 실행은 실패한다고 가정할 것 —
#    이미지가 아직 HTTP를 서비스하지 않는다(Dockerfile 상자 · T2-2).
#
# ⚠️ **여기에 서비스명·리전·min-instances를 적지 않는다.** 값의 출처는
#    `src/warranty/config.py` 하나이고, 이 스크립트는 렌더된 인자를 **받아서 실행만** 한다.
#    셸이 플래그를 직접 적는 순간 그것은 코드가 안 보는 두 번째 사본이 되고,
#    `min-instances`가 그 사본에 있으면 REQ-805는 아무도 안 읽는 문장이 된다.
#    게이트가 그 어긋남을 묻는다(tests/test_deploy_artifacts.py).
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
# 태그는 **커밋**이다. `latest`는 어느 리비전이 도는지 안 말하고, 롤백이 리비전 전환인
# 시스템에서 그 침묵은 되돌릴 대상을 모르게 만든다(REQ-302).
TAG="${TAG:-$(git rev-parse --short HEAD)}"

plan() {  # 값의 출처는 하나다 — 여기서 다시 적지 않는다.
  PYTHONPATH=src "$PY" tools/deploy_plan.py --tag "$TAG" "$@"
}

IMAGE="$(plan --image)"
# ⚠️ 한 줄에 하나로 읽는다. 공백으로 쪼개면 라벨·환경변수처럼 쉼표가 든 인자가 갈라진다.
ARGS=()
while IFS= read -r line; do ARGS+=("$line"); done < <(plan --args)

echo "이미지: $IMAGE"
printf '  gcloud %s\n' "${ARGS[*]}"

if [ "${1:-}" != "--yes" ]; then
  echo
  echo "⛔ 실제로 배포하려면 --yes를 붙일 것. (이 스크립트는 과금한다)"
  exit 1
fi

gcloud builds submit --tag "$IMAGE" .
gcloud "${ARGS[@]}"

echo
echo "⚠️ 배포가 끝났다는 것과 서비스가 산다는 것은 다르다 — design 10§5의 deploy-check(T2-4)."
echo "⚠️ 증거를 docs/evidence/deploy-\$(date +%F).log에 남길 것 (REQ-901 · design 10§7)."
