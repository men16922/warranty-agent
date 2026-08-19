# fleet-ledger
#
# ⚠️ `check`는 오프라인이고 어떤 과금 API도 부르지 않는다 (REQ-701).
#    무인 루프(overnight harness)의 안전 조건이 그것이다.
#    라이브 검증은 `live-check`이고 게이트에 없다.

PY := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff
MYPY := .venv/bin/mypy

.PHONY: check test lint types trace venv live-check demo clean

## 게이트 — 오프라인 · 결정론적 (REQ-701, REQ-702)
check: lint types test trace

lint:
	$(RUFF) check src tests tools
	$(RUFF) format --check src tests tools

types:
	$(MYPY)

test:
	$(PYTEST)

## spec 추적성 매트릭스 (사람이 읽는 리포트). 집행은 tests/test_g6_traceability.py
trace:
	$(PY) tools/spec_trace.py --report

venv:
	uv venv --python 3.13 .venv
	uv pip install --python .venv/bin/python -e ".[dev]"

## ⛔ 게이트 아님 — 실물 클라우드. 과금한다.
live-check:
	$(PYTEST) -m live

demo:
	$(PY) -m fleet_ledger.demo

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
