#!/usr/bin/env python3
"""성적표 + 화면 장면."""
from __future__ import annotations
import base64, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from render import shoot, esc, foot
from scenes import title

ROOT = pathlib.Path(__file__).parent
FRAMES = ROOT / "frames"

def crop(src, w, h, x, y, dst):
    out = FRAMES / f"{dst}.png"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(FRAMES/f"{src}.png"),
                    "-vf",f"crop={w}:{h}:{x}:{y}",str(out)], check=True)
    return out

def embed(p):
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f'<div class="shot"><img src="data:image/png;base64,{b64}"></div>'

made = []

made.append(shoot("t06_report", (
    title("The morning — one page",
          'It helped <em>once</em>. And it is the one that says so.')
    + '<div class="big">'
      '<div class="num"><div class="l">Executed</div><div class="v">14</div></div>'
      '<div class="num hi"><div class="l">Improved</div><div class="v">1</div></div>'
      '<div class="num"><div class="l">Rolled back</div><div class="v">12</div></div>'
      '<div class="num"><div class="l">Manual required</div><div class="v">3</div></div>'
      '</div>'
      '<p class="lede" style="margin-top:42px">A tool that counts only completions '
      'reports <b>fourteen successes</b>.<br>'
      '<em style="color:#ffb454;font-style:normal">Improved</em> is the only column that had '
      'to be earned twice — once by acting, once by measuring.</p>'
    + foot("agent:chat · daily accountability report"))))

print("\n".join(p.name for p in made))
