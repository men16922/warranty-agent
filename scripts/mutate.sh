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

MUT="${1:?사용법: scripts/mutate.sh <M-01..M-158|all>}"
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
    M-46) # REQ-803 — Makefile의 demo 레시피에서 PYTHONPATH를 뺀다
           # (선언된 진입점이 죽어도 main()을 직접 부르는 테스트는 초록이던 자리)
      backup Makefile
      perl -0pi -e 's|^\tPYTHONPATH=src \$\(PY\) -m warranty\.demo$|\t$(PY) -m warranty.demo|m' Makefile ;;
    M-47) # 최신 스윕이 선언한 기준선을 어긋나게 한다 (기록이 옛 스위트를 보고 적힌 상태)
           # ⚠️ 앞의 `.*`는 탐욕적이다 — **마지막** 스윕 절을 잡기 위해서다.
           #    현재를 주장하는 절은 그 하나뿐이고, 앞선 절들은 역사라 건드리면 안 된다.
      backup docs/evidence/mutations.md
      perl -0pi -e 's/(.*## 전체 스윕[^\n]*기준선 \*\*)\d+( passed)/${1}999${2}/s' docs/evidence/mutations.md ;;
    M-48) # 공허 통과 방지 — 가드가 스윕 절을 하나도 못 찾게 한다 (0개를 읽고 초록이 되는 경로)
      backup tests/test_mutation_freshness.py
      perl -0pi -e 's/^SWEEP_HEADING = "## 전체 스윕"$/SWEEP_HEADING = "## 전체 스윕이 아닌 표제"/m' tests/test_mutation_freshness.py ;;
    M-49) # `all` 목록에서 마지막 변이를 뺀다 (기록은 N종이라는데 스윕은 N-1건만 돈다)
           # ⚠️ `\d+`다. `\d\d`였을 때 M-100이 생기면 **패턴이 안 맞아 조용히 무효**가 됐다 —
           #    그 결과는 가드에 대한 판정이 아니라 하네스가 자기 자신을 못 깬 것이다(T11-3).
      backup scripts/mutate.sh
      perl -0pi -e 's/(for m in .*) M-\d+;/${1};/' scripts/mutate.sh ;;
    M-50) # REQ-206 — 대기 초를 **함수 안의 지역 이름**에 담아 쓴다 (T0-10 · M-44가 못 잡는 우회)
           # ⚠️ 최상위 상수도 아니고 리터럴도 아니다 — M-42·M-44 둘 다 통과한다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^        self\.clock\.sleep\(VERIFY_DELAY_S\)$/        delay_s = 45\n        self.clock.sleep(delay_s)/m' src/warranty/usecases/remediate.py ;;
    M-51) # REQ-508 — 설계가 리포트 칸의 **이름을 바꾼다** (T0-10: 손으로 베낀 목록은 안 따라온다)
      backup specs/warranty/design/05-accountability-ledger.md
      perl -0pi -e 's/"model_decided": 5/"model_decided_count": 5/' specs/warranty/design/05-accountability-ledger.md ;;
    M-52) # REQ-803 — 설계에서 데모 단계 하나를 **없앤다** (T0-10: 사본은 안 줄고 초록이던 자리)
      backup specs/warranty/design/11-demo.md
      perl -0pi -e 's/^   ④ remediate #2[^\n]*\n//m' specs/warranty/design/11-demo.md ;;
    M-53) # REQ-103 — `resource_filter`를 응답의 이름이 아니라 **박은 문자열**로 한다
           # (T3-2: 데모 이름과 우연히 같아서 값만 보는 테스트로는 안 잡히던 자리)
      backup src/warranty/usecases/provision.py
      perl -0pi -e 's/^            resource_filter=response\.name,[^\n]*$/            resource_filter="demo-target",/m' src/warranty/usecases/provision.py ;;
    M-54) # REQ-103 — 유도되는 자리를 **인자로 다시 연다** (계약이 선언으로 되돌아가는 경로)
           # ⚠️ 값은 하나도 안 바뀐다 — 구문으로 묻지 않으면 이 변이는 전부 초록이다.
      backup src/warranty/usecases/provision.py
      perl -0pi -e 's/^    recovery_criterion: Criterion,$/    recovery_criterion: Criterion,\n    previous_revision: str | None = None,/m' src/warranty/usecases/provision.py ;;
    M-55) # REQ-103 — 설계의 유도 표에서 **한 행을 지운다** (금지 집합이 조용히 줄어드는 경로)
      backup specs/warranty/design/01-operational-contract.md
      perl -0pi -e 's/^\| `reversibility` \|[^\n]*\n//m' specs/warranty/design/01-operational-contract.md ;;
    M-56) # REQ-103 — 가역성을 **리소스 타입만 보고** 정한다 (돌아갈 자리가 없어도 가역)
      backup src/warranty/usecases/provision.py
      perl -0pi -e 's/Reversibility\.IRREVERSIBLE if rollback_plan is None else Reversibility\.REVERSIBLE/Reversibility.REVERSIBLE/' src/warranty/usecases/provision.py ;;
    M-57) # REQ-201 — 기준선을 **조치 뒤에** 잰다 (T9-1: 값은 하나도 안 바뀐다)
           # ⚠️ 각본 신호는 순서대로 같은 값을 돌려준다 — 기준선/재측정의 **값도 판정도 그대로**다.
           #    바뀌는 것은 그 값이 무엇의 기준선인가뿐이고, 그 어긋남은 값으로 안 보인다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^            baseline = self\.signals\.read\(contract\.health_signal\)\n//m' src/warranty/usecases/remediate.py
      perl -0pi -e 's/^            actual = projected_usd$/            actual = projected_usd\n            baseline = self.signals.read(contract.health_signal)/m' src/warranty/usecases/remediate.py ;;
    M-58) # REQ-202 — 재측정이 **자기 질의를 새로 만든다** (같은 값, 다른 스펙 객체)
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^            after = self\.signals\.read\(contract\.health_signal\)$/            spec = contract.health_signal\n            after = self.signals.read(\n                SignalSpec(\n                    spec.metric_type, spec.resource_filter, spec.aggregation, spec.window_s\n                )\n            )/m' src/warranty/usecases/remediate.py
      perl -0pi -e 's/^    RollbackPlan,$/    RollbackPlan,\n    SignalSpec,/m' src/warranty/usecases/remediate.py ;;
    M-59) # REQ-203 — 판정 기준을 **조치가 들고 있다** (계약의 기준과 값이 같아 값으로는 안 보인다)
           # ⚠️ M-54 계열 — 계약을 바꿔도 이 자리는 안 바뀐다. 그때 모든 조치가 자기 기준으로 성공한다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^            verdict = classify\(baseline, after, contract\.recovery_criterion\)$/            verdict = classify(baseline, after, _ACTION_CRITERION)/m' src/warranty/usecases/remediate.py
      perl -0pi -e 's/^from warranty\.tunables import VERIFY_DELAY_S$/from warranty.tunables import VERIFY_DELAY_S\n\n_ACTION_CRITERION = Criterion(Direction.DECREASE, Decimal("0.5"), CriterionMode.RELATIVE, Decimal("0.1"))/m' src/warranty/usecases/remediate.py
      perl -0pi -e 's/^from warranty\.domain\.contract import \($/from warranty.domain.contract import (\n    Criterion,\n    CriterionMode,\n    Direction,/m' src/warranty/usecases/remediate.py ;;
    M-60) # REQ-301 — 롤백 계획을 **조치 뒤에** 읽는다 (T9-2: 값은 하나도 안 바뀐다)
           # ⚠️ 계약은 루프 시작에 한 번 읽은 얼어붙은 값이라 계획도 판정도 전환 대상도 그대로다.
           #    바뀌는 것은 *"그 계획이 조치 전에 고정됐는가"*뿐이고, 그 어긋남은 값으로 안 보인다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^            plan = contract\.rollback_plan\n//m' src/warranty/usecases/remediate.py
      perl -0pi -e 's/^            actual = projected_usd$/            actual = projected_usd\n            plan = contract.rollback_plan/m' src/warranty/usecases/remediate.py ;;
    M-61) # REQ-301 — 롤백 계획을 **계약 저장소에서 다시 읽는다** (조치가 바꾼 세상에서 온다)
           # ⚠️ 값은 여전히 같다 — fake 저장소가 같은 계약을 돌려주니까. 늘어나는 것은 조회 횟수뿐이다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^            plan = contract\.rollback_plan\n//m' src/warranty/usecases/remediate.py
      perl -0pi -e 's/^            actual = projected_usd$/            actual = projected_usd\n            fresh = self.contracts.active_for(resource)\n            plan = None if fresh is None else fresh.rollback_plan/m' src/warranty/usecases/remediate.py ;;
    M-62) # REQ-302 — **모델이 닫은** 미회복은 롤백하지 않는다 (규칙이 닫은 경우만 되돌린다)
           # ⚠️ 롤백이 사라지는 구간이 하필 판단이 애매한 구간과 겹친다. 원장은 똑같아 보인다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^            if verdict is Verdict\.RECOVERED:$/            if verdict is Verdict.RECOVERED or decided_by is DecidedBy.MODEL:/m' src/warranty/usecases/remediate.py ;;
    M-63) # REQ-104 — 계약이 **없는 것**을 검증 가능으로 친다 (없음은 못 읽음보다 약한 결격이 된다)
           # ⚠️ 원장의 `status`는 그대로 `manual_required`다 — 아래 한 줄이 따로 덮으니까.
           #    바뀌는 것은 **판정과 그 사유**뿐이고, 상태만 보는 자리에서는 안 보인다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/contract is not None and self\.signals\.readable\(contract\.health_signal\)/contract is None or self.signals.readable(contract.health_signal)/g' src/warranty/usecases/remediate.py ;;
    M-64) # REQ-104 — 계약 없음을 **게이트 결과에 맡긴다** (전용 분기를 지운다)
           # ⚠️ 여유가 있으면 게이트도 `MANUAL`을 내므로 **값이 똑같다.** 갈라지는 것은
           #    예산이 마른 경우 하나뿐이고, 그때 원장은 *"계약이 없었다"*를 말하지 않는다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^        status = Status\.MANUAL_REQUIRED if contract is None else _status_for\(decision\.verdict\)$/        status = _status_for(decision.verdict)/m' src/warranty/usecases/remediate.py ;;
    M-65) # REQ-105 — 저장소가 **`retired` 계약도 돌려준다** (수명을 거른다는 약속을 지운다)
           # ⚠️ 계약 객체의 값은 그대로다. 사라지는 것은 *"죽은 계약은 조회에 안 걸린다"*뿐이다.
      backup src/warranty/adapters/fakes.py
      perl -0pi -e 's/^        return found if found is not None and found\.is_active else None$/        return found/m' src/warranty/adapters/fakes.py ;;
    M-66) # REQ-105 — 종료해도 **상태가 `active`로 남는다** (종료가 이름만 있는 동작이 된다)
      backup src/warranty/domain/contract.py
      perl -0pi -e 's/^        return replace\(self, state=ContractState\.RETIRED\)$/        return replace(self, state=ContractState.ACTIVE)/m' src/warranty/domain/contract.py ;;
    M-67) # REQ-507 — 막는 판정에는 **행을 안 만든다** (원장이 실행된 것만 센다)
           # ⚠️ 반환값은 그대로 `LedgerEntry`고 상태도 `denied`/`manual_required` 그대로다.
           #    사라지는 것은 **원장에 남았는가**뿐이고, 반환만 보는 자리에서는 안 보인다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^        self\.ledger\.create\(entry\)\n\n//m' src/warranty/usecases/remediate.py
      perl -0pi -e 's/^        return self\._execute_and_verify\(\n            entry_id=entry_id,\n            agent_id=agent_id,/        self.ledger.create(entry)\n        return self._execute_and_verify(\n            entry_id=entry_id,\n            agent_id=agent_id,/m' src/warranty/usecases/remediate.py ;;
    M-68) # REQ-507 — **예약이 막은 것**을 원장에 안 적는다 (행은 `executed`로 남는다)
           # ⚠️ 게이트가 여유를 읽은 뒤 다른 조치가 다 가져간 경우다. 실행기는 안 불렸는데
           #    원장은 *"실행했다"*고 말하고, 그 거짓말은 리포트의 분모에 실린다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^        if reservation is None:\n            return self\.ledger\.complete\(entry_id, status=Status\.DENIED\)$/        if reservation is None:\n            stale = self.ledger.get(entry_id)\n            assert stale is not None\n            return stale/m' src/warranty/usecases/remediate.py ;;
    M-69) # REQ-507 — 실패한 조치를 **`executed`로 적는다** (실패가 원장에서 사라진다)
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/status=Status\.FAILED/status=Status.EXECUTED/' src/warranty/usecases/remediate.py ;;
    M-70) # REQ-506 — 화해가 **멱등이 아니다** (두 번째 청구 행이 첫 번째를 덮는다)
           # ⚠️ `assumed`는 그대로라 G2는 초록이다. 바뀌는 것은 **재실행이 같은 값을 내는가**뿐.
      backup src/warranty/domain/entry.py
      perl -0pi -e 's/^        if current\.reconcile_state is ReconcileState\.RECONCILED:\n            return current.*\n//m' src/warranty/domain/entry.py ;;
    M-71) # REQ-506 — **실측의 근거를 안 묻는다** (추정치가 실측 칸에 들어온다)
           # ⚠️ 값은 들어오고 delta도 파생된다. 사라지는 것은 *"이 숫자를 청구서가 말했는가"*뿐이고,
           #    그 뒤로 `assumed`와 `measured`는 같은 계산의 두 벌이 된다 (REQ-503의 구분이 죽는다).
      backup src/warranty/domain/entry.py
      perl -0pi -e 's/^        if measured\.basis is not Basis\.BILLING_EXPORT:\n            raise LedgerError\(f"measured의 근거가 청구서가 아니다: \{measured\.basis\}"\)\n//m' src/warranty/domain/entry.py ;;
    M-72) # REQ-509 — 추정이 0인데 **배율을 0으로 낸다** (정의되지 않음이 값이 된다)
           # ⚠️ 예외도 안 나고 차액도 맞다. 거부된 항목(assumed=0)의 배율이 *"0배"*로 읽힐 뿐이다.
      backup src/warranty/domain/cost.py
      perl -0pi -e 's/^        return Delta\(amount, None, "assumed가 0이라 배율이 정의되지 않는다"\)$/        return Delta(amount, Decimal(0))/m' src/warranty/domain/cost.py ;;
    M-73) # REQ-509 — 화해가 **차액을 안 남긴다** (실측만 채우고 파생값은 비운다)
           # ⚠️ `measured`는 들어와 있어 화해된 것처럼 보인다. 사라지는 것은 이 프로젝트의 산출물이다.
      backup src/warranty/domain/entry.py
      perl -0pi -e 's/^            delta=delta_of\(current\.assumed, measured\),\n//m' src/warranty/domain/entry.py ;;
    M-74) # REQ-506 — **기한을 안 본다** (아직 도착할 수 있는 청구서를 두고 포기한다)
           # ⚠️ 상태·사유는 그대로 `unreconciled`+사유다. 사라지는 것은 *"기한 내"* 하나뿐이고,
           #    그 행의 비용은 청구서가 나중에 와도 **영원히 추정으로 남는다.**
      backup src/warranty/domain/entry.py
      perl -0pi -e 's/^        if at - current\.started_at < timedelta\(days=deadline_days\):\n            raise LedgerError\(\n(.*\n)*?            \)\n//m' src/warranty/domain/entry.py ;;
    M-75) # REQ-506 — 포기는 하는데 **사유를 안 적는다** (결격이 한 칸으로 뭉친다)
      backup src/warranty/domain/entry.py
      perl -0pi -e 's/^            unreconciled_reason=reason,\n//m' src/warranty/domain/entry.py ;;
    M-76) # REQ-506 — **이미 화해된 행도 뒤집는다** (실측이 추정으로 돌아간다)
           # ⚠️ `measured`는 남아 있어 값으로는 멀쩡해 보인다. 바뀌는 것은 상태와 사유뿐이다.
      backup src/warranty/domain/entry.py
      perl -0pi -e 's/^        if current\.reconcile_state is not ReconcileState\.PENDING:\n            return current.*\n//m' src/warranty/domain/entry.py ;;
    M-77) # REQ-506 — **사유 없이도 포기를 받는다** (조용한 `unreconciled`)
      backup src/warranty/domain/entry.py
      perl -0pi -e 's/^        if not reason\.strip\(\):\n            raise LedgerError\(f"unreconciled에 사유가 없다: \{entry_id\}"\)\n//m' src/warranty/domain/entry.py ;;
    M-78) # G6⑤ — 문장 단위 검사를 **통째로 지운다** (귀속이 요구사항 단위로 되돌아간다)
           # ⚠️ 나머지 넷(①~④)은 그대로 초록이다. 사라지는 것은 *"약속한 문장마다"*뿐이고,
           #    그 뒤로 셋을 약속하고 하나만 겨냥한 요구사항이 다시 통과한다 (REQ-506의 모양).
      backup tools/spec_trace.py
      perl -0pi -e 's/^    promised = len\(req\.promises\)\n    if req\.status in \(Status\.IMPLEMENTED, Status\.VERIFIED\) and len\(row\.test_funcs\) < promised:\n(.*\n)*?        \)\n//m' tools/spec_trace.py ;;
    M-79) # G6⑤ — 분리기가 **쉼표 붙은 대등 접속에서 안 자른다** (REQ-506이 한 문장이 된다)
           # ⚠️ 문장 끝 분리는 살아 있어 대부분의 요구사항은 숫자가 안 바뀐다. 조용히 사라지는
           #    것은 *"한 문장 안에 약속 셋"*을 세는 능력이고, 그게 이 규칙이 겨냥한 모양이다.
      backup tools/spec_trace.py
      perl -0pi -e 's/^CONJUNCTION_RE = re\.compile\(r"\(\?<=\[고며\]\),\(\?=\\s\)"\)$/CONJUNCTION_RE = re.compile(r"(?!x)x")/m' tools/spec_trace.py ;;
    M-80) # G6⑤ — 겨냥을 **파일 단위로** 센다 (한 파일에 몰린 열 건이 1로 읽힌다)
           # ⚠️ 파일 단위로 세면 *"문장 셋을 약속하는데 겨냥이 하나"*를 영원히 못 본다 —
           #    테스트가 대개 요구사항별로 한 파일에 모여 있기 때문이다.
      backup tools/spec_trace.py
      perl -0pi -e 's/^            site = f"\{rel\}::\{node\.name\}"$/            site = rel/m' tools/spec_trace.py ;;
    M-81) # G6⑤ — 분리기가 **늘 한 문장을 낸다** (공허 통과 방지가 사는지)
           # ⚠️ 이러면 ⑤의 판정은 전부 `1 <= N`이라 항상 초록이다. 검사는 남아 있는데
           #    아무것도 안 묻는 상태 — 바닥이 없으면 이게 가장 조용한 실패다.
      backup tools/spec_trace.py
      perl -0pi -e 's/^    for pattern in \(SENTENCE_END_RE, CONJUNCTION_RE\):$/    for pattern in ():/m' tools/spec_trace.py ;;
    M-82) # REQ-501 — 저장이 **`retry_of`를 흘린다** (재시도가 원래를 못 가리킨다)
           # ⚠️ 행 수는 그대로 둘이다. 끊기는 것은 포인터뿐이고, 그때 원장은 같은 사건의
           #    두 시도를 **무관한 조치 둘로** 세어 회복률의 분모에 각각 싣는다.
           #    ⛔ 합쳐져 있던 테스트는 이 변이에 **초록이었다** — 행 수만 물었기 때문이다.
      backup src/warranty/domain/entry.py
      perl -0pi -e 's/^        self\._rows\[entry\.entry_id\] = entry$/        self._rows[entry.entry_id] = replace(entry, retry_of=None)/m' src/warranty/domain/entry.py ;;
    M-83) # REQ-305 — 롤백이 실패하면 **조치를 다시 해 본다** (더 조치하지 않는다가 죽는다)
           # ⚠️ 원장의 `rollback` 칸은 **한 글자도 안 바뀐다** — 되돌리기는 여전히 실패로
           #    남고 `escalated`도 그대로다. 늘어나는 것은 호출 횟수뿐이고, 그게 정확히
           #    *"실패한 자동화가 계속 시도하는"* 상태다. 값으로는 안 보인다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^            rollback = self\._rollback\(contract, resource, plan, baseline, verification\)$/            rollback = self._rollback(contract, resource, plan, baseline, verification)\n            if not rollback.performed:\n                self.executor.execute(action_id, resource)/m' src/warranty/usecases/remediate.py ;;
    M-84) # REQ-305 — 되돌릴 **계획이 없는데 롤백을 성공으로 적는다**
           # ⚠️ 사유 문자열은 그대로 `escalated`라고 말한다. 뒤집히는 것은 `performed`
           #    하나뿐이고, 그 순간 `escalated`는 False가 되고 `rolled_back`이 True가 된다 —
           #    **트래픽은 건드리지도 않았는데** 리포트가 되돌렸다고 센다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^            return Rollback\(performed=False, reason="irreversible or no rollback plan — escalated"\)$/            return Rollback(performed=True, reason="irreversible or no rollback plan — escalated")/m' src/warranty/usecases/remediate.py ;;
    M-85) # REQ-802 — 항목의 시각을 **주입된 시계가 아니라 살아 있는 시계**에서 읽는다
           # ⚠️ 예외도 안 나고 값도 그럴듯하다. 갈라지는 것은 **같은 입력의 두 실행**뿐이라
           #    한 번만 돌려 보는 테스트는 전부 초록이다 — 그래서 데모를 두 번 돌린다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^        started = datetime\.fromisoformat\(self\.clock\.now_iso\(\)\)$/        started = datetime.now().astimezone()/m' src/warranty/usecases/remediate.py ;;
    M-86) # REQ-802 — 항목 id를 **주입된 생성기가 아니라 난수**에서 만든다
           # ⚠️ 원장은 여전히 1회=1행이고 id는 유일하다(REQ-501은 초록이다). 사라지는 것은
           #    *"같은 서사가 같은 바이트를 낸다"*뿐이고, 그게 촬영·회귀 비교의 전제다.
      backup src/warranty/usecases/remediate.py
      perl -0pi -e 's/^from dataclasses import dataclass$/import uuid\nfrom dataclasses import dataclass/m' src/warranty/usecases/remediate.py
      perl -0pi -e 's/^        entry_id = self\.ids\.new_entry_id\(\)$/        entry_id = uuid.uuid4().hex/m' src/warranty/usecases/remediate.py ;;
    M-87) # T11-1 — 배포 스크립트가 config가 소유한 값을 **다시 적는다** (사본이 생긴다)
           # ⚠️ 렌더러는 그대로 옳게 낸다. 갈라지는 것은 *"값이 한 곳에서 오는가"*뿐이고,
           #    그 어긋남은 **배포가 성공할 때까지 안 보인다** — 그리고 배포는 게이트에 없다.
      backup scripts/deploy.sh
      printf '\necho "서비스: warranty-api · 리전: us-central1 · --min-instances=1"\n' >> scripts/deploy.sh ;;
    M-88) # REQ-805 — 상시 인스턴스를 하나 띄운다 (설계가 0이라고 적은 자리)
           # ⚠️ 렌더러도 초록이다 — 렌더러는 이 상수를 **그대로** 실으니까. 갈라지는 것은
           #    설계와 코드뿐이고, 그 차이는 청구서에서 처음 보인다.
      backup src/warranty/config.py
      perl -0pi -e 's/^MIN_INSTANCES = 0$/MIN_INSTANCES = 1/m' src/warranty/config.py ;;
    M-89) # T11-1 — 이미지의 파이썬을 pyproject의 요구와 어긋나게 한다
           # ⚠️ 빌드는 성공하고 설치도 대개 성공한다. 실패는 **첫 요청**에서 난다.
      backup Dockerfile
      perl -0pi -e 's/^FROM python:3\.13-slim$/FROM python:3.12-slim/m' Dockerfile ;;
    M-90) # T11-1 — `CMD`가 **없는 모듈**을 가리킨다 (컨테이너가 뜨자마자 죽는다 · M-46 계열)
            # ⚠️ T12-1이 이 변이의 전제를 지웠다: 원래 목적지는 `warranty.server`였고 그때는
            #    **없는 모듈**이었다. 지금은 실재하고 `CMD`가 바로 그것을 가리킨다 ⇒ 패턴도
            #    안 맞고, 맞았더라도 ⑥은 초록이다. 겨냥하는 것은 이름이 아니라 **부재**다.
            # ⚠️ M-126과 다른 질문이다: 저기는 *있는데 틀린* 모듈(⑧), 여기는 *없는* 모듈(⑥).
      backup Dockerfile
      perl -0pi -e 's/"warranty\.server"\]/"warranty.ghost"]/' Dockerfile ;;
    M-91) # T11-1 — `make deploy`가 스크립트를 안 거치고 **직접** 배포한다 (두 번째 경로)
           # ⚠️ 스크립트는 그대로 있고 그대로 옳다. 아무도 안 부를 뿐이다.
      backup Makefile
      perl -0pi -e 's|^\tbash scripts/deploy\.sh --yes$|\tgcloud run deploy|m' Makefile ;;
    M-92) # REQ-805 — 렌더러가 `--min-instances`를 **아예 안 낸다** (gcloud 기본값이 이긴다)
      backup src/warranty/config.py
      perl -0pi -e 's/^        f"--min-instances=\{MIN_INSTANCES\}",\n//m' src/warranty/config.py ;;
    M-93) # T11-1 공허 통과 방지 — 산출물 목록을 비운다 (0개를 훑고 ①·③이 초록이 되는 경로)
      backup tests/test_deploy_artifacts.py
      perl -0pi -e 's/^ARTIFACTS = \(DOCKERFILE, DEPLOY_SH\)$/ARTIFACTS = ()/m' tests/test_deploy_artifacts.py ;;
    M-94) # T11-1 — 빈 태그를 그냥 받는다 (`:` 뒤가 비어 어느 리비전인지 안 말하는 주소)
      backup src/warranty/config.py
      perl -0pi -e 's/^    if not tag\.strip\(\):$/    if False:/m' src/warranty/config.py ;;
    M-95) # T11-1 — 설정 견본의 리전이 설계와 어긋난다 (처음 채우는 사람이 다른 리전에 배포한다)
           # ⚠️ 코드는 한 글자도 안 바뀐다. 리전은 상수가 아니라 `WR_REGION`이라서,
           #    견본이 틀리면 **아무 테스트도 안 태우고** 배포만 틀린 곳으로 간다.
      backup .env.example
      perl -0pi -e 's/^WR_REGION=us-central1$/WR_REGION=asia-northeast3/m' .env.example ;;
    M-96) # REQ-801 — 게이트가 **배포를 선행으로 건다** (`make check`가 과금한다)
           # ⚠️ 스윕은 `make check`가 아니라 pytest를 돌리므로 이 변이는 배포를 실행하지 않는다.
      backup Makefile
      perl -0pi -e 's/^check: lint types test trace$/check: lint types test trace deploy/m' Makefile ;;
    M-97) # REQ-805 — 설계와 코드를 **함께** 1로 바꾼다 (T11-2가 존재하는 이유)
           # ⛔ 일치 검사(test_deploy_artifacts ④)는 **초록이다** — 둘이 같으니까. 렌더러도
           #    이 상수를 그대로 실으니 ②도 초록이다. 유휴 0을 **값으로** 묻는 자리만 운다.
      backup src/warranty/config.py
      backup specs/warranty/design/10-deployment.md
      perl -0pi -e 's/^MIN_INSTANCES = 0$/MIN_INSTANCES = 1/m' src/warranty/config.py
      perl -0pi -e 's/min-instances=0/min-instances=1/' specs/warranty/design/10-deployment.md ;;
    M-98) # REQ-805 — 배포 스크립트가 **GKE 클러스터를 만든다** (노드 풀은 요청이 0이어도 돈다)
           # ⚠️ 다른 검사는 전부 초록이다. 값도 안 바뀌고 사본도 안 생긴다 — 늘어나는 것은
           #    청구서뿐이고, 배포는 게이트에 없으니 두 번째로 알아챌 경로가 없다.
      backup scripts/deploy.sh
      printf '\ngcloud container clusters create demo-cluster --num-nodes=3\n' >> scripts/deploy.sh ;;
    M-99) # REQ-805 — **설계 표**가 GKE를 구성 요소로 선언한다 (스크립트는 아직 안 따라왔다)
           # ⛔ 실행 표면 스캔은 초록이다. 사람이 먼저 고치는 자리가 설계이고, 그 상태로
           #    콘솔에서 만들면 게이트는 끝까지 아무 말도 안 한다.
      backup specs/warranty/design/10-deployment.md
      perl -0pi -e 's/^(\| Cloud Run 서비스 `warranty-api`.*\n)/$1| GKE 클러스터 `warranty-gke` | 노드 3 | 805 |\n/m' specs/warranty/design/10-deployment.md ;;
    M-100) # T11-3 — 선언에서 `google-adk`를 지운다 (**T11-3 이전의 상태 그 자체다**)
            # ⛔ REQ-601이 필수로 이름하고 design 06§2가 실물 introspect 증거까지 남긴 그 이름이
            #    `pyproject.toml`에는 없던 상태. 두 문서는 서로 완벽히 일치했다 —
            #    일치는 그것이 **설치된다**는 뜻이 아니다.
      backup pyproject.toml
      perl -0pi -e 's/^    "google-adk>=2\.7",\n//m' pyproject.toml ;;
    M-101) # T11-3 — 이미지가 **extra 없이** 설치한다 (`.[cloud]` → `.`)
            # ⛔ 선언은 멀쩡하다. 빌드도 통과한다. 클라우드 스택만 이미지에서 조용히 빠진다.
      backup Dockerfile
      perl -0pi -e 's/^RUN pip install --no-cache-dir "\.\[cloud\]"$/RUN pip install --no-cache-dir "."/m' Dockerfile ;;
    M-102) # T11-3 — `google-adk`를 cloud extra에서 `[project].dependencies`로 **옮긴다**
            # ⛔ 선언은 여전히 있다(④는 초록이다). 그런데 게이트의 `.[dev]` 설치가 그것을 끌고,
            #    fake 어댑터의 전제(REQ-801)가 깨진다. ⑤만 이 자리를 본다.
      backup pyproject.toml
      perl -0pi -e 's/^dependencies = \[\]$/dependencies = ["google-adk>=2.7"]/m; s/^    "google-adk>=2\.7",\n//m' pyproject.toml ;;
    M-103) # T11-3 — 소스가 **선언 없는** 서드파티를 임포트한다 (설치는 돼 있다: pytest의 전이 의존)
            # ⛔ 이 기계에서는 돈다. 배포 이미지는 `.[cloud]`만 설치하므로 거기서 죽고,
            #    그 죽음은 빌드가 아니라 첫 요청에서 보인다.
      backup tools/spec_trace.py
      perl -0pi -e 's/^import argparse$/import argparse\nimport pluggy/m' tools/spec_trace.py ;;
    M-104) # T11-3 — 새 배포판을 선언하고 스캐너에게는 안 가르친다
            # ⛔ ②는 아무 말도 안 한다 — 아직 아무도 임포트하지 않으니까. 처음 임포트하는 날
            #    선언은 멀쩡한데 *"선언 안 된 임포트"*로 잡힌다. ③이 선언 쪽에서 그것을 본다.
      backup pyproject.toml
      perl -0pi -e 's/^    "google-cloud-firestore>=2\.16",$/    "google-cloud-monitoring>=2.0",\n    "google-cloud-firestore>=2.16",/m' pyproject.toml ;;
    M-105) # T11-3 공허 통과 방지 — stdlib 판정을 깨서 **아무것도 서드파티로 안 잡게** 한다
            # ⛔ ②는 0건을 잡고 초록이 된다. 그 초록은 *"선언이 다 있다"*가 아니라
            #    **"아무것도 안 봤다"**이다. T11-2가 못 태우고 적어 둔 자리가 여기다.
      backup tests/test_dependency_declaration.py
      perl -0pi -e 's/^    return module\.split\("\.", 1\)\[0\] in sys\.stdlib_module_names$/    return True/m' tests/test_dependency_declaration.py ;;
    M-106) # T11-4 — 장애를 **노이즈보다 작게** 줄인다 (DEGRADED 900 → 640)
            # ⛔ 판정은 그대로 `not_recovered`다(⑤는 초록이다). 그런데 롤백 후 재측정이
            #    *"돌아왔다"*를 **되돌리지 않아도** 말하게 되고, REQ-304가 하중을 잃는다.
      backup src/warranty/demo_target.py
      perl -0pi -e 's/^DEGRADED_LATENCY_MS = 900$/DEGRADED_LATENCY_MS = 640/m' src/warranty/demo_target.py ;;
    M-107) # T11-4 — 나쁜 리비전이 **헬스 프로브에서 죽는다** (프로브 분기를 지운다)
            # ⛔ 그러면 Cloud Run이 트래픽을 안 옮긴다 — 장애 주입이 **배포 실패**가 되고
            #    데모의 절정(검증 실패 → 자동 롤백)은 한 번도 안 일어난다.
      backup src/warranty/demo_target.py
      perl -0pi -e 's/^        if path == HEALTH_PATH:\n            return Response\(OK, self\.name, 0\)\n//m' src/warranty/demo_target.py ;;
    M-108) # T11-4 — 지연을 **선언만 하고 안 쓴다** (`pause` 호출을 지운다)
            # ⛔ `Response.latency_ms`는 그대로라 **값으로는 안 보인다.** 남는 것은
            #    *"느리다고 말하는 리비전"*이고, 그건 결과를 박아 두는 것과 같은 종류다.
      backup src/warranty/demo_target.py
      perl -0pi -e 's/^        pause\(self\.work_latency_ms \/ MS_PER_SECOND\)\n//m' src/warranty/demo_target.py ;;
    M-109) # T11-4 — 장애 주입이 신호를 **좋게** 만든다 (900 → 200: 두 값을 뒤집은 모양)
            # ⚠️ 여러 자리가 함께 운다 — 장애의 **방향**은 이 저장소의 서사 전체가 기대는 값이다.
      backup src/warranty/demo_target.py
      perl -0pi -e 's/^DEGRADED_LATENCY_MS = 900$/DEGRADED_LATENCY_MS = 200/m' src/warranty/demo_target.py ;;
    M-110) # T11-4 — 데모가 기준선을 **다시 적는다** (값은 오늘 똑같다)
            # ⛔ 값 검사는 **전부 초록이다.** 갈라지는 것은 앱의 지연을 바꾸는 날이고,
            #    그때 데모는 존재하지 않는 리비전의 이야기를 한다 (T11-1·T11-3과 같은 계열).
      backup src/warranty/demo.py
      perl -0pi -e 's/^BASELINE_MS = Decimal\(HEALTHY\.work_latency_ms\)$/BASELINE_MS = Decimal("620")/m' src/warranty/demo.py ;;
    M-111) # T11-4 공허 통과 방지 — 두 리비전이 **같은 이름**을 갖는다
            # ⛔ 트래픽을 옮겨도 어디서 어디로인지가 없다. 비교할 상대가 사라지면
            #    *"차이가 없다"*와 *"안 봤다"*가 같은 초록이 된다.
      backup src/warranty/demo_target.py
      perl -0pi -e 's/-00008-slow/-00007-abc/' src/warranty/demo_target.py ;;
    M-112) # T11-4 — 모르는 경로도 **작업으로 친다** (404 분기를 지운다)
            # ⛔ 오타 하나가 장애 주입이 되고, 그 지연이 계약이 재는 신호에 그대로 실린다.
      backup src/warranty/demo_target.py
      perl -0pi -e 's/^        if path != WORK_PATH:\n            return Response\(NOT_FOUND, self\.name, 0\)\n//m' src/warranty/demo_target.py ;;
    M-113) # T11-5 — README가 **없는 타깃**을 적는다 (`make trace` → `make traceability`)
            # ⛔ 죽은 명령을 적어 둔 README는 틀린 README보다 나쁘다 — 처음 오는 사람은
            #    자기가 틀렸다고 생각하고 저장소를 닫는다. 실행해 보기 전에는 안 보인다.
      backup README.md
      perl -0pi -e 's/^make trace  /make traceability  /m' README.md ;;
    M-114) # T11-5 — Makefile에서 **타깃이 사라진다** (`demo:` → `run-demo:`)
            # ⛔ 이것이 실제로 났던 모양이다 — README는 그대로 `make demo`를 적고 있고
            #    게이트는 초록이다. 반대 방향(이름을 바꾼 쪽)에서도 같은 자리가 울어야 한다.
      backup Makefile
      perl -0pi -e 's/^demo:$/run-demo:/m' Makefile ;;
    M-115) # T11-5 공허 통과 방지 — 재현 절차 블록을 **통째로 지운다**
            # ⛔ ②는 0개를 훑고 **초록이다.** 그 초록은 *"명령이 다 산다"*가 아니라
            #    **"적힌 게 없다"**이다. REQ-901이 요구한 것은 절차의 존재고, ③만 그것을 본다.
      backup README.md
      perl -0pi -e 's/^```bash\nmake venv[^`]*```\n//m' README.md ;;
    M-116) # T11-5 — 절차에서 **실행만** 빠진다 (`make demo` 한 줄)
            # ⛔ 게이트만 적힌 README는 *맞는지*는 알려 주고 **무엇을 하는지는 안 알려 준다.**
            #    ②는 초록이다(남은 둘은 실재하니까). 값을 묻는 자리는 ③ 하나다.
      backup README.md
      perl -0pi -e 's/^make demo .*\n//m' README.md ;;
    M-117) # T11-5 — 제출물의 진입점이 **없는 문서를 가리킨다**
            # ⛔ 재현은 첫 클릭에서 끝난다. G6④가 코드의 `Spec:`에 대해 하는 일을
            #    README에 대해 하는 자리가 ④다 — 이름을 바꾼 날 두 방향이 함께 지켜져야 한다.
      backup README.md
      perl -0pi -e 's{\(docs/PRINCIPLES\.md\)}{(docs/ENGINEERING.md)}' README.md ;;
    M-118) # T11-5 공허 통과 방지 — 스캐너가 **아무 명령도 못 뽑는다**
            # ⛔ ②·③이 함께 조용해진다. 표본(①)만 그것을 잡는다 — 스캐너를 스캐너로
            #    검사할 수는 없고, **기대값이 박힌 표본**이 유일한 바닥이다 (M-105와 같은 규칙).
      backup tests/test_readme_procedure.py
      perl -0pi -e 's/^MAKE_RE = re\.compile\(r"\\bmake/MAKE_RE = re.compile(r"\\bmakes/m' tests/test_readme_procedure.py ;;
    M-119) # T11-6 — 닫힘 표지가 **아무 데나 걸린다** (잘림이 안 보인다)
            # ⛔ 이것이 192에서 실제로 난 일이다. 열린 블록을 못 읽으면 tee가 끊긴 로그가
            #    *"전부 red 확인"*의 온전한 원본으로 통과한다. 방향은 **조용한 허용**이다.
      backup tests/test_sweep_log_integrity.py
      perl -0pi -e 's/^CLOSE_MARK = "잔여"$/CLOSE_MARK = ""/m' tests/test_sweep_log_integrity.py ;;
    M-120) # T11-6 — 실패 표지를 **못 알아본다** (`❌` → `❌❌`)
            # ⛔ 다 돌았는데 판정이 아닌 로그가 있다. `잘림`과 `판정 불가`는 다른 사고이고,
            #    ③이 초록인 채로 ④만 거짓이 될 수 있다.
      backup tests/test_sweep_log_integrity.py
      perl -0pi -e 's/^FAIL_MARK = "❌"$/FAIL_MARK = "❌❌"/m' tests/test_sweep_log_integrity.py ;;
    M-121) # T11-6 공허 통과 방지 — 스캐너가 **case를 하나도 못 뽑는다**
            # ⛔ 0개를 훑는 초록은 *"증거가 온전하다"*가 아니라 **"아무것도 안 봤다"**이다.
            #    스캐너는 스캐너로 검사할 수 없다 — 기대값이 박힌 표본만이 바닥이다(M-118).
      backup tests/test_sweep_log_integrity.py
      perl -0pi -e 's/^CASE_RE = re\.compile\(r"\^── /CASE_RE = re.compile(r"^-- /m' tests/test_sweep_log_integrity.py ;;
    M-122) # T12-1 — 헬스 경로가 `200`을 안 낸다
            # ⛔ **첫 배포의 생사가 이 한 줄이다.** 프로브가 실패하면 리비전은 트래픽을
            #    한 번도 못 받고, 나머지 경로가 무엇을 내든 아무도 못 본다.
      backup src/warranty/server.py
      perl -0pi -e 's/return Response\(OK, \{"status": "ok"/return Response(NOT_IMPLEMENTED, {"status": "ok"/' src/warranty/server.py ;;
    M-123) # T12-1 — 라우터에서 경로 한 행이 **사라진다** (코드→설계 방향)
            # ⛔ 그 경로는 조용히 `404`가 된다. 심사자가 보는 것은 *"아직 구현 안 됨"*이
            #    아니라 **"그런 경로 없음"**이고, 둘은 같은 제출물이 아니다.
      backup src/warranty/server.py
      perl -0pi -e 's/^    Route\("POST", "\/agent:chat"\),\n//m' src/warranty/server.py ;;
    M-124) # T12-1 ★ **가장 위험한 초록** — 배선 안 된 경로가 `200`을 낸다
            # ⛔ 어댑터가 없는데 성공을 흉내 내면 *"돌아간다"*와 *"가짜로 돌아간다"*가
            #    구별되지 않는다. design 08§5가 `WR_ADAPTERS` 기본값을 fake로 안 두는 이유다.
      backup src/warranty/server.py
      perl -0pi -e 's/^    return Response\(\n        NOT_IMPLEMENTED,/    return Response(\n        OK,/m' src/warranty/server.py ;;
    M-125) # T12-1 — `load_port`가 **주입된 값을 무시한다** (늘 기본값)
            # ⛔ Cloud Run이 준 포트를 안 들으면 컨테이너는 뜨고 프로브는 다른 문을 두드린다.
            #    로그에는 아무 이유도 안 남는다 — *"안 떴다"*와 구별되지 않는다.
      backup src/warranty/config.py
      perl -0pi -e 's/^    raw = env\.get\(PORT_ENV_KEY, ""\)\.strip\(\)$/    raw = ""/m' src/warranty/config.py ;;
    M-126) # T12-1 ★ **함정 자체** — `CMD`가 데모로 돌아간다
            # ⛔ `test_deploy_artifacts` ⑥는 **초록이다**(`warranty.demo`는 실재한다).
            #    있는 모듈을 가리키는 것과 서버를 가리키는 것은 다른 질문이고, ⑧만 후자를 본다.
      backup Dockerfile
      perl -0pi -e 's/"warranty\.server"/"warranty.demo"/' Dockerfile ;;
    M-127) # T12-1 — **설계 표**에서 행 하나가 사라진다 (설계→코드 방향)
            # ⛔ M-123의 반대편이다. 합의된 계약이 줄었는데 코드가 안 따라오면, 코드는
            #    아무도 합의 안 한 경로를 열어 둔 채 초록이다.
      backup specs/warranty/design/08-interfaces.md
      perl -0pi -e 's/^\| `POST` \| `\/agent:chat`.*\n//m' specs/warranty/design/08-interfaces.md ;;
    M-128) # T12-1 공허 통과 방지 — 설계 표 파서가 **한 행도 못 뽑는다**
            # ⛔ 0개를 훑는 초록은 *"설계와 코드가 같다"*가 아니라 **"아무것도 안 맞댔다"**이다.
            #    ②도 함께 울지만, *"설계가 지워졌다"*와 *"파서가 깨졌다"*를 가르는 것은 ①뿐이다.
      backup tests/test_http_server.py
      perl -0pi -e 's/DESIGN_ROW_RE = re\.compile\(r"\^\\\|/DESIGN_ROW_RE = re.compile(r"^!\\|/' tests/test_http_server.py ;;
    M-129) # T12-1 — 미등록 경로를 `405`로 낸다 (design 08§4)
            # ⛔ *"경로를 잘못 적었다"*와 *"동사를 잘못 골랐다"*가 같은 답이 된다.
            #    클라이언트가 고칠 곳을 못 찾는다.
      backup src/warranty/server.py
      perl -0pi -e 's/return Response\(NOT_FOUND, \{"error": "unknown_route"/return Response(METHOD_NOT_ALLOWED, {"error": "unknown_route"/' src/warranty/server.py ;;
    M-130) # T12-1 — 응답에 `Content-Length`가 안 실린다
            # ⛔ 판정이 옳아도 **바이트로 못 내면** 프로브는 실패한다. HTTP/1.1 클라이언트는
            #    응답의 끝을 모르고 타임아웃으로 죽고, 그건 서버가 답을 안 한 것과 안 갈린다.
      backup src/warranty/server.py
      perl -0pi -e 's/^        self\.send_header\("Content-Length", str\(len\(payload\)\)\)\n//m' src/warranty/server.py ;;
    M-131) # T12-1 — 요청 본문을 **안 읽는다**
            # ⛔ keep-alive에서 다음 요청이 그 본문을 요청 줄로 읽는다. 부하에서 나는
            #    실패가 아니라 **두 번째 클릭**에서 나고, 한 번만 눌러 보면 안 보인다.
      backup src/warranty/server.py
      perl -0pi -e 's/^            self\.rfile\.read\(int\(raw\)\)$/            pass/m' src/warranty/server.py ;;
    M-132) # T12-1 — 산출물이 포트를 **다시 적는다**
            # ⛔ 이미지가 듣는 포트와 프로브가 두드리는 포트가 따로 썩는다. `config.py`를
            #    고쳐도 이 줄은 안 따라오고, 그 어긋남은 첫 배포에서만 보인다.
      backup Dockerfile
      perl -0pi -e 's/^WORKDIR \/app$/WORKDIR \/app\nENV PORT=8080/m' Dockerfile ;;
    M-133) # T12-2 — 모델이 `ambiguous`로 되돌려줘도 통과한다
            # ⛔ 규칙이 이미 낸 답을 되돌려받으면 판정이 **안 닫힌다** — `Verification`이
            #    거부하고, 조치 한 건이 검증 없이 예외로 끝난다.
      backup src/warranty/adapters/model_judge.py
      perl -0pi -e 's/^ALLOWED_VERDICTS: tuple\[Verdict, \.\.\.\] = \(Verdict\.RECOVERED, Verdict\.NOT_RECOVERED\)$/ALLOWED_VERDICTS: tuple[Verdict, ...] = tuple(Verdict)/m' src/warranty/adapters/model_judge.py ;;
    M-134) # T12-2 ★ **가장 위험한 초록** — 파싱 실패가 조용히 `recovered`가 된다
            # ⛔ 못 읽은 응답 하나가 *"나아졌다"*가 되고, 그 조치는 롤백 없이 남으며
            #    리포트의 회복률만 오른다. 하필 모델이 불리는 구간은 **판단이 어려운 구간**이다.
      backup src/warranty/adapters/model_judge.py
      perl -0pi -e 's/^FALLBACK_VERDICT = Verdict\.NOT_RECOVERED$/FALLBACK_VERDICT = Verdict.RECOVERED/m' src/warranty/adapters/model_judge.py ;;
    M-135) # T12-2 — 폴백이 **근거를 안 남긴다**
            # ⛔ `Verification`이 *"모델이 판정했는데 근거가 없다"*로 예외를 낸다 —
            #    그 예외는 조치 한 건을 통째로 날리고, 원인은 모델 답이 이상했다는 것뿐이다.
      backup src/warranty/adapters/model_judge.py
      perl -0pi -e 's/^    return f"\{FALLBACK_PREFIX\}: \{reason\} · raw\[:\{RAW_EXCERPT_CHARS\}\]=\{excerpt!r\}"$/    return ""/m' src/warranty/adapters/model_judge.py ;;
    M-136) # T12-2 — **빈 근거**를 통과시킨다
            # ⛔ 근거 없는 모델 판정은 검증이 아니라 주사위다(REQ-204). 그리고 그 빈 문장은
            #    파싱을 지나 `Verification`에서 터진다 — 고칠 곳이 여기라는 말은 아무도 안 한다.
      backup src/warranty/adapters/model_judge.py
      perl -0pi -e 's/ or not rationale\.strip\(\)//' src/warranty/adapters/model_judge.py ;;
    M-137) # T12-2 — 프롬프트가 **재측정 대신 기준선**을 두 번 싣는다
            # ⛔ 모델은 조치 전 값만 보고 답하고, 그 답은 여전히 문장으로 그럴듯하다.
            #    원장에서 *"모델이 재측정을 봤다"*와 구별되지 않는다.
      backup src/warranty/adapters/model_judge.py
      perl -0pi -e 's/^        after=_render\(after\),$/        after=_render(baseline),/m' src/warranty/adapters/model_judge.py ;;
    M-138) # T12-2 — 폴백이 **원문을 안 싣는다**
            # ⛔ 원장은 *"못 읽었다"*고만 말하고 무엇을 못 읽었는지는 사라진다.
            #    프롬프트를 고쳐야 하는지 파서를 고쳐야 하는지 아무도 못 정한다.
      backup src/warranty/adapters/model_judge.py
      perl -0pi -e 's/^RAW_EXCERPT_CHARS = 200$/RAW_EXCERPT_CHARS = 0/m' src/warranty/adapters/model_judge.py ;;
    M-139) # T12-2 — 코드펜스를 **안 벗긴다**
            # ⛔ 모델은 JSON을 ```json으로 감싸는 쪽이 흔하다. 안 벗기면 **정상 응답이 전부
            #    폴백**으로 떨어지고, 원장은 모델이 판단한 적 없다고 말한다. 루프는 계속 돌고
            #    판정은 늘 보수적으로 옳아 보인다 — 조용한 실패의 교과서다.
      backup src/warranty/adapters/model_judge.py
      perl -0pi -e 's/^    if not stripped\.startswith\(FENCE\) or not stripped\.endswith\(FENCE\):$/    if True:/m' src/warranty/adapters/model_judge.py ;;
    M-140) # T12-2 — 판정 호출이 **사용량을 0으로 지어낸다**
            # ⛔ *"계량했는데 공짜였다"*와 *"얼마인지 모른다"*는 다른 문장이다(PRINCIPLES #2).
            #    원장은 조용한 0을 적고, 예산은 그 호출이 없었던 것처럼 남는다.
      backup src/warranty/adapters/model_judge.py
      perl -0pi -e 's/^        return ModelReply\(verdict, rationale, raw\.usage\)$/        return ModelReply(verdict, rationale, TokenUsage(raw.usage.model, 0, 0))/m' src/warranty/adapters/model_judge.py ;;
    M-141) # T12-3 — 명세가 선언하는 도구가 **설계와 다르다**
            # ⛔ 설계는 넷으로 고정한다고 적었고 지시문도 넷을 말한다. 명세만 셋이 되면
            #    모델은 있는 줄 아는 도구를 못 부르고, 그 실패는 *"모델이 이상하다"*로 읽힌다.
      backup src/warranty/adapters/adk_agent.py
      perl -0pi -e 's/^TOOL_NAMES: tuple\[str, \.\.\.\] = \("provision", "inspect", /TOOL_NAMES: tuple[str, ...] = ("provision", /m' src/warranty/adapters/adk_agent.py ;;
    M-142) # T12-3 공허 통과 방지 — 설계 도구 표 파서가 **한 행도 못 뽑는다**
            # ⛔ 0개를 훑는 초록은 *"설계와 명세가 같다"*가 아니라 **"아무것도 안 맞댔다"**이다.
      backup tests/test_adk_agent.py
      perl -0pi -e 's/DESIGN_TOOL_RE = re\.compile\(r"\^/DESIGN_TOOL_RE = re.compile(r"^!/' tests/test_adk_agent.py ;;
    M-143) # T12-3 ★ 모델 id가 **코드에 박힌다**
            # ⛔ `WR_MODEL`을 바꿔 배포해도 에이전트는 옛 모델을 부른다. 그 어긋남은 로그가
            #    아니라 **청구서**에서 보이고, 그때는 이미 다 쓴 뒤다.
      backup src/warranty/adapters/adk_agent.py
      perl -0pi -e 's/^        model=settings\.model,$/        model="gemini-3.7-flash",/m' src/warranty/adapters/adk_agent.py ;;
    M-144) # T12-3 — 명세와 **다른 함수를 붙여도** 통과한다
            # ⛔ ADK의 `tools`는 평범한 `Callable`을 받는다(probe ①) — 라이브러리는 아무 말도
            #    안 한다. 모델은 지시에 적힌 이름을 부르고 그 도구는 없다.
      backup src/warranty/adapters/adk_agent.py
      perl -0pi -e 's/^    if given != spec\.tools:$/    if False:/m' src/warranty/adapters/adk_agent.py ;;
    M-145) # T12-3 ★ `Runner`에 **세션 서비스가 안 실린다**
            # ⛔ probe ②: 기본값이 없는 키워드 인자다. 빠지면 `TypeError`이고 그 예외는
            #    게이트에도 빌드에도 안 난다 — **첫 실물 호출**에서만 난다.
      backup src/warranty/adapters/adk_agent.py
      perl -0pi -e 's/, "session_service": session_service\}/}/' src/warranty/adapters/adk_agent.py ;;
    M-146) # T12-3 ★ 클라우드 스택을 **최상위에서** 임포트한다
            # ⛔ `google-adk`는 cloud extra라 게이트 venv에 없다(REQ-801). 최상위에서 부르면
            #    게이트는 **수집 단계에서 통째로** 죽는다 — 이 한 줄이 오프라인 전제를 깬다.
      backup src/warranty/adapters/adk_agent.py
      perl -0pi -e 's/^from warranty\.config import Settings$/import google.adk\n\nfrom warranty.config import Settings/m' src/warranty/adapters/adk_agent.py ;;
    M-147) # T12-3 — 지시가 도구 하나를 **이름으로 안 부른다**
            # ⛔ 지시에 없는 도구는 모델이 부를 줄 모른다. 붙어는 있으므로 배선 검사는 전부
            #    초록이고, 그 도구는 **조용히 영영 안 불린다.**
      backup src/warranty/adapters/adk_agent.py
      perl -0pi -e 's/^- inspect\b/- lookup/m' src/warranty/adapters/adk_agent.py ;;
    M-148) # T12-3 공허 통과 방지 — 지연 임포트가 **아예 없어진다**
            # ⛔ 최상위가 깨끗한 이유가 *지연 임포트라서*가 아니라 **배선이 없어서**인 상태다.
            #    M-146의 반대편이다: 그 검사만 있으면 이 상태는 가장 깨끗한 초록으로 보인다.
      backup src/warranty/adapters/adk_agent.py
      perl -0pi -e 's/^        import google\.adk as adk.*\n        from google\.adk import sessions$/        adk = sessions = None/m' src/warranty/adapters/adk_agent.py ;;
    M-149) # T12-4 ★ **함정의 다음 얼굴** — 진입점이 `serve_forever`를 안 부른다
            # ⛔ 임포트도 되고 타입도 맞고 단위 테스트도 전부 통과한다. 이름도 여전히
            #    `warranty.server`라 `test_http_server` ⑧도 초록이다. 갈라지는 것은
            #    **프로세스가 끝나는가**뿐이고, 그건 첫 배포의 포트 프로브에서만 보인다.
      backup src/warranty/server.py
      perl -0pi -e 's/^    httpd\.serve_forever\(\)\n//m' src/warranty/server.py ;;
    M-150) # T12-4 — 진입점이 포트를 **박는다** (`load_port`를 안 부른다)
            # ⛔ `test_http_server` ⑥은 초록이다 — `load_port` 자체는 멀쩡하고, 산출물
            #    사본 검사가 보는 것은 `Dockerfile`·`deploy.sh`뿐이다. 진입점이 그 숫자를
            #    직접 적는 자리는 아무도 안 봤다. 그때 이미지는 뜨고 프로브만 실패한다.
      backup src/warranty/server.py
      perl -0pi -e 's/^    port = load_port\(\)$/    port = 8080/m' src/warranty/server.py ;;
    M-151) # T12-4 — 진입점의 `__main__` 가드가 사라진다
            # ⛔ `python -m`이 임포트만 하고 **조용히 0으로 끝난다.** 죽지도 않고
            #    서비스하지도 않으며, 로그에는 아무것도 안 남는다.
      backup src/warranty/server.py
      perl -0pi -e 's/^if __name__ == "__main__":\n    raise SystemExit\(main\(\)\)\n//m' src/warranty/server.py ;;
    M-152) # T12-4 공허 통과 방지 — 호출 이름 수집기가 **늘 둘 다 있다고 말한다**
            # ⛔ 0개를 훑는 초록의 반대 얼굴이다: 전부를 훑었다고 **지어내는** 초록.
            #    그러면 데모를 가리켜도, 포트를 박아도 검사는 아무 말도 안 한다.
      backup tools/deploy_preflight.py
      perl -0pi -e 's/^    names: set\[str\] = set\(\)$/    names: set[str] = {PORT_SOURCE, BLOCKING_CALL}/m' tools/deploy_preflight.py ;;
    M-153) # T12-4 ★ 셸이 검사를 **빌드 뒤에** 부른다 (순서 역전)
            # ⛔ 검사는 그대로 있고 그대로 옳다. 부르는 자리만 한 칸 내려간다 — 그런데
            #    그때는 이미 빌드 비용을 썼고 리비전이 생겼다. **올린 뒤에 막는 것은
            #    안 막은 것과 같다.** 배포는 게이트에 없으니 다음 배포까지 아무도 모른다.
      backup scripts/deploy.sh
      perl -0pi -e 's/^PYTHONPATH=src "\$PY" tools\/deploy_preflight\.py[^\n]*\n//m' scripts/deploy.sh
      perl -0pi -e 's/^gcloud builds submit --tag "\$IMAGE" \.$/gcloud builds submit --tag "\$IMAGE" .\nPYTHONPATH=src "\$PY" tools\/deploy_preflight.py --tag "\$TAG" --image "\$IMAGE"/m' scripts/deploy.sh ;;
    M-154) # T12-4 — 셸이 검사를 **아예 안 부른다**
            # ⛔ 도구도 테스트도 그대로다. 아무도 안 지날 뿐이고, 그 초록은 *"검사가 있다"*가
            #    아니라 **"검사가 있는 파일이 있다"**이다 (M-91과 같은 계열).
      backup scripts/deploy.sh
      perl -0pi -e 's/^PYTHONPATH=src "\$PY" tools\/deploy_preflight\.py[^\n]*\n//m' scripts/deploy.sh ;;
    M-155) # T12-4 — 발견이 있어도 **종료 코드 0**을 낸다
            # ⛔ 발견은 stderr에 그대로 찍힌다. `set -e`가 안 멈출 뿐이고, 사람이 보는 것은
            #    경고가 스쳐 지나간 **성공한 배포**다. 검사가 장식이 되는 정확한 한 줄.
      backup tools/deploy_preflight.py
      perl -0pi -e 's/^    return 1 if findings else 0$/    return 0/m' tools/deploy_preflight.py ;;
    M-156) # T12-4 — 이미지 대조가 **아무것도 안 본다**
            # ⛔ 빌드하는 주소와 배포하는 주소를 각각 집는 것은 셸이다. 갈라지면 올라간
            #    이미지와 도는 이미지가 다르고, 그 어긋남은 로그에 *"배포 성공"*으로 남는다.
      backup tools/deploy_preflight.py
      perl -0pi -e 's/^    if f"--image=\{image\}" in rendered:$/    if True:/m' tools/deploy_preflight.py ;;
    M-157) # T2-1 ★ **실물에서 이미 한 번 터진 자리** — Vertex location에 Cloud Run 리전을 싣는다
            # ⛔ 값은 그럴듯하고 빌드도 게이트도 조용하다. 갈라지는 곳은 **배포 후 첫 모델
            #    호출**이고, 거기서 404다 (2026-08-23 실물 확인: us-central1에 Gemini 3.x 없음).
      backup src/warranty/adapters/adk_agent.py
      perl -0pi -e 's/^        "GOOGLE_CLOUD_LOCATION": settings\.vertex_location,$/        "GOOGLE_CLOUD_LOCATION": settings.region,/m' src/warranty/adapters/adk_agent.py ;;
    M-158) # T2-1 — 어댑터가 location을 **자기가 적는다** (설정을 이긴다)
            # ⛔ 오늘은 값이 같아서 아무 증상이 없다. 모델이 리전을 늘리는 날 아무도 이 줄을
            #    못 찾는다 — T11-1(배포 값)·T11-4(데모 기준선)와 같은 계열의 세 번째 자리다.
      backup src/warranty/adapters/adk_agent.py
      perl -0pi -e 's/^        "GOOGLE_CLOUD_LOCATION": settings\.vertex_location,$/        "GOOGLE_CLOUD_LOCATION": "global",/m' src/warranty/adapters/adk_agent.py ;;
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

