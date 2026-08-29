#!/usr/bin/env python3
"""함대 회계 논지의 장면들. ⛔ 터미널 본문은 전부 실물에서 온다."""
from __future__ import annotations
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from render import shoot, esc, foot
from scenes import term, title

made = []

made.append(shoot("t00_title", (
    '<div class="center">'
    '<div class="eyebrow">Fortified Enterprise Fleet</div>'
    '<h1 style="font-size:92px;text-align:center">warranty</h1>'
    '<p class="lede" style="text-align:center;font-size:33px;margin-top:26px">'
    'An accountability ledger for agent fleets &mdash;<br>'
    'it records not just what an agent <em style="color:#ffb454;font-style:normal">did</em>, '
    'but whether it <em style="color:#ffb454;font-style:normal">helped</em>.</p>'
    '</div>' + foot("ADK &middot; Gemini &middot; Cloud Run &middot; Firestore"))))

made.append(shoot("t01_problem", (
    title("The morning after",
          'Fourteen green lines. <em>Which one actually helped?</em>')
    + '<div class="term"><div class="bar">'
      '<span class="dot" style="background:#f0787c"></span>'
      '<span class="dot" style="background:#ffb454"></span>'
      '<span class="dot" style="background:#7fd88f"></span>'
      '<span class="t">what an agent fleet leaves behind</span></div><div class="body">'
      '<span class="ok">✔</span> <span class="dim">03:14  agent-7   shifted traffic       </span><span class="ok">completed</span>\n'
      '<span class="ok">✔</span> <span class="dim">03:21  agent-2   changed concurrency   </span><span class="ok">completed</span>\n'
      '<span class="ok">✔</span> <span class="dim">03:44  agent-7   shifted traffic       </span><span class="ok">completed</span>\n'
      '<span class="dim">   …  eleven more                             </span><span class="ok">completed</span>\n\n'
      '<span class="wait">Every line is green. The service is as slow as it was last night.</span>\n'
      '<span class="bad">&ldquo;Completed&rdquo; is not &ldquo;improved&rdquo; — and only one column knows the difference.</span>'
      '</div></div>' + foot())))

made.append(shoot("t02_thesis", (
    title("What this agent does after it acts",
          'It goes back and measures <em>the same signal</em> again.',
          'Not a signal it picked &mdash; the one its own contract named when the resource '
          'was created. And it records what it found, whether or not that flatters it.')
    + '<div class="term"><div class="bar">'
      '<span class="dot" style="background:#f0787c"></span>'
      '<span class="dot" style="background:#ffb454"></span>'
      '<span class="dot" style="background:#7fd88f"></span>'
      '<span class="t">the loop</span></div><div class="body" style="font-size:26px">'
      '  act  <span class="dim">→</span>  <span class="wait">wait longer than the measurement window</span>  '
      '<span class="dim">→</span>  re-measure\n\n'
      '        <span class="ok">recovered</span>      <span class="dim">→ keep it, and say so</span>\n'
      '        <span class="bad">not_recovered</span>  <span class="dim">→ roll back, then read the state back</span>\n'
      '        <span class="k">unverifiable</span>   <span class="dim">→ never ran it in the first place</span>'
      '</div></div>' + foot())))

made.append(shoot("t09_selfcatch", (
    title("The honest part",
          'Building this demo, <em>the system failed its own test.</em> Four times.')
    + '<div class="term"><div class="bar">'
      '<span class="dot" style="background:#f0787c"></span>'
      '<span class="dot" style="background:#ffb454"></span>'
      '<span class="dot" style="background:#7fd88f"></span>'
      '<span class="t">found on 2026-08-30 · all four looked green in the logs</span>'
      '</div><div class="body" style="font-size:25px">'
      '<span class="k">1.</span> The re-measurement window still held <span class="bad">the past</span>.\n'
      '   <span class="dim">wait 45s &lt; window 120s → 75s of the "after" was before</span>\n\n'
      '<span class="k">2.</span> The recovery threshold was <span class="bad">unreachable</span>.\n'
      '   <span class="dim">needed −60% · the injected fault can only give −31%</span>\n'
      '   <span class="dim">990 → 674 ms (−32%) was reported not_recovered</span>\n\n'
      '<span class="k">3.</span> The contract kept the <span class="bad">old policy</span> after we fixed the code.\n'
      '   <span class="dim">policy lives in the contract — so we versioned it</span>\n\n'
      '<span class="k">4.</span> Waiting longer killed the request <span class="bad">before the verdict came home</span>.\n'
      '   <span class="dim">the action shipped, the ledger was right — only the answer was lost</span>'
      '</div></div>' + foot("three of the four are now guards; one is in the record"))))

made.append(shoot("t10_limits", (
    title("Two limits we will not hide",
          'We would rather say this than show you<br>a green number we did not measure.')
    + '<div class="term"><div class="bar">'
      '<span class="dot" style="background:#f0787c"></span>'
      '<span class="dot" style="background:#ffb454"></span>'
      '<span class="dot" style="background:#7fd88f"></span>'
      '<span class="t">known limits</span></div><div class="body">'
      '<span class="k">1.</span> <span class="bad">Correlation, not causation.</span>\n'
      '   Re-measuring after a rollback is a weak natural experiment.\n\n'
      '<span class="k">2.</span> Contracts exist only for resources <span class="bad">the agent provisioned.</span>\n'
      '   A hand-made resource is not an automation target.'
      '</div></div>' + foot())))

made.append(shoot("t12_end", (
    '<div class="center">'
    '<div class="eyebrow">warranty</div>'
    '<h1 style="font-size:60px;text-align:center;max-width:1560px">'
    'Let the agents act.<br><em>Just make them show their work.</em></h1>'
    '<p class="lede" style="text-align:center;margin-top:34px">'
    'Agent Development Kit &middot; Gemini &middot; Cloud Run &middot; Firestore &middot; Cloud Monitoring<br>'
    '<span style="color:#7fd88f">https://warranty-api-povpqj6m5a-uc.a.run.app/</span></p>'
    '</div>' + foot("Fortified Enterprise Fleet"))))

print("\n".join(p.name for p in made))
