# YouTube 업로드 — 붙여 넣을 값

파일: `submission/warranty-demo.mp4` · 3:47 · 1920x1080 · 영어

⚠️ **공개 범위: `Unlisted`(일부 공개)를 권한다.** 심사위원은 링크로 열 수 있고,
검색에는 안 걸린다. ⛔ `Private`는 안 된다 — 링크가 있어도 심사위원이 못 연다.

---

## 제목 (100자 이내)

```
warranty — An accountability ledger for AI agent fleets | Google All Things Agentic Hackathon
```

**대안 (더 짧게)**

```
warranty — Your agents say "completed." This one says whether it helped.
```

---

## 설명

```
When a fleet of AI agents runs against production overnight, every log line says "completed."
In the morning the service is exactly as slow as it was. Completed is not improved — and most
tools only count the first one.

warranty is an operations agent whose ledger keeps "improved" as a separate column from
"executed." After it acts, it re-measures the same signal its own contract named when the
resource was created. If the number did not move, it rolls itself back and reads the traffic
split back from Cloud Run to prove it. If it cannot measure the resource at all, it refuses to
act in the first place.

Everything in this video is a real response from the deployed service. Nothing is mocked.

Live ledger (read-only, no login):
https://warranty-api-povpqj6m5a-uc.a.run.app/

Source:
https://github.com/men16922/warranty-agent

── Chapters ──
0:00  warranty
0:03  The morning after — fourteen green lines
0:21  What it does after it acts
0:41  It fixed something: 990 ms → 674 ms, recovered
1:08  It made something worse: 674 ms → 990 ms, rolled back, verified
1:36  It refused: irreversible and not verifiable
2:00  The report — executed 14, improved 1, rolled back 12
2:28  The ledger page, served by the agent on Cloud Run
2:44  The same action, two different verdicts
2:58  The honest part — the system failed its own test, four times
3:27  Two limits we will not hide

── Built with ──
Agent Development Kit (ADK) · Gemini 3.7 Flash on Vertex AI · Cloud Run · Firestore ·
Cloud Monitoring · Cloud Build · Secret Manager

── Honest notes ──
• Most of those twelve rollbacks are ours — generated while testing this system. We did not
  clear the ledger to improve the ratio.
• Re-measuring after a rollback is correlation, not causation.
• Contracts exist only for resources the agent provisioned.
• The narration is synthesized (ElevenLabs v3). The scripts are in the repo under
  submission/vo/ so the whole video can be rebuilt.

Google All Things Agentic Hackathon — Fortified Enterprise Fleet track.
```

---

## 태그 (쉼표로)

```
AI agents, agentic AI, Google Cloud, Cloud Run, Gemini, Agent Development Kit, ADK,
SRE, DevOps, observability, AIOps, incident response, hackathon, Firestore,
Cloud Monitoring, autonomous agents, agent accountability
```

---

## 썸네일

⭐ 영상 **2:00 지점**(성적표 프레임)이 가장 좋다 — `Executed 14 · Improved 1`이 큰 숫자로
있고, 그 대비가 이 영상의 논지 전부다. YouTube가 자동 제안하는 프레임 중에 없으면
`submission/vo/`에서 `t06_report.png`를 다시 구워 올리면 된다.

## 업로드 후

⛔ **링크를 `submission/DEVPOST.md`의 `Video demo link` 칸에 박아야 한다.** 그게 안 되면
심사위원에게 영상이 없는 것과 같다.
