# PROGRESS_LOG — warranty

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 월별 아카이브로 민다.
> 밀려난 것 → [`archive/PROGRESS_LOG-2026-08.md`](archive/PROGRESS_LOG-2026-08.md) (T6-2 이전 전부).
> 권위: 요구사항=`specs/warranty/requirements.md` · 계획=`specs/warranty/tasks.md` ·
> 현재 상태=`docs/OVERVIEW.md` §10 · 검증 기록=`docs/evidence/`.

---

## 2026-08-29 — 신규 코드 요건은 참이었고, 그것을 말할 자리가 없었다 · T8-4 (gate 392 유지)

- **Status**: T8-4 `[x]`(확인 완료). REQ-902의 상태 칸은 여전히 `TODO`다 — 아래가 이유다.
- **Verified**: 첫 커밋 `741cec5` 2026-08-19, 79개 전부 08-19~08-29 — 제출 기간 08-03~08-31
  안이다. `dependencies = []`로 게이트는 표준 라이브러리만 쓰고, `[cloud]`는 전부 공개 Google
  패키지다. `git+`·`file://`·사설 인덱스 0건, `vendor/`·`third_party/` 없음.
- **⛔ 같은 벽이 셋째**: REQ-602·901·902 셋 다 **사실은 참인데** 겨냥한 테스트가 0이라
  게이트가 `TODO`를 강제한다. 손으로 확인한 것을 상태 칸에 올리려면 집행하는 자리가 필요하다
  — 그게 이 저장소가 스스로에게 건 규칙이고(§9), 여기서 예외를 두면 규칙이 규칙이 아니게 된다.
  ⇒ T5-3을 셋을 함께 닫는 태스크로 넓혔다.
- **Next**: T5-3(겨냥 + 변이) 또는 T8-3 영상. 제출 09-01 · teardown 09-02.

## 2026-08-29 — 헤드라인이 측정하지 않은 수를 측정치처럼 말하고 있었다 · T8-2 (gate 392 유지)

- **Status**: T8-2 `[x]`. README를 심사자 기준으로 걸으며 결함 셋을 회수했다.
- **⛔ 가장 큰 것**: 첫 화면이 `executed 41 · improved 23 (56%) · rolled back 12`를
  **측정치처럼** 적고 있었다. 그 수는 어디서도 측정되지 않았다 — 영상 대본(design 11§3)의
  리포트 슬라이드 값이 README와 OVERVIEW§7로 번진 것이다. 원장의 조치는 **둘**이고
  `make demo`는 `executed 1 · improved 0`을 낸다. **심사자가 재현하면 첫 화면과 어긋난다.**
- **왜 세 번째인가**: OVERVIEW §10이 이미 같은 병으로 `120 passed`·`VERIFIED 18` 넷을 틀렸고
  (T0-6), 그때 내린 규칙이 *"세는 자리는 하나다"*였다. 그 규칙이 §7과 README에는 안 닿아
  있었다 — 규칙을 적은 곳과 어긴 곳이 **같은 파일**이었다.
- **Changed**: 세 자리에서 수를 지우고 모양만 남겼다. 11§3은 리포트 칸을 *"그 실행이 실제로
  낸 값"*으로 바꿨다 — 숫자를 크게 만들고 싶으면 원장을 채우는 실행이 먼저다.
- **또 둘**: README 상태가 *"Design complete, implementation in progress"*였다(실물이 도는데).
  실물 URL 표와 `/livez` 200 · 무토큰 401 · demo-target `/work` 200을 넣고 셋 다 재확인했다.
  `make demo`의 caveat은 *"REQ-601·602는 TODO"*라고 말했는데 REQ-601은 `VERIFIED`다 —
  상태 주장을 지우고 `requirements.md`를 가리키게 했다.
- **Verified**: `make check` **392 passed**. `test_demo.py`가 caveat에서 `REQ-601`을 요구하는데
  문자열은 남아 있어 초록이다 — 지운 것은 **상태 주장**이지 참조가 아니다.
- **Next**: T8-3 영상(부하 켠 채) → T5-3(REQ-602 겨냥) → 제출(09-01) → teardown(09-02).

## 2026-08-29 — 신호는 트래픽이 흐르는 동안에만 존재한다 · T8-1 (gate 392 유지)

- **Status**: T8-1 `[x]`. 08-28에 `null`이던 신호가 부하 아래에서 값을 냈다.
- **Changed**: 코드는 안 건드렸다 — 실물 관측만 했다. demo-target `/work`에 1140건
  (워커 5 · 200초 · 약 5.7 req/s)을 넣어 120초 창을 채우고, 수집 지연 동안 창이 비지 않게
  워커 3으로 부하를 유지한 채 프로덕션 `inspect`를 불렀다.
