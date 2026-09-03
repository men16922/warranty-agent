#!/usr/bin/env python3
"""ElevenLabs v3 내레이션. ⛔ 키는 .env에서만 읽는다 — 인자로 받지 않는다(셸 히스토리에 남는다)."""
from __future__ import annotations
import json, os, pathlib, sys, urllib.request

ROOT = pathlib.Path(__file__).parent
REPO = pathlib.Path("/Users/men1692/Desktop/GCP/AllThings")
MODEL = "eleven_v3"


def api_key() -> str:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("ELEVENLAB_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("⛔ .env에 ELEVENLAB_API_KEY가 없다")


def actor() -> str:
    """⚠️ .env의 ELVENLAB_ACTOR가 우선. 없으면 인자, 그것도 없으면 실패한다."""
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(("ELVENLAB_ACTOR=", "ELEVENLAB_ACTOR=")):
            v = line.split("=", 1)[1].strip()
            if v:
                return v
    raise SystemExit("⛔ .env에 ELVENLAB_ACTOR가 없다 (voice_id를 넣어라)")


def speak(text: str, voice_id: str, out: pathlib.Path,
          stability: float = 0.5, similarity: float = 0.75) -> float:
    body = json.dumps({
        "text": text,
        "model_id": MODEL,
        "voice_settings": {"stability": stability, "similarity_boost": similarity},
    }).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=body,
        headers={"xi-api-key": api_key(), "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            out.write_bytes(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"⛔ {out.name}: HTTP {e.code} {e.read()[:300].decode(errors='replace')}")
    return out.stat().st_size / 1024


if __name__ == "__main__":
    # 사용: tts.py <voice_id|-> <텍스트파일> <출력mp3>
    vid = sys.argv[1] if sys.argv[1] != "-" else actor()
    src = pathlib.Path(sys.argv[2])
    dst = pathlib.Path(sys.argv[3])
    stab = float(sys.argv[4]) if len(sys.argv) > 4 else 0.65
    kb = speak(src.read_text(encoding="utf-8").strip(), vid, dst, stability=stab)
    print(f"{dst.name:<18} {kb:7.1f} KB")
