# tasks — warranty

작성: 2026-08-19 · 권위: `requirements.md` · 설계: `design.md` + `design/*.md`

> 모든 태스크는 REQ와 설계 절을 가리킨다. `[x]`는 **테스트가 있고 변이로 red를 확인한 것**만.
> `[auto]`는 **상태 박스와 다른 축**이다 — 무인 루프(overnight)가 소비해도 되는 것,
> 즉 `make check`로 **오프라인·결정론적으로** 판정 가능한 것만 붙는다.
> ⛔ 실물 클라우드가 필요한 T0-3·T2-*·T7-*는 원리상 붙을 수 없다(태그 없음 = 무인 금지).

---

## 일정

```
   08-19 ──── 08-21 ──── 08-24 ──────── 08-27 ──── 08-31
     T0/T1      T2      ★ 중단 기준      선택 판단   제출
   spec·도메인  배포     "Cloud Run에     (테넌트    09-01 09:00 KST
                        도는 게 없으면    신원·화해)
                        버린다"
```

⛔ **T2가 중단 기준의 판정 대상이다.** 나머지는 전부 그 뒤에 온다.

---

## T0 — 기반 *(대부분 완료)*

- [x] **T0-1** 레포·게이트·설정 계층 · `Implements: REQ-801, REQ-802` · `Design: 09§1, 08§5`
- [x] **T0-2** ★ **G6 추적성 가드** + 변이 하네스 · `Design: 09§3.1, 09§4`
- [ ] **T0-3** 전용 GCP 프로젝트 + 크레딧 결제 계정 연결 · `Implements: REQ-805` · `Design: 10§1`
      ⚠️ **막혀 있다**: 활성 계정이 `yeongsigchoe7@gmail.com`이고 Cloud Billing API 미활성이라
      크레딧이 어느 결제 계정에 붙었는지 **읽을 수 없다**. 콘솔 확인 필요.
- [ ] **T0-4** *(선택)* BQ 결제 내보내기 + 화해/차이 · `Implements: REQ-506, REQ-509` · `Design: 05§4`
      ⚠️ 하루 지연. **크리티컬 패스 아님** — REQ-506·509는 선택이다.
- [x] [auto] **T0-5** ★ **spec 참조 정합성 가드** — `Spec:` 도크스트링이 가리키는 설계 경로와
      인용 REQ가 **실재하는지** 집행한다 (G6④). 손으로 센 5곳이 아니라 **6곳**이었다 —
      `remediate.py`의 줄임 표기는 어떤 규칙으로도 안 풀렸다. ⇒ 저장소 루트 기준 전체 경로만 허용.
      dangling 0 · **M-23·M-24·M-25 red 확인** · `make check` 68 passed.
- [x] [auto] **T0-6** 스테일 문자열 정리 — **넷**이었다(셋으로 적었는데 하나 더 있었다):
      `mutate.sh` 사용법 `M-01~M-04`→**M-25까지** · 인라인 REQ 주석 넷이 구 번호
      (M-06·07·08·09 → REQ-505·504·501·503) · `spec_trace.py` 리포트 헤더 `fleet-ledger`→`warranty` ·
      `mutations.md` 절차 인용 `fleet-ledger/design/07-verification.md`→`warranty/design/09-quality-gate.md`
      (**문서 번호도 바뀌었다** — 07은 지금 tenant-identity다).
      ⚠️ **넷 다 기계가 안 읽는 자리**라 G6④(파이썬 도크스트링)도 `scan_mutation_refs`도 못 잡는다
      — 다음 이름 변경 때 **재발한다**. `make check` 68 passed.

## T1 — 도메인 *(일부 완료 · 전부 오프라인)*

- [x] **T1-1** 원장 행 · 비용 사실 · 귀속 · `Implements: REQ-503, REQ-504, REQ-505` · `Design: 05§1–3`
- [x] **T1-2** 저장소가 불변식 집행(범용 update 없음) · `Implements: REQ-505` · **G2**
- [x] **T1-3** 1회=1행 · 거부/실패 기록 · `Implements: REQ-501, REQ-507` · **G7**
- [x] **T1-4** **운영 계약 자료형** + 넷 필수 검증 · `Implements: REQ-102` · `Design: 01§2`
- [x] **T1-5** ★ `improved`를 **유도**로 (저장 금지) · `Implements: REQ-502` · `Design: 05§1.1` · **G8**
- [x] **T1-6** 3축 판정 행렬 **다섯 칸을 값으로** · `Implements: REQ-402` · `Design: 04§1` · **G9**

