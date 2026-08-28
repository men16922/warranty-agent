# L4 — 에이전트 런타임 (ADK · Gemini · Cloud Run)

`Satisfies: REQ-601, REQ-602, REQ-603, REQ-604`

---

## 1. 대회 필수 요건 대응

| 요건 | 충족 |
|---|---|
| Gemini 3.5 이상 (Gemini API 또는 Vertex AI) | **Gemini 3.7 Flash · Vertex AI** |
| Google Agent Framework 1개 이상 | **ADK** |
| Google Cloud 인프라 1개 이상 | **Cloud Run** (+ Firestore · Cloud Monitoring · BigQuery) |

## 2. 실물 확인 상태 (2026-08-28)

✅ **라이브러리는 존재하고 인터페이스도 실재한다** — `google-adk 2.7.1`을 실제로 설치해
introspect했다. 증거: `docs/evidence/adk-api-probe-2026-08-19.log`.

- `Agent`(=`LlmAgent`)의 `tools`가 **평범한 파이썬 `Callable`을 받는다** → 별도 래핑 불필요
- ⚠️ **`Runner`는 `session_service`가 필수다**(기본값 없음). `min-instances=0`이라
  **유휴 후 첫 요청은 항상 새 세션**이다 → 대화 연속성을 가정하지 않는다.
  **권고: `InMemorySessionService`** (데모에 연속성 불필요 · REQ-805에 부합)

✅ **실제 호출 확인**: ADK Runner → Vertex AI Gemini 3.7 Flash → `remediate` 도구 →
Cloud Monitoring·Cloud Run·Firestore 왕복. 증거: `docs/evidence/live-adk-remediate-2026-08-28.log`.
⛔ 남은 것은 이 새 코드를 `warranty-api` Cloud Run 리비전에 배포하는 일이다.

### 모델 갱신 — `gemini-3.5-flash` → `gemini-3.7-flash` (2026-08-23)

Gemini 3.7 Flash가 **2026-08-13에 나왔고 Vertex AI에서 쓸 수 있다**(1M 컨텍스트,
코딩·에이전트 워크로드용). 대회 요건의 바닥은 *"3.5 이상"*이라 3.7은 그 위다 —
**요건이 바뀐 게 아니라 우리가 고른 값이 바뀌었다.** 그래서 REQ-601의 문장과
`docs/HACKATHON.md`의 대회 원문 인용은 **안 건드렸다.**

2026-08-28 실물 호출로 *"우리 프로젝트의 Vertex 경로에서 그 id가 유효하다"*까지 확인했다.
⚠️ **"이름이 실재한다"·"임포트가 된다"·"호출이 된다"는 셋 다 다르다** — 이번 증거가
셋째를 닫았다. Cloud Run에 올라간 현재 리비전은 이전 코드이므로 REQ-602는 별도로 남는다.

스텁 위에서 통과하는 테스트는 *"우리 코드가 이 인터페이스를 이렇게 부른다"*를 말할 뿐
*"그 인터페이스가 존재한다"*를 말하지 않는다.

⇒ REQ-601의 실물 호출은 닫혔다. REQ-602의 새 리비전 배포·호출은 다음 배포가 소유한다.

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

판정 모델은 `ModelPort`를 통과하고, ADK Runner는 모델 응답 이벤트의 `usage_metadata`를
같은 `ModelCallMeter`에 넘긴다. 둘 다 **호출 1건 = 원장 1행**을 보장한다. usage가 없는
실패도 `FAILED` 행으로 남긴다. 호출부마다 원장 모양을 다시 만들지는 않는다.

## 6. Cloud Run 구성

| 설정 | 값 | 이유 |
|---|---|---|
| `min-instances` | **0** | 유휴 과금 0 (REQ-805) |
| `max-instances` | 2 | 폭주 방지 |
| `cpu`/`memory` | 1 / 512Mi | |
| 인증 | 미인증 (데모) | ⚠️ **게이트가 유일한 지출 방어선이다** → 예산 한도를 낮게 |

**콜드 스타트**: 촬영 직전 워밍 요청 1회. ⚠️ **`min-instances`를 바꿔 찍고 되돌리지 않는다** —
영상 속 시스템이 제출물과 달라진다.
