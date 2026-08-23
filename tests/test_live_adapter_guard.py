"""G5 — 게이트가 도는 동안 **라이브 어댑터 생성 0** (T12-5 · T5-4 · REQ-801).

Spec: specs/warranty/design/09-quality-gate.md §3.2 (G5 · REQ-801)

⛔ **마지막 미착수 가드였다.** T10-3이 미룬 이유는 정직했다 — 그때 `adapters/`에는
   `fakes.py`뿐이라 *"라이브 어댑터를 안 만든다"*를 집행해 봐야 **0개를 훑고 초록인 가드**였다.
   T12-3이 `adk_agent.build_agent`·`build_runner`를 만들면서 훑을 대상이 생겼고, 그 두 함수는
   도크스트링에 *"게이트는 이것을 안 부른다"*고 **적어만 두었다.** 여기가 그 문장을
   집행으로 바꾸는 자리다.

⚠️ **`test_adk_agent.py`가 묻는 것과 다르다.** 그쪽 M-146·M-148은 *"최상위에 `google`
   임포트가 없는가"* + *"지연 임포트가 실재하는가"*를 묻는다. 둘 다 참이면서 게이트가
   `build_agent`를 **부를 수 있다** — 지연 임포트는 부르는 순간에야 일어나기 때문이다.
   ⇒ 여기서 묻는 것은 임포트가 아니라 **생성 경로를 지났는가**다.

묻는 것은 여섯이다:
  ① 훑을 대상이 실재하고 census가 **실제로 잡는가** (표본 셋으로 태운다)
  ② 생성 경로의 **모든** 함수가 tripwire를 지나는가
  ③ 게이트가 도는 동안 tripwire가 **걸려 있는가** (`tests/conftest.py`)
  ④ 걸린 tripwire가 **실제로 거부하는가** (표본으로 태운다)
  ⑤ 이 게이트에서 지나간 생성 입구가 **0인가**
  ⑥ 클라우드 SDK 모듈이 `sys.modules`에 **한 번도 안 들어왔는가**

⚠️ ⑤가 ③·④의 되풀이가 아닌 이유: 걸린 tripwire는 위반을 **그 테스트 안에서** 터뜨린다.
   ⑤는 그 뒤에 남는 값이라 *"어느 테스트도 안 만들었다"*를 한 줄로 말한다.
   ⛔ 다만 ⑤의 하중은 **실행 순서에 달려 있다** — 이 파일보다 뒤에 도는 테스트가 만들면
   ⑤는 못 보고 ③·④가 만든 예외가 본다. 그래서 본체는 ②·③이고 ⑤는 마감이다.

⚠️ 상태를 안 올린다. REQ-801의 두 번째 문장(*"Firestore·BigQuery·Monitoring은 전부 fake로
   대체된다"*)은 지금 **대체할 실물이 없어서** 참이다. 그건 집행이 아니라 부재다.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from warranty.adapters import live_guard

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "warranty"

#: ⛔ 클라우드 SDK의 최상위 모듈 이름. 여기 없는 이름은 이 census가 **못 보는 자리**다.
CLOUD_ROOTS = ("google", "vertexai")

#: 생성 경로가 지나야 하는 자리 — `live_guard.note(...)`. **속성 호출 형태로만** 인정한다:
#: 이름만 보면 아무 `note()`나 통과하고, 그때 가드는 자기가 무엇을 봤는지 모른다.
TRIPWIRE_MODULE = "live_guard"
TRIPWIRE_CALL = "note"

#: 공허 통과 방지의 바닥. 0이 되면 ②는 **아무것도 안 보고** 초록이다 —
#: 이 저장소가 M-03·M-25·M-45·M-118에서 네 번 속은 그 모양이다.
MIN_LIVE_SITES = 3

#: ④가 쓰는 표지. ⑤는 이것만 빼고 센다 — 표본이 자기 검사를 오염시키면 안 된다.
CONTROL_FACTORY = "<control-sample>"

FuncDef = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True, slots=True)
class LiveSite:
    """라이브 클라이언트를 만드는 함수 하나."""

    where: str
    func: str
    why: str
    guarded: bool


def _cloud_import(node: ast.AST) -> str | None:
    """이 노드가 클라우드 SDK를 임포트하면 그 이름. 아니면 `None`."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.split(".")[0] in CLOUD_ROOTS:
                return alias.name
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module.split(".")[0] in CLOUD_ROOTS:
            return module
    return None


def _deferred_cloud_import(func: FuncDef) -> str | None:
    """⛔ **함수 몸 안의** 클라우드 임포트만 본다.

    최상위 임포트는 여기서 안 잡힌다 — 그건 M-146의 자리이고, 애초에 게이트가
    임포트 단계에서 통째로 죽는다(`google-adk`가 없다). 여기서 찾는 것은
    *"부르면 그때 네트워크에 가까워지는"* 자리다.
    """
    for node in ast.walk(func):
        found = _cloud_import(node)
        if found is not None:
            return found
    return None


