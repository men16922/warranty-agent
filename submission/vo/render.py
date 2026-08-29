#!/usr/bin/env python3
"""프레임 렌더러 — HTML 한 장을 Chrome headless로 1920x1080 PNG로 굽는다.

⛔ 여기서 문장을 지어내지 않는다. 들어오는 output은 전부 프로덕션에서 받은 것이다.
"""
from __future__ import annotations
import html, pathlib, subprocess, sys, json

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ROOT = pathlib.Path(__file__).parent
HTML = ROOT / "html"
FRAMES = ROOT / "frames"
HTML.mkdir(exist_ok=True)
FRAMES.mkdir(exist_ok=True)

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1920px;height:1080px;background:#0d0b12;color:#e9e6f2;overflow:hidden;
font-family:ui-sans-serif,-apple-system,"Segoe UI",Helvetica,sans-serif}
.stage{padding:64px 88px;height:1080px;display:flex;flex-direction:column}
.eyebrow{font-size:19px;letter-spacing:.24em;text-transform:uppercase;color:#8b7fb0;
font-weight:600;margin-bottom:14px}
h1{font-size:52px;line-height:1.14;letter-spacing:-.022em;font-weight:650;max-width:1500px}
h1 em{font-style:normal;color:#ffb454}
h1 s{text-decoration:none;color:#f0787c}
.lede{font-size:27px;color:#a79ec2;margin-top:20px;max-width:1360px;line-height:1.45}
.term{margin-top:38px;flex:1;background:#16131e;border:1px solid #2e2840;border-radius:12px;
display:flex;flex-direction:column;overflow:hidden;min-height:0}
.bar{height:44px;background:#1e1a2a;border-bottom:1px solid #2e2840;display:flex;
align-items:center;padding:0 18px;gap:9px;flex:0 0 44px}
.dot{width:12px;height:12px;border-radius:50%}
.bar .t{margin-left:16px;font-size:15px;color:#7d7396;letter-spacing:.04em}
.body{padding:26px 32px;font-family:ui-monospace,"SF Mono",Menlo,monospace;
font-size:22px;line-height:1.55;white-space:pre-wrap;overflow:hidden;flex:1;min-height:0}
.cmd{color:#7fd88f}.cmd b{color:#e9e6f2;font-weight:400}
.out{color:#c9c2dd;margin-top:14px}
.k{color:#ffb454;font-weight:600}
.bad{color:#f0787c;font-weight:600}
.ok{color:#7fd88f;font-weight:600}
.dim{color:#6d6488}
.wait{color:#8b7fb0;font-style:italic}
.foot{margin-top:auto;padding-top:26px;display:flex;justify-content:space-between;
font-size:18px;color:#5f5780;letter-spacing:.05em;flex:0 0 auto}
.big{display:flex;gap:34px;margin-top:44px}
.num{flex:1;background:#16131e;border:1px solid #2e2840;border-radius:12px;padding:34px 30px}
.num .l{font-size:19px;letter-spacing:.16em;text-transform:uppercase;color:#8b7fb0;font-weight:600}
.num .v{font-size:112px;font-weight:650;line-height:1;margin-top:16px;font-variant-numeric:tabular-nums}
.num.hi{border-color:#ffb454}.num.hi .v{color:#ffb454}
.center{justify-content:center;align-items:center;text-align:center;display:flex;flex:1;
flex-direction:column}
.shot{margin-top:34px;flex:0 0 auto;border:1px solid #2e2840;border-radius:12px;
overflow:hidden;background:#fff}
.shot img{width:100%;display:block}
"""

def esc(s: str) -> str:
    return html.escape(s)

def page(inner: str) -> str:
    return (f"<!doctype html><meta charset=utf-8><style>{CSS}</style>"
            f'<div class="stage">{inner}</div>')

def foot(right: str = "") -> str:
    return (f'<div class="foot"><span>warranty &middot; Cloud Run &middot; us-central1</span>'
            f'<span>{esc(right)}</span></div>')

def shoot(name: str, inner: str) -> pathlib.Path:
    p = HTML / f"{name}.html"
    p.write_text(page(inner), encoding="utf-8")
    out = FRAMES / f"{name}.png"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--screenshot={out}", "--window-size=1920,1080",
                    "--force-device-scale-factor=1", f"file://{p}"],
                   check=True, capture_output=True)
    return out

if __name__ == "__main__":
    print(json.dumps({"chrome": pathlib.Path(CHROME).exists()}))
