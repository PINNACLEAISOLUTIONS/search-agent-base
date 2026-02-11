import json
import csv
import sys
import asyncio
import datetime
import random

# Fix Windows console encoding for emoji output (ignore mypy error for reconfigure)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from ai_lead_processor import AIAntiqueProcessor
from models import Lead

# --- CONFIGURATION ---
REGIONS = {
    "Miami": "https://miami.craigslist.org",
    "Tampa": "https://tampa.craigslist.org",
    "Orlando": "https://orlando.craigslist.org",
    "Jacksonville": "https://jacksonville.craigslist.org",
    "Tallahassee": "https://tallahassee.craigslist.org",
    "Gainesville": "https://gainesville.craigslist.org",
    "Sarasota": "https://sarasota.craigslist.org",
    "Fort Myers": "https://fortmyers.craigslist.org",
    "Daytona": "https://daytona.craigslist.org",
    "Lakeland": "https://lakeland.craigslist.org",
    "Ocala": "https://ocala.craigslist.org",
    "Treasure Coast": "https://treasure.craigslist.org",
    "Space Coast": "https://spacecoast.craigslist.org",
    "St. Augustine": "https://staugustine.craigslist.org",
    "Pensacola": "https://pensacola.craigslist.org",
    "Panama City": "https://panamacity.craigslist.org",
    "Keys": "https://keys.craigslist.org",
    "Naples": "https://naples.craigslist.org",
    "Heartland": "https://cfl.craigslist.org",
    "Lake City": "https://lakecity.craigslist.org",
}

SEARCH_KEYWORDS = [
    "victrola",
    "phonograph",
    "gramophone",
    "edison",
    "columbia grafonola",
    "victor talking machine",
    "antique record player",
    "crank player",
    "brunswick phonograph",
    "sonora phonograph",
    "pathé",
    "amberola",
    "cylinder player",
]

# Output files
LEADS_JSON = "leads.json"
LEADS_V2_JSON = "leads-v2.json"
LEADS_CSV = "leads.csv"
SEEN_POSTS_FILE = "seen_posts.json"

ai_processor = AIAntiqueProcessor()

# In-memory store during this run
all_leads: list[dict] = []