def _called_names(func: FuncDef) -> set[str]:
    """이 함수가 부르는 이름들. `a.b()`는 `b`로 센다."""
    names: set[str] = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


def _passes_tripwire(func: FuncDef) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == TRIPWIRE_CALL
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == TRIPWIRE_MODULE
        for node in ast.walk(func)
    )


def census(source: str, where: str) -> tuple[LiveSite, ...]:
    """한 모듈의 **생성 경로 전체**. 씨앗은 지연 임포트, 나머지는 전이 폐포다.

    ⚠️ 폐포가 요점이다. 임포트하는 함수만 잡으면 `build_agent`는 census에 안 들어오고,
       그때 *"게이트가 `build_agent`를 부른다"*는 아무 데도 안 나타난다 — 그 함수는
       클라우드 이름을 한 글자도 안 적기 때문이다.
    """
    tree = ast.parse(source)
    funcs: dict[str, FuncDef] = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    why: dict[str, str] = {}
    for name, func in funcs.items():
        imported = _deferred_cloud_import(func)
        if imported is not None:
            why[name] = f"클라우드 SDK를 지연 임포트한다: {imported}"

    growing = True
    while growing:
        growing = False
        for name, func in funcs.items():
            if name in why:
                continue
            reached = sorted(_called_names(func) & set(why))
            if reached:
                why[name] = f"생성 경로를 부른다: {reached[0]}"
                growing = True

    return tuple(
        LiveSite(where=where, func=name, why=why[name], guarded=_passes_tripwire(funcs[name]))
        for name in sorted(why)
    )


def repo_census() -> tuple[LiveSite, ...]:
    sites: list[LiveSite] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = str(path.relative_to(ROOT))
        sites.extend(census(path.read_text(encoding="utf-8"), rel))
    return tuple(sites)


# ── ① census를 표본으로 태운다 ──────────────────────────────────────────────
#
# ⚠️ census를 census로 검사할 수는 없다. 기대값이 박힌 표본이 유일한 바닥이다
#    (test_sweep_log_integrity.py가 먼저 쓴 규칙).

#: 씨앗과 폐포를 함께 태운다 — `build`는 클라우드 이름을 한 글자도 안 적는다.
UNGUARDED_SAMPLE = """\
def _load():
    import google.adk as adk

    return adk


def build():
    return _load().Agent()
"""

#: 지나는 꼴. ⚠️ `live_guard.note(...)` **속성 호출**이어야 한다.
GUARDED_SAMPLE = """\
from warranty.adapters import live_guard


def _load():
    live_guard.note("sample._load")
    import vertexai

    return vertexai
"""

#: 순수 렌더러 — 생성 경로가 아니다. census가 전부를 잡으면 ②는 영원히 red다.
CLEAN_SAMPLE = """\
def agent_kwargs(spec, tools):
    return {"model": spec.model, "tools": list(tools)}
"""


@pytest.fixture(scope="module")
def sites() -> tuple[LiveSite, ...]:
    return repo_census()


def test_the_census_actually_finds_live_construction_sites(sites: tuple[LiveSite, ...]) -> None:
    """① 공허 통과 방지 — census가 0개를 읽으면 ②는 **아무것도 안 보고** 초록이다.

    ⚠️ 목록의 길이가 census의 능력이 아니다. 표본 셋이 각각 다른 질문에 답한다:
       씨앗을 찾는가 · **폐포를 따라가는가** · 아무거나 잡지는 않는가.
    """
    assert len(sites) >= MIN_LIVE_SITES, (
        f"생성 경로를 {len(sites)}개만 찾았다 (최소 {MIN_LIVE_SITES}) — "
        f"census가 깨졌거나 배선이 통째로 사라졌다: {[site.func for site in sites]}"
    )

    unguarded = census(UNGUARDED_SAMPLE, "<sample>")
    assert [site.func for site in unguarded] == ["_load", "build"], (
        f"표본에서 생성 경로를 {[site.func for site in unguarded]}로 읽었다 — "
        "기대는 ['_load', 'build']다. `build`가 빠지면 폐포가 끊긴 것이고, "
        "그때 **클라우드 이름을 안 적는 호출자**는 census 밖이다"
    )
    assert not any(site.guarded for site in unguarded), (
        f"tripwire가 없는 표본을 지난 것으로 읽었다: {unguarded}"
    )

    guarded = census(GUARDED_SAMPLE, "<sample>")
    assert [site.guarded for site in guarded] == [True], (
        f"tripwire를 지나는 표본을 못 알아봤다: {guarded} — "
        "인식이 깨지면 ②는 늘 red이고, 사람이 고치는 방향은 **가드를 지우는 것**이 된다"
    )

    assert not census(CLEAN_SAMPLE, "<sample>"), (
        "순수 렌더러를 생성 경로로 읽었다 — census가 전부를 잡으면 ②는 신호가 아니다"
    )


