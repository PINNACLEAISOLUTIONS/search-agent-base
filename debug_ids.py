import json

with open("leads-v2.json", "r") as f:
    leads = json.load(f)
    ids = [str(l.get("id")) for l in leads]
    test_ids = ["7911212752", "7914644328", "7914291739"]
    for tid in test_ids:
        found = tid in ids
        print(f"ID {tid} found: {found}")
        if found:
            lead = next(l for l in leads if str(l.get("id")) == tid)
            print(f"  Title: {lead.get('title')}")
            print(f"  Posted Date: {lead.get('posted_date')}")
            print(f"  Scraped At: {lead.get('scraped_at')}")
