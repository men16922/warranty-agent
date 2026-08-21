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

MUT="${1:?사용법: scripts/mutate.sh <M-01..M-45|all>}"
BACKUP="$(mktemp -d)"          # ⚠️ git checkout이 아니라 디스크 백업 — 커밋 안 된 고침을 안 날린다
PYTEST=".venv/bin/pytest"
TOUCHED=()                     # 이번 변이가 건드린 파일만 추적한다
REPO="$PWD"

# ⚠️ stale .pyc가 복구를 무효로 만든다. 소스는 되돌아왔는데 테스트가 옛 코드를 보고
#    red가 유지되어 "복구 실패"로 읽혔다 — 하네스 자신의 세 번째 결함이었다.
export PYTHONDONTWRITEBYTECODE=1

trap 'restore' EXIT

backup() {
  # ⚠️ 없는 파일을 조용히 넘기면 변이가 적용되지 않은 채 "가드가 하중을 안 받는다"로 읽힌다.
  #    실제로 났다 — 프로젝트 이름을 바꾸고 이 스크립트의 경로를 안 고쳤을 때(#8).
  if [ ! -f "$1" ]; then
    echo "  ❌ 변이 대상이 없다: $1 — 이 결과는 가드에 대한 판정이 아니다" >&2
    RESULT=1; return 1
  fi
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
      backup specs/warranty/requirements.md
      perl -0pi -e 's/^상태: `TODO`\n//m' specs/warranty/requirements.md ;;
    M-02) # REQ 하나를 IMPLEMENTED로 올리고 테스트는 안 만든다
      backup specs/warranty/requirements.md
      perl -0pi -e 's/^상태: `TODO`$/상태: `IMPLEMENTED`/m' specs/warranty/requirements.md ;;
    M-03) # 파서를 깨 0개를 읽게 한다 (공허 통과 방지가 사는지)
      backup tools/spec_trace.py
      perl -0pi -e 's/\^### \(REQ-\\d\{3\}\)/^#### (REQ-\\d{3})/' tools/spec_trace.py ;;
    M-04) # 정의 없는 REQ-999를 tasks.md가 가리키게 한다
      backup specs/warranty/tasks.md
      printf '\n- [ ] **T9-9** 없는 요구사항 · `Implements: REQ-999`\n' >> specs/warranty/tasks.md ;;
    M-05) # 산문 언급만으로는 커버리지가 되면 안 된다 (스캐너가 AST를 쓰는지)
      backup specs/warranty/requirements.md; backup tests/test_domain_ledger.py
      perl -0pi -e 's/^### REQ-101(.*?)^상태: `TODO`$/### REQ-101$1상태: `IMPLEMENTED`/sm' specs/warranty/requirements.md
      printf '\n\ndef test_mentions_but_does_not_verify() -> None:\n    """이 테스트는 REQ-101을 언급만 한다. 커버리지가 되면 안 된다."""\n    assert True\n' >> tests/test_domain_ledger.py ;;
    M-06) # G2 — 화해가 assumed를 덮게 한다 (REQ-505)
      backup src/warranty/domain/entry.py
      perl -0pi -e 's/            measured=measured,/            measured=measured,\n            assumed=measured,/' src/warranty/domain/entry.py ;;
    M-07) # G3 — method↔verifiability 매핑을 깬다 (REQ-504)
      backup src/warranty/domain/attribution.py
      perl -0pi -e 's/Method\.TOKEN_METER: Verifiability\.ASSUMED_ONLY,/Method.TOKEN_METER: Verifiability.RECONCILABLE,/' src/warranty/domain/attribution.py ;;
    M-08) # G7 — 같은 id로 덮어쓰기를 허용한다 (REQ-501)
      backup src/warranty/domain/entry.py
      perl -0pi -e 's/^        if entry\.entry_id in self\._rows:$/        if False:/m' src/warranty/domain/entry.py ;;
    M-09) # REQ-503 — 수량·단가 키 일치 검사를 없앤다
      backup src/warranty/domain/cost.py
      perl -0pi -e 's/set\(self\.inputs\) != set\(self\.unit_prices\)/False/' src/warranty/domain/cost.py ;;
    M-10) # 설정이 ADK 프로젝트 불일치를 그냥 넘기게 한다
      backup src/warranty/config.py
      perl -0pi -e 's/if adk_project and adk_project != project_id:/if False:/' src/warranty/config.py ;;
    M-11) # 어댑터 기본값을 fake로 바꾼다 (배포가 조용히 가짜로 도는 경로)
      backup src/warranty/config.py
      perl -0pi -e 's/env\.get\("WR_ADAPTERS", "live"\)/env.get("WR_ADAPTERS", "fake")/' src/warranty/config.py ;;
    M-12) # 설정이 environ을 줘도 .env를 함께 읽게 되돌린다 (결정론 회귀)
      backup src/warranty/config.py
      perl -0pi -e 's/        env = \{k: v for k, v in environ\.items\(\) if v\}/        env = dict(load_env_file()); env.update({k: v for k, v in environ.items() if v})/' src/warranty/config.py ;;
    M-13) # G8 — improved를 검증 없이도 참으로 (조용한 성공)
      backup src/warranty/domain/entry.py
      perl -0pi -e 's/return self\.verification is not None and self\.verification\.verdict is Verdict\.RECOVERED/return self.status is Status.EXECUTED/' src/warranty/domain/entry.py ;;
    M-14) # G9 — 검증 가능성 축을 없앤다 (정책 제거)
      backup src/warranty/domain/decision.py
      perl -0pi -e 's/    if not verifiable:/    if False:/' src/warranty/domain/decision.py ;;
    M-15) # REQ-102 — 가역인데 롤백 계획 없는 계약을 허용
      backup src/warranty/domain/contract.py
      perl -0pi -e 's/if self\.reversibility is Reversibility\.REVERSIBLE and self\.rollback_plan is None:/if False:/' src/warranty/domain/contract.py ;;
    M-16) # REQ-205 — 빈 창을 회복으로 판정 (거짓 판정)
      backup src/warranty/domain/verification.py
      perl -0pi -e 's/        return Verdict\.UNVERIFIABLE\n\n    assert/        return Verdict.RECOVERED\n\n    assert/' src/warranty/domain/verification.py ;;
    M-17) # REQ-406 — 파괴적 조치의 강제 승인을 없앤다
      backup src/warranty/domain/decision.py
      perl -0pi -e 's/    if destructive:/    if False:/' src/warranty/domain/decision.py ;;
    M-18) # G1 — 막는 판정인데도 실행기를 부른다
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/decision\.verdict in BLOCKING or //' src/warranty/usecases/remediate.py ;;
    M-19) # G4 — 판정 없는 항목을 만든다
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/            decision=decision,  # I-4/            decision=None,  # I-4/' src/warranty/usecases/remediate.py ;;
    M-20) # REQ-303 — 트래픽을 다시 읽지 않고 성공했다고 가정한다 (주장 ↔ 측정)
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/        traffic = dict\(self\.run\.read_traffic\(resource\)\)/        traffic = {plan.previous_revision: 100}/' src/warranty/usecases/remediate.py ;;
    M-21) # REQ-304 — 롤백 후 재측정을 건너뛴다
      backup src/warranty/usecases/remediate.py
      # ⚠️ 패턴은 **포맷에 안 흔들리는 조각**을 고른다. 첫 판은 여러 줄 표현식을 통째로
      #    잡으려다 ruff format이 접자마자 안 맞았고, 무변경 탐지가 그걸 잡았다.
      perl -0pi -e 's/else _within\(restored_m, baseline\)/else None/' src/warranty/usecases/remediate.py ;;
    M-22) # REQ-204 — 명확한 경우에도 모델을 부른다 (판정이 비결정적이 된다)
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/        if verdict is Verdict\.AMBIGUOUS:/        if True:/' src/warranty/usecases/remediate.py ;;
    M-23) # G6④ — `Spec:`가 없는 설계 문서를 가리키게 한다 (이름 변경 때 실제로 난 썩음)
      backup src/warranty/domain/contract.py
      perl -0pi -e 's|design/01-operational-contract\.md|design/99-nonexistent.md|' src/warranty/domain/contract.py ;;
    M-24) # G6④ — `Spec:`가 정의 없는 REQ를 인용하게 한다
      backup src/warranty/ports.py
      perl -0pi -e 's/REQ-801, REQ-802/REQ-801, REQ-999/' src/warranty/ports.py ;;
    M-25) # G6④ 공허 통과 방지 — 스캐너가 `Spec:`를 하나도 못 읽게 한다
      backup tools/spec_trace.py
      perl -0pi -e 's/r"\^Spec:/r"^NotSpec:/' tools/spec_trace.py ;;
    M-26) # REQ-404 — 승인 대기 항목을 **승인 없이** 실행한다 (승인이 장식이 된다)
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/ or decision\.verdict is Gate\.APPROVE//' src/warranty/usecases/remediate.py ;;
    M-27) # REQ-404 — 승인이 게이트를 **면제**하게 한다 (재판정 결과를 안 본다)
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/        if redecision\.verdict in BLOCKING:/        if False:/' src/warranty/usecases/remediate.py ;;
    M-28) # REQ-405 — 예약이 여유를 **안 붙잡는다** (예약이 commit의 다른 이름이 된다)
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/self\.budgets\.reserve\(agent_id, projected_usd\)/self.budgets.reserve(agent_id, Decimal(0))/' src/warranty/usecases/remediate.py ;;
    M-29) # REQ-405 — 정산을 건너뛴다 (예약이 안 풀려 예산이 **조용히 잠긴다**)
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^            self\.budgets\.settle\(reservation, actual\)$/            pass/m' src/warranty/usecases/remediate.py ;;
    M-30) # REQ-508 — 회복률의 분자를 `executed`로 센다 (★ 헤드라인이 늘 100%가 된다)
      backup src/warranty/domain/report.py
      perl -0pi -e 's/improved=sum\(1 for row in executed if row\.improved\)/improved=len(executed)/' src/warranty/domain/report.py ;;
    M-31) # REQ-508 — 낭비 비용이 회복 여부를 안 본다 ("쓴 돈 전부"가 되어 아무것도 안 말한다)
      backup src/warranty/domain/report.py
      perl -0pi -e 's/wasted = tuple\(row for row in executed if not row\.improved\)/wasted = executed/' src/warranty/domain/report.py ;;
    M-32) # REQ-305 — 에스컬레이션을 `rolled_back`의 **부정**으로 센다 (회복된 조치가 전부 잡힌다)
      backup src/warranty/domain/entry.py
      perl -0pi -e 's/return self\.rollback is not None and not self\.rollback\.performed/return not self.rolled_back/' src/warranty/domain/entry.py ;;
    M-33) # REQ-603 — 모델 호출이 원장에 **안 남는다** (호출은 있었는데 지출이 없다)
      backup src/warranty/usecases/meter.py
      perl -0pi -e 's/        finally:\n            self\._record\(action_id, usage\)/        finally:\n            pass/' src/warranty/usecases/meter.py ;;
    M-34) # REQ-508 — 리포트가 모델 호출 행을 **조치로 센다** (★ 모델을 쓸수록 회복률이 나빠진다)
      backup src/warranty/domain/report.py
      perl -0pi -e 's/ if row\.kind is EntryKind\.ACTION//' src/warranty/domain/report.py ;;
    M-35) # REQ-504 — 단가를 모르는 호출을 `token_meter` + 0원으로 적는다 ("계량했는데 공짜였다")
      backup src/warranty/usecases/meter.py
      perl -0pi -e 's/return Attribution\(Method\.NONE, reason=str\(exc\)\), zero/return Attribution(Method.TOKEN_METER), zero/' src/warranty/usecases/meter.py ;;
    M-36) # REQ-603 — 호출이 예외로 끝나면 행을 안 남긴다 (실패했는데 나간 토큰이 사라진다)
      backup src/warranty/usecases/meter.py
      perl -0pi -e 's/        finally:\n            self\._record\(action_id, usage\)/        except Exception:\n            raise\n        else:\n            self._record(action_id, usage)/' src/warranty/usecases/meter.py ;;
    M-37) # REQ-803 — 데모가 **살아 있는 시계**를 쓴다 (재현이 아니라 실행이 된다)
      backup src/warranty/demo.py
      perl -0pi -e 's/clock = FrozenClock\(DEMO_CLOCK_ISO\)/clock = FrozenClock(datetime.now().astimezone().isoformat())/' src/warranty/demo.py ;;
    M-38) # REQ-803 — 렌더가 **사전 순서**에 기댄다 (프로세스마다 다른 문자열이 될 수 있다)
      backup src/warranty/demo.py
      perl -0pi -e 's/for key in sorted\(step\.detail\)/for key in step.detail/' src/warranty/demo.py ;;
    M-39) # REQ-303 — 데모의 조치가 트래픽을 **안 옮긴다** (롤백의 배분 재확인이 공허해진다)
      backup src/warranty/demo.py
      perl -0pi -e 's/^        self\.run\.shift_all_traffic\(resource, self\.revision\)$/        pass/m' src/warranty/demo.py ;;
    M-40) # REQ-803 — 화면의 재측정값을 **보기 좋게 손본다** (판정과 숫자가 어긋난다)
      backup src/warranty/demo.py
      perl -0pi -e 's/"after_p95_ms": "·" if after is None else str\(after\.value\),/"after_p95_ms": "120",/' src/warranty/demo.py ;;
    M-41) # REQ-803 — 데모가 **증명하지 않는 것**을 말하지 않는다 (fake 초록이 실물로 읽힌다)
      backup src/warranty/demo.py
      perl -0pi -e 's/^        caveats=CAVEATS,$/        caveats=(),/m' src/warranty/demo.py ;;
    M-42) # REQ-804 — 대기 상수를 **두 번째 자리**에 다시 정의한다 (재촬영 때 한쪽만 바뀐다)
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^from warranty\.tunables import VERIFY_DELAY_S$/from warranty.tunables import VERIFY_DELAY_S\nVERIFY_DELAY_S = 45/m' src/warranty/usecases/remediate.py ;;
    M-43) # REQ-804 — 설계가 선언한 손잡이 하나를 코드에서 뺀다 (촬영 당일에야 없는 걸 안다)
      backup src/warranty/tunables.py
      perl -0pi -e 's/^WARMUP_REQUESTS = 1$/WARMUP_REQUESTS_UNUSED = 1/m' src/warranty/tunables.py ;;
    M-44) # REQ-206 — 호출부에 대기 초를 **박는다** (tunables를 고쳐도 이 자리는 안 바뀐다)
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^        self\.clock\.sleep\(VERIFY_DELAY_S\)$/        self.clock.sleep(45)/m' src/warranty/usecases/remediate.py ;;
    M-45) # REQ-804 — 스캔 경로를 틀리게 한다 (0개를 훑고 산재 검사가 전부 초록이 된다)
      backup tests/test_tunables.py
      perl -0pi -e 's|^SRC = ROOT / "src" / "warranty"$|SRC = ROOT / "src" / "warrantee"|m' tests/test_tunables.py ;;
    *) echo "알 수 없는 변이: $1" >&2; exit 2 ;;
  esac
}

