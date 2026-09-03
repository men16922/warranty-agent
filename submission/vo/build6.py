#!/usr/bin/env python3
from __future__ import annotations
import base64, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from render import shoot, foot
from scenes import title

FRAMES = pathlib.Path(__file__).parent / "frames"

def embed(name):
    b64 = base64.b64encode((FRAMES / f"{name}.png").read_bytes()).decode()
    return f'<div class="shot"><img src="data:image/png;base64,{b64}"></div>'

made = []
made.append(shoot("t07_dash", (
    title("Served by the agents themselves, on Cloud Run",
          '<em>Executed</em> and <em>Improved</em> are separate columns &mdash; '
          'and the second one is allowed to be smaller.')
    + embed("dash2_top")
    + foot("https://warranty-api-povpqj6m5a-uc.a.run.app/"))))

made.append(shoot("t08_attrib", (
    title("The same action. Two different verdicts.",
          '<em>recovered</em> once, <em>not_recovered</em> the next time &mdash; '
          'and the row tells you which.')
    + embed("dash2_act")
    + foot("attribution: none · cost 0 · &ldquo;no billable resource created&rdquo;"))))
print("\n".join(p.name for p in made))
