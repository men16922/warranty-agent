#!/usr/bin/env python3
"""데이터에 붙는 장면들. ⛔ 전부 오늘 프로덕션에서 받은 것이다."""
from __future__ import annotations
import base64, json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from render import shoot, esc, foot
from scenes import term, title
from build_frames import md, load

ROOT = pathlib.Path(__file__).parent
FRAMES = ROOT / "frames"

def crop(src: str, w: int, h: int, x: int, y: int, dst: str) -> pathlib.Path:
    out = FRAMES / f"{dst}.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(FRAMES / f"{src}.png"),
                    "-vf", f"crop={w}:{h}:{x}:{y}", str(out)], check=True)
    return out

def embed(p: pathlib.Path) -> str:
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f'<div class="shot"><img src="data:image/png;base64,{b64}"></div>'

made = []

# ── 04 조치 ──────────────────────────────────────────────────────────────
made.append(shoot("s04_act", (
    title("The remediation — act, then re-measure",
          'It shifts the traffic. And then <em>it waits.</em>',
          'Metrics arrive late. Measuring immediately would let us declare victory '
          'on data that has not arrived yet.')
    + term("agent:chat  ·  warranty-api on Cloud Run",
           'ask "Remediate demo-target by shifting traffic to revision demo-target-00002-lss. '
           'Report the gate verdict, the signal before and after, ..."',
           '<span class="dim">reading baseline from the contract\'s signal ...</span>\n'
           '<span class="ok">✔ traffic shifted → demo-target-00002-lss</span>\n\n'
           '<span class="wait">waiting 45s before re-measuring …</span>\n'
           '<span class="dim">   this pause is the point. most tools return success here.</span>')
    + foot("live · 2 min 3 s round trip"))))

# ── 05 판정 + 롤백 ───────────────────────────────────────────────────────
made.append(shoot("s05_verdict", (
    title("The verdict",
          'Not <s>&ldquo;I rolled back.&rdquo;</s> &nbsp;'
          '<em>&ldquo;I rolled back, and the server says so.&rdquo;</em>')
    + term("agent:chat  ·  warranty-api on Cloud Run",
           'ask "... report the verification verdict and what you did about it."',
           md(load("b4-core")))
    + foot("live production response"))))

made.append(shoot("s05_gcloud", (
    title("Read back from Cloud Run — not from our own memory",
          'The rollback is <em>a measurement, not a claim.</em>')
    + '<div class="term"><div class="bar">'
      '<span class="dot" style="background:#f0787c"></span>'
      '<span class="dot" style="background:#ffb454"></span>'
      '<span class="dot" style="background:#7fd88f"></span>'
      '<span class="t">gcloud · warranty-hack · us-central1</span></div><div class="body">'
      + "\n".join(
          f'<span class="cmd">{esc(ln)}</span>' if ln.startswith("$") or ln.startswith("      ")
          else (f'<span class="k">{esc(ln)}</span>' if "demo-target-00001-swl" in ln
                else f'<span class="dim">{esc(ln)}</span>')
          for ln in (ROOT / "data" / "gcloud.txt").read_text().splitlines())
      + '</div></div>' + foot("6 services on Cloud Run"))))

# ── 07 리포트 ────────────────────────────────────────────────────────────
made.append(shoot("s07_report", (
    title("The daily report — three separate numbers",
          'It ran. It did not help. And it was undone.')
    + '<div class="big">'
      '<div class="num"><div class="l">Executed</div><div class="v">4</div></div>'
      '<div class="num hi"><div class="l">Improved</div><div class="v">0</div></div>'
      '<div class="num"><div class="l">Rolled back</div><div class="v">4</div></div>'
      '</div>'
      '<p class="lede" style="margin-top:44px">A tool that counts only <b>executed</b> '
      'reports four successes today.<br>The <em style="color:#ffb454;font-style:normal">middle '
      'column</em> is the one most operations agents do not have.</p>'
    + foot("agent:chat · daily accountability report · 2026-08-29"))))

# ── 08 화면 ──────────────────────────────────────────────────────────────
top = crop("dash_full", 3440, 1100, 0, 0, "dash_top")
act = crop("dash_full", 3440, 640, 0, 1130, "dash_act")

made.append(shoot("s08a_dash", (
    title("The evidence — served by the agent itself",
          '<em>Executed</em> and <em>Improved</em> are separate columns.')
    + embed(top)
    + foot("https://warranty-api-povpqj6m5a-uc.a.run.app/"))))

made.append(shoot("s08b_attrib", (
    title("Can you find this number in the bill?",
          '<em>resource_label</em> means yes. <em>none</em> means no &mdash; and we say so.')
    + embed(act)
    + foot("https://warranty-api-povpqj6m5a-uc.a.run.app/"))))

# ── 10 마무리 ────────────────────────────────────────────────────────────
made.append(shoot("s10_end", (
    '<div class="center">'
    '<div class="eyebrow">warranty</div>'
    '<h1 style="font-size:64px;text-align:center;max-width:1500px">'
    'Executing is not improving.<br><em>So we made them different columns.</em></h1>'
    '<p class="lede" style="text-align:center;margin-top:36px">'
    'Agent Development Kit &middot; Gemini &middot; Cloud Run &middot; Firestore &middot; Cloud Monitoring<br>'
    '<span style="color:#7fd88f">https://warranty-api-povpqj6m5a-uc.a.run.app/</span></p>'
    '</div>' + foot("Fortified Enterprise Fleet"))))

print("\n".join(str(p) for p in made))
