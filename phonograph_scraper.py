import os
import asyncio
import datetime
import random
import psycopg2
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from ai_lead_processor import AIAntiqueProcessor

# DATABASE CONNECTION
# In production, use os.getenv("DATABASE_URL")
# Using the connection string you provided
DB_URL = "postgresql://postgres:Nazi1035!!!@db.lvevatkufgiwzmcyyuon.supabase.co:5432/postgres"

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

ai_processor = AIAntiqueProcessor()


def save_lead_to_db(lead):
    """Inserts a single lead into Supabase immediately."""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        # Upsert: Insert or Update if ID exists
        cur.execute(
            """
            INSERT INTO leads (id, title, link, region, keyword, score, classification, timestamp, is_new)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), TRUE)
            ON CONFLICT (id) DO UPDATE SET
                score = EXCLUDED.score,
                is_new = FALSE
        """,
            (
                lead["id"],
                lead["title"],
                lead["link"],
                lead["region"],
                lead["keyword"],
                lead["score"],
                lead["classification"],
            ),
        )

        conn.commit()
        cur.close()
        conn.close()
        print(f"    💾 Saved to DB: {lead['title']}")
        return True
    except Exception as e:
        print(f"    ❌ DB Error: {e}")
        return False


async def scrape_region(context, region_name, base_url, keyword):
    print(f"  Searching {region_name} for '{keyword}'...")
    search_url = f"{base_url}/search/atq?query={keyword}"

    leads_found = 0
    page = None

    try:
        page = await context.new_page()
        await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        # Human-like delay
        await asyncio.sleep(random.uniform(2, 5))

        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
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

                # AI Analysis
                analysis = ai_processor.score_lead(title)

                lead = {
                    "id": post_id,
                    "title": title,
                    "link": link,
                    "region": region_name,
                    "keyword": keyword,
                    "score": analysis["score"],
                    "classification": analysis["classification"],
                }

                # Save immediately to DB
                save_lead_to_db(lead)
                leads_found += 1

                if analysis["score"] >= 4.0:
                    print(f"    [GOLD FIND] {title}")

            except Exception:
                continue

    except Exception as e:
        print(f"⚠️ Failed {region_name}: {e}")
    finally:
        if page:
            try:
                await page.close()
            except:
                pass

    return leads_found


async def main():
    print(f"--- STARTING PRO SCRAPER (SUPABASE) ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use a real user agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        tasks = []
        # Batch requests to avoid blocking
        items = list(REGIONS.items())
        # Random shuffle to avoid patterns
        random.shuffle(items)

        # Using a semaphore to limit concurrency
        sem = asyncio.Semaphore(3)

        async def controlled_scrape(r_name, r_url, kw):
            async with sem:
                return await scrape_region(context, r_name, r_url, kw)

        for region_name, url in items:
            for keyword in SEARCH_KEYWORDS:
                tasks.append(controlled_scrape(region_name, url, keyword))

        # Run all tasks
        if tasks:
            await asyncio.gather(*tasks)

        await browser.close()
    print("--- SCRAPE COMPLETE ---")


if __name__ == "__main__":
    asyncio.run(main())
