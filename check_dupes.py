import json

with open("leads.json", "r") as f:
    try:
        leads = json.load(f)
    except Exception:
        print("leads.json is empty or invalid")
        exit()

seen = set()
duplicates = []
for lead in leads:
    # Key normalization
    sig = (
        lead.get("title", "").strip(),
        lead.get("price", "").strip(),
        lead.get("keyword", ""),
    )
    if sig in seen:
        duplicates.append(lead)
    else:
        seen.add(sig)

print(f"Total leads: {len(leads)}")
print(f"Unique signatures: {len(seen)}")
print(f"Duplicates found: {len(duplicates)}")

if duplicates:
    print("--- Example Duplicates ---")
    for d in duplicates[:3]:
        print(f"Title: {d.get('title')} | Price: {d.get('price')}")
