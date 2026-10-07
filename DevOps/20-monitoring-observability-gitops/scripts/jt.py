#!/usr/bin/env python3
import json, sys, urllib.request
tid = sys.argv[1]
print(f"GET /api/v3/traces/{tid}")
d = json.load(urllib.request.urlopen(f"http://localhost:19686/api/v3/traces/{tid}"))["result"]
rows = []
for rs in d["resourceSpans"]:
    sv = [a["value"]["stringValue"] for a in rs["resource"]["attributes"] if a["key"] == "service.name"][0]
    for ss in rs["scopeSpans"]:
        for s in ss["spans"]:
            attrs = {a["key"]: list(a["value"].values())[0] for a in s.get("attributes", [])}
            rows.append((int(s["startTimeUnixNano"]), sv, s["name"], (int(s["endTimeUnixNano"]) - int(s["startTimeUnixNano"])) / 1e6,
                         s.get("status", {}).get("code", "STATUS_CODE_UNSET"), attrs.get("http.response.status_code") or attrs.get("http.status_code") or ""))
for r in sorted(rows):
    print(f"  {r[1]:<15} {r[2]:<14} {r[3]:8.1f} ms  status={r[4]} http={r[5]}")
