"""demo-target — **두 리비전의 차이가 데모를 만든다** (T11-4 · design 11§1 원칙 5).

Spec: specs/warranty/design/11-demo.md (REQ-803)

⛔ 여기서 묻는 것은 *"이 앱이 Cloud Run에서 도는가"*가 **아니다.** 그건 T2-3의 질문이고
   오프라인 게이트가 판정할 수 없다 (docs/PRINCIPLES.md #3). 묻는 것은 둘이다 —
   **두 리비전이 서로 다른 이야기를 하는가**, 그리고 그 차이가 **실물 판정 코드를 지날 때
   데모의 서사(검증 실패 → 자동 롤백 → 신호 회복)를 만드는가.**

일곱을 묻는다:
  ① 리비전이 **둘이고 서로 다른가** (공허 통과 방지 — 하나로 뭉치면 아래가 전부 조용히 통과한다)
  ② 나쁜 리비전이 **실제로 느린가** — 선언이 아니라 `pause`가 **받은 값**으로
  ③ 헬스 프로브는 **둘 다 빠른가** (아니면 Cloud Run이 트래픽을 안 옮긴다)
  ④ 모르는 경로는 둘 다 거절하고 **시간을 안 쓴다**
  ⑤ ★ 건강 → 악화가 계약 기준으로 **`not_recovered`인가** (실물 `classify`가 판정한다)
  ⑥ ★ 장애가 **롤백 재측정의 허용 오차보다 큰가** — 아니면 안 되돌려도 "돌아왔다"가 된다
  ⑦ 데모의 신호 각본이 **이 앱에서 오는가** (값이 같은가가 아니라 **어디서 왔는가**)

⚠️ ⑥이 ⑤의 되풀이가 아닌 이유: ⑤의 기준(회복 = 50% 개선)은 *"안 나아졌다"*와
   *"더 나빠졌다"*를 구별하지 않는다 — 장애를 620→640으로 줄여도 ⑤는 **초록이다.**
   그런데 그때 롤백 후 재측정은 조치를 안 되돌려도 기준선의 ±15% 안이라 `signal_restored`가
   참이 되고, REQ-304가 하중을 잃는다. **장애의 크기를 묻는 자리는 ⑥ 하나다.**
"""

from __future__ import annotations

import ast
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import warranty.demo as demo  # `from warranty import demo`는 재수출이 아니다(strict)
from warranty.demo_target import (
    DEGRADED,
    HEALTH_PATH,
    HEALTHY,
    MS_PER_SECOND,
    NOT_FOUND,
    OK,
    REVISIONS,
    SERVICE_NAME,
    WORK_PATH,
    Response,
    Revision,
)
from warranty.domain.verification import Measurement, Verdict, classify

# ⛔ 허용 오차를 **여기 다시 적지 않는다.** 적으면 롤백 재측정이 0.15를 0.9로 바꿔도
#    ⑥은 옛 숫자를 지키며 초록이다 — 그건 이 저장소가 여러 번 겪은 사본의 모양이다.
from warranty.usecases.remediate import _within

ROOT = Path(__file__).resolve().parent.parent
DEMO_SOURCE = ROOT / "src" / "warranty" / "demo.py"

#: design 10§2 — *"조치 대상. 리비전 2개 이상"*.
MIN_REVISIONS = 2

#: 판정에 넘길 데이터 포인트 수. 값 자체는 이 파일의 관심이 아니다 — 창이 비면
#: `classify`가 `UNVERIFIABLE`을 내고 ⑤·⑥이 **장애와 무관하게** 초록이 된다.
POINTS = demo.SIGNAL_POINTS

#: 데모의 신호 각본이 **이 앱에서 오는지** 볼 때 찾는 출처.
TARGET_MODULE = "warranty.demo_target"

#: 데모가 **이 앱에서 받아 와야 하는** 이름들. ⚠️ `AFTER_ROLLBACK_MS`는 여기 없다 —
#: 그건 `BASELINE_MS`에서 파생되므로 기준선 하나만 지키면 함께 지켜진다.
DERIVED_IN_DEMO = (
    "DEMO_SERVICE",
    "HEALTHY_REVISION",
    "SLOW_REVISION",
    "BASELINE_MS",
    "AFTER_ACTION_MS",
)


def _served(revision: Revision, path: str) -> tuple[Response, list[float]]:
    """요청 하나를 처리시키고 **실제로 쓴 시간**을 함께 돌려준다.

    ⚠️ 여기서 진짜로 자지 않는다. 자면 게이트가 그만큼 느려지고, 무엇보다
       *"얼마를 쓰려 했는가"*를 값으로 볼 수 없다 — 볼 수 없으면 못 묻는다.
    """
    spent: list[float] = []
    return revision.serve(path, spent.append), spent