## T2 — ★ 배포 선행 (08-20~21) — **중단 기준**

- [~] **T2-1** ADK **실물 설치** + 최소 에이전트 로컬 응답 · `Implements: REQ-601` · `Design: 06§2`
      ✅ **라이브러리와 인터페이스는 실재한다**(`google-adk 2.7.1` introspect,
      증거 `evidence/adk-api-probe-2026-08-19.log`): `tools`가 평범한 `Callable`을 받고,
      ⚠️ `Runner`는 `session_service`가 **필수**다(`min-instances=0`이라 유휴 후 첫 요청은
      항상 새 세션 → 대화 연속성을 가정하지 않는다).
      ⛔ **실제 모델 호출은 아직 안 했다** — 프로젝트·인증 없음.
      **"임포트가 된다"와 "호출이 된다"는 다르다.**
- [ ] **T2-2** 컨테이너 → Artifact Registry → **Cloud Run 배포** · `Implements: REQ-602` · `Design: 10§2`
- [ ] **T2-3** `demo-target` 서비스 배포 (리비전 2개) · `Design: 10§2`
- [ ] **T2-4** 실물 왕복 증거 · `Implements: REQ-901` · `Design: 10§7`

⚠️ **수용 기준은 "테스트 통과"가 아니라 "실제 라이브러리로 실제 응답"이다.**
⛔ **08-24까지 T2-2가 안 되면 접는다.** 포기 비용 0.

## T3 — Day-1: 계약 방출 (08-21~22)

- [ ] **T3-1** Cloud Run 서비스 프로비저닝 · `Implements: REQ-101` · `Design: 01§1`
- [ ] **T3-2** ★ 계약을 **생성 응답에서 유도** · `Implements: REQ-103` · `Design: 01§3`
- [x] **T3-3** 계약 없는 리소스 → `MANUAL` · `Implements: REQ-104` · `Design: 01§4`
- [ ] **T3-4** 리소스 삭제 시 계약 `retired` · `Implements: REQ-105` · `Design: 01§5`

## T4 — Day-2: 조치 · 검증 · 롤백 (08-22~25) — **논지의 전부**

> ✅ **루프는 전부 fake 위에서 배선되고 검증됐다**(`usecases/remediate.py`).
> ⚠️ **남은 것은 어댑터뿐이다** — 실물 Cloud Monitoring·Cloud Run·Vertex.
> **스텁 위 통과는 REQ-601·602를 만족시키지 않는다.**

- [x] **T4-1** 기준선 측정 (Cloud Monitoring) · `Implements: REQ-201` · `Design: 02§2`
- [x] **T4-2** ★ 재측정 — **기준선과 같은 함수** · `Implements: REQ-202` · `Design: 02§2`
- [x] **T4-3** 계약 기준으로 판정 + 빈 창 → `unverifiable` · `Implements: REQ-203, REQ-205` · `Design: 02§3`
- [x] **T4-4** ★ **애매할 때 모델이 판단하고 근거를 남긴다** · `Implements: REQ-204` · `Design: 02§3.1`
- [x] **T4-5** 롤백 계획을 조치 **전에** 고정 · `Implements: REQ-301` · `Design: 03§2`
- [x] **T4-6** ★ 트래픽 전환 + **배분 재확인** · `Implements: REQ-302, REQ-303` · `Design: 03§3`
- [x] **T4-7** ★ **롤백 후 재측정** · `Implements: REQ-304` · `Design: 03§4`
- [x] **T4-8** 롤백 불가 → 에스컬레이션 · `Implements: REQ-305` · `Design: 03§5`
- [x] **T4-9** 게이트가 실행을 **막는다** · `Implements: REQ-403` · `Design: 04§2` · **G1**
- [x] **T4-10** 모든 항목에 `decision` · `Implements: REQ-401` · **G4**
- [x] [auto] **T4-11a** 승인 집행 — `awaiting_approval` 동안 **실행기를 부르지 않는다**,
      승인 시 게이트를 **재평가**한다 · `Implements: REQ-404` · `Design: 04§3`
      `Remediator.approve` + 원장의 `Approval`(원래 `decision`을 안 덮는다). AUTO와 **같은
      경로**를 탄다(`_execute_and_verify`). **M-26·M-27 red 확인** · `make check` 75 passed.
      ⚠️ M-27(승인이 게이트를 면제)은 **1건만** 죽였다 — 승인 뒤 예산이 마른 케이스를 값으로
      안 태웠으면 초록이었을 회귀다(M-14 계열).
