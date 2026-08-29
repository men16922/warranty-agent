# 완료 태스크 원문 — 2026-08 (T2·T3·T5·T6·T8)

> `specs/warranty/tasks.md`가 **열린 작업만** 들도록 옮긴 것이다. 원문을 그대로 보존한다.
> 압축 요약은 [`../COMPLETED_SUMMARY.md`](../COMPLETED_SUMMARY.md), 시간순은
> [`PROGRESS_LOG-2026-08.md`](PROGRESS_LOG-2026-08.md)에 있다.
> ⚠️ 추적성 인덱스(요구사항↔태스크)는 `tasks.md` 하단에 **그대로 남아 있다**.

---

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


- [x] **T2-5** 두 번째 조치 — **동시성 변경**. `Implements: REQ-302, REQ-303, REQ-601` ·
  `Design: 03§2` · 계획 `docs/plans/2026-08-29-llm-serving-pivot.md` P1
  - ⭐ **왜 했나**: 조치가 트래픽 전환 하나뿐인 동안 이 시스템은 Flagger·Argo Rollouts와
    **구분되지 않는다.** 그 도구들은 배포할 때만 움직이고, 동시성은 **아무 때나** 바뀐다.
  - 조치 문법 `traffic:<revision>` · `concurrency:<n>`. 구분자 없는 옛 형태는 그대로
    트래픽 전환이다 — 08-28 원장(`01m13fpgc8e091es3ekpqx48f4`)이 그 형태다.
  - ⭐ **롤백 코드는 한 줄도 안 늘었다**: 동시성 변경 = 새 리비전 ⇒ 되돌리기는 이미
    원자적이라고 **되읽어 증명한** 트래픽 전환이다(REQ-303).
  - ⛔ **트래픽을 LATEST로 함께 돌린다**: 롤백이 한 번이라도 돌면 배분이 특정 리비전에
    고정되고, 그 상태에서 템플릿만 바꾸면 새 리비전은 **아무 요청도 안 받는다** —
    조치는 200을 받고 아무것도 안 바꾼다. 그 순간 `improved`가 거짓말이 된다(M-261).
  - ⭐ 도구 표면도 열었다: `target_revision` → `action`. 이름이 그대로였으면 두 번째
    조치는 **코드에는 있고 에이전트는 못 부르는 능력**이었다(M-264).
  - 변이: M-256~M-264 **9종 전부 red 확인**. 낡아서 조용히 무효였던 **M-234도 되살렸다**.
  - ⭐ **실물 왕복 완료**(2026-08-29 · 리비전 `00007-mrq`): 원장 `01m16hwpsc44b8h64g5mc9weqm` ·
    게이트 `AUTO` · `674.17 → 988.60` · `not_recovered` · 롤백 확인.
    증거 `docs/evidence/live-cost-axis-2026-08-29.log` §9~11.
  - ⛔ **롤백은 트래픽이지 템플릿이 아니다**: 되돌린 뒤에도 서비스 템플릿의 동시성은 16이다.
    되돌린 것은 *"지금 무엇이 요청을 받는가"*이지 *"다음 리비전이 무엇을 물려받는가"*가
    아니다 — 템플릿까지 되돌리면 **리비전을 또 만드는 일**이라 원자적이지 않다.
    ⚠️ 대가는 있다: 다음 템플릿 변경이 16을 물려받는다. 촬영 전에 알고 시작할 것.


- [x] **T5-5** 비용 축 ①/③ — **공시 단가표**. `Implements: REQ-503, REQ-505` · `Design: 05§2` ·
  계획 `docs/plans/2026-08-29-cost-axis.md` C1
  - ⛔ **원장의 모든 행이 `amount_usd = 0`이었던 이유가 계량 부재가 아니었다.**
    `ModelCallMeter`는 단가를 못 찾으면 **조용한 0을 안 만들고** `Method.NONE` +
    *"단가표에 없는 모델이다"*를 적어 왔다. 빠진 것은 **숫자 둘과 그 출처**였다.
  - `prices.py` — 값만 있는 모듈(`tunables.py` 계열). 금액만 적지 않고 **출처 URL ·
    티어 · 확인일 · 유효기간**을 같은 자리에 둔다. 도입가는 2027-01-01에 두 배가 된다.
  - ⚠️ **출처의 한계를 숨기지 않는다**: 우리는 Vertex로 부르는데 직접 읽힌 것은 Gemini
    Developer API 페이지다. 그 차이를 `SOURCE_CAVEAT`에 적었다.
  - 변이 M-265~M-269 · **M-267은 처음에 안 물렸다**(perl 패턴 오류 → 하네스가 잡음).


