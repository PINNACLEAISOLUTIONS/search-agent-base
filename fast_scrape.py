import asyncio
import random
import json
import re
import logging
import os
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from ai_lead_processor import AIAntiqueProcessor

# Improved Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# REGIONS - Full coverage
SEARCH_REGIONS = {
    "Miami": "https://miami.craigslist.org",
    "Tampa": "https://tampa.craigslist.org",
    "Orlando": "https://orlando.craigslist.org",
    "Fort Myers": "https://fortmyers.craigslist.org",
    "Sarasota": "https://sarasota.craigslist.org",
    "Jacksonville": "https://jacksonville.craigslist.org",
    "Tallahassee": "https://tallahassee.craigslist.org",
}

# BROAD KEYWORDS to ensure we catch everything
KEYWORDS = [
    "victrola",
    "phonograph",
    "gramophone",
    "talking machine",
    "antique record player",
    "edison phonograph",
    "cylinder phonograph",
]


class RobustPhonographScraper:
    def __init__(self):
        self.ai_processor = AIAntiqueProcessor()
        self.all_leads = {}  # Map ID -> Lead object for easy updates
        self.last_run_stats = {"new": 0, "updated": 0, "total": 0}

    def load_existing(self):
        try:
            if os.path.exists("leads-v2.json"):
                with open("leads-v2.json", "r") as f:
                    data = json.load(f)
                    for l in data:
                        l["is_new"] = False
                        self.all_leads[str(l["id"])] = l
            logger.info(f"Loaded {len(self.all_leads)} existing leads.")
        except Exception as e:
            logger.error(f"Error loading leads: {e}")

    def save_data(self):
        sorted_leads = list(self.all_leads.values())
        # Sort by posted date desc, then by scraping time
        sorted_leads.sort(
            key=lambda x: (x.get("posted_date", "1970-01-01"), x.get("scraped_at", "")),
            reverse=True,
        )

        # Limit to reasonable number to keep dashboard fast
        top_leads = sorted_leads[:500]

        with open("leads-v2.json", "w") as f:
            json.dump(top_leads, f, indent=2)
        with open("leads.json", "w") as f:
            json.dump(top_leads, f, indent=2)

        # Export seen_posts for legacy support
        with open("seen_posts.json", "w") as f:
            json.dump(list(self.all_leads.keys()), f)

        with open("metadata.json", "w") as f:
            json.dump(
                {
                    "last_updated": datetime.now().isoformat(),
                    "total_leads": len(top_leads),
                    "new_leads_last_run": self.last_run_stats["new"],
                    "updated_leads_last_run": self.last_run_stats["updated"],
                    "status": "Success",
                },
                f,
            )

    async def scrape_region(self, context, region_name, base_url, keyword):
        logger.info(f"--- Scraping {region_name} for '{keyword}' ---")
        # Use a more modern sort to get newest first
        search_url = f"{base_url}/search/atq?query={keyword}&sort=date"

        page = await context.new_page()
        try:
            # Random desktop-class User-Agent
            await page.set_extra_http_headers(
                {
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.google.com/",
                }
            )

            await page.goto(search_url, wait_until="load", timeout=90000)

            # Wait for any of the result containers (new or old layout)
            try:
                await page.wait_for_selector(
                    ".cl-search-result, .cl-static-search-result, .result-row",
                    timeout=15000,
                )
            except:
                logger.warning(f"  Timeout/No results for {region_name}")
                return

            # Scroll once to trigger any lazy-loading
            await page.evaluate("window.scrollBy(0, 1000)")
            await asyncio.sleep(2)

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            # Catch multiple possible result item classes
            items = soup.select(
                ".cl-search-result, .cl-static-search-result, .result-row"
            )
            logger.info(f"  Found {len(items)} items on page.")

            for item in items:
                try:
                    # 1. Extraction (Robust selectors)
                    title_elem = item.select_one(
                        "a.posting-title, .title, .result-title"
                    )
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)

                    link_elem = item.select_one("a[href]")
                    if not link_elem:
                        continue
                    link = link_elem["href"]
                    if not link.startswith("http"):
                        link = base_url + link

                    # ID extraction
                    post_id = item.get("data-pid")
                    if not post_id:
                        match = re.search(r"/(\d+)\.html", link)
                        post_id = match.group(1) if match else None
                    if not post_id:
                        continue
                    post_id = str(post_id)

                    # Price
                    price_elem = item.select_one(".priceinfo, .price, .result-price")
                    price = price_elem.get_text(strip=True) if price_elem else "N/A"

                    # Date (CRITICAL FIX)
                    # Look for <time datetime="...">
                    posted_date = datetime.now().strftime(
                        "%Y-%m-%d"
                    )  # Default to today
                    time_tag = item.select_one("time")
                    if time_tag and time_tag.has_attr("datetime"):
                        # Usually "YYYY-MM-DD HH:MM:SS" or ISO
                        val = time_tag["datetime"]
                        if " " in val:
                            posted_date = val.split(" ")[0]
                        elif "T" in val:
                            posted_date = val.split("T")[0]
                        else:
                            posted_date = val[:10]

                    # AI Analysis
                    analysis = self.ai_processor.score_lead(title)
                    if analysis["score"] < 1.0:
                        continue  # Skip junk

                    # Image
                    image_url = "https://www.craigslist.org/images/peace.jpg"
                    img_tag = item.select_one("img")
                    if img_tag and img_tag.get("src"):
                        src = img_tag["src"]
                        if "images.craigslist.org" in src:
                            image_url = src

                    lead_obj = {
                        "id": post_id,
                        "title": title,
                        "link": link,
                        "price": price,
                        "region": region_name,
                        "score": analysis["score"],
                        "classification": analysis["classification"],
                        "analysis": analysis["analysis"],
                        "image": image_url,
                        "posted_date": posted_date,
                        "scraped_at": datetime.now().isoformat(),
                        "is_new": True,
                    }

                    if post_id in self.all_leads:
                        # Existing item - check if date changed (bumped)
                        if self.all_leads[post_id]["posted_date"] != posted_date:
                            logger.info(f"  * Updated: {title} ({posted_date})")
                            self.all_leads[post_id].update(lead_obj)
                            self.last_run_stats["updated"] += 1
                    else:
                        # Brand new item
                        logger.info(f"  + New Discovery: {title} ({price})")
                        self.all_leads[post_id] = lead_obj
                        self.last_run_stats["new"] += 1

                except Exception as e:
                    continue

        except Exception as e:
            logger.error(f"Error scraping {region_name}: {e}")
        finally:
            await page.close()

    async def run(self):
        async with async_playwright() as p:
            # Use specific channels and args to look more human
            browser = await p.chromium.launch(
                headless=True, args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            )
            await stealth_async(context)

            self.load_existing()

            for region, url in SEARCH_REGIONS.items():
                for kw in KEYWORDS:
                    await self.scrape_region(context, region, url, kw)
                    # Respectful delay
                    await asyncio.sleep(random.uniform(5, 10))

            self.last_run_stats["total"] = len(self.all_leads)
            await browser.close()
            self.save_data()
            logger.info(
                f"DONE. Found {self.last_run_stats['new']} new and {self.last_run_stats['updated']} updated items."
            )


if __name__ == "__main__":
    scraper = RobustPhonographScraper()
    asyncio.run(scraper.run())