def _measured(value: int) -> Measurement:
    return Measurement(Decimal(value), POINTS)


def _imported_from(module: str, path: Path) -> set[str]:
    """`path`가 `module`**에서** 들여온 이름들 (test_tunables.py와 같은 규칙)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == module
        for alias in node.names
    }


def _module_assignments(path: Path) -> dict[str, ast.expr]:
    """모듈 **최상위**의 `NAME = <식>` → 그 식."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }


def _names_in(expr: ast.expr) -> set[str]:
    return {node.id for node in ast.walk(expr) if isinstance(node, ast.Name)}


# ── ① 공허 통과 방지 ──────────────────────────────────────────────────────


def test_the_app_declares_two_distinct_revisions() -> None:
    """① ⚠️ 리비전이 하나로 뭉치면 아래 여섯이 **전부 조용히 통과한다** — 비교할 상대가
    없으면 *"차이가 없다"*와 *"안 봤다"*가 같은 초록이다 (M-03·M-25·M-45의 모양).
    """
    assert len(REVISIONS) >= MIN_REVISIONS, (
        f"design 10§2는 리비전 {MIN_REVISIONS}개 이상을 요구하는데 {len(REVISIONS)}개다"
    )
    names = [revision.name for revision in REVISIONS]
    assert len(set(names)) == len(names), (
        f"리비전 이름이 겹친다: {names} — 겹치면 트래픽 전환이 무엇에서 무엇으로인지 없다"
    )
    latencies = [revision.work_latency_ms for revision in REVISIONS]
    assert len(set(latencies)) == len(latencies), (
        f"리비전이 전부 같은 지연을 낸다: {latencies} — 옮겨도 신호가 안 움직인다"
    )
    assert all(revision.name.startswith(SERVICE_NAME) for revision in REVISIONS), (
        f"리비전 이름이 서비스명에서 안 왔다: {names}"
    )


# ── ②③④ 행동 — 선언이 아니라 실제로 쓴 것 ────────────────────────────────


def test_the_degrading_revision_actually_spends_more_time_than_the_healthy_one() -> None:
    """② ★ 이 태스크의 한 줄 수용 기준이다 — **두 리비전의 동작 차이.**

    ⛔ `latency_ms`만 물으면 *"느리다고 말하는 리비전"*으로 충분해진다. 그건 결과를
       박아 두는 것과 같은 종류다 (design 11§1 원칙 5). 그래서 **`pause`가 받은 값**을 본다.
    """
    healthy, healthy_spent = _served(HEALTHY, WORK_PATH)
    degraded, degraded_spent = _served(DEGRADED, WORK_PATH)

    assert healthy_spent == [HEALTHY.work_latency_ms / MS_PER_SECOND], (
        f"건강한 리비전이 쓴 시간이 선언과 다르다: {healthy_spent}"
    )
    assert degraded_spent == [DEGRADED.work_latency_ms / MS_PER_SECOND], (
        f"나쁜 리비전이 지연을 **선언만 하고 안 썼다**: {degraded_spent}"
    )
    assert degraded_spent[0] > healthy_spent[0], (
        f"장애 주입 리비전이 더 느리지 않다: {degraded_spent} ≤ {healthy_spent}"
    )
    assert (healthy.status, degraded.status) == (OK, OK), "작업 경로가 200을 안 낸다"
    assert degraded.latency_ms == DEGRADED.work_latency_ms


def test_both_revisions_answer_the_health_probe_without_spending_time() -> None:
    """③ ⛔ **나쁜 리비전은 살아 있으면서 느려야 한다.**

    프로브에서 죽으면 Cloud Run은 그리로 트래픽을 안 옮기고, 장애 주입이 **배포 실패**로
    바뀐다 — 그러면 데모가 보여 주려던 것(검증 실패 → 자동 롤백)은 한 번도 안 일어나고,
    화면에 남는 것은 *"배포가 안 됐다"*뿐이다.
    """
    for revision in REVISIONS:
        response, spent = _served(revision, HEALTH_PATH)
        assert response.status == OK, f"{revision.name}이 헬스 프로브에 {response.status}를 낸다"
        assert spent == [], f"{revision.name}이 헬스 프로브에서 시간을 쓴다: {spent}"
        assert response.latency_ms == 0


def test_an_unknown_path_is_refused_by_both_revisions_without_spending_time() -> None:
    """④ ⚠️ 모르는 경로를 작업으로 치면 **오타 하나가 장애 주입이 된다** — 그리고 그 지연은
    계약이 재는 신호에 그대로 실린다. 무엇을 쟀는지 말할 수 없는 측정이 된다.
    """
    for revision in REVISIONS:
        response, spent = _served(revision, "/nope")
        assert response.status == NOT_FOUND, f"{revision.name}이 모르는 경로를 받아 준다"
        assert spent == [], f"{revision.name}이 모르는 경로에 시간을 쓴다: {spent}"


