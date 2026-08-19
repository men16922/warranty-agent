# L7 — 배포 (프로젝트 · IAM · teardown)

`Satisfies: REQ-602, REQ-805, REQ-901`

---

## 1. 전용 GCP 프로젝트

이유 셋:
1. **청구 귀속이 깨끗해진다** — 결제 내보내기에 다른 워크로드가 안 섞인다.
2. **teardown이 완전해진다** — 프로젝트 삭제 하나. 리소스를 하나씩 지우면 **반드시 뭔가 남는다.**
3. **IAM 경계가 프로젝트 경계와 일치한다** — 테넌트 신원(REQ-7xx)의 전제이기도 하다.

```
   프로젝트 id (제안): warranty-hack
   리전:               us-central1   (Vertex Gemini 가용 · 단가 낮음)
```

⚠️ **크레딧이 붙은 결제 계정을 확인하고 연결한다.** 안 붙은 계정에 만들면 자비로 나간다.

## 2. 구성 요소

| 리소스 | 설정 | REQ |
|---|---|---|
| Cloud Run 서비스 `warranty-api` | `min-instances=0`, `max=2` | 602, 805 |
| Cloud Run 서비스 `demo-target` | ★ **조치 대상**. 리비전 2개 이상 | 303 |
| Firestore (Native) | 계약 · 원장 · 예산 | 101, 501 |
| Cloud Monitoring | 신호 (별도 프로비저닝 없음) | 201 |
| BigQuery 결제 내보내기 | **콘솔 수동 · 선택** | 506 |
| Artifact Registry | 이미지 | 602 |

⛔ **GKE 없음 · 상시 VM 없음 · Cloud SQL 없음** (REQ-805).

⚠️ **`demo-target`이 있어야 롤백이 실증된다.** 조치 대상이 없으면 트래픽 전환을 보여줄 수 없다.

## 3. IAM — 최소 권한

```
   sa: warranty-api@
     roles/datastore.user            계약·원장
     roles/aiplatform.user           Vertex 모델
     roles/monitoring.viewer         신호 읽기
     roles/run.developer             리비전·트래픽 조작 (조치 대상에만)
```

⚠️ **`run.developer`를 프로젝트 전역으로 주지 않는다** — 조치 대상 서비스에만 바인딩한다.
그러지 않으면 자기 자신(`warranty-api`)도 조치 대상이 될 수 있다.

⚠️ 광범위 권한을 쓸 거면 **왜 필요한지를 주석으로 남긴다.** 만족 불가능한 규칙("전면 금지")은
우회를 습관으로 만든다.

## 4. 라벨

인프라: `wr_project=warranty`, `wr_env=hack`
조치가 만든 것: `wr_entry=<entry_id>` (귀속용)

⚠️ **인프라 라벨과 귀속 라벨을 섞지 않는다.** 화해 질의는 `wr_entry`만 본다 —
인프라 라벨로 매칭하면 **인프라 비용이 조치에 귀속된다.**

## 5. 절차

```bash
make deploy         # 이미지 → Artifact Registry → Cloud Run
make deploy-check   # /healthz + 실제 remediate 1건 왕복
```

⚠️ **`make deploy`는 게이트에 없다.** 과금하고 되돌리기 어렵다 — 무인 루프의 deny 목록에 넣는다.

## 6. teardown

**2026-09-02.** 심사 중 Hosted가 필요하면 Cloud Run만 남긴다(scale-to-zero). 종료 후 **프로젝트 삭제**.

⚠️ **날짜를 지금 박는 이유**: 제출이 끝나면 관심이 떠나고, 떠난 뒤에도 과금은 계속된다.

## 7. 증거 (REQ-901)

`docs/evidence/`에 남긴다 — `deploy-<date>.log` · `live-remediate-<date>.log`
(판정·검증·롤백이 보이는 왕복) · 콘솔 스크린샷(Cloud Run 리비전 · 트래픽 배분).

⚠️ **날짜와 명령을 적고, 재현 안 되면 재현 안 된다고 적는다.**

## 8. 제출 제약 (REQ-902)

이 저장소의 코드는 제출 기간(2026-08-03~08-31) 중 새로 작성된다.
**기존 코드를 임포트하거나 복사해 편입하지 않는다.**

- 의존성 목록에 외부 사설 저장소가 없다
- 표준 개발 도구(프레임워크·라이브러리·스타터 템플릿·AI 코딩 어시스턴트)는 규칙이 명시적으로 허용한다
- 이 저장소가 스스로에게 부과하는 엔지니어링 규율은 `docs/PRINCIPLES.md`에 있고,
  **그것은 코드가 아니라 판단이다**

⚠️ 확인은 T8-4에서 한다.
