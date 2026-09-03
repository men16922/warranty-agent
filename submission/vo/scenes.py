#!/usr/bin/env python3
"""장면 — **전부 실물 출력에서 만든다.** 지어낸 화면이 없다."""
from __future__ import annotations
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from render import shoot, esc, foot   # noqa: E402

def term(title: str, cmd: str, out: str = "") -> str:
    body = f'<div class="cmd">$ <b>{esc(cmd)}</b></div>'
    if out:
        body += f'<div class="out">{out}</div>'
    return (f'<div class="term"><div class="bar">'
            f'<span class="dot" style="background:#f0787c"></span>'
            f'<span class="dot" style="background:#ffb454"></span>'
            f'<span class="dot" style="background:#7fd88f"></span>'
            f'<span class="t">{esc(title)}</span></div>'
            f'<div class="body">{body}</div></div>')

def title(eyebrow: str, h1: str, lede: str = "") -> str:
    s = f'<div class="eyebrow">{esc(eyebrow)}</div><h1>{h1}</h1>'
    if lede:
        s += f'<p class="lede">{lede}</p>'
    return s
