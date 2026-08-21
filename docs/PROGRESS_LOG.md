# PROGRESS_LOG — warranty

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs`로 압축.
> 권위: 요구사항=`specs/warranty/requirements.md` · 계획=`specs/warranty/tasks.md` ·
> 현재 상태=`docs/OVERVIEW.md` §10 · 검증 기록=`docs/evidence/`.

---

## 2026-08-21 — T4-11a: `APPROVE`는 종착역이었다 — 승인이 들어오는 문을 냈다 (gate 75)

- **Status**: `[auto]` T4-11a 완료. REQ-404 `TODO`→**`VERIFIED`**. 전부 오프라인·fake 위다.
- **Changed**: `Remediator.approve(entry_id, resource, approver)`를 냈다. ★ **승인 시 게이트를
  다시 평가한다**(REQ-404 후반) — 대기하는 동안 예산이 마르거나 계약이 `retired`가 될 수 있다.
  재판정에 쓰는 것은 원래 판정의 `projected_usd`·`destructive`(**같은 조치여야 하니까**)와
  **지금 다시 읽은** 계약·신호·예산이다. 원장에 `Approval(approver, approved_at, reevaluated)`을
  더했고 **원래 `decision`을 덮지 않는다** — 덮으면 "무엇에 동의했는가"가 사라진다.
  `InMemoryLedger.approve`는 `awaiting_approval`인 항목에만 **한 번만** 붙인다(사후 승인 금지).
  ⚠️ AUTO와 승인된 조치가 **같은 경로**(`_execute_and_verify`)를 타게 뽑았다 — 승인 경로를
  따로 배선하면 그 경로만 검증·롤백을 빠뜨리고, 그 누락은 조용하다.
  포트는 `Ledger = LedgerWriter + LedgerReader`로 갈랐다(승인은 **기록을 읽어서** 시작한다).
- **Verified**: `make check` → **75 passed** (2026-08-21 로컬 macOS·py3.13).
  **M-26·M-27 red 확인** · **M-01~M-27 전체 스윕 27종 전부 red** · 복구 후 75 passed · 잔여 0.
- **Verified(죽은 건수의 차이가 위험도다)**: M-26(승인 없이 실행)은 **7건**을 죽였고
  M-27(승인이 게이트를 면제)은 **1건**뿐이다. 재판정을 빼도 *승인이 실제로 붙은 경로 하나*만
  어긋나고 나머지는 전부 초록이다 — **M-14와 같은 계열의 조용한 회귀**다. 승인 뒤 예산이
  마른 케이스를 값으로 태워 두지 않았다면 M-27은 초록이었을 것이다.
- **Blockers**: 없음(이 항목 한정). ⛔ 레포 전체는 그대로 — **전용 GCP 프로젝트**가 T2를
  잠그고 **08-24 중단 기준**의 판정 대상이다.
- **Next**: 오프라인 `[auto]` 남은 것 — T4-11b(예산 예약/정산, REQ-405) · T5-2(회복률 리포트) ·
  T5-3(모델 호출 원장) · T6-2(T5-2 선행) · T6-3(상수 한 모듈).
  ⚠️ T4-11b는 지금 `budgets.commit`이 **실행 후 한 번**이라 동시 초과를 못 막는다 —
  `reserve`→`settle`로 갈라야 하고, 그 예약은 `approve`의 재판정과 같은 자리를 만진다.

## 2026-08-21 — T0-6: 기계가 안 읽는 문자열이 썩어 있었다 — 사람만 속는 자리 넷 (gate 68)

- **Status**: `[auto]` T0-6 완료. 문자열 정리뿐이고 동작은 안 건드렸다. 클라우드는 여전히 막혀 있다(T0-3).
- **Changed**: 넷을 현행으로 맞췄다. ① `mutate.sh` 사용법이 `<M-01|M-02|M-03|M-04|all>`이었다 —
  실제 변이는 **M-25까지**다(`all` 목록은 이미 맞았고 사용법 줄만 안 따라왔다) ⇒ `<M-01..M-25|all>`.
  ② `mutate.sh` 인라인 REQ 주석 넷이 **구 번호**였다 — M-06 `REQ-204`→`REQ-505` ·
  M-07 `REQ-203`→`REQ-504` · M-08 `REQ-201`→`REQ-501` · M-09 `REQ-202`→`REQ-503`
  (권위는 `docs/evidence/mutations.md`의 REQ 칸, 그리고 tasks.md의 T1-1~T1-3와 일치한다).
  ③ `tools/spec_trace.py`의 리포트 헤더가 아직 `fleet-ledger`였다 ⇒ `warranty`.
  ④ `mutations.md` 머리말의 절차 인용이 `specs/fleet-ledger/design/07-verification.md`였다 ⇒
  현행 `specs/warranty/design/09-quality-gate.md` §4(문서 번호까지 바뀌었다 — 07은 지금
  `07-tenant-identity.md`라 경로만 갈아끼우면 **다른 문서를 가리켰을 것**이다).
- **Verified**: `make check` → **68 passed** (2026-08-21 로컬 macOS·py3.13). 변이 기록은
  안 늘렸다 — 주석·사용법 문자열이라 밀 가드가 없다(있다고 적으면 그게 G6가 막는 거짓 주장이다).
- **Verified(왜 가드가 이걸 못 잡았나)**: 넷 다 **기계가 안 읽는 자리**다. `scan_mutation_refs`는
  `mutations.md`의 표만 읽고 `mutate.sh` 주석은 안 읽는다. G6④는 파이썬 도크스트링의 `Spec:`만
  본다 — 셸 주석·마크다운 산문·출력 헤더는 사거리 밖이다. ⚠️ **그래서 이건 재발한다.**
  다음에 이름을 바꾸면 같은 자리가 또 썩는다. 자동화는 T0-6의 범위가 아니라서 안 했다.
- **남긴 것(의도)**: `PROGRESS_LOG`·`DECISIONS`·`spec_trace.py:193` 도크스트링·
  `tests/test_g6_traceability.py`·`mutations.md`의 T0-5 회고에 남은 `fleet-ledger`는
  **이름 변경을 서술하는 역사**다. 고치면 문장이 거짓이 된다.
- **Blockers**: 없음(이 항목 한정). ⛔ 레포 전체는 그대로 — **전용 GCP 프로젝트**가 T2를
  잠그고 **08-24 중단 기준**의 판정 대상이다.
- **Next**: 오프라인 `[auto]` 남은 것은 T4-11a(승인 집행) · T4-11b(예산 예약) · T5-2(회복률
  리포트) · T5-3(모델 호출 원장) · T6-2(T5-2 선행) · T6-3(상수 한 모듈).
  ⚠️ 그 여섯을 다 해도 **중단 기준의 판정 대상(T2-2)은 안 움직인다.**

## 2026-08-21 — T0-5: 참조를 **양방향으로** 물었다 — 코드→spec 방향이 썩고 있었다 (gate 68)

- **Status**: `[auto]` T0-5 완료. 오프라인 하네스 작업이고 클라우드는 여전히 막혀 있다(T0-3).
- **Changed**: G6에 **④ spec 참조 정합성**을 붙였다(`tools/spec_trace.py`의
  `scan_spec_refs`·`unresolved_spec_path`·`spec_reference_violations`). 코드 도크스트링의
  `Spec:` 블록에서 설계 경로와 인용 REQ를 AST로 읽어 **실재하는지** 묻는다.
  `REQ-201~206` 같은 **범위 표기를 펼친다**(안 펼치면 끝 번호가 검사에서 빠진다).
  판정은 `all_violations` 한 곳 → `make trace`와 테스트가 안 갈라진다.
  dangling 6곳을 고쳤다(`specs/fleet-ledger/...` 5 + `remediate.py` 줄임 표기 1).
  `entry.py`가 인용하던 **REQ-207은 존재하지 않는 요구사항**이었다.
- **Verified**: `make check` → **68 passed** (2026-08-21 로컬 macOS·py3.13).
  **M-23·M-24·M-25 전부 red 확인** · 복구 후 68 passed · 잔여 0 (`docs/evidence/mutations.md`).
  각각 없는 설계 문서 · 정의 없는 REQ · 스캐너 공허 통과를 민다.
- **Verified(가드가 태스크보다 정확했다)**: T0-5는 dangling을 **5곳**으로 적었는데 기계는 **6곳**을
  셌다. `remediate.py`가 `02-verification.md · 03-atomic-rollback.md`처럼 **직전 경로의 형제**를
  줄여 적고 있었다. 해석 규칙을 형제 추론으로 만들면 조용히 틀리므로 **저장소 루트 기준
  전체 경로만** 허용하고 줄임 표기 자체를 위반으로 센다. ⚠️**손으로 센 목록은 가드가 아니다.**
- **Blockers**: 없음(이 항목 한정). ⛔ 레포 전체의 블로커는 그대로 — **전용 GCP 프로젝트**가
  T2를 잠그고 있고 **08-24 중단 기준**의 판정 대상이다.
- **Next**: T0-6(스테일 문자열 — `mutate.sh` 사용법 `M-01~M-04`, `spec_trace.py` 리포트 헤더
  `fleet-ledger`, `mutations.md` 머리말의 `specs/fleet-ledger/design/07-verification.md`).
  ⚠️ 마지막 것은 **마크다운 산문**이라 G6④(파이썬 도크스트링)가 안 잡는다 — T0-6이 가져가야 한다.

## 2026-08-19 — 레포 생성부터 루프 배선까지: spec을 집행 가능하게 만들고, GCP 올인으로 재정의했다 (gate 65)

- **Status**: 저장소를 새로 만들었다(커밋 6). Google All Things Agentic Hackathon 제출물.
  **코드는 아직 클라우드에 안 올라갔다.** 논지의 루프는 fake 위에서 전부 배선·검증됐다.
- **Changed — ① SDD를 집행 가능하게**: `tools/spec_trace.py` + 가드 **G6**가
  요구사항의 **상태 주장을 현실에 맞댄다**(`IMPLEMENTED`면 테스트, `VERIFIED`면 red가 확인된
  변이 기록). 형제 검사 셋(테스트·태스크·설계 귀속)을 함께 묻는다. `scripts/mutate.sh`가
  변이·실행·복구를 한 스크립트에서 한다.
- **Changed — ② GCP 올인 재정의**(`fleet-ledger` → `warranty`): 주제를 비용 장부에서
  **자동화**로 옮겼다. 논지 = *"클라우드 중립성을 포기하면 에이전트가 무엇을 할 수 있게 되는가."*
  Day-1이 **운영 계약**(신호·회복기준·롤백계획·가역성)을 산출하고, Day-2가 조치 후
  **같은 신호를 다시 재고** 안 나아졌으면 **Cloud Run 트래픽 전환으로 되돌린다**.
  판정 게이트 축이 셋(가역성 × **검증 가능성** × 예산) — ⛔**검증할 수 없는 조치는 자동으로 하지 않는다.**
  REQ 36 → **44**, 설계 11편 재작성. 비용은 주제가 아니라 리포트의 한 열로 종속(D9).
- **Changed — ③ 도메인 + 루프**: 계약·검증·판정 게이트·원장 + 포트 9종 + fake 어댑터 +
  `Remediator`. `improved`를 **저장하지 않고 검증 결과에서 유도**한다(G8).
  **남은 것은 어댑터뿐이다** — 실물 Cloud Monitoring·Cloud Run·Vertex.
- **Verified**: `make check` → **65 passed** (2026-08-19 로컬 macOS·py3.13, ruff+mypy+pytest+trace).
  REQ 44종 — VERIFIED 14 · IMPLEMENTED 14 · TODO 16.
  **변이 M-01~M-22 전부 red 확인** · 복구 후 초록 · 백업 대조 잔여 0 (`docs/evidence/mutations.md`).
  **ADK 실물 확인**: `google-adk 2.7.1`을 별도 venv에 설치해 introspect —
  `tools`가 평범한 `Callable`을 받고, `Runner`는 `session_service`가 **필수**
  (`docs/evidence/adk-api-probe-2026-08-19.log`). ⛔**모델 호출은 아직 안 했다.**
- **Verified(가드 자신의 실패 다섯)**: ⚠️추적성 스캐너가 문자열 검색이라 **산문 언급이
  커버리지로 계산**됐다(REQ-802 오탐) → AST로. ⚠️변이 하네스가 출력 문자열로 판정해 **red를
  초록으로 읽었고**, `git status`로 잔여를 물어 무관한 변경을 오인했고, **stale `.pyc`**에
  속았고, 이름을 바꾼 뒤 **없는 파일에** 물었고, 포맷 변경으로 **조용히 무효인 변이**를 냈다
  → 종료 코드·백업 대조·바이트코드 끄기·대상 부재/무변경을 **판정이 아니라 오류**로.
  ⚠️**M-20은 가드가 없어서가 아니라 픽스처가 약해서 초록이었다**(원칙 #8).
- **Blockers**: ⛔**전용 GCP 프로젝트가 없다.** 활성 gcloud 계정이 `yeongsigchoe7@gmail.com`이고
  **Cloud Billing API 미활성**이라 크레딧이 어느 결제 계정에 붙었는지 **읽을 수 없다**(콘솔 확인 필요).
  이것이 T2(Cloud Run 배포) 전체를 잠근다. BQ 결제 내보내기는 **선택**으로 내려 크리티컬 패스에서 빠졌다.
- **Next**: ⛔**T2-2 (Cloud Run 배포)가 08-24 중단 기준의 판정 대상**이다.
  프로젝트가 열리면 T0-3 → T2 → T3. 그전까지 오프라인으로 가능한 것은
  **REQ-508(회복률 리포트) · REQ-404/405(승인·예약)** 셋뿐이다.
