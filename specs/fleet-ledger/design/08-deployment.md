# L7 — 배포 (프로젝트 · IAM · 리전 · teardown)

`Satisfies: REQ-502, REQ-705, REQ-801`

---

## 1. ★ 전용 GCP 프로젝트를 새로 만든다 (요구사항 Q1)

**권고: 그렇게 한다.** 이유 셋 — 전부 이 프로젝트의 논지에 직결된다:

1. **청구 귀속이 깨끗해진다.** 결제 내보내기에 다른 워크로드가 섞이면 화해 질의가
   남의 비용을 우리 라벨 없는 행으로 끌어온다. 전용 프로젝트면 **프로젝트 필터 하나로
   경계가 선다.**
2. **teardown이 완전해진다.** 프로젝트 삭제 하나로 끝난다. 리소스를 하나씩 지우는 방식은
   **반드시 뭔가 남긴다** — 레퍼런스 저장소의 7월 사건(방치된 클러스터)과 정지 인스턴스의
   잔여 디스크가 그 전례다.
3. **IAM 경계가 프로젝트 경계와 일치한다.** 서비스 계정 권한을 프로젝트 수준으로 줘도
   blast radius가 이 프로젝트를 안 넘는다.

```
   프로젝트 id (제안):  fleet-ledger-hack
   결제 계정:           해커톤 크레딧이 적용된 계정
   리전:                us-central1   (Vertex Gemini 가용 · 단가 낮음)
```

⚠️ **결제 계정을 확인하고 붙인다.** 크레딧이 안 붙은 계정에 만들면 자비로 나간다.

## 2. 구성 요소

| 리소스 | 이름 | 설정 | REQ |
|---|---|---|---|
| Cloud Run 서비스 | `fleet-ledger-api` | `min-instances=0`, `max=2`, 512Mi | 502, 705 |
| Cloud Run Job | `fleet-ledger-reconciler` | 일 1회 | 401 |
| Cloud Scheduler | `fl-reconcile-daily` | `0 3 * * *` (KST 12:00 무관, UTC 기준) | 401 |
| Firestore | (기본 DB) | **Native 모드** | 201 |
| BigQuery 데이터셋 | `billing_export` | **콘솔 수동 활성화** | 401 |
| Artifact Registry | `fl` | 컨테이너 이미지 | 502 |

⛔ **GKE 없음. 상시 VM 없음. Cloud SQL 없음.**(REQ-705)

## 3. IAM — 최소 권한

```
   서비스 계정: fl-api@<project>.iam.gserviceaccount.com
     roles/datastore.user                 Firestore 읽기/쓰기
     roles/aiplatform.user                Vertex 모델 호출
     (액션이 만지는 리소스에 필요한 최소 역할)

   서비스 계정: fl-reconciler@<project>.iam.gserviceaccount.com
     roles/bigquery.jobUser               질의 실행
     roles/bigquery.dataViewer            결제 내보내기 데이터셋에만 (프로젝트 전체 X)
     roles/datastore.user                 measured 기록
```

⚠️ **`dataViewer`는 데이터셋 수준으로 준다.** 프로젝트 수준으로 주면 결제 데이터 외에도
닿는다. 그리고 **API용 계정과 화해용 계정을 나눈다** — API는 청구 데이터를 읽을 이유가 없다.

⚠️ **`Resource:"*"`류 광범위 권한을 쓸 거면 왜 필요한지를 주석으로 남긴다.**
만족 불가능한 규칙("전면 금지")은 우회를 습관으로 만든다. 규칙은 **"이유를 적지 않은 광범위
권한 금지"**다.

## 4. 배포 절차 (재현 가능해야 한다 — REQ-801)

```bash
make deploy            # 1) 이미지 빌드 → Artifact Registry
                       # 2) Cloud Run 서비스 배포
                       # 3) Job + Scheduler 갱신
make deploy-check      # 배포 후 /healthz + 실제 액션 1건 왕복
```

⚠️ **`make deploy`는 게이트에 없다**(REQ-701). 배포는 과금하고 되돌리기 어렵다.
overnight 하네스의 permission boundary에서 **deny 목록에 들어간다**(`docs/COST_GUARDRAILS.md`).

## 5. 라벨 규약

배포되는 **모든 리소스**에 붙인다:

```
   fl_project = fleet-ledger
   fl_env     = hack
```

액션이 만드는 리소스에는 추가로 `fl_entry=<entry_id>`(REQ-205).

⚠️ **인프라 라벨(`fl_project`)과 귀속 라벨(`fl_entry`)을 섞지 않는다.**
화해 질의는 `fl_entry`만 본다. 인프라 라벨로 매칭하면 **인프라 비용이 액션에 귀속**된다.

## 6. teardown — 제출과 동시에 날짜를 박는다

```
   teardown 날짜: 2026-09-02
```

**절차**: ① 심사 중 Hosted가 필요하면 **Cloud Run만 남긴다**(scale-to-zero라 유휴 과금 0)
② 그 외 전부 정지 ③ 심사 종료 후 **프로젝트 삭제**.

⚠️ **날짜를 지금 박는 이유**: 제출이 끝나면 관심이 떠나고, 떠난 뒤에도 과금은 계속된다.
레퍼런스 저장소의 7월 사건이 정확히 이 모양이었다 — 잊힌 컴퓨트.

## 7. 배포 증거 (REQ-801)

영상과 별개로 `docs/evidence/`에 남긴다:

- `deploy-<date>.log` — 배포 명령과 출력, 서비스 URL, 리비전 id
- `live-roundtrip-<date>.log` — 실제 요청/응답 (판정 근거가 보이는 것)
- `reconcile-<date>.log` — BQ 질의 결과와 `measured`가 채워진 항목
- 콘솔 스크린샷 — Cloud Run 리비전, 청구 페이지

⚠️ **"한때 됐다"와 "지금 재현된다"는 다르다.** 증거 파일에는 **날짜와 명령**을 적고,
재현 안 되는 것은 재현 안 된다고 적는다.
