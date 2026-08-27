"""Cloud Monitoring 신호 요청 — 실물에서 확인한 모양을 오프라인에서 태운다 (T13-1).

Spec: specs/warranty/design/02-verification.md (REQ-201, REQ-202, REQ-205)

이 파일은 SDK를 임포트하거나 클라이언트를 만들지 않는다. 묻는 것은 우리가 **무엇을 보낼지**와
응답을 **어떻게 Measurement로 옮길지**다. 실제 API가 답하는지는 라이브 수용 기준이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from warranty.adapters.live_signal import (
    ALIGN_PERCENTILE_95,
    ALIGNMENT_SECONDS,
    FULL_VIEW,
    REDUCE_PERCENTILE_95,
    SignalSourceError,
    aggregation_args,
    list_time_series_request,
    parse_measurement,
    signal_filter,
)
from warranty.domain.contract import SignalSpec

SPEC = SignalSpec(
    metric_type="run.googleapis.com/request_latencies",
    resource_filter="demo-target",
    aggregation="P95",
    window_s=120,
)
ENDED_AT = datetime(2026, 8, 23, 12, 58, 30, 250_000, tzinfo=UTC)


@dataclass(frozen=True)
class _Timestamp:
    seconds: int
    nanos: int = 0


@dataclass(frozen=True)
class _Interval:
    end_time: _Timestamp | datetime


@dataclass(frozen=True)
class _Value:
    double_value: float


@dataclass(frozen=True)
class _Point:
    value: _Value
    interval: _Interval


@dataclass(frozen=True)
class _Series:
    points: tuple[_Point, ...]


def _point(value: float, seconds: int, nanos: int = 0) -> _Point:
    return _Point(_Value(value), _Interval(_Timestamp(seconds, nanos)))


def _datetime_point(value: float, ended_at: datetime) -> _Point:
    return _Point(_Value(value), _Interval(ended_at))


def test_filter_is_the_introspected_metric_and_cloud_run_service() -> None:
    assert signal_filter(SPEC) == (
        'metric.type="run.googleapis.com/request_latencies" '
        'AND resource.labels.service_name="demo-target"'
    )
    other = SignalSpec(SPEC.metric_type, "another-service", SPEC.aggregation, SPEC.window_s)
    assert 'resource.labels.service_name="another-service"' in signal_filter(other)


def test_p95_uses_the_introspected_aligner_and_reducer() -> None:
    assert aggregation_args(SPEC) == {
        "alignment_period": {"seconds": ALIGNMENT_SECONDS},
        "per_series_aligner": ALIGN_PERCENTILE_95,
        "cross_series_reducer": REDUCE_PERCENTILE_95,
    }
    assert ALIGNMENT_SECONDS == 60


def test_aggregation_is_inside_the_list_request_not_a_separate_kwarg() -> None:
    request = list_time_series_request("warranty-hack", SPEC, ENDED_AT)

    assert request["name"] == "projects/warranty-hack"
    assert request["filter"] == signal_filter(SPEC)
    assert request["view"] == FULL_VIEW == "FULL"
    assert request["aggregation"] == aggregation_args(SPEC)
    assert request["interval"] == {
        "start_time": {"seconds": int(ENDED_AT.timestamp()) - SPEC.window_s, "nanos": 250_000_000},
        "end_time": {"seconds": int(ENDED_AT.timestamp()), "nanos": 250_000_000},
    }


def test_response_parser_uses_the_newest_point_without_trusting_response_order() -> None:
    response = [
        _Series(
            (
                _point(674.2, 100),
                _datetime_point(988.6, datetime.fromtimestamp(300, tz=UTC)),
            )
        ),
        _Series((_point(800.0, 200),)),
    ]

    measured = parse_measurement(response)

    assert measured.value == Decimal("988.6")
    assert measured.points == 3
    assert not measured.is_empty


def test_an_empty_window_is_an_empty_measurement_not_a_zero() -> None:
    measured = parse_measurement([_Series(())])

    assert measured.value is None
    assert measured.points == 0
    assert measured.is_empty


@pytest.mark.parametrize(
    ("project", "spec", "ended_at"),
    [
        ("", SPEC, ENDED_AT),
        (
            "p",
            SignalSpec("run.googleapis.com/request_latencies", "svc", "MEAN", 120),
            ENDED_AT,
        ),
        ("p", SPEC, ENDED_AT.replace(tzinfo=None)),
    ],
)
def test_requests_refuse_an_unknown_or_ambiguous_shape(
    project: str, spec: SignalSpec, ended_at: datetime
) -> None:
    with pytest.raises(SignalSourceError):
        list_time_series_request(project, spec, ended_at)