- [x] [auto] **T4-11b** 예산 예약/정산 — AUTO·승인 시 예상 비용을 **예약**하고 실행 후 실제 비용으로
      정산한다 · `Implements: REQ-405` · `Design: 04§4`
      `Done:` 예약이 동시 초과를 막는 것이 테스트로 물린다(잔여 예산 < 예상 비용 → 실행 안 됨).
      `commit`을 `reserve`→`settle`로 갈랐고 예약은 `_execute_and_verify` **한 자리**에서만
      잡힌다(AUTO·승인이 같은 이음매). 정산은 `finally`에 있다 — 안 풀린 예약은 여유를
      조용히 잠근다. **M-28·M-29 red 확인.**
      ⚠️ **예약이 M-18·M-27을 가렸다** — 그 둘의 기존 증거가 *예산이 마른* 케이스였고,
      이제 예약이 실행기보다 먼저 막아 초록으로 돌아섰다. **여유가 남은 채로 막히는**
      케이스(`MANUAL`) 둘을 태워 하중을 되돌렸다. `make check` 83 passed.
- [ ] **T4-12** 파괴적 조치 강제 승인 · `Implements: REQ-406` · `Design: 04§5`
- [x] **T4-13** 재측정 상수 한 곳 · `Implements: REQ-206, REQ-804` · `Design: 02§4`

## T5 — 출력 (08-25~26)

- [ ] **T5-1** 응답에 판정·검증 근거·트래픽 배분 · `Implements: REQ-604` · `Design: 08§3.1`
- [x] [auto] **T5-2** ★ **회복률 리포트** · `Implements: REQ-508` · `Design: 05§5`
      `Done:` 원장에서 `executed·improved·improvement_rate·rolled_back·escalated·unverifiable·wasted_usd`를
      **유도**한다(저장 금지 — G8과 같은 계열). 회복 실패 조치가 쓴 비용이 분리돼 나온다.
      ★ **분모는 `executed`다** — 전체 건수로 나누면 게이트가 잘 막을수록 성적이 나빠 보인다.
      실행 0이면 비율은 `0`이 아니라 **정의되지 않는다**. `escalated`는 `rolled_back`의
      **부정이 아니다**(부정으로 세면 회복된 조치가 전부 잡힌다).
      **M-30·M-31·M-32 red 확인** · `make check` 96 passed.
      ⚠️ 루프가 쓰는 행의 `assumed`가 지금 **항상 0**이라 `wasted_usd`는 실물 경로에서 늘 0이다
      — 비용 경로(T3·REQ-503)가 붙기 전까지 이 칸은 손으로 태운 행에서만 하중을 받는다.
