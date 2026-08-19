"""설정 계층 — 조용한 기본값을 만들지 않는다.

Spec: specs/fleet-ledger/design/06-interfaces.md §6
"""

from __future__ import annotations

import pytest

from fleet_ledger.config import Adapters, ConfigError, Settings, load_settings

BASE = {
    "FL_PROJECT_ID": "fleet-ledger-hack",
    "FL_REGION": "us-central1",
    "FL_MODEL": "gemini-3.5-flash",
    "FL_ADAPTERS": "live",
}


def _load(**over: str) -> Settings:
    return load_settings({**BASE, **over})


def test_missing_project_is_refused_not_defaulted() -> None:
    """Verifies: REQ-701

    빠진 설정에 기본값을 주면 **설정 안 된 채로 배포가 성공**하고 그 실패는 조용하다.
    """
    with pytest.raises(ConfigError, match="FL_PROJECT_ID"):
        load_settings({k: v for k, v in BASE.items() if k != "FL_PROJECT_ID"})


def test_adk_project_mismatch_is_refused() -> None:
    """Verifies: REQ-701

    ADK가 직접 읽는 `GOOGLE_CLOUD_PROJECT`가 우리 설정과 어긋나면 **모델 호출이
    우리가 믿는 프로젝트가 아닌 곳에 청구된다.** 그 어긋남은 조용하므로 여기서 막는다.
    """
    with pytest.raises(ConfigError, match="다른 프로젝트에 청구된다"):
        _load(GOOGLE_CLOUD_PROJECT="someone-elses-project")


def test_adapters_must_be_live_or_fake() -> None:
    """Verifies: REQ-701"""
    with pytest.raises(ConfigError, match="live/fake"):
        _load(FL_ADAPTERS="mock")


def test_adapters_default_is_live_not_fake() -> None:
    """Verifies: REQ-701

    ⚠️ 기본을 fake로 두면 **배포가 조용히 가짜로 돌 수 있다.**
    테스트가 명시적으로 fake를 주입하는 것이지, 기본값이 하는 일이 아니다.
    """
    settings = load_settings({k: v for k, v in BASE.items() if k != "FL_ADAPTERS"})
    assert settings.adapters is Adapters.LIVE


def test_billing_table_absent_means_reconciliation_is_not_possible() -> None:
    """Verifies: REQ-404

    빈 값을 조용히 넘기지 않고 **물을 수 있게** 한다 — "아직 안 켰다"와
    "켰는데 안 온다"는 다른 상태다.
    """
    assert _load().can_reconcile is False
    assert _load(FL_BILLING_TABLE="p.d.gcp_billing_export_v1_XXXX").can_reconcile is True


def test_billing_table_shape_is_validated() -> None:
    """Verifies: REQ-401

    형식이 틀리면 화해 질의가 런타임에 실패한다 — 그때는 이미 BQ 비용을 썼다.
    """
    with pytest.raises(ConfigError, match="형식이"):
        _load(FL_BILLING_TABLE="just-a-dataset")


def test_reconcile_deadline_must_be_a_positive_integer() -> None:
    """Verifies: REQ-404"""
    with pytest.raises(ConfigError, match="양의 정수"):
        _load(FL_RECONCILE_DEADLINE_DAYS="0")
