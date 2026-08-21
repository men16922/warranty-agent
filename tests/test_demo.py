"""`make demo` — 다섯 단계가 **매번 같은 결과**인가 (REQ-803).

Spec: specs/warranty/design/11-demo.md (REQ-803)

⚠️ **데모의 판정을 사람에게 맡기면 데모는 검증되지 않는다.** 영상 찍는 날 처음 돌려보고
   숫자가 다르면 그때는 늦다 — 그래서 판정이 게이트 안에 있다 (design 11§1 원칙 1).

⚠️ 여기서 지키는 것은 "출력이 예쁜가"가 아니라 셋이다:
   ① **두 번 돌려 같은가** (시계·id·사전 순서가 새면 여기서 red다)
   ② **결과를 박아 두지 않았는가** — 판정이 출력된 측정값에서 다시 계산되는가
   ③ **데모가 증명하지 않는 것을 말하는가** — fake 위의 초록은 실물 왕복이 아니다

⛔ 그 셋은 전부 `demo.main()`을 직접 불러 태운다. **그것만으로는 진입점이 검증되지 않는다** —
   실제로 `make demo`는 `ModuleNotFoundError`로 죽어 있었고 위 셋은 초록이었다.
   그래서 `test_req_803_declared_entrypoint_runs`가 선언된 명령을 그대로 태운다
   (권한 경계도 그에 맞춰 `make demo`를 allow로 열었다 — 오프라인·결정론이다).
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

import warranty.demo as demo  # `from warranty import demo`는 재수출이 아니다(strict)
from warranty.domain.contract import ResourceRef
from warranty.domain.verification import Measurement, classify

ROOT = Path(__file__).resolve().parent.parent

#: design 11§2가 이름 붙인 다섯 단계. **순서까지가 서사다.**
DESIGN_STEPS = ("provision", "inject", "remediate", "manual", "report")


@pytest.fixture(scope="module")
def run() -> demo.DemoRun:
    return demo.run_demo()


def _step(run: demo.DemoRun, name: str) -> dict[str, object]:
    return dict(next(step for step in run.steps if step.name == name).detail)


# ── ① 두 번 돌려 같은가 ────────────────────────────────────────────────────


def test_req_803_the_narrative_is_identical_when_run_twice() -> None:
    """Verifies: REQ-803, REQ-802

    ★ 이 태스크의 한 줄 수용 기준이다. 살아 있는 시계나 uuid가 새어 들어오면
    두 번째 판이 첫 판과 달라지고, 그 순간 데모는 **재현이 아니라 실행**이 된다.
    """
    assert demo.run_demo().as_dict() == demo.run_demo().as_dict()


def test_req_803_make_demo_prints_the_same_bytes_twice(capsys: pytest.CaptureFixture[str]) -> None:
    """Verifies: REQ-803

    ⚠️ `run_demo()`만 물으면 **`make demo`가 실제로 부르는 경로**는 안 물어진다.
    렌더가 사전 순서에 기대거나 진입점이 다른 값을 찍어도 위 테스트는 초록이다.
    """
    assert demo.main() == 0
    first = capsys.readouterr().out
    assert demo.main() == 0
    second = capsys.readouterr().out

    assert first == second
    assert demo.TITLE in first


def test_req_803_the_render_sorts_details_so_dict_order_cannot_leak(run: demo.DemoRun) -> None:
    """Verifies: REQ-803, REQ-802

    ⚠️ 삽입 순서로 찍으면 **같은 원장이 프로세스마다 다른 문자열**을 낼 수 있다
    (해시 시드가 도는 자료구조가 하나만 끼어도 그렇다). 한 프로세스 안에서 두 번
    돌려 보는 것으로는 그 새는 구멍이 안 잡힌다 — 그래서 정렬을 직접 묻는다.
    """
    blocks = run.render().split("\n\n")
    assert len(blocks) >= len(run.steps)
    for step, block in zip(run.steps, blocks[1:], strict=False):
        assert step.name in block.splitlines()[0]
        printed = [line.strip().split(":", 1)[0] for line in block.splitlines()[1:]]
        assert printed == sorted(step.detail)


def test_req_803_the_five_steps_are_the_ones_the_design_names(run: demo.DemoRun) -> None:
    """Verifies: REQ-803

    단계가 조용히 빠지면 서사가 바뀐다 — 특히 ④(MANUAL)는 **아무 일도 안 일어나는**
    단계라 빠져도 출력이 멀쩡해 보인다.
    """
    assert tuple(step.name for step in run.steps) == DESIGN_STEPS


# ── ② 절정: 검증 실패 → 자동 롤백 ─────────────────────────────────────────


def test_req_803_the_action_executes_fails_verification_and_is_rolled_back(
    run: demo.DemoRun,
) -> None:
    """Verifies: REQ-803, REQ-502

    ★ 데모의 절정이자 이 프로젝트가 말할 수 있는 문장이다:
    **executed=true · improved=false · rolled_back=true.**
    셋 중 하나라도 합쳐지면 다른 도구와 같아진다.
    """
    acted = _step(run, "remediate")
    assert acted["gate"] == "AUTO"
    assert acted["executed"] is True
    assert acted["improved"] is False
    assert acted["verdict"] == "not_recovered"
    assert acted["rolled_back"] is True


def test_req_803_the_rollback_moves_traffic_back_and_reads_it_back(run: demo.DemoRun) -> None:
    """Verifies: REQ-803, REQ-303

    ⚠️ 조치가 **아무것도 안 옮기면** 롤백의 배분 재확인이 하중을 못 받는다 — 트래픽이
    처음부터 목적지에 있으니 안 옮겨도 100%다. 그래서 데모의 조치는 트래픽을 실제로
    나쁜 리비전으로 옮기고, 롤백이 실제로 되돌린다 (docs/PRINCIPLES.md #8).
    """
    acted = _step(run, "remediate")
    assert acted["traffic_shifts"] == [demo.SLOW_REVISION, demo.HEALTHY_REVISION]
    assert acted["verified_traffic"] == {demo.HEALTHY_REVISION: 100}
    assert acted["signal_restored"] is True


def test_req_803_the_verdict_is_computed_from_the_numbers_it_printed(run: demo.DemoRun) -> None:
    """Verifies: REQ-803, REQ-203

    ⛔ **결과 하드코딩은 실증이 아니다** (design 11§1 원칙 5). 검증 실패를 박아 두면
    데모는 늘 성공하고 아무것도 증명하지 않는다. 화면에 찍힌 기준선·재측정값을
    같은 계약 기준으로 다시 판정해 **출력된 판정과 맞는지** 묻는다.
    """
    acted = _step(run, "remediate")
    contract = demo.demo_contract(
        ResourceRef("cloud_run_service", demo.DEMO_SERVICE, demo.DEMO_REGION),
        datetime.fromisoformat(demo.DEMO_CLOCK_ISO),
    )
    recomputed = classify(
        Measurement(Decimal(str(acted["baseline_p95_ms"])), demo.SIGNAL_POINTS),
        Measurement(Decimal(str(acted["after_p95_ms"])), demo.SIGNAL_POINTS),
        contract.recovery_criterion,
    )
    assert str(recomputed) == acted["verdict"]


def test_req_803_the_rule_decides_so_the_demo_can_be_deterministic(run: demo.DemoRun) -> None:
    """Verifies: REQ-803, REQ-204

    ⚠️ 모델이 판정하는 순간 데모는 **재현 가능하지 않다.** 명확한 경우까지 모델에
    맡기면 REQ-802가 깨진다 — 그래서 이 서사는 모델을 한 번도 안 부른다.
    """
    assert _step(run, "remediate")["decided_by"] == "rule"
    assert _step(run, "manual")["model_calls_total"] == 0


# ── ③ 정책: 검증할 수 없으면 자동으로 안 한다 ─────────────────────────────


def test_req_803_an_uncontracted_resource_is_manual_and_the_executor_is_not_called(
    run: demo.DemoRun,
) -> None:
    """Verifies: REQ-803, REQ-104

    ⛔ 이 단계의 전부는 **아무 일도 안 일어났다**는 것이다. 상태만 보면
    *"판정은 MANUAL인데 실행은 됐다"*를 못 잡는다 — 실행기 호출 수를 함께 묻는다
    (G1과 같은 형태의 질문이고, 여기서 막는 것은 계약이 없다는 쪽이다).
    """
    blocked = _step(run, "manual")
    assert blocked["status"] == "manual_required"
    assert blocked["gate"] == "MANUAL"
    assert blocked["contract_id"] == "None"
    assert blocked["executor_calls_total"] == 1  # ③에서 한 번. 여기서는 안 늘었다.


# ── ④ 리포트 — 원장에서 유도된다 ──────────────────────────────────────────


def test_req_803_the_report_counts_what_the_loop_actually_wrote(run: demo.DemoRun) -> None:
    """Verifies: REQ-803, REQ-508

    ⚠️ 손으로 만든 숫자를 찍으면 데모가 **원장과 다른 이야기**를 한다. 여기 숫자는
    전부 이 실행이 남긴 원장에서 유도된 것이라야 한다.
    """
    report = _step(run, "report")
    assert report["executed"] == 1
    assert report["improved"] == 0
    assert report["improvement_rate"] == 0.0
    assert report["rolled_back"] == 1
    assert report["escalated"] == 0
    assert report["manual_required"] == 1
    assert report["model_decided"] == 0


def test_req_803_the_demo_does_not_fabricate_the_wasted_column(run: demo.DemoRun) -> None:
    """Verifies: REQ-803, REQ-503

    ★ 유혹이 정확히 여기다. `docs/OVERVIEW.md` §7의 헤드라인에는 `wasted $0.84`가
    있는데 이 데모는 **0을 낸다** — 루프가 쓰는 원장 행의 `assumed`가 아직 0이기
    때문이다(비용 경로 REQ-503 미착수). 숫자를 손으로 넣어 맞추면 그건 실증이 아니다.
    ⚠️ 그래서 0을 내되 **왜 0인지 함께 말한다.** 말 없는 0은 "낭비가 없었다"로 읽힌다.
    """
    report = _step(run, "report")
    assert Decimal(str(report["wasted_usd"])) == 0
    assert report["wasted_assumed_only"] == 1  # 회복 실패 조치는 있었다
    assert any("REQ-503" in caveat for caveat in run.caveats)


def test_req_803_the_demo_says_what_it_does_not_prove(run: demo.DemoRun) -> None:
    """Verifies: REQ-803, REQ-601

    ⛔ fake 위에서 도는 서사는 *"우리가 이 인터페이스를 이렇게 부른다"*를 말할 뿐이다
    (docs/PRINCIPLES.md #3). 그 문장이 출력에서 빠지면 다음 사람이 이 초록을
    **실물 왕복으로 읽는다** — 그건 대회 필수 요건을 만족한다는 주장이 된다.
    """
    assert run.caveats
    assert any("REQ-601" in caveat for caveat in run.caveats)
    assert "이 데모가 증명하지 않는 것" in run.render()


def test_req_803_declared_entrypoint_runs() -> None:
    """`make demo`가 **실제로 도는가** (REQ-803).

    ⛔ 이 저장소에서 실제로 깨져 있었다. `demo.main()`을 직접 부르는 위의 테스트들은
       전부 초록인데 `make demo`는 `ModuleNotFoundError`였다 — pytest는
       `pythonpath = ["src", "."]`를 주입하지만 `python -m`은 아무도 안 주입한다.
       ⇒ **진입점을 그 진입점으로 태우지 않으면 그 진입점은 검증되지 않는다.**

    ⚠️ `PYTHONPATH`를 여기서 직접 세우지 않는다. 세우면 Makefile이 그것을 빠뜨려도
       이 테스트는 초록이다 — 물어야 할 것은 **선언된 명령**이지 우리가 고친 환경이 아니다.
    """
    result = subprocess.run(
        ["make", "demo"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"`make demo` 실패:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
    )
    assert "report" in result.stdout, "다섯 단계의 마지막이 출력에 없다"
