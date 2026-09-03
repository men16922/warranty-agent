# 썸네일 / 아이콘 — Gemini 이미지 생성 프롬프트

## 무엇을 그려야 하는가

이 프로젝트의 논지는 **"실행됨"과 "나아짐"이 다른 칸**이라는 것이다.
⛔ **방패나 체크마크 하나로는 아무 말도 못 한다.** 로고는 그 **둘 사이의 간격**을 그려야 한다.

⚠️ 뽑은 뒤 반드시 **100px로 줄여서** 본다. 그 크기에서 안 읽히면 실패다.
⚠️ 정사각형(1:1)으로 뽑는다 — Devpost 썸네일과 Medium 커버가 둘 다 정사각으로 자른다.

---

## A · 두 개의 체크 — 가장 직접적 (추천)

```
Create a minimal, flat vector app icon in Google Material Design style.

Two checkmarks arranged diagonally. The upper-left checkmark is large, bold and confident,
drawn in Google blue #4285F4. Below and to the right of it sits a second checkmark that is
clearly smaller and thinner, drawn in Google amber #F9AB00.

Even stroke weights, rounded stroke caps, purely geometric construction. Perfectly centered
on a plain white background with generous empty padding around the marks — the icon should
occupy about 60% of the frame.

Completely flat: no gradients, no drop shadows, no 3D, no bevels, no texture.
No text, no letters, no words, no numbers anywhere in the image.
Square 1:1 composition.

The idea it must communicate: the first mark means "it ran", the second smaller mark means
"it actually helped" — and the second one being smaller is the entire point.
```

## B · 되돌아와서 확인하는 고리

```
Create a minimal, flat vector app icon in Google Material Design style.

A single circular arrow that loops counter-clockwise, like a refresh or undo symbol, drawn
in Google blue #4285F4. Where the loop ends, the stroke continues into a checkmark tip drawn
in Google green #34A853, so the loop and the check read as one continuous motion.

Uniform stroke weight throughout, rounded stroke caps, geometric and precise. Centered on a
plain white background with generous empty padding; the mark occupies about 60% of the frame.

Completely flat: no gradients, no shadows, no 3D. No text, no letters, no numbers.
Square 1:1 composition.

The idea: it undoes what did not work, and then verifies that the undo actually landed.
```

## C · 세 개의 기둥 — 성적표

```
Create a minimal, flat vector app icon in Google Material Design style.

Three vertical rounded bars standing side by side on an invisible baseline, evenly spaced.
The left bar is tall and Google blue #4285F4. The middle bar is dramatically shorter than
the others — only about a quarter of the height — and Google amber #F9AB00. The right bar
is medium height and neutral light gray #DADCE0.

Fully rounded bar ends, equal bar widths, generous spacing between them. Centered on a plain
white background with generous empty padding.

Completely flat: no gradients, no shadows, no axis lines, no grid, no chart frame.
No text, no letters, no numbers, no labels.
Square 1:1 composition.

The idea: these are three counts — executed, improved, rolled back. The middle one being
short is not a mistake; it is the honest result.
```

## D · 자로 된 체크마크

```
Create a minimal, flat vector app icon in Google Material Design style.

A single bold checkmark in Google blue #4285F4. Along the long rising stroke of the
checkmark sit three short perpendicular tick marks, evenly spaced, drawn in Google amber
#F9AB00 — so the checkmark also reads as a measuring ruler.

Uniform stroke weight, rounded stroke caps, geometric. Centered on a plain white background
with generous empty padding; the mark occupies about 60% of the frame.

Completely flat: no gradients, no shadows, no 3D. No text, no letters, no numbers.
Square 1:1 composition.

The idea: this was not merely marked done — it was measured.
```

---

## 후속 지시 (Gemini는 대화로 고치는 게 빠르다)

뽑고 나서 마음에 안 들면 새로 뽑지 말고 이렇게 이어서 말한다:

```
Make the two marks further apart and increase the empty padding around them.
```
```
The smaller mark should be noticeably thinner, not just shorter.
```
```
Remove everything except the two shapes. Pure white background, nothing else.
```
```
Make it read clearly at 64 pixels — thicker strokes, simpler geometry, less detail.
```
```
Keep the exact same composition but give me a version with a transparent background.
```

## ⚠️ 검수 항목

- [ ] 글자가 하나도 없는가 (모델이 자주 몰래 넣는다)
- [ ] 100px로 줄였을 때 두 요소가 **구분되는가**
- [ ] 대칭·정렬이 맞는가 (생성 모델이 가장 자주 틀리는 곳)
- [ ] 배경이 완전한 흰색 또는 투명인가 (미세한 회색 그라데이션이 잘 섞여 들어온다)
- [ ] 색이 실제로 Google 팔레트인가 (#4285F4 / #F9AB00 / #34A853)
