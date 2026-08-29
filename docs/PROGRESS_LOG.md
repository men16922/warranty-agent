# PROGRESS_LOG — warranty

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 월별 아카이브로 민다.
> 밀려난 것 → [`archive/PROGRESS_LOG-2026-08.md`](archive/PROGRESS_LOG-2026-08.md) (T6-2 이전 전부).
> 권위: 요구사항=`specs/warranty/requirements.md` · 계획=`specs/warranty/tasks.md` ·
> 현재 상태=`docs/OVERVIEW.md` §10 · 검증 기록=`docs/evidence/`.

---

## 2026-08-29 — 로컬에서만 참이던 Day-1이 공개 URL에서 같은 값을 냈다 (gate 399)

- **Status**: T3-1의 실물 절반까지 끝. 배포 `warranty-api-00004-4db`(이미지 `32ffcad`).
- **Changed**: 코드는 안 건드렸다 — 커밋 `32ffcad`를 올리고 프로덕션에서 확인만 했다.
  빌드 `ad07e352` SUCCESS 44s.
- **Verified**: 자연어 한 줄(*"provision a service named day1-prod-demo, then tell me the
  contract"*)에 배포된 에이전트가 **실제로 서비스를 만들고** 계약
  `01m15qfgxv5ed6rzgr7bjzp1fk`를 함께 냈다. 리비전 `00001-qhp` Ready·ContainerHealthy,
  Firestore 계약의 `resource_filter`가 만든 이름을 가리킨다. HTTP 200 · 23.7s.
- **응답에 이유가 있다**: 에이전트가 `irreversible`을 말하면서 *"Initial deployment / no
  prior rollback revision available"*을 함께 냈다 — 판단 근거는 로그가 아니라 응답에
  있다(REQ-604)가 자연어 경로에서도 참이다.
- **태그가 스스로를 증명했다**: 만들어진 서비스의 이미지가 `32ffcad`다 — 만든 자와 같은
  태그. 프로비저너가 이미지를 설정으로 안 받고 *"지금 내가 무엇으로 도는지"*를 Cloud Run에
  물어서 쓰기 때문이고, 로컬(`dbb6f74`)에서 참이던 성질이 프로덕션에서도 같은 방식으로 참이었다.
- **경계는 그대로**: `/livez` 200 공개 · 무헤더 401 · 틀린 토큰 401.
- **⛔ 한계도 그대로**: 만든 서비스의 IAM은 비어 있다(T3-5).
- **teardown 범위가 넷이 됐다**: `warranty-api`·`demo-target`·`day1-warranty-demo`·
  `day1-prod-demo`. 만든 것을 목록에 안 적으면 teardown이 그것을 안 본다(T8-6).
- **Next**: T8-3 영상(부하 켠 채) → 제출(09-01) → teardown(09-02).
- **Evidence**: `docs/evidence/live-day1-prod-2026-08-29.log` · `deploy-2026-08-29.log`.

## 2026-08-29 — 첫 화면이 내세우던 Day-1 절반이 비어 있었다 · T3-1 (gate 394 → 399)

- **Status**: T3-1 `[x]` · REQ-101 `VERIFIED`. 실물 `provision`은 08-29까지
  `not_implemented`를 돌려주고 있었다 — Day-2만 실물이었다.
- **Changed**: `adapters/live_provision.py`(생성·되읽기) · `ContractStore.put`을 **포트에**
  넣고 Firestore에 구현 · `runtime.provision`이 생성→유도→기록을 **한 번에** 한다.
  계약은 어댑터가 안 만든다 — `derive_contract`가 생성 응답에서 유도한다(REQ-103).
- **이미지 출처가 하나다**: 새 서비스의 이미지를 설정으로 안 받고 *"지금 내가 무엇으로
  도는지"*를 Cloud Run에 물어서 쓴다. 그래서 만들어진 것은 `warranty-api`와 **같은 태그**
  (`dbb6f74`)로 떴다. 설정으로 받으면 값의 출처가 둘이 되고 한쪽만 낡는다.
- **Verified(실물)**: `day1-warranty-demo` 리비전 `00001-k9c` Ready·ContainerHealthy ·
  minScale 0 · 계약 `01m14xkweqd3bb0cf9ne4bwjkg`가 Firestore에 났고, **`inspect`가 같은
  실행에서 그것을 읽었다** — Day-1→Day-2 인계가 실물에서 성립했다.
- **⛔ `irreversible`은 결함이 아니다**: 갓 만든 서비스에는 돌아갈 리비전이 없다. 타입만
  보고 `reversible`을 쓰면 그 계약은 필요한 날 틀린다(design 01§3). 그리고 그 결과의 값은
  판정에서 난다 — 그 리소스는 자동 조치 대상이 아니다(REQ-402).
- **⛔ 만든 서비스는 아무도 못 부른다**: IAM 바인딩이 비어 403/401이다. 프로비저너는 초대
  권한을 주지 않는다 — 에이전트가 조용히 서비스를 전 세계에 여는 것은 기본값이 될 수 없다.
  대가는 분명하다: 그 리소스의 신호를 밖에서 부하로 못 채운다. 주장하지 않고 T3-5로 열었다.
- **G5가 자기 일을 했다**: `LiveContractStore.put`이 생성 경로를 부르면서 tripwire를 안
  지나 red가 났다. 가드가 시킨 대로 census가 아니라 **함수의 첫 줄**을 고쳤다(M-252).
- **Verified**: `make check` **399 passed** · 전체 스윕 **252종 전부 red**, `❌` 0,
  복구 252 · 잔여 0.
- **Next**: T8-3 영상(부하 켠 채) → 제출(09-01) → teardown(09-02, `day1-warranty-demo` 포함).
- **Evidence**: `docs/evidence/live-provision-2026-08-29.log`.

## 2026-08-29 — 참인데 말할 자리가 없던 요건 다섯을 회수했다 · T5-3 (gate 392 → 394)

- **Status**: T5-3 `[x]`. **TODO 7 → 3 · VERIFIED 36 → 41.** 남은 셋은 진짜 미구현이다.
- **Changed**: `tests/test_new_project.py`(REQ-902) 둘을 새로 썼다 — 선언이 저장소 밖 출처를
  끌어오는가 · 베끼어 심은 트리가 있는가. 편입의 흔한 모양이 **복사**라 따로 묻는다.
  REQ-602·901은 **새 테스트를 안 썼다** — 이미 검증하던 테스트가 선언만 안 하고 있었다.
  REQ-805·801은 겨냥·변이를 이미 갖고도 낮게 적혀 있었다.
- **⛔ 못 묻는 절반은 안 주장한다**: 실물에서 도는가(602) · 영상과 시각 증거(901) · 작성
  날짜(902). 셋 다 요구사항 본문에 *"게이트가 이것을 검증한다고 하지 않는다"*를 적었다.
  특히 902의 날짜는 `git log`로 물으면 shallow clone·tarball에서 **참인데 red**가 된다 —
  요구사항이 아니라 체크아웃 방식을 태우는 것이라 안 묻는다.
- **⛔ 하네스가 열한 번째로 스스로 틀렸다**: `backup`은 있는 파일만 다루고 `restore`는 복사만
  해서 *"금지된 것을 하나 만들어 본다"*류 변이를 표현할 수 없었다. `create()`를 넣었는데
  **잎**(`vendor/borrowed/__init__.py`)을 기록해 복구가 파일만 지우고 빈 `vendor/`를 남겼다.
  더 나쁜 것은 `residue`도 그 잎만 봐서 **"잔여 없음"이라고 말한 것**이다 — 복구 실패와 잔여
  보고가 서로 다른 것을 보고 있었다. **아직 없는 가장 위 조상**을 기록하게 고쳤다.
  ⇒ 오염된 첫 스윕은 버리고 전체를 처음부터 다시 돌렸다.
- **Verified**: `make check` **394 passed** · 전체 스윕 **248종 전부 red**, `❌` 0,
  복구 248 · 잔여 248/0 (1240줄 원본 로그).
- **Next**: T8-3 영상(부하 켠 채) → 제출(09-01) → teardown(09-02).
- **Evidence**: `docs/evidence/mutation-sweep-2026-08-29-394.log`.

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
