# tasks — warranty

작성: 2026-08-19 · 최종 정리: 2026-08-28 · 권위: `requirements.md` · 설계: `design.md` + `design/*.md`

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
- **다음**: 부하를 켠 채 4분 영상을 녹화한다(T8-3) — 신호는 T8-1에서 살아났다.
- 현재 실물: `warranty-api` 리비전 `00003-z9m`(이미지 `dbb6f74` · `/agent:chat` 실물) + `demo-target`(리비전 2개).
- 오프라인 기준선: 이 파일 하단의 `make check` 한 곳만 권위로 둔다.

## 열린 작업 — 우선순위순

### P0 — 실물 에이전트 왕복

- [x] **T2-4** 에이전트가 기준선→조치→같은 신호 재측정→실패 판정→트래픽 롤백→배분 재확인→
  롤백 후 재측정→원장 기록까지 수행한다. `Implements: REQ-201, REQ-202, REQ-301,
  REQ-302, REQ-303, REQ-304, REQ-501, REQ-502, REQ-601, REQ-604, REQ-901` · `Design: 10§7, 11`
  - [x] D15 로컬 경계: 공개 invoker + Secret Manager bearer, 503/401/유효→501 계약과 변이 검증.
  - [x] D15 실물: 비밀·`secretAccessor` IAM·재배포 뒤 `/livez` 200 공개, 무헤더/틀린 토큰/틀린 스킴
    전부 401, 유효 토큰만 501을 실물에서 확인했다 — `docs/evidence/d15-auth-matrix-2026-08-27.log`.
  - 실물 확인: ADK·Gemini가 도구를 호출해 Monitoring p95 `674.2 → 988.6 ms`,
    `not_recovered`, 원자적 롤백과 건강 리비전 100%를 응답·Firestore 원장에 남겼다.
  - [x] 계약·원장의 Firestore 어댑터(T14-1): 문서 매핑·질의·전이가 오프라인에서 검증됐다.
  - 증거: `docs/evidence/live-adk-remediate-2026-08-28.log` · 원장 `01m13fpgc8e091es3ekpqx48f4`.
- [x] **T2-1** ADK Runner + Vertex AI Gemini 3.7 Flash 실물 도구 호출 완료.
  `Implements: REQ-601` · `Design: 06§2–3`
- [x] **T5-2** 판정 모델과 ADK 오케스트레이션 모델 응답을 호출 1건=원장 1행으로 계량했다.
  실물 `inspect`의 모델 응답 둘이 Firestore 두 행이 됐다. `Implements: REQ-603` · `Design: 06§5`

### P1 — 제출 가능한 데모

- [~] **T5-1** 응답 렌더러와 인증된 `/agent:chat` 콜백 경로는 끝났다(`wire.py` · M-224~M-243).
  리비전 `00003-z9m`이 트래픽 100%이고 프로덕션 `/agent:chat`이 유효 토큰에 **200**을 낸다
  (무헤더·틀린 토큰은 401 유지). 그 요청 하나가 Firestore 원장에 model_call 두 행을 남겼다 —
  `docs/evidence/live-agent-chat-2026-08-28.log`.
  ⛔ `POST /actions/{action_id}:remediate` 직접 경로는 아직 501이다.
  `Implements: REQ-604` · `Design: 08§3.1`
- [x] **T8-1** demo-target `/work`에 부하 1140건을 넣어 120초 창을 채웠고, 프로덕션 `inspect`가
  p95 `674.17 ms` · 관측점 1을 냈다(08-28에는 점 0 · `null`이었다).
  ⚠️ **신호는 트래픽이 흐르는 동안에만 존재한다** — 촬영은 부하를 켜 둔 채로 한다.
  증거 `docs/evidence/live-signal-load-2026-08-29.log`. `Design: 11§1`
