#!/usr/bin/env bash
# 변이 하네스 — 변이·실행·복구를 **한 스크립트 안에서** 한다.
#
# ⚠️ 레퍼런스 저장소가 이 하네스 자신에서 다섯 번 틀렸다 (REFERENCE_FROM_PARENT #9):
#    틀린 파일에 물었고 · 문법을 깬 변이를 red로 셌고 · 없는 파일을 적어 "0건 실행"을
#    red로 셌고 · 복구가 커밋 안 된 고침을 날렸다.
#    ⇒ 기준선을 먼저 찍고 · 백업은 디스크에(git 아님) · 초록 복귀까지 확인한다.
set -uo pipefail
RESULT=0
LAST_SUMMARY=""
cd "$(dirname "$0")/.."

MUT="${1:?사용법: scripts/mutate.sh <M-01|M-02|M-03|M-04|all>}"
BACKUP="$(mktemp -d)"          # ⚠️ git checkout이 아니라 디스크 백업 — 커밋 안 된 고침을 안 날린다
PYTEST=".venv/bin/pytest"
TOUCHED=()                     # 이번 변이가 건드린 파일만 추적한다
REPO="$PWD"

# ⚠️ stale .pyc가 복구를 무효로 만든다. 소스는 되돌아왔는데 테스트가 옛 코드를 보고
#    red가 유지되어 "복구 실패"로 읽혔다 — 하네스 자신의 세 번째 결함이었다.
export PYTHONDONTWRITEBYTECODE=1

trap 'restore' EXIT

backup() {
  mkdir -p "$BACKUP/$(dirname "$1")"; cp "$1" "$BACKUP/$1"; TOUCHED+=("$1")
}

restore() {
  local f
  for f in "${TOUCHED[@]:-}"; do
    [ -n "$f" ] && [ -f "$BACKUP/$f" ] && cp "$BACKUP/$f" "$REPO/$f"
  done
  find "$REPO/src" "$REPO/tests" "$REPO/tools" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
}

# 변이 잔여 확인 — git이 아니라 **백업과의 대조**다.
# git으로 물으면 커밋 안 된 다른 작업이 변이 잔여로 오인된다 (하네스의 두 번째 결함).
residue() {
  local f dirty=""
  for f in "${TOUCHED[@]:-}"; do
    [ -z "$f" ] && continue
    cmp -s "$BACKUP/$f" "$REPO/$f" || dirty="$dirty $f"
  done
  printf '%s' "$dirty"
}

# ⚠️ 출력 문자열이 아니라 **종료 코드**로 판정한다.
#    첫 판에서 정확히 여기서 틀렸다 — 변이는 red를 냈는데 `tail -1`이 요약 줄이 아니라
#    short summary의 마지막 줄을 집어 "초록"으로 읽었다. 하네스 자신이 #9의 사례가 됐다.
run_suite() {  # 전체 스위트에 묻는다. 한 파일에만 물으면 #9의 첫 번째 실패다.
  local out rc
  out="$($PYTEST 2>&1)"; rc=$?   # ⚠️ -q를 또 주면 -qq가 되어 요약 줄이 사라진다
  LAST_SUMMARY="$(printf '%s' "$out" | grep -Eo '[0-9]+ (passed|failed|error[s]?)(, [0-9]+ (passed|failed|error[s]?))*' | tail -1)"
  return $rc
}

baseline() {
  if run_suite; then echo "  기준선: 초록 ($LAST_SUMMARY)"
  else echo "  ❌ 기준선이 이미 red다 — 변이 결과를 신뢰할 수 없다"; exit 3; fi
}

