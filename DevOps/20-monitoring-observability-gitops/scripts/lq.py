#!/usr/bin/env python3
import json, sys, time, urllib.parse, urllib.request
q = sys.argv[1]; limit = sys.argv[2] if len(sys.argv) > 2 else "8"
now = time.time_ns()
p = {"query": q, "limit": limit, "start": now - 15 * 60 * 10**9, "end": now, "direction": "backward"}
d = json.load(urllib.request.urlopen("http://localhost:19100/loki/api/v1/query_range?" + urllib.parse.urlencode(p)))["data"]
print(f"LogQL> {q}")
if d["resultType"] == "streams":
    rows = []
    for s in d["result"]:
        for ts, line in s["values"]:
            rows.append((ts, s["stream"].get("pod", ""), line))
    for ts, pod, line in sorted(rows, reverse=True)[: int(limit)]:
        print(f"  {time.strftime('%H:%M:%S', time.localtime(int(ts)/1e9))} {pod}  {line.strip()[:220]}")
else:
    for s in d["result"]:
        print(f"  {s['metric']}  last={s['values'][-1][1]}")
print()
