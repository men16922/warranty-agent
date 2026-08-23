# L4 — 에이전트 런타임 (ADK · Gemini · Cloud Run)

`Satisfies: REQ-601, REQ-602, REQ-603, REQ-604`

---

## 1. 대회 필수 요건 대응

| 요건 | 충족 |
|---|---|
| Gemini 3.5 이상 (Gemini API 또는 Vertex AI) | **Gemini 3.7 Flash · Vertex AI** |
| Google Agent Framework 1개 이상 | **ADK** |
| Google Cloud 인프라 1개 이상 | **Cloud Run** (+ Firestore · Cloud Monitoring · BigQuery) |

## 2. 실물 확인 상태 (2026-08-19)

✅ **라이브러리는 존재하고 인터페이스도 실재한다** — `google-adk 2.7.1`을 실제로 설치해
introspect했다. 증거: `docs/evidence/adk-api-probe-2026-08-19.log`.

- `Agent`(=`LlmAgent`)의 `tools`가 **평범한 파이썬 `Callable`을 받는다** → 별도 래핑 불필요
- ⚠️ **`Runner`는 `session_service`가 필수다**(기본값 없음). `min-instances=0`이라
  **유휴 후 첫 요청은 항상 새 세션**이다 → 대화 연속성을 가정하지 않는다.
  **권고: `InMemorySessionService`** (데모에 연속성 불필요 · REQ-805에 부합)

⛔ **아직 확인 안 된 것**: **실제 모델 호출**(프로젝트·인증 없음)과 Cloud Run 배포.

### 모델 갱신 — `gemini-3.5-flash` → `gemini-3.7-flash` (2026-08-23)

Gemini 3.7 Flash가 **2026-08-13에 나왔고 Vertex AI에서 쓸 수 있다**(1M 컨텍스트,
코딩·에이전트 워크로드용). 대회 요건의 바닥은 *"3.5 이상"*이라 3.7은 그 위다 —
**요건이 바뀐 게 아니라 우리가 고른 값이 바뀌었다.** 그래서 REQ-601의 문장과
`docs/HACKATHON.md`의 대회 원문 인용은 **안 건드렸다.**

⛔ **그런데 이것도 여전히 "호출해 본 것"이 아니다.** 확인된 것은 *"그런 이름의 모델이
공개돼 있다"*까지고(2026-08-23 웹 확인), *"우리 프로젝트의 Vertex 경로에서 그 id가
유효하다"*는 **미확인**이다. 둘은 다른 값이고, 후자는 T2-1이 소유한다.
⚠️ **"이름이 실재한다"·"임포트가 된다"·"호출이 된다"는 셋 다 다르다** — 지금 우리가 가진
것은 첫째와 둘째뿐이다. REQ-601·602는 여전히 `TODO`다.

스텁 위에서 통과하는 테스트는 *"우리 코드가 이 인터페이스를 이렇게 부른다"*를 말할 뿐
*"그 인터페이스가 존재한다"*를 말하지 않는다.

⇒ **REQ-601·602의 수용 기준은 실물 호출과 실물 배포다.** 그리고 **T2가 08-24 중단 기준의
판정 대상이다.**

## 3. 도구 (의도)

```
   Agent "warranty"
     model: gemini-3.7-flash (Vertex AI)
     tools:
       ├─ provision(spec)          Day-1 — 리소스 생성 + ★ 계약 방출
       ├─ inspect(resource)        계약·최근 신호 조회               (부수효과 없음)
       ├─ remediate(resource, action)  ★ 게이트 → 조치 → 검증 → 롤백
       └─ report(date)             회복률 리포트                     (부수효과 없음)
```

**도구는 4개로 고정한다.** 늘리면 4분 안에 설명이 안 된다.

## 4. ★ 모델의 판단이 하중을 받는 자리 (REQ-204)

`remediate` 안에서, 재측정이 계약의 `tolerance` 안쪽에 떨어졌을 때만 모델이 불린다.

```
   judge_ambiguous(baseline, after, criterion) -> (verdict, rationale)
```

- **명확한 경우는 모델을 안 부른다** — 부르면 판정이 비결정적이 되고 REQ-802가 깨진다.
- **근거(rationale)는 원장에 문장으로 남고 응답에 나온다** (REQ-604).

⚠️ 이 자리가 없으면 이 시스템에서 LLM은 **자연어를 도구 호출로 바꾸는 파서**일 뿐이다.

## 5. 토큰 계량 (REQ-603)

모든 모델 호출은 `ModelPort`를 통과하고, 그 포트가 **호출 1건 = 원장 1행**을 보장한다.
호출부마다 기록을 시키면 언젠가 한 곳이 빠지고, 그 빠짐은 조용하다.

## 6. Cloud Run 구성

| 설정 | 값 | 이유 |
|---|---|---|
| `min-instances` | **0** | 유휴 과금 0 (REQ-805) |
| `max-instances` | 2 | 폭주 방지 |
| `cpu`/`memory` | 1 / 512Mi | |
| 인증 | 미인증 (데모) | ⚠️ **게이트가 유일한 지출 방어선이다** → 예산 한도를 낮게 |

**콜드 스타트**: 촬영 직전 워밍 요청 1회. ⚠️ **`min-instances`를 바꿔 찍고 되돌리지 않는다** —
영상 속 시스템이 제출물과 달라진다.