one() {
  echo "── $1 ──"
  TOUCHED=()
  baseline
  apply "$1" || { echo "  ⛔ 변이를 적용하지 못했다 — 건너뛴다"; restore; return; }
  # ⚠️ 파일은 있는데 패턴이 안 맞아 **조용히 무효**인 변이가 있다. 실제로 났다 —
  #    설정 변수 접두사를 바꾼 뒤 이 스크립트의 패턴을 안 고쳤을 때.
  #    적용되지 않은 변이의 초록은 가드에 대한 판정이 아니다.
  if [ -z "$(residue)" ]; then
    echo "  ⛔ 변이가 파일을 바꾸지 못했다 (패턴 불일치) — 이 결과는 판정이 아니다"
    RESULT=1; restore; return
  fi
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

if [ "$MUT" = "all" ]; then for m in M-01 M-02 M-03 M-04 M-05 M-06 M-07 M-08 M-09 M-10 M-11 M-12 M-13 M-14 M-15 M-16 M-17 M-18 M-19 M-20 M-21 M-22 M-23 M-24 M-25 M-26 M-27 M-28 M-29 M-30 M-31 M-32 M-33 M-34 M-35 M-36 M-37 M-38 M-39 M-40 M-41 M-42 M-43 M-44 M-45; do one "$m"; done; else one "$MUT"; fi
exit $RESULT