- [x] **T5-6** 비용 축 ②/③ — **프로비저닝의 원장 행 + `fl_entry` 라벨**.
  `Implements: REQ-504, REQ-501` · `Design: 05§3` · 계획 `cost-axis.md` C2·C3
  - ⛔ **`Method.RESOURCE_LABEL`은 테스트에만 있었다** — `grep -rn RESOURCE_LABEL src/` → 0건.
    라벨 키·검증 정규식·화해 경로는 다 있는데 **붙이는 손이 없었다.** 그리고
    `runtime.provision`은 원장 행조차 안 남겼다 — 돈 쓰는 리소스가 원장 밖에서 태어났다.
  - 원장 id를 **먼저** 만들어 그것을 라벨로 박는다. 순서가 반대면 만들어 놓고 나중에
    붙이게 되고, 그 사이 실패는 **라벨 없는 리소스**를 남긴다.
  - ⭐ **귀속은 되읽은 라벨이 있을 때만** `resource_label`이다. 안 붙었으면 `Method.NONE`에
    사유를 적는다 — 되읽기가 롤백(REQ-303)에서 하는 일을 라벨에 대해 한다.
  - `EntryKind.PROVISION` 신설. ⛔ `ACTION`으로 두면 검증이 없어 **절대 `improved`가 안 되고**
    프로비저닝할수록 회복률이 떨어진다(M-273).
  - 변이 M-270~M-274. ⛔ **M-270이 처음에 안 물렸다** — 라벨 다는 줄이 실물 어댑터 안이라
    오프라인 게이트가 원리상 못 지난다. ⇒ `cost_labels`를 순수 함수로 빼고 **요청의 모양**을
    태웠다(`traffic_spec`과 같은 수법).

- [x] **T8-9** ★ **사람이 보는 원장 화면** — `GET /`. `Implements: REQ-508, REQ-604, REQ-901` ·
  `Design: 08§3`
  - ⛔ **화면이 없는 동안 이 프로젝트의 문장은 `curl`을 아는 사람에게만 도착했다.**
    `executed`와 `improved`가 다른 칸이라는 것이 논지인데, 두 칸이 나란히 보이는 화면이
    없으면 그 논지는 읽는 사람에게 도착하지 않는다.
  - ⚠️ **대시보드가 아니다** — 버튼이 없고 아무것도 저장하지 않는다. `OVERVIEW` §11이
    범위 밖으로 선언한 것은 **조작 표면**이고 그건 여전히 안 만든다. §11을 고쳐 적었다.
  - 렌더러가 **순수 함수**라 게이트가 화면의 내용을 태운다. 변이 M-275~M-280.
  - ⛔ 셋(M-276·277·280)이 처음에 안 물렸고 **셋 다 테스트가 약해서였다** —
    각주가 단언을 공짜로 통과시켰고, 이스케이프 경로가 둘인데 하나만 태웠고,
    라우트에 테스트가 아예 없었다.


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

