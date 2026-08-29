#!/usr/bin/env python3
"""세그먼트를 이어 붙인다. ⚠️ 길이는 **내레이션이 정한다** — 그림이 말을 자르지 않게."""
from __future__ import annotations
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).parent
FRAMES, AUDIO, SEG = ROOT / "frames", ROOT / "audio", ROOT / "seg"
SEG.mkdir(exist_ok=True)

PAD_HEAD = 0.45   # 말 시작 전 숨
PAD_TAIL = 0.9    # 말 끝나고 남기는 여운

def dur(p: pathlib.Path) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True).stdout.strip())

def segment(name: str, frame: str, vo: str | None, hold: float = 0.0,
            lead_silence: float = 0.0) -> tuple[pathlib.Path, float]:
    """프레임 한 장 + (있으면) 내레이션 한 줄 = 세그먼트 하나."""
    png = FRAMES / f"{frame}.png"
    assert png.exists(), f"프레임이 없다: {png}"
    out = SEG / f"{name}.mp4"
    if vo:
        aif = AUDIO / f"{vo}.aiff"
        length = PAD_HEAD + lead_silence + dur(aif) + PAD_TAIL + hold
        # 앞뒤로 무음을 붙여 말이 컷에 물리지 않게 한다.
        afilter = (f"adelay={int((PAD_HEAD + lead_silence) * 1000)}|"
                   f"{int((PAD_HEAD + lead_silence) * 1000)},apad")
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(png), "-i", str(aif),
               "-filter_complex", f"[1:a]{afilter}[a]", "-map", "0:v", "-map", "[a]"]
    else:
        length = hold
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(png),
               "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
               "-map", "0:v", "-map", "1:a"]
    vf = (f"fade=t=in:st=0:d=0.35,fade=t=out:st={length - 0.35:.3f}:d=0.35,"
          f"format=yuv420p")
    cmd += ["-t", f"{length:.3f}", "-vf", vf, "-r", "30",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out, length

def build(plan: list[dict], final: pathlib.Path) -> float:
    parts, total = [], 0.0
    for step in plan:
        p, length = segment(**step)
        parts.append(p)
        total += length
        print(f"  {step['name']:<18} {length:6.2f}s   ({total:6.2f}s)")
    listing = SEG / "concat.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", "-movflags", "+faststart", str(final)],
                   check=True, capture_output=True, cwd=SEG)
    return total

if __name__ == "__main__":
    plan = json.loads(pathlib.Path(sys.argv[1]).read_text())
    final = ROOT / "warranty-demo.mp4"
    total = build(plan, final)
    print(f"\nTOTAL {total:.1f}s = {int(total // 60)}:{int(total % 60):02d}  →  {final}")
