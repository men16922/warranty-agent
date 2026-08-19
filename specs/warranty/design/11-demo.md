# L8 — 실증 최적화 · 4분 영상

`Satisfies: REQ-803, REQ-804, REQ-604, REQ-901`

---

## 1. 원칙

| # | 원칙 | 이 프로젝트에서 |
|---|---|---|
| 1 | **결정론적 데모** | `make demo` 한 줄. 랜덤·외부 의존 금지 |
| 2 | **타이머를 줄인다** | `VERIFY_DELAY_S`·`VERIFY_WINDOW_S`를 영상 길이에 맞춘다. **상수 한 곳** |
| 3 | **실패 경로가 중심** | **검증 실패 → 자동 롤백이 데모의 절정이다** |
| 4 | **화면에 보이게** | 판정·검증 근거·트래픽 배분이 응답에 있다 |
| 5 | ⚠️ **가짜로 만들지 않는다** | 타이머 단축은 최적화, **결과 하드코딩은 실증이 아니다** |

⚠️ **원칙 5의 구체적 함정**: 검증이 실패해야 롤백이 보이는데, 실패를 만들려면 **실제로
나빠지는 조치**가 필요하다. 유혹은 `verdict`를 박아 두는 것이다. **정직한 해법**: 데모 대상
서비스에 **실제로 신호를 악화시키는 리비전**을 준비해 두고, 조치가 그리로 트래픽을 옮기게 한다.
→ 신호가 진짜로 나빠지고, 검증이 진짜로 실패하고, 롤백이 진짜로 되돌린다.

## 2. `make demo`

```
   ① provision      Cloud Run 서비스 생성 + ★ 계약 방출 (화면에 계약이 보인다)
   ② inject         신호를 악화시키는 리비전으로 트래픽 이동 (장애 주입)
   ③ remediate #1   게이트 AUTO → 조치 → 검증 실패 → ★ 자동 롤백 → 신호 회복 확인
   ④ remediate #2   계약 없는 리소스 → ★ MANUAL (검증 불가라 자동 안 함)
   ⑤ report         회복률 · 롤백 수 · 검증 불가 수 · 낭비된 비용
```

## 3. 4분 구성 (영어)

| 시각 | 비트 | 말할 것 |
|---|---|---|
| 0:00–0:25 | **문제** | *"Remediation agents execute an action and report success. Executing is not improving. Most of them cannot tell the difference."* |
| 0:25–0:55 | **논지** | *"This one is GCP-only on purpose. That's what buys verification, atomic rollback, and per-action cost."* |
| 0:55–1:30 | **Day-1** | provision → **계약이 화면에 뜬다**. *"The agent that built it also wrote down how to check it and how to undo it."* |
| 1:30–2:30 | ★ **핵심** | 장애 주입 → 조치 → **재측정 실패** → **자동 롤백** → 트래픽 배분 100% 확인 → 신호 회복 |
| 2:30–3:00 | ★ **모델의 판단** | 애매한 케이스의 `rationale` 문장을 보여준다 |
| 3:00–3:30 | ★ **정책** | 계약 없는 리소스 → `MANUAL`. *"If we can't verify it, we don't automate it."* |
| 3:30–3:50 | **리포트** | **executed 41 · improved 23 (56%) · rolled back 12 · unverifiable 3** |
| 3:50–4:00 | **증거 + 한계** | GCP 콘솔. 그리고 *"we prove correlation, not causation"* 한 줄 |

⚠️ **마지막 10초의 한계 고백이 값이다.** Production Readiness는 완벽함이 아니라
**무엇이 안 되는지 아는가**이다.

## 4. 제작 유의

- **≤4분 · 영어 · 공개 URL** · **GCP 배포의 시각 증거 필수**
- 콜드 스타트 대비 워밍 1회. **`min-instances`를 바꿔 찍고 되돌리지 않는다**
- 자막 권장

⚠️ **영상이 병목이다.** 코드보다 오래 걸릴 수 있다 — `tasks.md`가 이틀을 통째로 배정한다.

## 5. 상수 (REQ-804)

```python
VERIFY_DELAY_S      = 45
VERIFY_WINDOW_S     = 120
DEMO_BUDGET_USD     = Decimal("0.50")
WARMUP_REQUESTS     = 1
```

⚠️ 값이 흩어지면 재촬영 때 **반드시 하나를 놓친다.**