apply() {
  case "$1" in
    M-01) # requirements.md의 `상태:` 한 줄 삭제
      backup specs/fleet-ledger/requirements.md
      perl -0pi -e 's/^상태: `TODO`\n//m' specs/fleet-ledger/requirements.md ;;
    M-02) # REQ 하나를 IMPLEMENTED로 올리고 테스트는 안 만든다
      backup specs/fleet-ledger/requirements.md
      perl -0pi -e 's/^상태: `TODO`$/상태: `IMPLEMENTED`/m' specs/fleet-ledger/requirements.md ;;
    M-03) # 파서를 깨 0개를 읽게 한다 (공허 통과 방지가 사는지)
      backup tools/spec_trace.py
      perl -0pi -e 's/\^### \(REQ-\\d\{3\}\)/^#### (REQ-\\d{3})/' tools/spec_trace.py ;;
    M-04) # 정의 없는 REQ-999를 tasks.md가 가리키게 한다
      backup specs/fleet-ledger/tasks.md
      printf '\n- [ ] **T9-9** 없는 요구사항 · `Implements: REQ-999`\n' >> specs/fleet-ledger/tasks.md ;;
    M-05) # 산문 언급만으로는 커버리지가 되면 안 된다 (스캐너가 AST를 쓰는지)
      backup specs/fleet-ledger/requirements.md; backup tests/test_domain_ledger.py
      perl -0pi -e 's/^### REQ-101(.*?)^상태: `TODO`$/### REQ-101$1상태: `IMPLEMENTED`/sm' specs/fleet-ledger/requirements.md
      printf '\n\ndef test_mentions_but_does_not_verify() -> None:\n    """이 테스트는 REQ-101을 언급만 한다. 커버리지가 되면 안 된다."""\n    assert True\n' >> tests/test_domain_ledger.py ;;
    M-06) # G2 — 화해가 assumed를 덮게 한다 (REQ-204)
      backup src/fleet_ledger/domain/entry.py
      perl -0pi -e 's/            measured=measured,/            measured=measured,\n            assumed=measured,/' src/fleet_ledger/domain/entry.py ;;
    M-07) # G3 — method↔verifiability 매핑을 깬다 (REQ-203)
      backup src/fleet_ledger/domain/attribution.py
      perl -0pi -e 's/Method\.TOKEN_METER: Verifiability\.ASSUMED_ONLY,/Method.TOKEN_METER: Verifiability.RECONCILABLE,/' src/fleet_ledger/domain/attribution.py ;;
    M-08) # G7 — 같은 id로 덮어쓰기를 허용한다 (REQ-201)
      backup src/fleet_ledger/domain/entry.py
      perl -0pi -e 's/^        if entry\.entry_id in self\._rows:$/        if False:/m' src/fleet_ledger/domain/entry.py ;;
    M-09) # REQ-202 — 수량·단가 키 일치 검사를 없앤다
      backup src/fleet_ledger/domain/cost.py
      perl -0pi -e 's/set\(self\.inputs\) != set\(self\.unit_prices\)/False/' src/fleet_ledger/domain/cost.py ;;
    *) echo "알 수 없는 변이: $1" >&2; exit 2 ;;
  esac
}

one() {
  echo "── $1 ──"
  TOUCHED=()
  baseline
  apply "$1"
  if run_suite; then
    echo "  ❌ 변이 후에도 초록 — 이 가드는 하중을 안 받는다 ($LAST_SUMMARY)"; VERDICT=fail
  else
    echo "  ✅ red — 가드가 하중을 받는다 ($LAST_SUMMARY)"; VERDICT=ok
  fi
  restore
  # ⑤ 초록으로 안 돌아오는 복구는 복구가 아니다.
  if run_suite; then echo "  ✅ 복구 후 초록 ($LAST_SUMMARY)"
  else echo "  ❌ 복구했는데 red다 — 복구가 안 됐다"; VERDICT=fail; fi
  # ⑥ 변이 대상 파일만 본다. 신규 untracked 파일은 이 검사의 대상이 아니다.
  local dirty; dirty="$(residue)"
  if [ -n "$dirty" ]; then echo "  ❌ 변이 잔여가 남았다:$dirty"; VERDICT=fail
  else echo "  ✅ 잔여 없음 (백업 대조)"; fi
  [ "$VERDICT" = ok ] || RESULT=1
}

if [ "$MUT" = "all" ]; then for m in M-01 M-02 M-03 M-04 M-05 M-06 M-07 M-08 M-09; do one "$m"; done; else one "$MUT"; fi
exit $RESULT
