import os
import json
import datetime
import asyncio
from playwright.async_api import async_playwright  # type: ignore
from playwright_stealth import stealth_async  # type: ignore
from bs4 import BeautifulSoup
from ai_lead_processor import AIAntiqueProcessor
import pandas as pd  # type: ignore

# ALL Florida Craigslist Subdomains
REGIONS = {
    "Miami": "https://miami.craigslist.org",
    "Ft Lauderdale": "https://fortlauderdale.craigslist.org",
    "West Palm": "https://westpalm.craigslist.org",
    "Treasure Coast": "https://treasure.craigslist.org",
    "Space Coast": "https://spacecoast.craigslist.org",
    "Daytona Beach": "https://daytona.craigslist.org",
    "St Augustine": "https://staugustine.craigslist.org",
    "Jacksonville": "https://jacksonville.craigslist.org",
    "Orlando": "https://orlando.craigslist.org",
    "Ocala": "https://ocala.craigslist.org",
    "Gainesville": "https://gainesville.craigslist.org",
    "Tallahassee": "https://tallahassee.craigslist.org",
    "Tampa Bay": "https://tampa.craigslist.org",
    "Lake City": "https://lakecity.craigslist.org",
    "Lakeland": "https://lakeland.craigslist.org",
    "Sarasota": "https://sarasota.craigslist.org",
    "Ft Myers": "https://fortmyers.craigslist.org",
    "FL Keys": "https://keys.craigslist.org",
    "Panama City": "https://panamacity.craigslist.org",
    "Pensacola": "https://pensacola.craigslist.org",
}

# Targeted Antique Keywords
SEARCH_KEYWORDS = [
    "phonograph",
    "edison",
    "columbia",
    "victor",
    "victrola",
    "gramophone",
    "graphophone",
    "antique",
]

# SPIFY / APIFY Discovery Hooks:
# These keywords are shared with the external discovery engine

SEEN_POSTS_FILE = "seen_posts.json"
LEADS_CSV = "leads.csv"
LEADS_JSON = "leads.json"


def load_seen_posts():
    if os.path.exists(SEEN_POSTS_FILE):
        try:
            with open(SEEN_POSTS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen_posts(seen_posts):
    with open(SEEN_POSTS_FILE, "w") as f:
        json.dump(list(seen_posts), f)


async def scrape_region(
    browser, region_name, base_url, keyword, seen_posts, ai_processor
):
    leads = []
    # Create a fresh context for each search to avoid cross-pollution and crashes
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    await stealth_async(page)

    # Category atq = Antiques
    search_url = f"{base_url}/search/atq?query={keyword}"
    print(f"  Searching {region_name} for '{keyword}'...")

    try:
        # Increased timeout to 60s for stability
        await page.goto(search_url, wait_until="mask", timeout=60000)
        # Random sleep to mimic human behavior
        await asyncio.sleep(2)
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")

        # Craigslist layout selectors
        results = soup.select(".cl-search-result") or soup.select(".result-row")

        for res in results:
            try:
                title_elem = res.select_one(".titlestring") or res.select_one(
                    ".result-title"
                )
                if not title_elem:
                    continue

                title = title_elem.get_text().strip()
                link = title_elem["href"]
                if not link.startswith("http"):
                    link = base_url + link

                post_id = link.split("/")[-1].split(".")[0]

                if post_id in seen_posts:
                    continue

                # AI Antique Scoring
                analysis = ai_processor.score_lead(title)

                lead = {
                    "id": post_id,
                    "title": title,
                    "link": link,
                    "region": region_name,
                    "keyword": keyword,
                    "score": analysis["score"],
                    "classification": analysis["classification"],
                    "timestamp": datetime.datetime.now().isoformat(),
                    "is_new": True,
                }

                leads.append(lead)
                seen_posts.add(post_id)

                if analysis["score"] >= 4.0:
                    print(f"    [GOLD FIND] {title} (Score: {analysis['score']})")
                elif analysis["score"] >= 2.0:
                    print(f"    [NEW] {title}")

            except Exception as e:
                # Log but verify scraper continues
                print(f"Error parsing result in {region_name}: {e}")
                continue

    except Exception as e:
        print(f"⚠️ Search failed for {region_name} - {keyword}: {e}")
    finally:
        try:
            await context.close()
        except:
            pass
    return leads


async def main():
    print("=" * 40)
    print("OLDTIMECRANK - ANTIQUE PHONOGRAPH ENGINE")
    print(f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 40)

    seen_posts = load_seen_posts()
    ai_processor = AIAntiqueProcessor()
    all_leads = []

    # Limit concurrency to 3 cities at once to avoid crashing Chromium
    sem = asyncio.Semaphore(3)

    async def sem_scrape(
        browser, region_name, base_url, keyword, seen_posts, ai_processor
    ):
        async with sem:
            return await scrape_region(
                browser, region_name, base_url, keyword, seen_posts, ai_processor
            )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        tasks = []
        for region_name, base_url in REGIONS.items():
            for keyword in SEARCH_KEYWORDS:
                tasks.append(
                    sem_scrape(
                        browser,
                        region_name,
                        base_url,
                        keyword,
                        seen_posts,
                        ai_processor,
                    )
                )

        print(
            f"🚀 Launching Stabilized Parallel Search (Concurrency: 3) for {len(tasks)} queries..."
        )
        result_lists = await asyncio.gather(*tasks)

        for r_list in result_lists:
            all_leads.extend(r_list)

        await browser.close()

    # Update state
    save_seen_posts(seen_posts)

    # Save results
    if all_leads:
        new_df = pd.DataFrame(all_leads)
        if os.path.exists(LEADS_CSV):
            try:
                existing_df = pd.read_csv(LEADS_CSV)
                combined_df = pd.concat([new_df, existing_df]).drop_duplicates(
                    subset="id"
                )
            except Exception:
                combined_df = new_df
        else:
            combined_df = new_df

        combined_df.sort_values(by="score", ascending=False, inplace=True)
        combined_df.to_csv(LEADS_CSV, index=False)
        combined_df.to_json(LEADS_JSON, orient="records", indent=2)

    print("\n" + "=" * 40)
    print(f"Search Complete. Found {len(all_leads)} new potential machines.")
    print("=" * 40)


if __name__ == "__main__":
    asyncio.run(main())