- [x] **T5-3** 제출·실물 요건의 상태 칸을 현실과 맞췄다 — **TODO 7 → 3 · VERIFIED 36 → 41**.
  - `REQ-902` 새 `tests/test_new_project.py` 둘 — 선언이 저장소 밖 출처를 끌어오는가 ·
    베끼어 심은 트리가 있는가. 편입의 흔한 모양이 **복사**라 따로 묻는다. M-247·M-248 red.
  - `REQ-602`·`REQ-901`은 **이미 검증하던 테스트가 선언만 안 하고 있었다** — `Verifies:`를
    붙였다(겨냥 2·3). 새 테스트를 쓰지 않았다.
  - `REQ-805`·`REQ-801`은 겨냥·변이를 이미 갖고 있는데 낮게 적혀 있었다 — 올렸다.
  - ⛔ **못 묻는 절반은 상태 칸이 덮지 않는다**고 요구사항 본문에 각각 적었다: 실물에서
    도는가(602) · 영상과 시각 증거(901) · 작성 날짜(902). 게이트가 그것을 안다고 하지 않는다.
  - ⛔ **하네스에 구멍이 있어 먼저 메웠다** — `create()`. 아래 T5-3(하네스)를 볼 것.
  `Implements: REQ-602, REQ-801, REQ-805, REQ-901, REQ-902` · `Design: 10§5, 10§8`
- [x] **T6-1** 느린 리비전 `00002-lss`로 p95를 실제 악화시키고 롤백했다. `Design: 11§1`
- [x] **T8-2** README를 심사자 기준으로 걸었고 **결함 셋을 회수했다**. `Implements: REQ-901`
  - ⛔ 헤드라인이 `executed 41 · improved 23 (56%)`을 **측정치처럼** 적고 있었다. 그 수는
    어디서도 측정되지 않았다 — 영상 대본(11§3)의 슬라이드 값이 번진 것이고, 원장의 조치는
    **둘**이다. `make demo`는 `executed 1 · improved 0`을 낸다. README·OVERVIEW§7·11§3 셋 다
    수를 지우고 **모양**만 남겼다(T0-6의 교훈이 세 번째로 같은 자리에서 났다).
  - ⛔ 상태가 *"Design complete, implementation in progress"*였다 — 실물이 도는데 안 돈다고
    말하고 있었다. 실물 URL 표와 `/livez` 200 · 무토큰 401을 넣었다(셋 다 재확인).
  - ⛔ `make demo`의 caveat이 *"REQ-601·602는 TODO"*라고 말했다. REQ-601은 `VERIFIED`다 —
    상태 주장을 지우고 `requirements.md`를 가리키게 했다.
- [ ] **T8-3** 4분 영어 영상을 녹화한다. `Implements: REQ-901` · `Design: 11§3`
- [x] **T8-4** 신규 코드 여부를 확인했다 — 사실관계는 전부 맞다. `Implements: REQ-902` · `Design: 10§8`
  - 첫 커밋 `741cec5` **2026-08-19**, 마지막까지 79개 전부 08-19~08-29 — 제출 기간
    08-03~08-31 **안**이다. 이전 이력이 없다.
  - `dependencies = []` — 게이트는 표준 라이브러리만으로 돈다. `[cloud]` 추가분은 전부
    공개 Google 패키지다. `git+`·`file://`·사설 인덱스 **0건**, `vendor/`·`third_party/` 없음.
  - 추적 파일 176 · 소스/테스트 `.py` 38.
  - ⛔ 그래도 상태는 `TODO`다 — 겨냥한 테스트가 없다. T5-3이 이 칸을 함께 닫는다.
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
| T14-1 | Firestore 문서 매핑·원장 전이 단일화·census 이름 한정 | REQ-102, REQ-501, REQ-503, REQ-505, REQ-801 |
| T5-3 | 제출·실물 요건의 오프라인 절반을 겨냥 + `create()` 변이 경로 | REQ-602, REQ-901, REQ-902 |
| T5-1(렌더러) | 원장 행 → design 08§3.1 응답 덩어리 | REQ-205, REQ-302, REQ-502, REQ-503, REQ-505, REQ-604 |
| T2-1·4 | ADK·Gemini 실물 도구 호출 → Monitoring·Cloud Run·Firestore 왕복 | REQ-201, REQ-202, REQ-301, REQ-302, REQ-303, REQ-304, REQ-501, REQ-502, REQ-601, REQ-604 |

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

**게이트**: `make check` → **394 passed** (2026-08-29 로컬 macOS·py3.13)

숫자는 여기 한 곳에만 둔다. 변이 문서의 기준선 숫자는 해당 증거가 어느 스위트를 봤는지
나타내는 별도 사실이며, T0-8이 둘의 불일치를 집행한다.
