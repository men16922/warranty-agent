"""README 재현 절차 — **적어 둔 명령이 실재하는가** (T11-5 · REQ-901).

Spec: specs/warranty/requirements.md (REQ-901)

REQ-901은 제출물에 **재현 가능한 실행 절차**를 요구한다. 그 절차가 사는 곳은 README이고,
README는 지금까지 이 저장소에서 **아무 게이트도 안 지나는 유일한 문서였다.**

⛔ **실제로 났던 종류다**: `make demo`가 죽어 있던 적이 있다. 죽은 명령을 적어 둔 README는
   틀린 README보다 나쁘다 — 처음 오는 사람은 **자기가 틀렸다고 생각하고** 저장소를 닫는다.

⚠️ 여기서 묻지 않는 것: *"그 명령이 성공하는가"*. 게이트가 자기를 부르는 일이 되고
   (`make check`가 `make check`를 돌린다), `make venv`는 네트워크를 쓴다(REQ-801).
   묻는 것은 **이름이 실재하는가**까지다 — 죽은 *타깃*은 잡히고 죽은 *동작*은 안 잡힌다.

⚠️ REQ-901의 나머지 넷(저장소 URL · 데모 영상 · 아키텍처 다이어그램 · 실물 실행의 시각 증거)은
   오프라인 게이트가 판정할 질문이 아니다(docs/PRINCIPLES.md #3). **그래서 `Verifies:`를 안
   붙였고 상태도 안 올렸다** — 이 열이 태우는 것은 다섯 중 하나의 절반이다.

넷을 묻는다:
  ① 스캐너가 **실제로 읽고 뽑는가** (표본으로 태운다 · 바닥)
  ② README가 적은 `make` 명령이 **전부 실재하는 타깃인가**
  ③ 절차가 **부트스트랩·게이트·실행을 이름으로 갖는가** (일치가 아니라 **값**)
  ④ README가 가리키는 저장소 안의 경로가 **실재하는가**

⚠️ ③이 ②의 되풀이가 아닌 이유: 재현 절차 블록을 **통째로 지우면** ②는 0개를 훑고 **초록이다.**
   그 초록은 *"명령이 다 산다"*가 아니라 **"적힌 게 없다"**이다. REQ-901이 요구한 것은 절차의
   **존재**이고, 그것을 값으로 묻는 자리는 ③ 하나다 (T11-2·T11-3과 같은 계열).

⚠️ 스캐너는 **코드 문맥만** 본다 — 펜스 블록과 인라인 코드다. 산문의 "make sure"를 타깃으로
   읽으면 영어 문장을 고칠 때마다 게이트가 red고, 그러면 다음 사람은 **가드를 끈다.**
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
MAKEFILE = ROOT / "Makefile"

#: 재현에 필요한 것 셋. ⛔ **일치가 아니라 값이다** — 셋이 각각 다른 질문에 답한다:
#: 부트스트랩(의존성을 어디서 얻는가) · 게이트(무엇이 맞다고 말하는가) · 실행(무엇을 하는가).
#: ⚠️ `demo`가 여기 있는 이유: 오늘 이 저장소에서 **무엇을 하는지 보여 주는 명령은 그것뿐이다**
#:    (실물 왕복은 T2-4다). 그리고 그 결정론은 REQ-803이 이미 집행한다.
REQUIRED_COMMANDS = ("venv", "check", "demo")

#: 공허 통과 방지의 바닥. 스캐너가 깨지면 아래 단언들이 조용히 참이 된다.
MIN_DOCUMENTED_COMMANDS = 3
MIN_REPO_LINKS = 5
MIN_MAKE_TARGETS = 8

FENCED_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
INLINE_RE = re.compile(r"`([^`\n]+)`")
MAKE_RE = re.compile(r"\bmake\s+([a-z][a-z0-9_-]*)")
#: `foo:` 형태의 타깃 **선언**. ⚠️ `.PHONY:` 목록만 보면 **몸통 없는 이름이 실재하는 것으로
#: 읽힌다.** `(?!=)`는 `:=` 대입을 타깃으로 세지 않게 한다.
TARGET_RE = re.compile(r"^([a-zA-Z][\w-]*)\s*:(?!=)", re.MULTILINE)
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code_spans(text: str) -> list[str]:
    """명령이 사는 곳 — 펜스 블록과 인라인 코드. **산문은 안 본다.**"""
    fenced = FENCED_RE.findall(text)
    return [*fenced, *INLINE_RE.findall(FENCED_RE.sub("\n", text))]


def _documented_commands(text: str) -> set[str]:
    """README가 **적어 둔** make 타깃 이름. 주석 뒤는 안 센다(`# … make ghost`)."""
    found: set[str] = set()
    for span in _code_spans(text):
        for line in span.splitlines():
            found.update(MAKE_RE.findall(line.split("#", 1)[0]))
    return found


def _repo_links(text: str) -> list[str]:
    """저장소 안을 가리키는 링크만. 외부 URL과 앵커는 이 가드의 대상이 아니다."""
    return [
        token
        for token in LINK_RE.findall(text)
        if not token.startswith(("http://", "https://", "#", "mailto:"))
    ]


def _make_targets() -> set[str]:
    return set(TARGET_RE.findall(_read(MAKEFILE)))


# ── ① 스캐너를 표본으로 태운다 ──────────────────────────────────────────────

#: ⚠️ 표본은 **실패해야 하는 것들을 일부러 담는다** — 산문의 `make sure`, 주석 뒤의
#:    `make ghost`, 외부 URL. 이 셋이 안 걸러지면 아래 셋은 판정이 아니다.
SAMPLE = """\
Prose that says make sure to read this first.

