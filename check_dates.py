import json

with open("leads-v2.json", "r") as f:
    leads = json.load(f)
    for l in leads[:10]:
        print(f"{l.get('posted_date')} | {l.get('title')}")