# ── ⑤⑥ 그 차이가 서사를 만드는가 — 실물 판정 코드가 판정한다 ──────────────


def test_the_injected_fault_is_judged_not_recovered_by_the_demo_contract() -> None:
    """Verifies: REQ-803

    ⑤ ★ 조치가 트래픽을 나쁜 리비전으로 옮겼을 때 **검증이 실패해야** 롤백이 일어난다.
    판정은 여기서 안 적는다 — 데모가 쓰는 그 계약 기준으로 실물 `classify`가 낸다.
    """
    contract = demo.demo_contract(datetime.fromisoformat(demo.DEMO_CLOCK_ISO))
    verdict = classify(
        _measured(HEALTHY.work_latency_ms),
        _measured(DEGRADED.work_latency_ms),
        contract.recovery_criterion,
    )
    assert verdict is Verdict.NOT_RECOVERED, (
        f"장애 주입 뒤 판정이 {verdict}다 — 검증이 실패하지 않으면 롤백이 없고, 데모의 절정도 없다"
    )


def test_the_fault_is_bigger_than_what_the_rollback_check_calls_unchanged() -> None:
    """Verifies: REQ-803, REQ-304

    ⑥ ⛔ **이 파일에서 가장 하중이 큰 자리다.** 롤백 후 재측정은 *"기준선으로 돌아왔는가"*를
    허용 오차로 판정한다. 장애가 그 오차보다 작으면 **되돌리지 않아도** 돌아온 것으로
    읽히고, REQ-304는 늘 참인 문장이 된다 — 그리고 그 초록은 조치가 아무것도 안 해도 난다.

    ⚠️ 오차 값을 여기 안 적는다. `_within`을 그대로 부른다 — 사본을 두면 판정 쪽이 오차를
       넓혀도 이 검사는 옛 숫자를 지키며 초록이다.
    """
    baseline = _measured(HEALTHY.work_latency_ms)
    faulted = _measured(DEGRADED.work_latency_ms)
    assert not _within(faulted, baseline), (
        f"장애({faulted.value}ms)가 기준선({baseline.value}ms)에서 '그대로'라고 불릴 만큼 "
        "가깝다 — 롤백을 안 해도 신호가 회복된 것으로 읽힌다"
    )
    # 되돌아온 쪽은 반대다 — 같은 리비전으로 돌아왔으니 '그대로'여야 한다.
    assert _within(baseline, baseline)


# ── ⑦ 데모의 각본이 어디서 오는가 ─────────────────────────────────────────


def test_the_demo_signal_script_comes_from_this_app_not_a_second_copy() -> None:
    """Verifies: REQ-803

    ⑦ ⛔ **값이 같은지 묻는 것과 어디서 왔는지 묻는 것은 다르다** (T11-1·T11-3이 남긴 교훈).
    `BASELINE_MS = Decimal("620")`은 오늘 이 앱과 값이 같아서 **아래 값 검사를 전부
    통과한다.** 그런데 앱의 지연을 바꾸는 날 그 줄은 **안 따라온다** — 그때 데모는
    존재하지 않는 리비전의 이야기를 하고, 게이트는 초록이다.
    ⇒ 값과 **출처를 함께** 묻는다. 출처는 구문으로만 물어진다.
    """
    imported = _imported_from(TARGET_MODULE, DEMO_SOURCE)
    assert {"HEALTHY", "DEGRADED"} <= imported, (
        f"데모가 {TARGET_MODULE}에서 두 리비전을 안 들여온다: {sorted(imported)} — "
        "각본의 숫자가 앱과 따로 산다"
    )
    assignments = _module_assignments(DEMO_SOURCE)
    missing = [name for name in DERIVED_IN_DEMO if name not in assignments]
    assert not missing, f"데모에서 못 찾은 이름: {missing} — 이 검사가 공허하다"
    unsourced = [
        f"{name} = {ast.unparse(assignments[name])}"
        for name in DERIVED_IN_DEMO
        if not (imported & _names_in(assignments[name]))
    ]
    assert not unsourced, (
        f"데모가 앱에서 안 받고 **직접 적은** 값: {unsourced} — "
        "값은 오늘 같아도 앱을 고치는 날 안 따라온다"
    )
    assert HEALTHY.name == demo.HEALTHY_REVISION
    assert DEGRADED.name == demo.SLOW_REVISION
    assert Decimal(HEALTHY.work_latency_ms) == demo.BASELINE_MS
    assert Decimal(DEGRADED.work_latency_ms) == demo.AFTER_ACTION_MS
