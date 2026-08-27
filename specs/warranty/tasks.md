# tasks — warranty

작성: 2026-08-19 · 최종 정리: 2026-08-27 · 권위: `requirements.md` · 설계: `design.md` + `design/*.md`

> 이 파일은 **열린 실행 계획**과 요구사항→태스크 추적성만 소유한다.
> 완료 상세는 [`docs/COMPLETED_SUMMARY.md`](../../docs/COMPLETED_SUMMARY.md), 시간순 증거는
> [`docs/PROGRESS_LOG.md`](../../docs/PROGRESS_LOG.md)와
> [`docs/archive/PROGRESS_LOG-2026-08.md`](../../docs/archive/PROGRESS_LOG-2026-08.md),
> 정리 전 경고 원문은
> [`TASKS-SNAPSHOT-2026-08-27.md`](../../docs/archive/TASKS-SNAPSHOT-2026-08-27.md)에 있다.
> `[x]`는 테스트와 변이 red까지 확인한 오프라인 완료, `[~]`는 실물 수용 기준이 남은 부분 완료다.
> `[auto]`만 overnight가 소비한다. 실물 API·배포·제출·주관 검수는 사람이 한다.

---

## 일정과 현재 초점

- 제출: **2026-09-01 09:00 KST** · teardown: **09-02** · Free Trial 만료: **09-06**.
- **다음**: T2-4 — Secret Manager 비밀·IAM을 준비해 재배포하고 D15 인증 행렬을 실물 검증한다.
- 현재 실물: `warranty-api` + `demo-target`(리비전 2개). D15 코드는 로컬 완료, 실물은 이전 리비전.
- 오프라인 기준선: 이 파일 하단의 `make check` 한 곳만 권위로 둔다.

## 열린 작업 — 우선순위순

### P0 — 실물 에이전트 왕복

- [~] **T2-4** 에이전트가 기준선→조치→같은 신호 재측정→실패 판정→트래픽 롤백→배분 재확인→
  롤백 후 재측정→원장 기록까지 수행한다. `Implements: REQ-201, REQ-202, REQ-301,
  REQ-302, REQ-303, REQ-304, REQ-501, REQ-502, REQ-601, REQ-604, REQ-901` · `Design: 10§7, 11`
  - [x] D15 로컬 경계: 공개 invoker + Secret Manager bearer, 503/401/유효→501 계약과 변이 검증.
  - [ ] D15 실물: 비밀 생성·`secretAccessor` IAM·재배포 뒤 `/livez` 공개와 인증 행렬을 확인한다.
  - 이미 확인: 사람이 한 실물 왕복과 Monitoring p95 `674.2 → 988.6 → 674.2 ms`.
  - 남음: `RunControl` + `SignalSource` + Firestore를 ADK 도구 경로에 배선하고 실물 증거를 남긴다.
- [~] **T2-1** ADK + Gemini 실물 호출은 성공했다. 라이브 테스트와 에이전트 왕복으로
  수용 기준을 닫은 뒤 REQ 상태를 재판정한다. `Implements: REQ-601` · `Design: 06§2–3`

### P1 — 제출 가능한 데모

- [ ] **T5-1** 응답에 판정·검증 근거·트래픽 배분을 노출한다. `Implements: REQ-604` · `Design: 08§3.1`
- [ ] **T6-1** 건강하지만 느린 리비전으로 신호를 실제 악화시킨다. `Design: 11§1`
- [ ] **T8-2** README 재현 절차를 사람 기준으로 최종 확인한다. `Implements: REQ-901`
- [ ] **T8-3** 4분 영어 영상을 녹화한다. `Implements: REQ-901` · `Design: 11§3`
- [ ] **T8-4** 신규 코드 여부를 확인한다. `Implements: REQ-902` · `Design: 10§8`
- [ ] **T8-5** Devpost에 제출한다 — **09-01 09:00 KST**.
- [ ] **T8-6** 프로젝트 teardown 캘린더를 등록한다 — **09-02** · `Design: 10§6`

### P2 — Day-1 수명주기

- [ ] **T3-1** Cloud Run 서비스 프로비저닝과 계약 동시 산출. `Implements: REQ-101` · `Design: 01§1`
- [ ] **T3-4** 리소스 삭제 시 계약을 `retired`로 전환. `Implements: REQ-105` · `Design: 01§5`

### P3 — 선택 범위

