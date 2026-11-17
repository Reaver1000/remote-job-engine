import os
import sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app

d = app.diff_counts()
rows = []
for src, v in d.items():
    for j in v["jobs"]:
        j["src"] = src
        rows.append(j)
rows.sort(key=lambda j: -j["score"])
print("APPLY QUEUE - top scored across all sources:")
print()
for j in rows[:20]:
    band = j["band"]
    print(f"[{band:>7} {j['score']:>3}] {j['title'][:70]}")
    print(f"           {j['loc'][:50]} | {j['pay'][:15]} | {j['src']}")
    print(f"           {j['url'][:90]}")
    print()