| **What this is** | [`docs/X.md`](docs/X.md) |
| Upstream | [ADK](https://example.invalid/adk) |

```bash
make venv && make check   # also mentions make ghost
make trace
```

Inline `make demo` counts too.
"""


def test_scanner_reads_commands_and_links_from_a_sample() -> None:
    """① 스캐너가 코드 문맥만 읽고, `&&`를 가르고, 주석 뒤를 버리는가."""
    assert _documented_commands(SAMPLE) == {"venv", "check", "trace", "demo"}, (
        "표본에서 뽑힌 명령이 기대와 다르다 — 산문('make sure')이 섞였거나 "
        "주석 뒤('make ghost')를 셌거나 `&&`를 안 갈랐다."
    )
    assert _repo_links(SAMPLE) == ["docs/X.md"], (
        "표본에서 뽑힌 링크가 기대와 다르다 — 외부 URL이 섞였다."
    )


def test_readme_and_makefile_yield_enough_to_judge() -> None:
    """① 바닥 — 0개를 훑는 초록은 *'다 맞다'*가 아니라 **'아무것도 안 봤다'**이다."""
    assert REQUIRED_COMMANDS, "필수 명령 목록이 비었다 — ③이 판정하는 것이 없어진다."
    documented = _documented_commands(_read(README))
    assert len(documented) >= MIN_DOCUMENTED_COMMANDS, (
        f"README에서 명령을 {len(documented)}개만 읽었다({sorted(documented)}). "
        "스캐너가 깨졌거나 재현 절차가 지워졌다."
    )
    targets = _make_targets()
    assert len(targets) >= MIN_MAKE_TARGETS, (
        f"Makefile에서 타깃을 {len(targets)}개만 읽었다 — 파서가 깨지면 ②가 "
        "**모든 명령을 죽은 것으로** 읽는다(반대 방향의 거짓말이다)."
    )
    links = _repo_links(_read(README))
    assert len(links) >= MIN_REPO_LINKS, (
        f"README에서 저장소 내부 링크를 {len(links)}개만 읽었다 — ④가 공허해진다."
    )


# ── ② 적어 둔 명령이 실재하는가 ─────────────────────────────────────────────


def test_documented_make_commands_are_real_targets() -> None:
    """② ⛔ **죽은 명령을 적어 둔 README는 재현 절차가 아니다.**"""
    documented = _documented_commands(_read(README))
    dead = sorted(documented - _make_targets())
    assert not dead, (
        f"README가 적은 명령이 Makefile에 없다: {dead}. "
        "타깃 이름을 바꿨다면 README도 같이 바꾼다 — 값의 출처는 Makefile 하나다."
    )


# ── ③ 절차가 무엇을 갖는가 (값) ────────────────────────────────────────────


def test_procedure_names_bootstrap_gate_and_run() -> None:
    """③ ⛔ 블록을 통째로 지우면 ②는 초록이다. **존재를 묻는 자리는 여기 하나다.**"""
    documented = _documented_commands(_read(README))
    missing = [command for command in REQUIRED_COMMANDS if command not in documented]
    assert not missing, (
        f"README의 재현 절차에 없는 것: {[f'make {c}' for c in missing]}. "
        "REQ-901이 요구하는 것은 부트스트랩·게이트·실행 셋이다 — "
        "게이트만 적힌 README는 *맞는지*는 알려 주고 *무엇을 하는지*는 안 알려 준다."
    )


# ── ④ 가리키는 곳이 실재하는가 ─────────────────────────────────────────────


def test_repo_relative_links_resolve() -> None:
    """④ 제출물의 진입점이 **없는 문서를 가리키면** 재현은 첫 클릭에서 끝난다."""
    dangling = [token for token in _repo_links(_read(README)) if not (ROOT / token).exists()]
    assert not dangling, (
        f"README가 없는 경로를 가리킨다: {dangling}. "
        "G6④가 코드의 `Spec:`에 대해 하는 일을 README에 대해 하는 자리다."
    )
