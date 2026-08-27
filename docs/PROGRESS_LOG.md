# PROGRESS_LOG — warranty

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 월별 아카이브로 민다.
> 밀려난 것 → [`archive/PROGRESS_LOG-2026-08.md`](archive/PROGRESS_LOG-2026-08.md) (T6-2 이전 전부).
> 권위: 요구사항=`specs/warranty/requirements.md` · 계획=`specs/warranty/tasks.md` ·
> 현재 상태=`docs/OVERVIEW.md` §10 · 검증 기록=`docs/evidence/`.

---

## 2026-08-27 — 공개 URL과 무인 과금 권한을 갈랐다 · D15 (gate 311 → 330)

- **Status**: D15 앱 인증 경계의 로컬 구현·검증 완료. 실물 배포는 아직 이전 리비전이다.
- **Changed**: bearer 검증, 503/동일 401/유효→501 서버 경계, 공개 invoker+Secret Manager 배포 렌더링, 설계·테스트.
- **Verified**: `make check` **330 passed** · M-206~M-213 red · 전체 213종 red, `❌` 0, 복구·잔여 213/0(1065줄).
- **Blockers**: 비밀 생성·`secretAccessor` IAM·재배포·실물 HTTP 확인, ADK/Firestore 도구 배선은 미수행.
- **Next**: D15를 재배포해 `/livez` 공개와 503/401/501 행렬을 실증한 뒤 T2-4 실물 왕복을 잇는다.

---

## 2026-08-27 — 시작 문맥 예산을 다시 회복했다 · T13-6/T12-9 (gate 311 유지)

- **Status**: T13-6/T12-9 `[x]`. 완료 서사를 현재 계획에서 걷어내고 열린 판단만 남겼다.
- **Changed**: `PROGRESS_LOG` 1012→55줄 · open `tasks.md` 638→103줄 · `OVERVIEW` 240→239줄.
  옛 로그는 8월 아카이브에 최신순으로 병합했고, 정리 전 태스크 638줄은 읽기 전용 스냅샷으로 보존했다.
- **Completed**: `COMPLETED_SUMMARY`에 T13-1·2·4와 이번 정리를 M7 한 줄로 압축했다.
- **Verified**: 상대 링크 해석 · `git diff --check` · `make check` **311 passed**.
- **Blockers**: 공개 `/agent:chat`은 D15 앱 인증 선행. `/livez` 외 7경로는 정책상 501.
- **Next**: **T2-4** — D15 앱 인증을 설계·배선한 뒤 에이전트 실물 왕복을 원장까지 통과시킨다.

---

## 2026-08-27 — 기존 Mermaid를 단일 출처의 제출 다이어그램으로 회수 · T13-4 (gate 307 → 311)

- **Status**: T13-4/T8-1 `[x]`. 새 그림 없이 `OVERVIEW.md` §4를 독립 제출 표면으로 회수했다.
- **Changed**: README `Architecture diagram` 직접 앵커 · 링크 fragment 해석 · 테스트 4.
- **Verified**: 파일·§4 앵커·Mermaid 렌더 블록·단일 출처 · M-202~M-205 red.
  전체 **205종 전부 red**, `❌` 0, 복구 205, 잔여 없음 205(1025줄 원본 로그).
  최종 `make check` **311 passed**.
- **Blockers**: REQ-901의 영상·저장소 URL·실물 실행 시각 증거는 사람 판정이라 상태를 안 올렸다.
- **Next**: **T13-6 `/tidy-docs`**로 log≤120 · open plan≤200을 회복한 뒤 T2-4 실물 왕복 배선.

---

## 2026-08-27 — p95를 측정할 구간별 부하를 각본 값으로 고정 · T13-2 (gate 304 → 307)

- **Status**: T13-2 `[x]`. baseline/action/rollback의 부하 계획을 **40/40/40**으로 고정했다.
- **Changed**: design 11§1.1 · `demo.py` 출력 · 설계/코드/출력/0회·빈 계획을 묶는 테스트 3.
- **Verified**: `make demo`가 계획을 출력 · `make check` **307 passed** · M-198~M-201 red.
  전체 **201종 전부 red**, `❌` 0, 복구 201, 잔여 없음 201(1005줄 원본 로그).
- **Blockers**: 실제 부하 전송·실물 호출·배포는 미수행. 부하 계획 소비는 T2-4에 남아 있다.
- **Next**: **T13-4** 기존 Mermaid를 독립 산출물로 회수 → T2-4 실물 왕복 배선.
  T13-6 `/tidy-docs`도 남아 있다 — 이 파일은 여전히 120줄 한도를 크게 넘는다.

---

## 2026-08-27 — Cloud Monitoring 신호 어댑터의 오프라인 절반 완료 · T13-1 (gate 296 → 304)

- **Status**: T13-1 `[x]`. 실물 증거의 필터·p95 aligner/reducer·요청 모양을 어댑터로 옮겼다.
- **Changed**: `live_signal.py`(순수 요청/응답 + 지연 SDK + G5) · Monitoring 의존성/매핑 · 테스트 8.
- **Verified**: 실제 SDK 2.31 요청 타입과 proto-plus 응답 파싱 · `make check` **304 passed**.
  M-188~M-197 red · 전체 **197종 전부 red**, 복구 197, 잔여 0, `❌` 0(985줄 원본 로그).
- **Blockers**: 실물 API 재호출·배포·에이전트 도구 배선은 미수행. 공개 `/agent:chat`은 인증 선행.
- **Next**: **T13-2** 구간별 부하 → T13-4 독립 다이어그램 → T2-4 실물 에이전트 왕복 배선.

---