def load_seen_posts():
    """Load previously seen post IDs to avoid duplicates."""
    try:
        with open(SEEN_POSTS_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen_posts(seen):
    """Save seen post IDs."""
    with open(SEEN_POSTS_FILE, "w") as f:
        json.dump(list(seen), f)


def load_existing_leads():
    """Load existing leads so we accumulate over time."""
    try:
        with open(LEADS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return []


def save_all_leads(leads):
    """Save leads to all output files (JSON + CSV)."""
    # Sort by posted_date desc (newest first), then score desc
    # Handle missing posted_date by treating as 'oldest' or 'newest' depending on pref.
    # Here we treat empty dates as old.
    leads.sort(
        key=lambda x: (x.get("posted_date", "") or "0000", x.get("score", 0)),
        reverse=True,
    )

    # Save leads.json
    with open(LEADS_JSON, "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=4)

    # Save leads-v2.json (same data, consumed by index.html)
    with open(LEADS_V2_JSON, "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=4)

    # Save leads.csv
    if leads:
        fieldnames = [
            "id",
            "title",
            "link",
            "region",
            "keyword",
            "score",
            "classification",
            "timestamp",
            "is_new",
        ]
        with open(LEADS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(leads)

    print(f"💾 Saved {len(leads)} leads to {LEADS_JSON}, {LEADS_V2_JSON}, {LEADS_CSV}")


async def scrape_region(context, region_name, base_url, keyword, seen_posts):
    """Scrape a single region+keyword combo. Returns list of new leads found."""
    search_url = f"{base_url}/search/atq?query={keyword}"
    new_leads = []
    page = None

    try:
        page = await context.new_page()
        await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        # Human-like delay
        await asyncio.sleep(random.uniform(2, 5))

        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")

        # Craigslist 2026 uses .cl-search-result divs
        results = soup.select(".cl-search-result") or soup.select(".result-row")

        for res in results:
            try:
                # --- TITLE ---
                # Primary: span.label inside a.posting-title
                title_elem = res.select_one("a.posting-title span.label")
                # Fallback 1: the div's title attribute
                if not title_elem:
                    title = res.get("title", "").strip()
                else:
                    title = title_elem.get_text().strip()
                # Fallback 2: old .titlestring selector
                if not title:
                    old_title = res.select_one(".titlestring") or res.select_one(
                        ".result-title"
                    )
                    if old_title:
                        title = old_title.get_text().strip()
                if not title:
                    continue

                # --- LINK ---
                link_elem = (
                    res.select_one("a.posting-title")
                    or res.select_one("a.main")
                    or res.select_one("a")
                )
                if not link_elem:
                    continue
                link = link_elem.get("href", "")
                if not link:
                    continue
                if not link.startswith("http"):
                    link = base_url + link

                post_id = link.split("/")[-1].split(".")[0]

                # Skip if we've seen this before - REMOVED to allow updating timestamp
                # if post_id in seen_posts:
                #    continue

                # --- PRICE (optional) ---
                price_elem = res.select_one("span.priceinfo")
                price = price_elem.get_text().strip() if price_elem else ""

                # --- IMAGE (Enhancement) ---
                image_url = ""
                img_elem = res.select_one("img")
                if img_elem:
                    image_url = img_elem.get("src", "")

                # Fallback: data-ids attribute (common in CL gallery view)
                if not image_url and res.has_attr("data-ids"):
                    # data-ids="1:00K0K_keZxtGWi5Z4,1:00..."
                    data_ids = res["data-ids"].split(",")
                    if data_ids:
                        # format: 1:ID -> https://images.craigslist.org/{ID}_300x300.jpg
                        first_id = (
                            data_ids[0].split(":")[1]
                            if ":" in data_ids[0]
                            else data_ids[0]
                        )
                        image_url = (
                            f"https://images.craigslist.org/{first_id}_300x300.jpg"
                        )

                # --- DATE: Try multiple Craigslist selectors ---
                posted_date = ""
                date_selectors = [
                    "time.result-date",  # Classic CL layout
                    "time.posted-date",  # Alternative CL layout
                    ".meta time",  # Gallery/grid layout
                    "time[datetime]",  # Any time element with datetime
                    ".result-date",  # Span variant
                ]
                for sel in date_selectors:
                    date_elem = res.select_one(sel)
                    if date_elem:
                        posted_date = (
                            date_elem.get("datetime", "")
                            or date_elem.get("title", "")
                            or date_elem.get_text(strip=True)
                        )
                        if posted_date:
                            break

                # If no date from search result, fallback to scrape time
                if not posted_date:
                    posted_date = datetime.datetime.now().isoformat()

                # AI Analysis
                analysis = ai_processor.score_lead(title)

                # Create Lead using Pydantic Model (Validation)
                try:
                    lead_obj = Lead(
                        id=post_id,
                        title=title,
                        link=link,
                        region=region_name,
                        keyword=keyword,
                        score=analysis["score"],
                        classification=analysis["classification"],
                        price=price,
                        image=image_url,
                        timestamp=datetime.datetime.now().isoformat(),  # Scrape time
                        posted_date=posted_date,  # Original post time
                        is_new=True,
                    )

                    # Convert back to dict for storage compatibility
                    new_leads.append(lead_obj.model_dump())
                    seen_posts.add(post_id)

                    tag = "GOLD" if analysis["score"] >= 4.0 else "MATCH"
                    price_str = f" {price}" if price else ""
                    print(
                        f"    {tag} [{region_name}] {title}{price_str} (Date: {posted_date})"
                    )
                except Exception as val_err:
                    print(f"    Data Validation Failed: {val_err}")
                    continue

            except Exception:
                continue

    except Exception as e:
        print(f"  Failed {region_name}/{keyword}: {e}")
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass

    return new_leads


async def main():
    print(f"{'=' * 60}")
    print(
        f"  OLDTIMECRANK SCRAPER — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    print(f"  Regions: {len(REGIONS)} | Keywords: {len(SEARCH_KEYWORDS)}")
    print(f"{'=' * 60}")

    # Load state
    seen_posts = load_seen_posts()
    existing_leads = load_existing_leads()
    # Mark old leads as not new
    for lead in existing_leads:
        lead["is_new"] = False

    print(
        f"📂 Loaded {len(existing_leads)} existing leads, {len(seen_posts)} seen posts"
    )

    new_leads = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # Using a semaphore to limit concurrency (avoid getting blocked)
            sem = asyncio.Semaphore(3)

            async def controlled_scrape(r_name, r_url, kw):
                async with sem:
                    return await scrape_region(context, r_name, r_url, kw, seen_posts)

            # Shuffle regions to avoid predictable patterns
            items = list(REGIONS.items())
            random.shuffle(items)

            tasks = []
            for region_name, url in items:
                for keyword in SEARCH_KEYWORDS:
                    tasks.append(controlled_scrape(region_name, url, keyword))

            # Run all tasks, ignore failures so we keep what we got
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for batch in results:
                if isinstance(batch, list):
                    new_leads.extend(batch)
                else:
                    print(f"  Create Task Error: {batch}")

            try:
                await browser.close()
            except Exception:
                pass
    except Exception as e:
        print(f"CRITICAL PLAYWRIGHT ERROR: {e}")
        # Continue to save whatever we found

    # Merge new leads into existing
    # Improved Deduplication: Check ID OR (Title + Price + Keyword match) to filter cross-posts
    # We use a dictionary for O(1) lookups by ID
    existing_leads_map = {entry["id"]: entry for entry in existing_leads}

    unique_new_leads_count = 0
    updated_leads_count = 0

    for lead in new_leads:
        lead_id = lead["id"]

        if lead_id in existing_leads_map:
            # Update existing lead
            existing_rec = existing_leads_map[lead_id]
            existing_rec["timestamp"] = lead["timestamp"]  # Update seen time
            existing_rec["price"] = lead["price"]  # Update price if changed
            existing_rec["is_new"] = False  # It's not "new" new, just updated
            updated_leads_count += 1
        else:
            # New lead
            existing_leads.append(lead)
            existing_leads_map[lead_id] = (
                lead  # Update map to prevent dupes in same run
            )
            unique_new_leads_count += 1

    # Re-sort by timestamp descending to ensure newest checks are top
    existing_leads.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # Save everything
    save_all_leads(existing_leads)
    save_seen_posts(seen_posts)

    # Save Metadata for Frontend Status
    meta = {
        "last_updated": datetime.datetime.now().isoformat(),
        "total_leads": len(existing_leads),
        "new_leads_this_run": unique_new_leads_count,
    }
    with open("metadata.json", "w") as f:
        json.dump(meta, f)

    print(f"\n{'=' * 60}")
    print("Scrape Complete.")
    print(f"Found {len(new_leads)} raw leads.")
    print(f"Added {unique_new_leads_count} new leads.")
    print(f"Updated {updated_leads_count} existing leads (timestamp refresh).")
    print(f"Total leads in DB: {len(existing_leads)}")
    print("=====================")


if __name__ == "__main__":
    asyncio.run(main())
