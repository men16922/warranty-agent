#!/usr/bin/env python3
"""실물 응답에서 만든 장면들."""
from __future__ import annotations
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from render import shoot, esc, foot
from scenes import term, title
from build_frames import md, load

made = []

# ── 성공 ─────────────────────────────────────────────────────────────────
made.append(shoot("t03_fix", (
    title("Night, 03:14 — checkout is slow",
          'It shifted traffic, waited, and <em>measured again.</em>')
    + term("agent:chat  ·  warranty-api on Cloud Run",
           'ask "Remediate demo-target. Report the gate verdict, the signal before '
           'and after, and the verification verdict."',
           md(load("g1-recovered")))
    + foot("live production response · 2 min 40 s round trip"))))

# ── 실패 + 롤백 ──────────────────────────────────────────────────────────
LEDGER = (
    '<span class="dim"># the agent\'s own ledger entry, read back from Firestore</span>\n'
    '<span class="cmd">$ </span><span class="dim">entry 01m17p8r8bqqr8dpd140kn4260</span>\n\n'
    '  <span class="k">action_id</span>    : traffic:demo-target-00002-lss\n'
    '  <span class="k">decision</span>     : AUTO   <span class="dim">(reversible and verifiable within budget)</span>\n'
    '  <span class="k">baseline</span>     : 674.17 ms\n'
    '  <span class="k">after</span>        : <span class="bad">990.04 ms</span>   <span class="dim">← it got worse</span>\n'
    '  <span class="k">verdict</span>      : <span class="bad">not_recovered</span>\n\n'
    '  <span class="k">rollback</span>     : performed <span class="ok">true</span>\n'
    '  <span class="k">signal_restored</span>: <span class="ok">true</span>   <span class="dim">← re-measured after the rollback, too</span>\n'
    '  <span class="k">verified_traffic</span>: {"demo-target-00001-swl": 100}\n'
    '                 <span class="dim">← read back from Cloud Run, not from memory</span>'
)
made.append(shoot("t04_fail", (
    title("Night, 03:44 — the second action did not help",
          'Not <s>&ldquo;I rolled back.&rdquo;</s>&nbsp; <em>&ldquo;The server says I did.&rdquo;</em>')
    + '<div class="term"><div class="bar">'
      '<span class="dot" style="background:#f0787c"></span>'
      '<span class="dot" style="background:#ffb454"></span>'
      '<span class="dot" style="background:#7fd88f"></span>'
      '<span class="t">ledger · warranty-hack · Firestore</span></div>'
      f'<div class="body">{LEDGER}</div></div>'
    + foot("the response timed out; the ledger did not"))))

# ── 거부 ─────────────────────────────────────────────────────────────────
made.append(shoot("t05_refuse", (
    title("Night, 03:51 — it refused",
          'Nowhere to roll back to, and <em>no signal to read yet.</em>')
    + term("agent:chat  ·  warranty-api on Cloud Run",
           'ask "Remediate day1-demo-final by shifting traffic to its first revision. '
           'Tell me the gate verdict and the exact rule."',
           md(load("b6-refuse")))
    + foot("live production response"))))

print("\n".join(p.name for p in made))
