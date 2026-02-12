import json
from datetime import datetime

file_path = "leads-v2.json"

try:
    with open(file_path, "r") as f:
        data = json.load(f)

    fixed_count = 0
    for lead in data:
        pd = lead.get("posted_date", "")
        if pd and "T" in pd:
            try:
                # Handle ISO format like 2026-02-11T08:23:18.007147
                dt = datetime.fromisoformat(pd)
                lead["posted_date"] = dt.strftime("%Y-%m-%d")
                fixed_count += 1
            except ValueError:
                pass

        # Aggressive check: if not YYYY-MM-DD (length 10) starting with 20, fix it
        # This catches weird strings or old formats
        if len(lead.get("posted_date", "")) != 10 or not lead["posted_date"].startswith(
            "20"
        ):
            # Inspect title to guess? No, just set to old to bury it, or current if it looks new?
            # Better to bury it.
            lead["posted_date"] = "1970-01-01"
            fixed_count += 1

    # Sort primarily by date (newest first), secondarily by score
    data.sort(
        key=lambda x: (x.get("posted_date", "1970-01-01"), x.get("score", 0)),
        reverse=True,
    )

    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

    print(
        f"Successfully normalized dates for {fixed_count} leads and re-sorted {len(data)} total records."
    )

except Exception as e:
    print(f"Error fixing dates: {e}")