- [x] [auto] **T5-3** 모델 호출도 원장에 · `Implements: REQ-603` · `Design: 06§5`
      `Done:` fake 모델 포트 호출 1회 = 원장 1행. 원장을 만드는 경로 **전부**를 가드가 훑는다(#9).
      계량은 `MeteredModel._call` **한 곳**에만 있고 기록은 `finally`다(실패한 호출의 토큰도
      이미 나갔을 수 있다). 가드는 `ModelPort`의 **메서드 집합**과 `EntryKind` **전체**에
      걸린다 — 포트나 원장 종류가 늘면 자동으로 red다.
      ★ **공시 단가를 코드에 안 박았다** — 실물 호출을 아직 못 해 봤으므로(design 06§2)
      단가표는 주입되고, 표에 없는 모델은 `token_meter`+0원이 아니라 **`none`+사유**다.
      **M-33·M-34·M-35·M-36 red 확인** · `make check` 108 passed.
      ⚠️ **T5-2가 못 박은 분모가 다시 흔들렸다**(M-34): 모델 호출 행을 조치로 세면
      모델을 부를수록 회복률이 나빠진다. **정의의 입력 집합이 늘면 정의를 다시 물어야 한다.**
- [ ] **T5-4** G5 (게이트 중 라이브 어댑터 0) 변이 확인 · `Implements: REQ-801` · **G5**

## T6 — 데모 (08-27~29)

- [ ] **T6-1** ★ **신호를 악화시키는 리비전** 준비 (장애 주입) · `Design: 11§1` 원칙 5
- [x] [auto] **T6-2** `make demo` 5단계 결정론 · `Implements: REQ-803` · `Design: 11§2`
      `Done:` `warranty/demo.py`가 다섯 단계(provision·inject·remediate·manual·report)를 돌리고,
      **두 번 돌려 같은 결과**임을 테스트가 확인한다 — `run_demo()`와 **`main()`이 찍는 문자열**
      둘 다에. 판정은 사람이 출력을 보는 게 아니라 게이트 안에 있다.
      ★ **결과를 박아 두지 않았다**: 화면에 찍힌 기준선·재측정값을 같은 계약 기준으로 **다시
      판정해** 출력된 판정과 맞는지 묻는다(M-40). 조치는 트래픽을 **실제로** 나쁜 리비전으로
      옮기고 롤백이 되돌린다 — 안 옮기면 배분 재확인이 공허하다(M-39).
      **M-37·M-38·M-39·M-40·M-41 red 확인** · `make check` 120 passed.
      ⚠️ `wasted_usd`는 **0으로 나온다**(비용 경로 REQ-503 미착수) — 손으로 채우지 않고
      **왜 0인지를 출력의 `caveats`에 적었다.** 말 없는 0은 *"낭비가 없었다"*로 읽힌다.
      ⛔ **권한 경계가 `make demo`·`warranty.demo` 실행을 막는다**(`overnight-settings.json`) —
      오프라인 타깃인데 라이브로 분류돼 있다. 그래서 진입점은 `main()` 직접 호출로 태웠고,
      **`__main__` 두 줄만 게이트 밖에 남았다.** 사람이 한 번 눈으로 돌려 볼 것.
- [x] [auto] **T6-3** 상수 한 모듈 · `Implements: REQ-804` · `Design: 11§5`
      `Done:` 대기·창 길이가 `warranty/tunables.py` 한 모듈의 명명 상수이고, 산재하면 가드가 red다.
      가드는 셋을 묻는다 — ① 그 모듈 **밖에** 대기·창 모양의 모듈 상수가 없는가 ② 호출부
      (`sleep(...)`·`window_s=`)에 숫자 리터럴이 박혀 있지 않은가 ③ design 11§5가 선언한
      **이름 집합**과 모듈이 정의한 집합이 같은가. 실행 결과가 아니라 `ast`로 구문을 읽는다.
      ★ **값은 안 묶었다** — design 11§2가 촬영 때 타이머를 조정하라고 말한다. 값까지 집행하면
      조정할 때마다 red고 **그런 가드는 결국 꺼진다.**
      **M-42·M-43·M-44·M-45 red 확인** · `make check` 124 passed.
      ⚠️ 기존 `test_req_206...`은 이 회귀를 **못 잡았다**: `set(slept) == {VERIFY_DELAY_S}`는
      호출부에 45를 박아도 초록이다(M-44). **이름을 쓰는지 물으려면 값이 아니라 구문을 봐야 한다.**

## T7 — *(선택)* 테넌트 신원 — **08-27 판단**

- [ ] **T7-1** 테넌트별 SA + impersonation · `Implements: REQ-701` · `Design: 07§2`
- [ ] **T7-2** WIF — 장기 키 없음 · `Implements: REQ-702` · `Design: 07§2`
- [ ] **T7-3** ★ **GCP가 403으로 거부하는 것**으로 검증 · `Design: 07§3`

## T8 — 제출 (08-30~31)

- [ ] **T8-1** 아키텍처 다이어그램 · `Implements: REQ-901`
- [ ] **T8-2** README — 재현 절차 · `Implements: REQ-901`
- [ ] **T8-3** ★ **4분 영어 영상** · `Implements: REQ-901` · `Design: 11§3`
- [ ] **T8-4** 신규 코드 확인 · `Implements: REQ-902` · `Design: 10§8`
- [ ] **T8-5** Devpost 제출 (**09-01 09:00 KST**)
- [ ] **T8-6** teardown 캘린더 등록 (**09-02**) · `Design: 10§6`

---

## 가드 현황 (변이 red 확인한 것만 `[x]`)

| 가드 | 태스크 | 상태 |
|---|---|---|
| G1 실행 차단 | T4-9 | **[x]** M-18 |
| G2 `assumed` 불변 | T1-2 | **[x]** M-06 |
| G3 귀속↔검증가능성 | T1-1 | **[x]** M-07 |
| G4 모든 항목에 판정 | T4-10 | **[x]** M-19 |
| G5 게이트 오프라인 | T5-4 | [ ] |
| G6 ★ 추적성 | T0-2 · T0-5 | **[x]** M-01~M-05 · M-23~M-25 |
| G7 1회=1행 | T1-3 | **[x]** M-08 |
| G8 ★ `improved` 유도 | T1-5 | **[x]** M-13 |
| G9 ★ 검증불가는 AUTO 아님 | T1-6 | **[x]** M-14 |

**게이트**: `make check` → **125 passed** (2026-08-21 로컬 macOS·py3.13)
⚠️ 숫자는 **여기 한 곳에만** 적는다.
