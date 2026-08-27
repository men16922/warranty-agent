# PROGRESS_LOG — warranty

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 월별 아카이브로 민다.
> 밀려난 것 → [`archive/PROGRESS_LOG-2026-08.md`](archive/PROGRESS_LOG-2026-08.md) (T6-2 이전 전부).
> 권위: 요구사항=`specs/warranty/requirements.md` · 계획=`specs/warranty/tasks.md` ·
> 현재 상태=`docs/OVERVIEW.md` §10 · 검증 기록=`docs/evidence/`.

---

## 2026-08-27 — 논지 한 덩어리를 응답 모양으로 고정했다 · T5-1 렌더러 (gate 356 → 372)

- **Status**: T5-1 `[~]`. design 08§3.1의 응답을 내는 `wire.py`가 생겼다. 경로는 아직 501이다.
- **Changed**: `remediate_response()` — `rule`·`rationale`·`verified_traffic`이 **필수 칸**이고,
  `executed`·`improved`·`rolled_back`이 셋으로 따로 나간다. 돈은 문자열, 빈 창은 `null`,
  실측은 추정 **옆칸**이다. 테스트 16 · 변이 M-224~M-232.
- **왜 이 셋인가**: 4분 안에 논지가 전달되려면 화면에 보여야 한다. 로그에만 있으면 없는
  것과 같다 — `performed: true`만 남기고 배분을 지우면 그것은 측정이 아니라 주장이다.
- **Verified**: `make check` **372 passed** · 전체 **232종 red**, `❌` 0, 복구·잔여 232/0
  (1160줄 원본 로그).
- **Blockers**: `POST /actions/{action_id}:remediate`가 501이라 이 덩어리는 아직 아무에게도
  안 보인다. 경로를 열려면 실물 `ActionExecutor`·`BudgetStore`와 합성 지점이 먼저다.
- **Next**: **T2-4 잔여** — 실행자·예산·합성 지점 → ADK 도구 넷 → `/agent:chat` 실물 왕복.

---

## 2026-08-27 — 계약과 원장이 Firestore로 나갔다 오는 길 · T14-1 (gate 330 → 356)

- **Status**: T14-1 `[x]`. `ContractStore`·`Ledger`의 실물 절반이 생겼다. 배선은 아직 아니다.
- **Changed**: `live_store.py`(문서 매핑·질의·트랜잭션 전이) · 원장 전이 넷을 `domain/entry.py`의
  순수 함수로 분리하고 인메모리 저장소가 그것을 **위임**하게 했다 · design 08§2.1 · 테스트 26 ·
  `google-api-core` 선언(`AlreadyExists`를 이름으로 잡는다 — 1회=1행을 Firestore가 집행한다).
- **왜 분리했나**: 저장소가 둘이 되는 순간 불변식이 두 벌이 된다. 두 벌이면 한쪽만 고쳐지는
  날이 오고, 그날 원장은 **저장소에 따라 다른 것을 허용한다**. 어댑터에 `replace(` 가 없다는
  것을 소스로 집행한다.
- **⛔ 가드가 먼저 틀렸다**: M-222(Firestore 생성 입구의 tripwire 제거)가 **안 죽었다.**
  G5 census가 함수를 **단순 이름**으로 담고 있어서 `LiveContractStore._db`를 지워도
  `LiveLedger._db`가 그 자리를 덮고 있었다 — 같은 이름의 메서드가 서로를 가린 것이다.
  census를 클래스까지 붙인 이름으로 고친 뒤 M-222는 red가 됐다. 이 blind spot은
  live 어댑터가 **둘 이상 같은 이름의 메서드를 가진 첫 모듈**에서만 보였다.
- **⛔ 리팩터가 변이 여덟을 껐다**: 전이를 모듈 함수로 옮기자 M-06·M-70·M-71·M-73~M-77의
  패턴이 들여쓰기와 `{entry_id}`→`{current.entry_id}`에서 어긋나 **적용조차 안 됐다.**
  하네스가 *"변이가 파일을 바꾸지 못했다"*로 잡았다 — 그 줄이 없었으면 여덟은 조용히
  죽은 변이가 됐다. 전부 다시 겨눠 red 회복.
- **Verified**: `make check` **356 passed** · M-214~M-223 red · 전체 **223종 red**, `❌` 0,
  복구·잔여 223/0(1115줄 원본 로그).
- **Blockers**: 실물 Firestore 왕복은 미수행(컬렉션도 아직 없다). 실물 `ActionExecutor`·
  `BudgetStore`와 이들을 조립하는 합성 지점이 없어 `/agent:chat`은 여전히 501이다.
- **Next**: **T2-4 잔여** — 실행자·예산·합성 지점을 만들어 ADK 도구 넷을 실물 어댑터에 붙인다.

---

## 2026-08-27 — 공개 URL은 200, 과금 경로는 401 — 실물이 계약대로 답했다 · D15 (gate 330 유지)

- **Status**: T2-4의 D15 실물 `[x]`. 로컬에서만 참이던 인증 경계가 Cloud Run에서 같은 값을 냈다.
- **Changed**: `secretmanager` API 활성 · 비밀 `warranty-agent-auth` v1(64B) · 런타임 SA에
  `secretAccessor` · 이미지 `a7c660d` 재배포 → 리비전 `warranty-api-00002-c6q` 100% 트래픽.
  ⚠️ 배포 직전에 발견: 문서는 gate 330을 말하는데 HEAD는 296이었다. 증분 4개가 미커밋이라
  이미지 태그(=커밋)가 가리키는 곳에 D15 코드가 없었다 — 먼저 커밋하고 배포했다.
- **Verified**: `/livez` **200** 공개 · 무헤더/틀린 토큰/틀린 스킴 **전부 401** · 유효 토큰만
  **501**(어댑터 없음 사유 포함) · 선언 안 된 경로 404. 구형·신형 URL 둘 다 같은 서비스.
  증거 `docs/evidence/d15-auth-matrix-2026-08-27.log` · `deploy-2026-08-27.log`.
- **Blockers**: `503`(비밀 미주입) 분기는 실물에서 안 만들었다 — 만들려면 살아 있는 리비전의
  비밀 바인딩을 떼야 해서, 로컬 계약·변이 검증(M-206~M-213)으로만 남는다.
- **Next**: **T2-4 잔여** — `RunControl`·`SignalSource`·Firestore를 ADK 도구 경로에 배선해
  `/agent:chat`의 501을 실물 왕복으로 바꾸고 원장까지 잇는다.

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
