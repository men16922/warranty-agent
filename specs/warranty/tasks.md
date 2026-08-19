# tasks — warranty

작성: 2026-08-19 · 권위: `requirements.md` · 설계: `design.md` + `design/*.md`

> 모든 태스크는 REQ와 설계 절을 가리킨다. `[x]`는 **테스트가 있고 변이로 red를 확인한 것**만.

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
- [ ] **T3-3** 계약 없는 리소스 → `MANUAL` · `Implements: REQ-104` · `Design: 01§4`
- [ ] **T3-4** 리소스 삭제 시 계약 `retired` · `Implements: REQ-105` · `Design: 01§5`

## T4 — Day-2: 조치 · 검증 · 롤백 (08-22~25) — **논지의 전부**

- [ ] **T4-1** 기준선 측정 (Cloud Monitoring) · `Implements: REQ-201` · `Design: 02§2`
- [ ] **T4-2** ★ 재측정 — **기준선과 같은 함수** · `Implements: REQ-202` · `Design: 02§2`
- [ ] **T4-3** 계약 기준으로 판정 + 빈 창 → `unverifiable` · `Implements: REQ-203, REQ-205` · `Design: 02§3`
- [ ] **T4-4** ★ **애매할 때 모델이 판단하고 근거를 남긴다** · `Implements: REQ-204` · `Design: 02§3.1`
- [ ] **T4-5** 롤백 계획을 조치 **전에** 고정 · `Implements: REQ-301` · `Design: 03§2`
- [ ] **T4-6** ★ 트래픽 전환 + **배분 재확인** · `Implements: REQ-302, REQ-303` · `Design: 03§3`
- [ ] **T4-7** ★ **롤백 후 재측정** · `Implements: REQ-304` · `Design: 03§4`
- [ ] **T4-8** 롤백 불가 → 에스컬레이션 · `Implements: REQ-305` · `Design: 03§5`
- [ ] **T4-9** 게이트가 실행을 **막는다** · `Implements: REQ-403` · `Design: 04§2` · **G1**
- [ ] **T4-10** 모든 항목에 `decision` · `Implements: REQ-401` · **G4**
- [ ] **T4-11** 예약/정산 · 승인 시 재판정 · `Implements: REQ-404, REQ-405` · `Design: 04§3–4`
- [ ] **T4-12** 파괴적 조치 강제 승인 · `Implements: REQ-406` · `Design: 04§5`
- [ ] **T4-13** 재측정 상수 한 곳 · `Implements: REQ-206, REQ-804` · `Design: 02§4`

## T5 — 출력 (08-25~26)

- [ ] **T5-1** 응답에 판정·검증 근거·트래픽 배분 · `Implements: REQ-604` · `Design: 08§3.1`
- [ ] **T5-2** ★ **회복률 리포트** · `Implements: REQ-508` · `Design: 05§5`
- [ ] **T5-3** 모델 호출도 원장에 · `Implements: REQ-603` · `Design: 06§5`
- [ ] **T5-4** G5 (게이트 중 라이브 어댑터 0) 변이 확인 · `Implements: REQ-801` · **G5**

## T6 — 데모 (08-27~29)

- [ ] **T6-1** ★ **신호를 악화시키는 리비전** 준비 (장애 주입) · `Design: 11§1` 원칙 5
- [ ] **T6-2** `make demo` 5단계 결정론 · `Implements: REQ-803` · `Design: 11§2`
- [ ] **T6-3** 상수 한 모듈 · `Implements: REQ-804` · `Design: 11§5`

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
| G1 실행 차단 | T4-9 | [ ] |
| G2 `assumed` 불변 | T1-2 | **[x]** M-06 |
| G3 귀속↔검증가능성 | T1-1 | **[x]** M-07 |
| G4 모든 항목에 판정 | T4-10 | [ ] |
| G5 게이트 오프라인 | T5-4 | [ ] |
| G6 ★ 추적성 | T0-2 | **[x]** M-01~M-05 |
| G7 1회=1행 | T1-3 | **[x]** M-08 |
| G8 ★ `improved` 유도 | T1-5 | **[x]** M-13 |
| G9 ★ 검증불가는 AUTO 아님 | T1-6 | **[x]** M-14 |

**게이트**: `make check` → **51 passed** (2026-08-19 로컬 macOS·py3.13)
⚠️ 숫자는 **여기 한 곳에만** 적는다.