- [x] **T8-3** 영상을 만들었다 — **3:47** · 영어 · https://youtu.be/KAcHpX3nSSM (Unlisted).
  `Implements: REQ-901` · `Design: 11§3` · 원본 `submission/warranty-demo.mp4`
  - ⛔ **실제 데스크톱 촬영은 버렸다.** Chrome 창이 여럿이라 프레임에 개인 창이 세 번 들어왔다.
    ⇒ headless 렌더링(HTML→PNG) + ffmpeg 합성. 결정론적이고 남의 화면을 안 건드린다.
    재현 절차·대본·스크립트 전부 [`submission/vo/`](../../submission/vo/README.md).
  - ⚠️ 내레이션은 **합성 음성**(ElevenLabs `eleven_v3`, 감정 태그). 목소리를 바꾸면 길이가
    바뀌고 그것이 **4분 상한을 건드린다** — `assemble.py`의 `TEMPO`가 그 자리다.
  - ⭐ **촬영이 결함 여섯을 잡았다**: 화면이 한국어였다 · 표가 잘려 `Cost`·`Reason`이 화면
    밖에 있었다 · 그리고 검증 결함 넷(08-30 증분 참조).
  - ⚠️ **`submission/SCRIPT.md`는 옛 논지의 대본이다** — 영상과 다른 이야기를 한다.
    저장소를 열어 본 심사위원이 어느 쪽이 진짜인지 묻게 된다. 교체 필요.
  - ⛔ **갤러리·아티클도 같이 나왔다**: `submission/gallery/`(7장 + `architecture.drawio`
    소스 + `logo.png`) · `submission/article/medium-article.md`(2,400단어, 이미지 raw URL 삽입).

- [x] **T8-4** 신규 코드 여부를 확인했다 — 사실관계는 전부 맞다. `Implements: REQ-902` · `Design: 10§8`
  - 첫 커밋 `741cec5` **2026-08-19**, 마지막까지 79개 전부 08-19~08-29 — 제출 기간
    08-03~08-31 **안**이다. 이전 이력이 없다.
  - `dependencies = []` — 게이트는 표준 라이브러리만으로 돈다. `[cloud]` 추가분은 전부
    공개 Google 패키지다. `git+`·`file://`·사설 인덱스 **0건**, `vendor/`·`third_party/` 없음.
  - 추적 파일 176 · 소스/테스트 `.py` 38.
  - ⛔ 그래도 상태는 `TODO`다 — 겨냥한 테스트가 없다. T5-3이 이 칸을 함께 닫는다.

- [x] **T8-7** 저장소를 만들고 밀었다 — **https://github.com/men16922/warranty-agent** (public · 88 커밋).
  ⇒ public이라 `testing@devpost.com`·`cloudhackathons@google.com` **초대가 필요 없다** —
  private 경로는 GitHub 초대가 이메일이 아니라 계정명 기준이라 실패할 수 있었다.
  ⚠️ 푸시 전에 이력 전체를 훑어 API 키·개인키·토큰 **0건**을 확인했고 `.env`는 이력에도 없다.
  `Implements: REQ-901`

- [x] **T3-1** Cloud Run 서비스 프로비저닝과 계약을 **한 번에** 냈다 — 실물 확인.
  `Implements: REQ-101` · `Design: 01§1, 01§3`
  - 08-29까지 실물 `provision`은 `not_implemented`였다 — 첫 화면이 내세우는 **Day-1 절반이
    비어 있었다.** `live_provision.py` + `ContractStore.put` + 합성 지점으로 닫았다.
  - 이미지 주소를 설정으로 안 받는다. *"지금 내가 무엇으로 도는지"*를 Cloud Run에 물어서
    쓴다 — 그래서 만들어진 리소스는 `warranty-api`와 **같은 태그**(`dbb6f74`)로 떴다.
  - 실물: `day1-warranty-demo` 리비전 `00001-k9c` Ready · minScale 0 · 계약
    `01m14xkweqd3bb0cf9ne4bwjkg`가 Firestore에 났고 `inspect`가 같은 실행에서 읽었다.
  - ⛔ 갓 만든 서비스는 `irreversible`이다(돌아갈 리비전 없음) — 결함이 아니라 design 01§3의
    결과이고, 그래서 그 리소스는 자동 조치 대상이 아니다(REQ-402).
  - ⛔ **만든 서비스는 아무도 못 부른다** — IAM 바인딩이 비어 있다. 프로비저너는 초대
    권한을 주지 않는다. 그 대가로 이 리소스의 신호는 밖에서 부하로 못 채운다. 아래 T3-5.
  - ⭐ **프로덕션에서도 완주했다**: 배포된 에이전트가 자연어 한 줄로 `day1-prod-demo`를 만들고
    계약 `01m15qfgxv5ed6rzgr7bjzp1fk`를 냈다 — 가역성의 이유까지 응답에 있다(REQ-604).
  - 증거 `docs/evidence/live-provision-2026-08-29.log` · `live-day1-prod-2026-08-29.log`.

