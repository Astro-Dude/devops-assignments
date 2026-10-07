#!/usr/bin/env python3
"""Run an instant PromQL query against the port-forwarded Prometheus and print the result as a table."""
import json, sys, urllib.parse, urllib.request
q = sys.argv[1]
url = "http://localhost:19090/api/v1/query?" + urllib.parse.urlencode({"query": q})
d = json.load(urllib.request.urlopen(url))["data"]
print(f"PromQL> {q}")
if not d["result"]:
    print("  (empty result)")
for r in d["result"]:
    m = r["metric"]; v = r["value"][1]
    lbl = ", ".join(f'{k}="{m[k]}"' for k in sorted(m) if k not in ("__name__",))
    name = m.get("__name__", "")
    print(f"  {name}{{{lbl}}}  =>  {v}")
print()
