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

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SEARCH_REGIONS = {
    "Miami": "https://miami.craigslist.org",
    "Tampa": "https://tampa.craigslist.org",
    "Orlando": "https://orlando.craigslist.org",
    "Fort Myers": "https://fortmyers.craigslist.org",
    "Sarasota": "https://sarasota.craigslist.org",
}

KEYWORDS = ["victrola", "phonograph", "antique record player"]


class FinalRobustScraper:
    def __init__(self):
        self.ai_processor = AIAntiqueProcessor()
        self.all_leads = {}

    def load_existing(self):
        try:
            if os.path.exists("leads-v2.json"):
                with open("leads-v2.json", "r") as f:
                    for l in json.load(f):
                        l["is_new"] = False
                        self.all_leads[str(l["id"])] = l
        except:
            pass

    def save_data(self):
        sorted_leads = list(self.all_leads.values())
        # Final sort for output
        sorted_leads.sort(
            key=lambda x: (x.get("posted_date", "1970-01-01"), x.get("id", "")),
            reverse=True,
        )

        with open("leads-v2.json", "w") as f:
            json.dump(sorted_leads, f, indent=2)
        with open("leads.json", "w") as f:
            json.dump(sorted_leads, f, indent=2)
        with open("metadata.json", "w") as f:
            json.dump(
                {
                    "last_updated": datetime.now().isoformat(),
                    "total": len(sorted_leads),
                },
                f,
            )

    async def scrape_region(self, context, region_name, base_url, keyword):
        url = f"{base_url}/search/atq?query={keyword}&sort=date"
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="load", timeout=60000)
            await asyncio.sleep(2)
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            items = soup.select(
                ".cl-search-result, .cl-static-search-result, .result-row"
            )

            for item in items:
                try:
                    title_elem = item.select_one(
                        "a.posting-title, .title, .result-title"
                    )
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    link = item.select_one("a[href]")["href"]
                    if not link.startswith("http"):
                        link = base_url + link

                    post_id = str(
                        item.get("data-pid")
                        or re.search(r"/(\d+)\.html", link).group(1)
                    )

                    # --- AGGRESSIVE DATE PARSING ---
                    posted_date = datetime.now().strftime("%Y-%m-%d")  # Default Today

                    # Look for ANY date-ish text (e.g., "Feb 20", "2/20", "1h ago")
                    meta_text = item.get_text()
                    date_match = re.search(r"(\d{1,2}/\d{2})", meta_text)  # 2/20
                    if not date_match:
                        date_match = re.search(
                            r"([A-Z][a-z]{2}\s+\d{1,2})", meta_text
                        )  # Feb 20

                    if date_match:
                        try:
                            # Assume current year
                            raw_val = date_match.group(1)
                            fmt = "%m/%d" if "/" in raw_val else "%b %d"
                            dt = datetime.strptime(raw_val, fmt)
                            dt = dt.replace(year=datetime.now().year)
                            # If date is in future (e.g. Dec in Jan), subtract a year
                            if dt > datetime.now():
                                dt = dt.replace(year=dt.year - 1)
                            posted_date = dt.strftime("%Y-%m-%d")
                        except:
                            pass

                    analysis = self.ai_processor.score_lead(title)
                    if analysis["score"] < 1.0:
                        continue

                    lead = {
                        "id": post_id,
                        "title": title,
                        "link": link,
                        "price": (
                            item.select_one(
                                ".priceinfo, .price, .result-price"
                            ).get_text(strip=True)
                            if item.select_one(".priceinfo, .price, .result-price")
                            else "N/A"
                        ),
                        "region": region_name,
                        "score": analysis["score"],
                        "classification": analysis["classification"],
                        "analysis": analysis["analysis"],
                        "image": "https://www.craigslist.org/images/peace.jpg",
                        "posted_date": posted_date,
                        "scraped_at": datetime.now().isoformat(),
                        "is_new": True,
                    }
                    self.all_leads[post_id] = lead
                except:
                    continue
        finally:
            await page.close()

    async def run(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            await stealth_async(context)
            self.load_existing()
            for r, u in SEARCH_REGIONS.items():
                for kw in KEYWORDS:
                    await self.scrape_region(context, r, u, kw)
                    await asyncio.sleep(random.uniform(2, 5))
            await browser.close()
            self.save_data()


if __name__ == "__main__":
    asyncio.run(FinalRobustScraper().run())