if [ "$MUT" = "all" ]; then for m in M-01 M-02 M-03 M-04 M-05 M-06 M-07 M-08 M-09 M-10 M-11 M-12 M-13 M-14 M-15 M-16 M-17 M-18 M-19 M-20 M-21 M-22 M-23 M-24 M-25 M-26 M-27 M-28 M-29 M-30 M-31 M-32 M-33 M-34 M-35 M-36 M-37 M-38 M-39 M-40 M-41 M-42 M-43 M-44 M-45 M-46 M-47 M-48 M-49 M-50 M-51 M-52 M-53 M-54 M-55 M-56 M-57 M-58 M-59 M-60 M-61 M-62 M-63 M-64 M-65 M-66 M-67 M-68 M-69 M-70 M-71 M-72 M-73 M-74 M-75 M-76 M-77 M-78 M-79 M-80 M-81 M-82 M-83 M-84 M-85 M-86 M-87 M-88 M-89 M-90 M-91 M-92 M-93 M-94 M-95 M-96 M-97 M-98 M-99 M-100 M-101 M-102 M-103 M-104 M-105 M-106 M-107 M-108 M-109 M-110 M-111 M-112 M-113 M-114 M-115 M-116 M-117 M-118 M-119 M-120 M-121 M-122 M-123 M-124 M-125 M-126 M-127 M-128 M-129 M-130 M-131 M-132 M-133 M-134 M-135 M-136 M-137 M-138 M-139 M-140 M-141 M-142 M-143 M-144 M-145 M-146 M-147 M-148 M-149 M-150 M-151 M-152 M-153 M-154 M-155 M-156 M-157 M-158; do one "$m"; done; else one "$MUT"; fi
exit $RESULT
