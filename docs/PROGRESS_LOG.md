# PROGRESS_LOG — warranty

> 최신 3–5개 증분. **최신이 위.** **≤120줄.** 넘치면 `/tidy-docs`로 압축.
> 권위: 요구사항=`specs/warranty/requirements.md` · 계획=`specs/warranty/tasks.md` ·
> 현재 상태=`docs/OVERVIEW.md` §10 · 검증 기록=`docs/evidence/`.

---

## 2026-08-19 — 레포 생성부터 루프 배선까지: spec을 집행 가능하게 만들고, GCP 올인으로 재정의했다 (gate 65)

- **Status**: 저장소를 새로 만들었다(커밋 6). Google All Things Agentic Hackathon 제출물.
  **코드는 아직 클라우드에 안 올라갔다.** 논지의 루프는 fake 위에서 전부 배선·검증됐다.
- **Changed — ① SDD를 집행 가능하게**: `tools/spec_trace.py` + 가드 **G6**가
  요구사항의 **상태 주장을 현실에 맞댄다**(`IMPLEMENTED`면 테스트, `VERIFIED`면 red가 확인된
  변이 기록). 형제 검사 셋(테스트·태스크·설계 귀속)을 함께 묻는다. `scripts/mutate.sh`가
  변이·실행·복구를 한 스크립트에서 한다.
- **Changed — ② GCP 올인 재정의**(`fleet-ledger` → `warranty`): 주제를 비용 장부에서
  **자동화**로 옮겼다. 논지 = *"클라우드 중립성을 포기하면 에이전트가 무엇을 할 수 있게 되는가."*
  Day-1이 **운영 계약**(신호·회복기준·롤백계획·가역성)을 산출하고, Day-2가 조치 후
  **같은 신호를 다시 재고** 안 나아졌으면 **Cloud Run 트래픽 전환으로 되돌린다**.
  판정 게이트 축이 셋(가역성 × **검증 가능성** × 예산) — ⛔**검증할 수 없는 조치는 자동으로 하지 않는다.**
  REQ 36 → **44**, 설계 11편 재작성. 비용은 주제가 아니라 리포트의 한 열로 종속(D9).
- **Changed — ③ 도메인 + 루프**: 계약·검증·판정 게이트·원장 + 포트 9종 + fake 어댑터 +
  `Remediator`. `improved`를 **저장하지 않고 검증 결과에서 유도**한다(G8).
  **남은 것은 어댑터뿐이다** — 실물 Cloud Monitoring·Cloud Run·Vertex.
- **Verified**: `make check` → **65 passed** (2026-08-19 로컬 macOS·py3.13, ruff+mypy+pytest+trace).
  REQ 44종 — VERIFIED 14 · IMPLEMENTED 14 · TODO 16.
  **변이 M-01~M-22 전부 red 확인** · 복구 후 초록 · 백업 대조 잔여 0 (`docs/evidence/mutations.md`).
  **ADK 실물 확인**: `google-adk 2.7.1`을 별도 venv에 설치해 introspect —
  `tools`가 평범한 `Callable`을 받고, `Runner`는 `session_service`가 **필수**
  (`docs/evidence/adk-api-probe-2026-08-19.log`). ⛔**모델 호출은 아직 안 했다.**
- **Verified(가드 자신의 실패 다섯)**: ⚠️추적성 스캐너가 문자열 검색이라 **산문 언급이
  커버리지로 계산**됐다(REQ-802 오탐) → AST로. ⚠️변이 하네스가 출력 문자열로 판정해 **red를
  초록으로 읽었고**, `git status`로 잔여를 물어 무관한 변경을 오인했고, **stale `.pyc`**에
  속았고, 이름을 바꾼 뒤 **없는 파일에** 물었고, 포맷 변경으로 **조용히 무효인 변이**를 냈다
  → 종료 코드·백업 대조·바이트코드 끄기·대상 부재/무변경을 **판정이 아니라 오류**로.
  ⚠️**M-20은 가드가 없어서가 아니라 픽스처가 약해서 초록이었다**(원칙 #8).
- **Blockers**: ⛔**전용 GCP 프로젝트가 없다.** 활성 gcloud 계정이 `yeongsigchoe7@gmail.com`이고
  **Cloud Billing API 미활성**이라 크레딧이 어느 결제 계정에 붙었는지 **읽을 수 없다**(콘솔 확인 필요).
  이것이 T2(Cloud Run 배포) 전체를 잠근다. BQ 결제 내보내기는 **선택**으로 내려 크리티컬 패스에서 빠졌다.
- **Next**: ⛔**T2-2 (Cloud Run 배포)가 08-24 중단 기준의 판정 대상**이다.
  프로젝트가 열리면 T0-3 → T2 → T3. 그전까지 오프라인으로 가능한 것은
  **REQ-508(회복률 리포트) · REQ-404/405(승인·예약)** 셋뿐이다.
