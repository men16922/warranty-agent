"""demo-target 배포 진입점 — **기본값이 없다는 것이 요점이다** (T2-3 · REQ-803·602).

Spec: specs/warranty/design/11-demo.md (REQ-803)

⛔ 이 열이 태우는 것은 *"서버가 도는가"*가 아니다 — 그건 실물 배포(T2-3)의 증거다.
   묻는 것은 **진입점이 무엇을 정하고 무엇을 거부하는가**다.

넷을 묻는다:
  ① 리비전을 **환경이 정하는가** (역할 → 리비전)
  ② 환경이 비었거나 모르는 값이면 **뜨지 않는가** (기본값 금지)
  ③ 두 역할이 **서로 다른 리비전**인가 (공허 통과 방지)
  ④ 벽시계를 만지는 코드가 **이 파일 하나뿐인가**

⚠️ ②가 이 파일의 본체다. 기본값을 두면 배포가 조용히 건강한 쪽으로 뜨고, **장애 주입은
   일어나지 않는데 화면은 멀쩡하다** — 이 저장소가 통째로 반대하는 모양이다(design 08§5).
   그리고 그 침묵은 데모 당일에야 보인다.

⚠️ `main()`을 부르지 않는다. 부르면 포트를 열고 `serve_forever`가 안 돌아온다 —
   그리고 실제 `time.sleep`이 게이트에 들어와 결정론이 샌다(REQ-802).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from warranty import demo_target_server as entry
from warranty.demo_target import DEGRADED, HEALTHY

ROOT = Path(__file__).resolve().parent.parent


def test_the_role_decides_which_revision() -> None:
    """① 환경의 **역할**이 리비전을 정한다."""
    assert entry.resolve_revision({entry.REVISION_ENV_KEY: "healthy"}) is HEALTHY
    assert entry.resolve_revision({entry.REVISION_ENV_KEY: "degraded"}) is DEGRADED


@pytest.mark.parametrize("raw", ["", "   ", "HEALTHY", "slow", "demo-target-00008-slow"])
def test_an_unset_or_unknown_role_refuses_to_boot(raw: str) -> None:
    """② ⛔ **기본값을 두지 않는다.** 조용히 건강한 쪽으로 뜨는 것이 최악이다.

    ⚠️ 리비전 **이름**(`demo-target-00008-slow`)도 거부한다 — 받으면 그 이름이 여기
       사본으로 살게 되고, 서비스명을 바꾸는 날 진입점만 안 따라온다.
    """
    with pytest.raises(entry.RevisionError):
        entry.resolve_revision({entry.REVISION_ENV_KEY: raw})


def test_the_two_roles_are_actually_different() -> None:
    """③ 공허 통과 방지 — 둘이 같아지면 위 검사들이 전부 조용히 통과한다."""
    assert len(entry.ROLES) >= 2
    revisions = set(entry.ROLES.values())
    assert len(revisions) == len(entry.ROLES), "역할이 같은 리비전을 가리킨다"
    assert HEALTHY.work_latency_ms != DEGRADED.work_latency_ms, (
        "두 리비전의 지연이 같다 — 장애 주입이 신호를 안 바꾼다"
    )


def test_the_wall_clock_is_touched_only_in_deployment_entrypoints() -> None:
    """④ ⛔ `time.sleep`은 **배포 진입점**에서만 실물 시계 포트에 주입한다.

    ⚠️ 실제로 그 규칙이 T11-4의 결정이었다: `demo_target`은 지연을 주입받고 구현을 안 갖는다.
       주입하는 자리가 늘어나면 그 결정은 문서에만 남는다.
    """
    offenders = []
    entrypoints = {"demo_target_server.py", "server.py"}
    for path in sorted((ROOT / "src").rglob("*.py")):
        if path.name in entrypoints:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "sleep"
                and isinstance(node.value, ast.Name)
                and node.value.id == "time"
            ):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, (
        f"`time.sleep`이 배포 진입점 밖에 있다: {offenders} — 게이트가 그것을 상속받고 "
        "결정론이 샌다(REQ-802)."
    )
