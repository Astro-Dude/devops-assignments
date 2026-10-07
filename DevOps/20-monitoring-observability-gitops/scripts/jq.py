#!/usr/bin/env python3
"""List recent traces from Jaeger's api/v3 (OTLP JSON) as span trees."""
import json, sys, time, urllib.parse, urllib.request
svc, op, n = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2
now = time.time()
fmt = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
p = {"query.service_name": svc, "query.operation_name": op, "query.start_time_min": fmt(now - 600),
     "query.start_time_max": fmt(now + 60), "query.search_depth": n}
url = "http://localhost:19686/api/v3/traces?" + urllib.parse.urlencode(p)
print(f"GET /api/v3/traces?query.service_name={svc}&query.operation_name={op}&query.search_depth={n}")
d = json.load(urllib.request.urlopen(url))["result"]
traces = {}
for rs in d["resourceSpans"]:
    svcname = [a["value"]["stringValue"] for a in rs["resource"]["attributes"] if a["key"] == "service.name"][0]
    for ss in rs["scopeSpans"]:
        for s in ss["spans"]:
            traces.setdefault(s["traceId"], []).append((svcname, s))
for tid, spans in list(traces.items())[:n]:
    byid = {s["spanId"]: (sv, s) for sv, s in spans}
    kids = {}
    for sv, s in spans: kids.setdefault(s.get("parentSpanId", ""), []).append((sv, s))
    print(f"trace {tid}  ({len(spans)} spans)")
    def walk(pid, depth):
        for sv, s in sorted(kids.get(pid, []), key=lambda x: int(x[1]["startTimeUnixNano"])):
            dur = (int(s["endTimeUnixNano"]) - int(s["startTimeUnixNano"])) / 1e6
            attrs = {a["key"]: list(a["value"].values())[0] for a in s.get("attributes", [])}
            extra = attrs.get("http.response.status_code") or attrs.get("http.status_code") or attrs.get("db.statement") or ""
            print(f"  {'  '*depth}{sv:<15} {s['name']:<28} {dur:8.1f} ms  {extra}")
            walk(s["spanId"], depth + 1)
    roots = [s for _, s in spans if s.get("parentSpanId", "") not in byid]
    for r in {s.get("parentSpanId", "") for s in roots}: walk(r, 0)
    print()
