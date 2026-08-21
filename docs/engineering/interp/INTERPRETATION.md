# Engineering Interpretation — warranty

바이블(`docs/engineering/*_ENGINEERING.md`)은 **무엇을/왜**(이식 가능)를 정의하고,
이 문서는 **이 레포에서는 어떻게**(레포 고유)를 정의한다.
권위 충돌이 나면 이 레포의 권위는 `specs/warranty/requirements.md`이고,
규율의 권위는 `docs/PRINCIPLES.md`다. 이 문서는 **가리키기만 한다**(PRINCIPLES #10).

## HARNESS — 성숙도/검증/권한 (Bible `HARNESS_ENGINEERING.md`)

- gate: `make check` = `lint types test trace` (`Makefile`, harness-config.gate)
  - ⚠️ **오프라인이고 어떤 과금 API도 부르지 않는다** — REQ-801 · REQ-802 · PRINCIPLES #3.
    이게 무인 루프를 돌려도 되는 유일한 근거다.
- permission boundary: `scripts/overnight/overnight-settings.json`
  - allow = 게이트 타깃(`check/lint/types/test/trace`)과 `.venv` 도구, 변이 하네스(`scripts/mutate.sh`)
  - deny = 온라인·과금 경로 전부: `gcloud` `bq` `gsutil` `docker` `terraform` `uv` `pip`,
    그리고 `make live-check` · `pytest -m live` · `make demo`(실물 호출)
  - `Bash(make *)` 통짜 허용은 **하지 않는다** — 나중에 배포 타깃이 생겨도 자동으로 열리면 안 된다.
- 현재 성숙도 / 다음 투자: 게이트는 있고(65 통과) **변이로 red를 확인한 가드**까지 있다
  (`scripts/mutate.sh`, 증거 `docs/evidence/mutations.md`). 다음 투자는 **실물 축**이다 —
  T2-2(Cloud Run 배포)가 열리기 전까지 무인 루프가 만질 수 있는 건 오프라인 축뿐이다.

## LOOP — 무인 루프 (Bible `LOOP_ENGINEERING.md`)

- runner: 플러그인 소유(`make overnight-where`로 위치 확인). 이 레포는 **벤더링하지 않는다**.
- backlog: `specs/warranty/tasks.md` (harness-config.docs.plan)
  - 태그 축은 상태 박스(`[x]`/`[~]`/`[ ]`)와 **다른 축**이다. 루프는 `[auto]`만 소비한다.
  - ⛔ **T0-3 · T2-* 는 전부 `[manual]`이다** — GCP 프로젝트·자격증명·실배포가 필요하다.
- iteration prompt: 플러그인 기본값. 레포 오버라이드가 필요하면 `scripts/overnight/PROMPT.md`.
- skills: `/sync` `/checkpoint` `/overnight-report` `/overnight-seed` `/tidy-docs` `/diagnose`

## VERIFICATION — 3계층 (Bible `VERIFICATION_ENGINEERING.md`)

아래로 갈수록 비싸다. 각 검사는 **갈 수 있는 만큼 위로**(기계적) 민다.

- **기계적 (gate)**: `make check`
  - `ruff check` + `ruff format --check` · `mypy`(strict 설정은 pyproject) ·
    `pytest`(오프라인, fake 어댑터 위) · `tools/spec_trace.py`(REQ↔테스트 추적성, AST 기반)
  - 이 계층이 증명하는 것: **선언된 REQ가 테스트로 물려 있다**, 그리고 fake 위에서 도메인 불변식이 산다.
- **의미적 (critic)**: `OVERNIGHT_CRITIC=auto` · 프롬프트 `scripts/overnight/CRITIC_PROMPT.md`
  (`.example.md`에서 복사). 이 레포의 "초록인데 틀린" 패턴 — 전부 실제로 난 적이 있거나 가드가 있다:
  1. **스텁이 만드는 거짓 초록** — fake 위 통과는 *"우리가 이 인터페이스를 이렇게 부른다"*이지
     *"그 인터페이스가 존재한다"*가 아니다(PRINCIPLES #3). 실물 주장을 fake 증거로 하면 red.
  2. **`improved`를 저장** — 유도여야 한다(REQ-502 · G8). 필드로 저장되면 red.
  3. **`verifiability`를 저장** — 귀속 방법에서 유도여야 한다(REQ-504 · G3).
  4. **형제 집합 일부만 순회** — 판정 5칸, 귀속 3종, 파괴적 조치 전체를 **값으로** 태워야 한다
     (PRINCIPLES #9 · G9).
  5. **1회=1행 위반** — 거부·실패도 원장에 남아야 한다(REQ-501, REQ-507 · G7).
  6. **게이트에서 실물 호출** — 포트/어댑터 우회는 G5(REQ-801) 위반.
  7. **날짜·기계 없는 게이트 숫자** — 주장이 아니다(PRINCIPLES #10).
- **창의적 (human, `[manual]`)**: 실물 클라우드가 필요한 전부 —
  전용 프로젝트/결제(T0-3), ADK 실물 호출(T2-1), 배포와 실물 왕복 증거(T2-2~4), 데모 서사.
  - `/overnight-report` 아침 검수 초점: (a) 커밋이 **fake 증거로 실물을 주장**하지 않았는가,
    (b) 새 필드에 **읽는 쪽**이 같이 왔는가(PRINCIPLES #4), (c) 가드가 **지워 보면 red**인가
    (`bash scripts/mutate.sh`), (d) `tasks.md`의 게이트 숫자가 갱신·검증됐는가.

## AGENTIC — 멀티 에이전트 (Bible `AGENTIC_ENGINEERING.md`)

단일 엔진(claude)이다. 레인 분리·worktree 격리는 아직 필요 없다 —
크리티컬 패스가 **한 줄**(T2 배포)이고 그건 무인으로 못 한다.

## CONTEXT — 문서 규율 (Bible `CONTEXT_ENGINEERING.md`)

⚠️ 이 레포는 하네스 기본 문서 토폴로지를 **쓰지 않는다**(PRINCIPLES #10 — 권위는 한 곳).
`AGENT_BRIEF`/`STATUS`/`NEXT_PLAN`을 따로 만들면 `OVERVIEW`·`tasks.md`와 같은 내용이 두 벌 생긴다.

- Read Path: `docs/OVERVIEW.md`(brief=status) → `specs/warranty/tasks.md`(plan) → `docs/PROGRESS_LOG.md`(log)
- 권위: 요구사항 `specs/warranty/requirements.md` · 근거 `specs/warranty/design.md` ·
  그림과 서사 `docs/OVERVIEW.md` · 결정 `docs/DECISIONS.md`
- 줄 예산: harness-config.budgets (brief/status 240 · plan 200 · log 120)
- Resume Pointer: `docs/OVERVIEW.md` 맨 위 `▶ NEXT SESSION` 줄
- archive: `docs/archive/`

## PROMPT — 프롬프트 계층 (Bible `PROMPT_ENGINEERING.md`)

- harness prompt: 플러그인 기본값 (오버라이드 시 `scripts/overnight/PROMPT.md`)
- runtime/domain prompt: **아직 없다** — ADK 에이전트가 T2-1에서 실물 호출을 하는 시점에 생긴다.
  생기면 포트 뒤(`src/warranty/ports.py` → `adapters/`)에 놓는다.
  ⚠️ 런타임 프롬프트는 **게이트에서 모델을 부르지 않는다**. 변경은 fake로 검증되고,
  실물 확인은 `[manual]`이다.
