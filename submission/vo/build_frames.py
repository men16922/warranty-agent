#!/usr/bin/env python3
"""프레임을 굽는다. ⛔ 터미널 본문은 **프로덕션 응답을 그대로** 옮긴다."""
from __future__ import annotations
import json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from render import shoot, esc, foot
from scenes import term, title

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"

def md(text: str, keep: int = 999) -> str:
    """에이전트가 실제로 낸 마크다운을 터미널 본문으로. **볼드만** 색으로 바꾼다."""
    lines = [ln for ln in text.splitlines() if ln.strip() not in ("", "###", "####")]
    lines = [re.sub(r"^#+\s*", "", ln) for ln in lines][:keep]
    out = []
    for ln in lines:
        # ⚠️ 글머리표는 **이스케이프 전에** 없앤다 — 뒤에 하면 들여쓰기와 엉킨다.
        ln = re.sub(r"^(\s*)[*-]\s+", lambda m: " " * (len(m.group(1)) + 2), ln)
        e = esc(ln)
        e = re.sub(r"\*\*(.+?)\*\*", r'<span class="k">\1</span>', e)
        e = re.sub(r"\*(.+?)\*", r"\1", e)          # 남은 이탤릭
        e = re.sub(r"`(.+?)`", r"\1", e)
        out.append(e)
    return "\n".join(out)

def load(name: str) -> str:
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))["message"]

made = []

# ── 00 타이틀 ────────────────────────────────────────────────────────────
made.append(shoot("s00_title", (
    '<div class="center">'
    '<div class="eyebrow">Fortified Enterprise Fleet</div>'
    '<h1 style="font-size:96px;text-align:center">warranty</h1>'
    '<p class="lede" style="text-align:center;font-size:34px;margin-top:24px">'
    'An operations agent that re-measures after it acts &mdash;<br>'
    'and <em style="color:#ffb454;font-style:normal">rolls itself back</em> when the number did not move.</p>'
    '</div>' + foot("ADK &middot; Gemini &middot; Cloud Run")
)))

# ── 01 문제 ──────────────────────────────────────────────────────────────
made.append(shoot("s01_problem", (
    title("The problem",
          'Every remediation agent ends its run<br>the same way: <em>it reports success.</em>')
    + '<div class="term"><div class="bar">'
      '<span class="dot" style="background:#f0787c"></span>'
      '<span class="dot" style="background:#ffb454"></span>'
      '<span class="dot" style="background:#7fd88f"></span>'
      '<span class="t">what the logs say</span></div><div class="body">'
      '<span class="ok">✔ restarted service</span>   <span class="dim">→ error rate unchanged</span>\n'
      '<span class="ok">✔ scaled up</span>            <span class="dim">→ latency got worse</span>\n'
      '<span class="ok">✔ shifted traffic</span>      <span class="dim">→ nothing improved</span>\n\n'
      '<span class="wait">All three are the same shade of green.</span>\n'
      '<span class="bad">Executing is not improving.</span>'
      '</div></div>' + foot()
)))

# ── 02 논지 ──────────────────────────────────────────────────────────────
made.append(shoot("s02_thesis", (
    title("Why they cannot tell",
          'Nobody wrote down what <em>&ldquo;better&rdquo;</em> would look like.',
          'That knowledge exists exactly once &mdash; when the resource is created &mdash; '
          'and it never makes it into the code. So the Day&#8209;2 agent guesses.')
    + '<div class="term"><div class="bar">'
      '<span class="dot" style="background:#f0787c"></span>'
      '<span class="dot" style="background:#ffb454"></span>'
      '<span class="dot" style="background:#7fd88f"></span>'
      '<span class="t">the claim</span></div><div class="body" '
      'style="display:flex;align-items:center;justify-content:center;font-size:38px;text-align:center">'
      '<span class="bad">Verification built on a guessed signal\nis not verification.</span>'
      '</div></div>' + foot()
)))

# ── 03 Day-1 ─────────────────────────────────────────────────────────────
made.append(shoot("s03_day1_cmd", (
    title("Day 1 — the contract is born with the resource",
          'Create a service. Watch what comes back <em>with</em> it.')
    + term("agent:chat  ·  warranty-api on Cloud Run",
           'ask "Provision a Cloud Run service named day1-demo-final, then tell me '
           'the operational contract you recorded."')
    + foot("live production response")
)))
made.append(shoot("s03_day1_out", (
    title("Day 1 — the contract is born with the resource",
          'It wrote down <em>which signal means health</em> &mdash; and that '
          'there is <em>nowhere to roll back to yet.</em>')
    + term("agent:chat  ·  warranty-api on Cloud Run",
           'ask "Provision a Cloud Run service named day1-demo-final, ..."',
           md(load("b3-day1")))
    + foot("live production response")
)))

# ── 06 거부 ──────────────────────────────────────────────────────────────
made.append(shoot("s06_refuse", (
    title("The gate — it refuses",
          'Same service, ninety seconds old. <em>The executor was never called.</em>')
    + term("agent:chat  ·  warranty-api on Cloud Run",
           'ask "Remediate day1-demo-final by shifting traffic to its first revision. '
           'Tell me the gate verdict and the exact rule."',
           md(load("b6-refuse")))
    + foot("live production response")
)))

# ── 09 한계 ──────────────────────────────────────────────────────────────
made.append(shoot("s09_limits", (
    title("Two honest limits",
          'We would rather say this than show you<br>a green number we did not measure.')
    + '<div class="term"><div class="bar">'
      '<span class="dot" style="background:#f0787c"></span>'
      '<span class="dot" style="background:#ffb454"></span>'
      '<span class="dot" style="background:#7fd88f"></span>'
      '<span class="t">known limits</span></div><div class="body">'
      '<span class="k">1.</span> This is <span class="bad">correlation, not causation.</span>\n'
      '   Re-measuring after a rollback is a weak natural experiment.\n\n'
      '<span class="k">2.</span> Contracts exist only for resources <span class="bad">the agent provisioned.</span>\n'
      '   A hand-made resource is not an automation target.\n\n'
      '<span class="k">3.</span> Monitoring ingestion lags the action window.\n'
      '   The same action twice gave 674→988 and 674→674 ms.\n'
      '   <span class="dim">Both were correctly reported as not_recovered.</span>'
      '</div></div>' + foot()
)))

print("\n".join(str(p) for p in made))
