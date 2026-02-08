import os
import json
import time
import requests
import datetime
import pandas as pd
from bs4 import BeautifulSoup

# Regions defined from Fort Pierce to Georgia Border
REGIONS = {
    "Treasure Coast": "treasure",
    "Space Coast": "spacecoast",
    "Daytona Beach": "daytona",
    "St. Augustine": "staugustine",
    "Jacksonville": "jacksonville"
}

# Search Categories (Labor/Landscaping/Gigs)
CATEGORIES = ["lbs", "lbg"] # lbs = labor, lbg = labor gigs
SEARCH_QUERY = "landscaping"
SEEN_POSTS_FILE = "seen_posts.json"
LEADS_CSV = "leads.csv"
LEADS_JSON = "leads.json"

def load_seen_posts():
    if os.path.exists(SEEN_POSTS_FILE):
        with open(SEEN_POSTS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_seen_posts(seen_posts):
    with open(SEEN_POSTS_FILE, 'w') as f:
        json.dump(list(seen_posts), f)

def scrape_craigslist():
    print("="*40)
    print("CRAIGSLIST PHONOGRAPH SCRAPER")
    print(f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*40)
    
    seen_posts = load_seen_posts()
    all_leads = []
    new_count = 0

    for region_name, region_sub in REGIONS.items():
        print(f"\nChecking {region_name}...")
        for cat in CATEGORIES:
            # Using RSS feed for cleaner data parsing and IDs
            rss_url = f"https://{region_sub}.craigslist.org/search/{cat}?format=rss&query={SEARCH_QUERY}"
            try:
                response = requests.get(rss_url, timeout=15)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.content, 'xml')
                items = soup.find_all('item')

                for item in items:
                    title = item.find('title').text
                    link = item.find('link').text
                    date = item.find('dc:date').text if item.find('dc:date') else ""
                    post_id = link.split('/')[-1].split('.')[0] # Extract ID from URL

                    lead = {
                        "id": post_id,
                        "title": title,
                        "link": link,
                        "date": date,
                        "region": region_name,
                        "timestamp": datetime.datetime.now().isoformat()
                    }

                    if post_id not in seen_posts:
                        print(f"[NEW] {title} ({region_name})")
                        print(f"      {link}")
                        seen_posts.add(post_id)
                        lead["is_new"] = True
                        new_count += 1
                    else:
                        lead["is_new"] = False
                    
                    all_leads.append(lead)

            except Exception as e:
                print(f"Error checking {region_name} ({cat}): {e}")

    # Update state
    save_seen_posts(seen_posts)
    
    # Save results to CSV/JSON for UI consumption
    if all_leads:
        df = pd.DataFrame(all_leads)
        # Append to master leads list or overwrite with newest
        if os.path.exists(LEADS_CSV):
            existing_df = pd.read_csv(LEADS_CSV)
            df = pd.concat([df, existing_df]).drop_duplicates(subset='id').sort_values(by='date', ascending=False)
        
        df.to_csv(LEADS_CSV, index=False)
        df.to_json(LEADS_JSON, orient='records', indent=2)

    print("\n" + "="*40)
    print(f"Scan Complete. Found {new_count} new leads.")
    print("="*40)

if __name__ == "__main__":
    scrape_craigslist()
