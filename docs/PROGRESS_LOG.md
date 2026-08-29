# PROGRESS_LOG — warranty

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 월별 아카이브로 민다.
> 밀려난 것 → [`archive/PROGRESS_LOG-2026-08.md`](archive/PROGRESS_LOG-2026-08.md) (T6-2 이전 전부).
> 권위: 요구사항=`specs/warranty/requirements.md` · 계획=`specs/warranty/tasks.md` ·
> 현재 상태=`docs/OVERVIEW.md` §10 · 검증 기록=`docs/evidence/`.

---

## 2026-08-29 — 저장소를 열고, 대본을 쓰고, 논지가 약하다는 것을 찾았다 (gate 403 유지)

- **Status**: 제출물 자격 조건 하나 해소. ⛔ **논지 전환 계획을 세웠고 결정 대기 중이다.**
- **Changed**: 코드 없음. `github.com/men16922/warranty-agent` 공개(89 커밋) ·
  `submission/SCRIPT.md`(4분 대본) · `docs/plans/2026-08-29-llm-serving-pivot.md`.
- **Verified**: 프로덕션 리비전 `00005-8x9`가 자연어 한 줄에 08-28 원장을 긁어
  `executed 1 · improved 0 · rolled_back 1`을 냈다. 게이트 거부 비트도 실물에서 확인 —
  `MANUAL` · 규칙 `irreversible and not verifiable` · 6.3s. 대본의 출력은 전부 실측이다.
- **푸시 전 점검**: API 키·개인키·토큰 **0건**, `.env`는 이력에도 없다. public으로 정한 이유는
  private 초대가 이메일이 아니라 계정명 기준이라 실패하면 **점수가 아니라 자격** 문제가 되기 때문.
- **⛔ 이 세션의 가장 큰 발견 — 논지가 약하다**: *"조치 후 재측정해 안 나아졌으면 롤백"*은
  Flagger·Argo Rollouts·Kayenta가 이미 성숙하게 한다. *"이거 Flagger 아니야?"*에 답할 말이
  없고, 조치가 트래픽 전환 하나뿐이라 더 그렇다. **기계가 약한 게 아니라 프레이밍이 틀렸다.**
- **길이 보였다**: 사용자 아티클(Cloud Run GPU·vLLM) §A4가 이미 답이다 — 동시성 16에서
  요청 100% 성공, **goodput 50%**. `executed ≠ improved`의 가장 순수한 형태이고 LLM 서빙에서는
  헬스체크가 원리적으로 못 잡는다. ⭐ 게다가 동시성 변경은 **새 리비전을 만들어서** 롤백이
  지금 메커니즘 그대로다 — 어댑터 하나 + `KNOWN_KINDS` 한 줄이면 된다.
- **Blockers**: ① 결정 대기(ⓑ 이동 vs ⓒ 서사만) ② `warranty-hack`의 **L4 GPU 쿼터 미확인**
  ③ 영상 미촬영 — 남은 유일한 필수 산출물.
- **Next**: 계획의 **P0**(GPU 쿼터 확인 · 30분) → 결과에 따라 갈래 확정. P1(동시성 조치)은
  어느 갈래에서도 한다.
- **Evidence**: `docs/evidence/live-report-prod-2026-08-29.log` · `deploy-2026-08-29b.log`.

## 2026-08-29 — 마지막 스텁이 헤드라인 숫자를 내는 자리였다 · T5-4 리포트 + DEVPOST (gate 399 → 403)

- **Status**: 실물 `report` 배선 완료. `submission/DEVPOST.md`를 **실제 원고로** 다시 썼다.
- **Changed**: `LedgerReader.for_day` + `LiveLedger`의 하루치 범위 질의 + `runtime.report`.
  세는 규칙은 `domain/report.daily_report`가 이미 갖고 있었다 — 더한 것은 *"그 함수에 무엇을
  넘기는가"*뿐이다. `InMemoryLedger.for_day`는 `all_entries()`를 거쳐 간다(읽기 경로 한 벌).
- **⚠️ 질의를 에이전트로 안 좁힌다**: 좁히면 Firestore가 복합 색인을 요구하고, 색인이 없는 날
  리포트는 **예외로 죽는다.** 좁히는 일은 도메인이 이미 한다 — 넉넉히 긁고 한 곳에서 판정한다.
- **Verified(실물)**: 08-28 원장에서 **`executed 1 · improved 0 · rolled_back 1`**이 나왔다.
  이 프로젝트가 말하는 문장 그 자체이고, 각본이 아니라 **실제 조치 하나의 결과**다.
- **⛔ DEVPOST가 답이 아니라 폼 스크랩이었다**: 필드 목록만 있고 답이 없었다. 칸별 원고 ·
  Testing instructions · 심사 항목별 정직한 강약 판정을 썼다.
- **⛔ 제출 블로커 둘을 찾았다**: ① `git remote`가 **비어 있다** — 코드 저장소 URL은 필수
  칸이다(T8-7). ② teardown 09-02인데 심사는 그 뒤이고 크레딧은 09-06 만료다 — Hosted URL
  수명을 정해야 한다(T8-8).
- **⛔ `HACKATHON.md` §4가 없는 요구사항을 가리키고 있었다**: 비중 40%짜리 항목의 획득 경로가
  `REQ-307`이었는데 **REQ-3xx는 305까지다.** 가장 큰 항목의 계획이 허공을 가리켰다 —
  실재하는 REQ-502·402·303·304·503~505로 바꿨다.
- **Verified**: `make check` **403 passed** · 전체 스윕 **255종 전부 red**, `❌` 0,
  복구 255 · 잔여 0 (1275줄).
- **Next**: T8-7 저장소 → T8-3 영상 → T8-5 제출(09-01) → T8-8 결정 → teardown(09-02).
- **Evidence**: `docs/evidence/mutation-sweep-2026-08-29-403.log`.

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
