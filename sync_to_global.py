import json
import os
import csv
from datetime import datetime

global_json_path = r"C:\Users\futur\gemini_workspace\leads.json"
global_csv_path = r"C:\Users\futur\gemini_workspace\leads.csv"
local_json_path = "leads-v2.json"

def sync():
    if not os.path.exists(local_json_path):
        print(f"Local {local_json_path} does not exist yet. Scraper might still be running.")
        return

    print("Loading local phonograph leads...")
    with open(local_json_path, "r", encoding="utf-8") as f:
        local_leads = json.load(f)

    print(f"Loaded {len(local_leads)} local leads.")

    # Load existing global leads
    global_leads = []
    if os.path.exists(global_json_path):
        print("Loading global leads...")
        try:
            with open(global_json_path, "r", encoding="utf-8") as f:
                global_leads = json.load(f)
            print(f"Loaded {len(global_leads)} existing global leads.")
        except Exception as e:
            print(f"Error loading global leads: {e}. Starting fresh.")
    else:
        print("Global leads.json does not exist. Creating new.")

    # Track seen URLs/IDs
    # We will deduplicate by Source_URL or post_url
    seen_urls = set()
    for l in global_leads:
        url = l.get("Source_URL") or l.get("post_url")
        if url:
            # normalize URL
            seen_urls.add(str(url).strip().lower())

    newly_added = 0
    # Map phonograph leads to global schema and append if new
    for l in local_leads:
        link = l.get("link", "").strip()
        if not link:
            continue
        
        normalized_link = link.lower()
        if normalized_link in seen_urls:
            continue
        
        # Map fields to match the combined schema
        scraped_time = l.get("scraped_at") or datetime.now().isoformat()
        mapped_lead = {
            "Job_Title": l.get("title"),
            "Source_URL": link,
            "Score": float(l.get("score", 0)),
            "Source_Platform": "Craigslist",
            "Closing_Date": "",
            "Agency": l.get("region", "Florida"),
            "Screened_At": scraped_time,
            "platform": "craigslist",
            "username": "",
            "profile_url": "",
            "post_url": link,
            "caption_snippet": l.get("title"),
            "detected_intent": l.get("classification"),
            "intent_keywords_found": l.get("classification"),
            "intent_score": float(l.get("score", 0)),
            "bio": l.get("analysis", ""),
            "website_link": link,
            "source_hashtag": "phonograph",
            "scraped_at": scraped_time
        }
        global_leads.append(mapped_lead)
        seen_urls.add(normalized_link)
        newly_added += 1

    print(f"Merged {newly_added} new phonograph leads into global list.")

    # Save to global leads.json
    with open(global_json_path, "w", encoding="utf-8") as f:
        json.dump(global_leads, f, indent=2)
    print(f"Saved global JSON to {global_json_path}")

    # Save to global leads.csv
    # Headers must match exactly
    headers = [
        "Job_Title", "Source_URL", "Score", "Source_Platform", "Closing_Date", 
        "Agency", "Screened_At", "platform", "username", "profile_url", 
        "post_url", "caption_snippet", "detected_intent", "intent_keywords_found", 
        "intent_score", "bio", "website_link", "source_hashtag", "scraped_at"
    ]
    
    with open(global_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(global_leads)
    print(f"Saved global CSV to {global_csv_path}")

if __name__ == "__main__":
    sync()