- **Verified**: p95 **674.17 ms** · 관측점 1 · 계약 `demo-target-warranty-v1` ·
  롤백 대상 `demo-target-00001-swl`. 조치는 실행하지 않았다.
- **대비가 요점이다**: 같은 질문에 08-28은 "점 0 · null", 08-29는 "674.17". 08-28의 답은
  고장이 아니라 계약대로였고(REQ-205), **영상에 담을 그림이 아니었을 뿐이다.**
  ⇒ 촬영은 부하를 켜 둔 채로 한다. 이건 scale-to-zero의 대가이고 REQ-805를 지키는 값이다.
- **⚠️ 확인하지 않은 것**: 674.171849767732가 08-28 기준선과 찍힌 자리까지 같다. 고정
  620ms + 히스토그램 버킷 보간이면 결정론적이 되는 것으로 설명되지만 **확인하지 않았다.**
  관찰만 적는다 — 재현성에는 유리하고, 원측정이 아닐 가능성은 열려 있다.
- **Next**: T8-3 영상(부하 켠 채) → T8-2 README 검수 → 제출(09-01) → teardown(09-02).
- **Evidence**: `docs/evidence/live-signal-load-2026-08-29.log`.

## 2026-08-28 — 공개 URL이 드디어 200을 냈다 · 커밋 → 배포 → 프로덕션 왕복 (gate 392)

- **Status**: T5-1의 배포 절반 완료. 직접 `/actions/*` 경로는 아직 501이다.
- **Changed**: 미커밋 29건을 `dbb6f74` 하나로 묶어 커밋했다 — 배포 태그가 커밋 SHA라
  **커밋이 곧 배포 블로커**였다. 빌드 `e5fb704c` SUCCESS, 리비전 `00003-z9m` 트래픽 100%.
- **Verified**: `/livez` 200 공개 · 무헤더 401 · 틀린 토큰 401 · **유효 토큰 200**(이전 배포는 501).
  프로덕션 `inspect` 한 번이 Firestore 원장에 model_call 두 행(`01m1404chq…`·`01m1404cnt…`)을
  남겼다 — REQ-603이 로컬이 아니라 배포된 리비전에서 성립한다.
- **⛔ 경계**: 신호 점 0 · 값 `null`. demo-target에 트래픽이 없어 p95 창에 표본이 없다.
  에이전트는 *"건강하다"*가 아니라 **"지금은 읽을 수 없다"**를 답했다 — 계약대로다(REQ-205).
  ⇒ 영상은 **부하가 먼저다**(T8-1을 새로 열었다).
- **⛔ 상태 칸이 실물보다 뒤에 있다**: REQ-602(대회 필수 · Cloud Run에서 돈다)는 실제로 도는데
  `TODO`다. `Verifies: REQ-602`를 단 테스트가 0이라 게이트가 그렇게 강제한다 — 게이트가 틀린 게
  아니라 **겨냥한 자리가 없다.** 조용히 올리지 않고 T5-3으로 열어 뒀다.
- **Next**: T8-1 부하 → T8-3 영상 → T8-2 README 검수 → 제출(09-01) → teardown(09-02).
- **Evidence**: `docs/evidence/live-agent-chat-2026-08-28.log` · `docs/evidence/deploy-2026-08-28.log`.

## 2026-08-28 — ADK가 실물 조치·검증·원자적 롤백을 끝까지 돌렸다 (gate 372 → 392)

- **Status**: T2-1·T2-4·T5-2·T6-1 `[x]`; REQ-601·603·604 `VERIFIED`. 공개 리비전 배포는 아직이다.
- **Changed**: 실행자·Firestore 예산·시계/ULID·Vertex 전송·합성 지점·ADK 단발 세션을 만들고,
  인증된 `/agent:chat` JSON을 실물 콜백에 연결했다. `(default)` Firestore Native DB와 계약도 생성했다.
- **Verified**: `make check` **392 passed** · M-01~M-246 **246종 전부 red**, 복구 392·잔여 0.
  실물 ADK 응답은 `AUTO`, p95 `674.17 → 988.60`, `not_recovered`, 건강 리비전 100% 롤백.
- **원장/예산**: `01m13fpgc8e091es3ekpqx48f4` · 잔액 `$0.49` · 미정산 0.
- **Boundary**: `signal_restored=false` — 120초 p95 창에 장애 표본이 남아 신호 복구는 증명 못 했다.
- **모델 계량**: 실물 `inspect`의 ADK 모델 응답 둘이 Firestore `model_call` 두 행이 됐다.
- **Blockers**: 현재 Cloud Run 리비전은 이전 SHA다. 커밋 없이 배포하면 이미지 태그가 거짓이 된다.
- **Next**: 명시적 커밋·재배포 → bearer `/agent:chat` 프로덕션 왕복 → 영상.
- **Evidence**: `docs/evidence/live-adk-remediate-2026-08-28.log`.

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