# ── ② 생성 경로가 전부 tripwire를 지나는가 (본체) ──────────────────────────


def test_every_live_construction_site_passes_the_tripwire(sites: tuple[LiveSite, ...]) -> None:
    """② ⛔ **이 가드의 본체다.** 라이브 클라이언트를 만드는 함수는 전부 tripwire를 지난다.

    Verifies: REQ-801

    ⚠️ 새 라이브 어댑터(Firestore·Monitoring·Cloud Run)가 들어오는 날 red가 나는 자리가
       여기다. 그때 고칠 것은 census가 아니라 **그 함수의 첫 줄**이다.
    """
    naked = [f"{site.where}::{site.func} ({site.why})" for site in sites if not site.guarded]
    assert not naked, (
        f"tripwire를 안 지나는 생성 경로가 있다: {naked} — "
        f"첫 줄에 `{TRIPWIRE_MODULE}.{TRIPWIRE_CALL}(...)`를 넣어라. "
        "게이트가 그 함수를 부르는 순간 REQ-801은 문장으로만 남는다"
    )


# ── ③④ tripwire가 걸려 있고 실제로 거부하는가 ─────────────────────────────


def test_the_tripwire_is_armed_while_the_gate_runs() -> None:
    """③ ⛔ 거는 줄이 사라지면 ②·⑤는 그대로 초록이고 **게이트는 조용히 온라인이 된다**.

    Verifies: REQ-801

    ⚠️ 거는 자리는 `tests/conftest.py` 한 줄이다. tripwire의 기본값이 *안 걸림*인 것은
       설계다(배포된 프로세스는 자기 자신을 만들어야 한다) — 그러니 *"안 걸렸다"*는
       게이트에서만 비정상이고, 그것을 묻는 자리는 여기 하나뿐이다.
    """
    assert live_guard.is_armed(), (
        "게이트가 도는데 tripwire가 안 걸려 있다 — `tests/conftest.py`의 `live_guard.arm()`이 "
        "사라졌다. 그러면 라이브 어댑터를 만들어도 아무 일도 안 일어난다"
    )


def test_an_armed_tripwire_actually_refuses() -> None:
    """④ 걸린 tripwire가 **막는가** — 기록만 하고 통과시키면 ③은 초록이고 위반은 지나간다."""
    assert live_guard.is_armed(), "표본을 태우기 전에 tripwire가 걸려 있어야 한다"
    with pytest.raises(live_guard.LiveAdapterForbidden) as caught:
        live_guard.note(CONTROL_FACTORY)
    assert CONTROL_FACTORY in str(caught.value), (
        f"거부 메시지가 무엇을 만들려 했는지 안 말한다: {caught.value} — "
        "그러면 사람이 하는 일은 다시 재현해서 찾아내는 것이다"
    )
    assert CONTROL_FACTORY in live_guard.constructions(), (
        "막기만 하고 기록을 안 남겼다 — 기록이 없으면 ⑤는 아무것도 안 보고 초록이다"
    )


# ── ⑤⑥ 이 게이트가 실제로 만든 것이 0인가 ─────────────────────────────────


def test_no_live_adapter_was_constructed_during_the_gate() -> None:
    """⑤ 지나간 생성 입구가 0인가 (④의 표본은 뺀다).

    Verifies: REQ-801

    ⚠️ 하중은 실행 순서에 달려 있다(모듈 상자 참조) — 이 파일보다 뒤에 도는 테스트가
       만들면 그 테스트가 `LiveAdapterForbidden`으로 죽고, 게이트는 어느 쪽이든 red다.
    """
    real = [name for name in live_guard.constructions() if name != CONTROL_FACTORY]
    assert not real, (
        f"게이트가 라이브 어댑터를 만들었다: {real} — REQ-801은 게이트가 과금하지 않는다고 "
        "약속한다. 테스트는 fake를 명시적으로 주입한다(design 08§5)"
    )


def test_no_cloud_sdk_module_was_ever_imported() -> None:
    """⑥ 생성의 **흔적**을 본다 — 지연 임포트가 한 번이라도 돌면 `sys.modules`에 남는다.

    Verifies: REQ-801

    ⚠️ ②가 정적이고 ③④⑤가 우리 코드의 자리를 본다면, 여기는 **런타임 사실**을 본다:
       우리가 census에 안 적은 경로로 누가 클라우드 SDK를 끌어왔어도 이 줄은 안다.
    """
    loaded = sorted(name for name in sys.modules if name.split(".")[0] in CLOUD_ROOTS)
    assert not loaded, (
        f"게이트가 클라우드 SDK를 임포트했다: {loaded} — 임포트는 생성의 흔적이고, "
        "게이트 venv에 그 패키지가 없는 것이 REQ-801이다"
    )
