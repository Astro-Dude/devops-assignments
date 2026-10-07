#!/usr/bin/env python3
import json, sys, urllib.request
d = json.load(urllib.request.urlopen("http://localhost:19090/api/v1/rules?type=alert"))["data"]["groups"]
for g in d:
    if g["name"] != "shop.rules": continue
    for r in g["rules"]:
        print(f'{r["name"]:<20} state={r["state"]:<9} health={r["health"]}')
        for a in r["alerts"]:
            print(f'    -> {a["state"].upper():<8} since {a["activeAt"][:19]}Z value={float(a["value"]):.3f} labels={ {k:v for k,v in a["labels"].items() if k in ("pod","severity")} }')
print()
