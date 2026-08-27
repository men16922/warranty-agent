"""Cloud Monitoring 신호 어댑터 — 조치 전후에 **같은 요청 모양**을 쓴다 (REQ-201·202).

Spec: specs/warranty/design/02-verification.md (REQ-201, REQ-202, REQ-205)

실물 요청의 권위는 ``docs/evidence/live-signal-2026-08-23.log``다. 특히 Cloud Run 지연은
60초 p95 aligner와 p95 reducer를 함께 쓰며, ``aggregation``은 별도 kwarg가 아니라
``ListTimeSeriesRequest`` 안에 들어간다. 이 모듈은 그 모양을 순수 함수로 먼저 만들고,
실제 SDK는 첫 호출에서만 지연 임포트한다(REQ-801).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from warranty.adapters import live_guard
from warranty.domain.contract import SignalSpec
from warranty.domain.verification import Measurement

PROJECT_PATH = "projects/{project}"
ALIGNMENT_SECONDS = 60
FULL_VIEW = "FULL"

P95 = "P95"
ALIGN_PERCENTILE_95 = "ALIGN_PERCENTILE_95"
REDUCE_PERCENTILE_95 = "REDUCE_PERCENTILE_95"


class SignalSourceError(RuntimeError):
    """Cloud Monitoring 요청이나 응답을 신뢰할 수 없다."""


def _quoted(value: str) -> str:
    """Monitoring 필터의 문자열 리터럴 안에서 백슬래시와 따옴표를 보존한다."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def signal_filter(spec: SignalSpec) -> str:
    """Cloud Run 서비스 하나의 시계열만 고르는 필터. **순수하다.**"""
    if spec.kind != "cloud_monitoring":
        raise SignalSourceError(f"Cloud Monitoring 신호가 아니다: {spec.kind!r}")
    if not spec.metric_type:
        raise SignalSourceError("metric_type이 비었다 — 무엇을 읽을지 모른다")
    return (
        f'metric.type="{_quoted(spec.metric_type)}" AND '
        f'resource.labels.service_name="{_quoted(spec.resource_filter)}"'
    )


def aggregation_args(spec: SignalSpec) -> dict[str, Any]:
    """실물에서 확인한 p95 aligner/reducer 요청 조각. **순수하다.**"""
    if spec.aggregation != P95:
        raise SignalSourceError(f"지원하지 않는 집계다: {spec.aggregation!r}")
    return {
        "alignment_period": {"seconds": ALIGNMENT_SECONDS},
        "per_series_aligner": ALIGN_PERCENTILE_95,
        "cross_series_reducer": REDUCE_PERCENTILE_95,
    }


def list_time_series_request(project: str, spec: SignalSpec, ended_at: datetime) -> dict[str, Any]:
    """``ListTimeSeriesRequest``에 넘길 전체 요청. **순수하다.**

    ``aggregation``이 이 사전 안에 있다는 사실이 중요하다. 실물 첫 시도처럼 별도 kwarg로
    보내면 Python SDK가 요청을 보내기도 전에 ``TypeError``를 낸다.
    """
    if not project:
        raise SignalSourceError("프로젝트가 비었다 — Monitoring 경로를 만들 수 없다")
    if ended_at.tzinfo is None or ended_at.utcoffset() is None:
        raise SignalSourceError("측정 종료 시각에 timezone이 없다")

    started_at = ended_at - timedelta(seconds=spec.window_s)

    def timestamp(value: datetime) -> dict[str, int]:
        seconds = int(value.timestamp())
        nanos = value.microsecond * 1_000
        return {"seconds": seconds, "nanos": nanos}

    return {
        "name": PROJECT_PATH.format(project=project),
        "filter": signal_filter(spec),
        "interval": {
            "start_time": timestamp(started_at),
            "end_time": timestamp(ended_at),
        },
        "view": FULL_VIEW,
        "aggregation": aggregation_args(spec),
    }


def parse_measurement(series: Iterable[Any]) -> Measurement:
    """시계열 응답을 최신 p95 한 값과 관측 포인트 수로 옮긴다. **순수하다.**

    API가 포인트를 어떤 순서로 돌려주는지에 기대지 않고 ``interval.end_time``이 가장 늦은
    값을 고른다. 포인트가 하나도 없으면 ``Measurement(None, 0)``이며, 이는 판정에서
    ``unverifiable``로 내려간다(REQ-205).
    """
    latest: tuple[int, int, Decimal] | None = None
    points = 0

    def timestamp_key(value: Any) -> tuple[int, int]:
        # proto-plus는 Timestamp를 ``DatetimeWithNanoseconds``(datetime 하위 타입)로 노출한다.
        if isinstance(value, datetime):
            nanos = int(getattr(value, "nanosecond", value.microsecond * 1_000))
            return int(value.timestamp()), nanos
        seconds = getattr(value, "seconds", None)
        if seconds is None:
            raise SignalSourceError("Monitoring 포인트의 end_time을 읽을 수 없다")
        return int(seconds), int(getattr(value, "nanos", 0))

    for time_series in series:
        for point in getattr(time_series, "points", ()):
            points += 1
            interval = getattr(point, "interval", None)
            end_time = getattr(interval, "end_time", None)
            value = getattr(getattr(point, "value", None), "double_value", None)
            if end_time is None or value is None:
                raise SignalSourceError("Monitoring 포인트에 end_time 또는 double_value가 없다")
            seconds, nanos = timestamp_key(end_time)
            candidate = (seconds, nanos, Decimal(str(value)))
            if latest is None or candidate[:2] > latest[:2]:
                latest = candidate

    if latest is None:
        return Measurement(value=None, points=0)
    return Measurement(value=latest[2], points=points)


class LiveSignalSource:
    """실물 Cloud Monitoring. 클라이언트는 첫 읽기에서만 만든다 (G5 · REQ-801)."""

    def __init__(self, project: str, now: Callable[[], datetime] | None = None) -> None:
        self._project = project
        self._now = now or (lambda: datetime.now(UTC))
        self._client: Any | None = None
        self._prefetched: dict[SignalSpec, Measurement] = {}

    def _metrics(self) -> tuple[Any, Any]:
        live_guard.note("live_signal.LiveSignalSource._metrics")
        # 지연 임포트 — 게이트에는 이 패키지가 없다(REQ-801).
        from google.cloud import monitoring_v3  # type: ignore[import-not-found]

        if self._client is None:
            self._client = monitoring_v3.MetricServiceClient()
        return self._client, monitoring_v3

    def _query(self, spec: SignalSpec) -> Measurement:
        live_guard.note("live_signal.LiveSignalSource._query")
        client, _monitoring_v3 = self._metrics()
        response = client.list_time_series(
            request=list_time_series_request(self._project, spec, self._now())
        )
        return parse_measurement(response)

    def read(self, spec: SignalSpec) -> Measurement:
        live_guard.note("live_signal.LiveSignalSource.read")
        prefetched = self._prefetched.pop(spec, None)
        return prefetched if prefetched is not None else self._query(spec)

    def readable(self, spec: SignalSpec) -> bool:
        live_guard.note("live_signal.LiveSignalSource.readable")
        try:
            measured = self._query(spec)
        except Exception:
            # 검증 가능성은 fail-close다. 읽기 실패를 AUTO로 올리지 않는다.
            self._prefetched.pop(spec, None)
            return False
        if measured.is_empty:
            self._prefetched.pop(spec, None)
            return False
        self._prefetched[spec] = measured
        return True
