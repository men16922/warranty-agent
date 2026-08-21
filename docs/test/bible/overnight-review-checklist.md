# Overnight 루프 종료 후 검수 체크리스트

매 overnight 가동(`make overnight-watch`) **종료 후 사람이 수행하는 반복 검수 프로세스**.
자동 검수는 `/overnight-report`가, 사람 판단(무엇이 깨졌나·뭘 고칠까·다음 seed)은 이 체크리스트가 담당한다.

> 이 파일은 **정적 바이블(템플릿)** 이다(`docs/test/bible/`). `/overnight-report`는 마지막 단계에서 아래 B~E를
> **이번 런 사실로 채운 체크박스 인스턴스**(커밋 해시·새 `[blocked]`·ahead 수·잔여 seed)를
> `docs/test/history/<MMDD-HHMM>-overnight-review-checklist.md` 파일로 **생성**한다. 그 파일들은 gitignore —
> 재생성 가능한 산출물이라 커밋하지 않는다. "이번 런에 내가 확인할 리스트"가 곧 그 생성 파일이다.

> 한 줄 흐름:
> `make overnight-status`(끝났나?) → `/overnight-report`(자동 요약 + 런별 체크리스트) → 아래 A~E 처리 → `git push` → 다음 seed

---

## A. 종료 상태 확인
- [ ] `make overnight-status` — 프로세스 종료됨? 종료 사유는?(DONE 소진 / STOP 수동·red잔여물 / MAX_ITER / 연속실패 / 무진행)
- [ ] claude 세션에서 **`/overnight-report`** — 회차 수, 만든 커밋, **게이트 재실측(green?)**, 잔여 `[auto]` 확인.
- [ ] STOP으로 멈췄다면: red 잔여물(사람 검수 필요)이 핵심 신호. `git status` + `scripts/overnight/logs/iter-<N>.log` 마지막 부분 확인.

## B. 루프가 만든 것 검토 (커밋)
- [ ] `git log --oneline <시작HEAD>..HEAD` — 회차별 커밋 훑기. `[recovered]`(잔여물 복구)·`[blocked]` 강조.
- [ ] **커밋별로 `git show <hash>` diff를 읽고 두 줄로 적는다**:
  - ① **무엇이 바뀌었나** — 건드린 파일·추가/수정 테스트·동작 변화를 구체적으로(generic "의도대로인가?" 금지).
  - ② **무엇을 확인하면 되나** — 변경 종류에 맞는 검증: **테스트 추가**→무엇을 보장하나·허위 green/과검출 아닌가, **리팩터/codemod**→동작·공개 API 불변인가, **버그픽스**→근본 원인·재현·회귀 테스트 동반인가, **docs 산문**→문장이 사실인가(테스트 아닌 주장은 `make check`가 못 잡는다 — 실제 파일을 열어 확인).

## C. 이 저장소의 판정 (템플릿의 게임용 C절을 대체)

> 게이트가 초록인 것은 **입력**이지 결론이 아니다. 아래는 `make check`가 원리상 못 잡는 것들이다.

- [ ] **거짓 초록 — fake 증거로 실물을 주장했나** (PRINCIPLES #3 · 최우선)
      커밋 메시지·docs가 "ADK가 응답한다"·"Cloud Run에서 돈다"류를 주장하는데
      근거가 `adapters/fakes.py` 위 테스트뿐이면 **되돌린다**. REQ-601·602의 수용 기준은 실물이다.
- [ ] **가드가 하중을 받나** (PRINCIPLES #8)
      새 테스트가 추가됐으면 `docs/evidence/mutations.md`에 **red 확인 행**이 함께 왔는가.
      안 왔으면 그 테스트는 아직 가드가 아니다. `bash scripts/mutate.sh <M-xx>`로 직접 확인.
      ⚠️ 문법을 깬 변이는 red로 세지 않는다.
- [ ] **읽는 쪽이 같이 왔나** (PRINCIPLES #4)
      새 필드/새 자료형이 생겼으면 그것을 **읽는 코드**가 같은 커밋에 있는가.
      없으면 "우리가 그걸 안다"는 착각만 남는다.
- [ ] **유도해야 할 것을 저장하지 않았나** (G3·G8)
      `improved`·`verifiability`·`improvement_rate`는 **유도**다. 필드로 저장됐으면 red 사유.
- [ ] **형제 집합을 전부 셌나** (PRINCIPLES #9)
      판정 5칸 · 귀속 3종 · 파괴적 조치 전체 · 원장을 만드는 경로 전부.
      하나만 순회하는 가드는 나머지를 **안 물은 채**다.
- [ ] **게이트 숫자가 한 곳인가** (PRINCIPLES #10)
      `tasks.md` 맨 아래 한 곳에만. 날짜와 잰 기계가 없는 숫자는 주장이 아니다.
      커밋 메시지의 `(gate NN)`과 실제 재실측이 일치하는가.
- [ ] **스테일 참조가 늘지 않았나**
      T0-5가 만든 양방향 가드가 이제 집행한다 — dangling이 생기면 게이트가 red다.
      게이트가 초록인데 산문이 낡은 경우(예: `tools/spec_trace.py` 리포트 헤더)는 T0-6 몫.

### 우선순위 (되돌릴 것부터)
실물 주장 위조 > 유도해야 할 값의 저장 > 하중 안 받는 가드 > 읽는 쪽 없는 필드 > 산문 스테일

## D. 반영 (push / 정리)
- [ ] 결과가 좋으면 **`git push`** (로컬 `main` → origin). *(첫 푸시는 `gh repo create <repo> --private --source=. --remote=origin --push`.)*
- [ ] 잘못된 커밋이 있으면: `git revert <hash>` 또는 수정 후 재커밋.

## E. 다음 가동 준비
- [ ] C에서 나온 Blocker 중 **봇이 고칠 수 있는 것**(기계적·결정론)은 새 `[auto]`로, **사람 판단 필요**한 것은 `[manual]`로 NEXT_PLAN에 환류.
- [ ] `[auto]` seed가 소진됐으면 **새 묶음 seeding**(콘텐츠 무결성 / 회귀 테스트 / 타입·lint 부채 / codemod / hygiene). seeding 없이 돌리면 즉시 무진행 종료.
- [ ] `make overnight-clean`(STOP/DONE 정리) → 다음 `make overnight-watch`.

---

## 참고
- 설계·환경변수·종료 조건: `docs/engineering/LOOP_ENGINEERING.md` + `docs/engineering/interp/INTERPRETATION.md`.
- 봇이 할 수 없는 것(플레이 feel·캐릭터·엔딩 잔향)은 사람 플레이 QA: `docs/test/neo_seoul_live_qa.md`.
- 직전 가동(2026-06-14) seed: 콘텐츠/밸런스 무결성 7종(루트/엔딩 도달성·플래그/스킬/조우 무결성·조우 승률 밴드·진행도 경제).
