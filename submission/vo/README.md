# 데모 영상 재현 — `submission/warranty-demo.mp4`

⛔ **여기 있는 화면은 전부 실물에서 왔다.** 터미널 본문은 프로덕션 `agent:chat` 응답과
Firestore 원장 항목을 그대로 옮긴 것이고, 원장 화면은 배포된 공개 URL을 찍은 것이다.

## 순서

```bash
# ① 내레이션 (ElevenLabs eleven_v3)
#    ⛔ 키는 .env의 ELEVENLAB_API_KEY / ELVENLAB_ACTOR에서만 읽는다 — 인자로 안 받는다.
for f in vo3/*.txt; do
  python3 tts.py - "$f" "audio3/$(basename $f .txt).mp3" 0.65
done

# ② 프레임 (Chrome headless → 1920x1080 PNG)
python3 build3.py   # 타이틀·문제·논지·자기고백·한계·엔딩
python3 build4.py   # 성공·실패·거부 (실물 응답에서)
python3 build5.py   # 성적표
python3 build6.py   # 원장 화면 (공개 URL 캡처를 크롭해서 넣는다)

# ③ 합성 — 길이는 **오디오에서 읽는다**
python3 assemble.py plan3.json    # → submission/warranty-demo.mp4
```

## ⚠️ 알아 둘 것

- **목소리를 바꾸면 길이가 바뀌고, 그것이 4분 상한을 건드린다.** `assemble.py`의 `TEMPO`가
  그 자리다. 대본을 더 깎는 대신 여기서 아주 살짝 당긴다.
- **감정 태그가 본문에 박혀 있다** (`[serious]`/`[thoughtful]`/`[curious]`/`[pause]`).
  태그도 ElevenLabs 과금 글자수에 든다.
- **`stability 0.65`인 이유**: 지정된 보이스가 `use_case: advertisement`라 기본값(0.5)이면
  *"Improved: one"*을 신나게 읽는다. **이 저장소가 반대하는 톤이다.**
- **실제 데스크톱 촬영은 버렸다.** Chrome 창이 여럿이라 프레임에 개인 창이 들어왔다.
  headless 렌더링은 결정론적이고 남의 화면을 안 건드린다.
- `p95.sh` — 조치 전에 **120초 창 안에 지표 점이 있는지** 확인하는 자리. 없으면 신호가
  `null`이고, 그러면 게이트가 검증 불가로 막는다(정상 동작이지만 촬영할 그림은 아니다).
