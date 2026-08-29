#!/bin/bash
# demo-target p95 — ⚠️ 조치 전에 **120초 창 안에 점이 있는지** 확인하는 자리.
TOK=$(gcloud auth print-access-token)
END=$(date -u +%Y-%m-%dT%H:%M:%SZ); START=$(date -u -v-10M +%Y-%m-%dT%H:%M:%SZ)
curl -s -G "https://monitoring.googleapis.com/v3/projects/warranty-hack/timeSeries" \
  -H "Authorization: Bearer $TOK" \
  --data-urlencode 'filter=metric.type="run.googleapis.com/request_latencies" AND resource.labels.service_name="demo-target"' \
  --data-urlencode "interval.startTime=$START" --data-urlencode "interval.endTime=$END" \
  --data-urlencode 'aggregation.alignmentPeriod=60s' \
  --data-urlencode 'aggregation.perSeriesAligner=ALIGN_PERCENTILE_95' \
 | python3 -c "
import json,sys,datetime
d=json.load(sys.stdin)
now=datetime.datetime.now(datetime.timezone.utc)
pts=[]
for s in d.get('timeSeries',[]):
    for p in s.get('points',[]):
        t=datetime.datetime.fromisoformat(p['interval']['endTime'].replace('Z','+00:00'))
        pts.append((t, float(p['value']['doubleValue'])))
pts.sort(reverse=True)
if not pts: print('점 없음'); raise SystemExit
for t,v in pts[:5]:
    age=(now-t).total_seconds()
    mark='✅ 120초 창 안' if age<=120 else ''
    print(f'{t:%H:%M:%S}Z  {v:7.1f} ms   {age:5.0f}s 전  {mark}')
"