- [ ] **T0-4** BQ 결제 내보내기·멱등 화해·기한/차이. `Implements: REQ-506, REQ-509` · `Design: 05§4`
- [ ] **T7-1** 테넌트별 SA + impersonation. `Implements: REQ-701` · `Design: 07§2`
- [ ] **T7-2** WIF로 장기 키를 제거. `Implements: REQ-702` · `Design: 07§2`
- [ ] **T7-3** 다른 테넌트 접근이 GCP 403으로 거부되는지 실증. `Design: 07§3`

---

## 완료 추적성 인덱스

> 상세·실패·교훈은 위 완료 요약/로그/스냅샷 링크가 소유한다. 여기서는 G6가 요구하는
> **요구사항→태스크 귀속**과 현재 판단에 필요한 결과만 남긴다.

| 태스크 | 압축 결과 | Implements |
|---|---|---|
| T0-1~3 | 레포·게이트·전용 GCP 프로젝트·Cloud Run 배포 기반 | REQ-801, REQ-802, REQ-805 |
| T0-5~10 | spec 참조·기록 신선도·타입·설계값 가드 | REQ-801, REQ-802 |
| T1-1~6 | 계약/원장 자료형·3축 판정·불변식 | REQ-102, REQ-402, REQ-501, REQ-502, REQ-503, REQ-504, REQ-505, REQ-507 |
| T2-2~3 | Cloud Run 서비스와 장애 리비전 2개 실물 배포 | REQ-602 |
| T3-2~3 | 생성 응답에서 계약 유도·계약 없으면 MANUAL | REQ-103, REQ-104 |
| T4-1~4 | 같은 신호 측정·계약 판정·모델 근거·빈 창 처리 | REQ-201, REQ-202, REQ-203, REQ-204, REQ-205 |
| T4-5~8 | 사전 롤백 계획·원자적 롤백·재측정·에스컬레이션 | REQ-301, REQ-302, REQ-303, REQ-304, REQ-305 |
| T4-9~12 | 판정 집행·승인·예산 예약·파괴 조치 승인 | REQ-401, REQ-403, REQ-404, REQ-405, REQ-406 |
| T4-13 | 재측정 상수 단일 출처 | REQ-206, REQ-804 |
| T5-2~4 | 회복률·모델 호출 원장·오프라인 게이트 | REQ-508, REQ-603, REQ-801 |
| T6-2~3 | 결정론적 5단계 데모·상수 단일 출처 | REQ-803, REQ-804 |
| T8-1 | OVERVIEW §4 Mermaid를 제출 다이어그램 단일 출처로 노출 | REQ-901 |
| T9-1~5 | 검증·롤백·계약 수명·원장·선택 화해의 변이 하중 | REQ-105, REQ-201, REQ-202, REQ-203, REQ-301, REQ-302, REQ-506, REQ-507, REQ-509 |
| T10-1~3 | 문장 단위 추적성·상태/설계 어긋남 기록 | REQ-501, REQ-506, REQ-802 |
| T11-1~6 | 배포 산출물·의존성·README·스윕 증거 가드 | REQ-602, REQ-801, REQ-802, REQ-805, REQ-901 |
| T12-1~10 | 서버·모델 판정·ADK 배선·배포 검사·live 격리 | REQ-303, REQ-601, REQ-602, REQ-604, REQ-801, REQ-802 |
| T13-1~5 | Monitoring 어댑터·40/40/40 부하·다이어그램 회수 | REQ-201, REQ-202, REQ-803, REQ-901 |
| T13-6 | 문서 예산 회수: log≤120 · open plan≤200 | REQ-802 |

## 가드 현황

| 가드 | 태스크 | 변이 |
|---|---|---|
| G1 실행 차단 | T4-9 | M-18 |
| G2 `assumed` 불변 | T1-2 | M-06 |
| G3 귀속↔검증가능성 | T1-1 | M-07 |
| G4 모든 항목 판정 | T4-10 | M-19 |
| G5 게이트 오프라인 | T5-4 · T12-5 | M-159~M-164 |
| G6 추적성 | T0-2 · T0-5 · T10-1 | M-01~M-05 · M-23~M-25 · M-78~M-81 |
| G7 1회=1행 | T1-3 | M-08 |
| G8 `improved` 유도 | T1-5 | M-13 |
| G9 검증불가는 AUTO 아님 | T1-6 | M-14 |

**게이트**: `make check` → **330 passed** (2026-08-27 로컬 macOS·py3.13)

숫자는 여기 한 곳에만 둔다. 변이 문서의 기준선 숫자는 해당 증거가 어느 스위트를 봤는지
나타내는 별도 사실이며, T0-8이 둘의 불일치를 집행한다.
