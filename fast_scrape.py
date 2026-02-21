import asyncio
import random
import json
import re
import logging
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

KEYWORDS = ["victrola", "phonograph", "antique record player", "gramophone"]


class PhonographScraper:
    def __init__(self):
        self.ai_processor = AIAntiqueProcessor()
        self.seen_posts = self.load_seen_posts()
        self.all_leads = []

    def load_seen_posts(self):
        try:
            with open("seen_posts.json", "r") as f:
                return set(json.load(f))
        except:
            return set()

    def save_data(self):
        self.all_leads.sort(
            key=lambda x: x.get("posted_date", "1970-01-01"), reverse=True
        )
        unique = {l["id"]: l for l in self.all_leads}.values()
        self.all_leads = list(unique)

        with open("leads-v2.json", "w") as f:
            json.dump(self.all_leads, f, indent=2)
        with open("leads.json", "w") as f:
            json.dump(self.all_leads, f, indent=2)
        with open("seen_posts.json", "w") as f:
            json.dump(list(self.seen_posts), f)

        with open("metadata.json", "w") as f:
            json.dump(
                {
                    "last_updated": datetime.now().isoformat(),
                    "total_leads": len(self.all_leads),
                    "new_leads_this_run": len(
                        [l for l in self.all_leads if l.get("is_new", False)]
                    ),
                },
                f,
            )

    async def scrape_region(self, context, region_name, base_url, keyword):
        logger.info(f"Scraping {region_name} for '{keyword}'...")
        search_url = f"{base_url}/search/atq?query={keyword}"
        page = await context.new_page()
        try:
            await page.set_extra_http_headers(
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                }
            )
            await page.goto(search_url, wait_until="networkidle", timeout=60000)

            try:
                await page.wait_for_selector(
                    ".cl-search-result, .cl-static-search-result", timeout=10000
                )
            except:
                logger.info(f"  No results/timeout for {region_name}")
                return

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            dom_results = soup.select(".cl-search-result, .cl-static-search-result")
            logger.info(f"  Found {len(dom_results)} DOM items")

            for res in dom_results:
                try:
                    title_elem = res.select_one("a.posting-title, .title")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    link_elem = res.select_one("a[href]")
                    if not link_elem:
                        continue
                    link = link_elem.get("href")
                    if not link.startswith("http"):
                        link = base_url + link
                    match = re.search(r"/(\d+)\.html", link)
                    post_id = match.group(1) if match else res.get("data-pid")

                    if not post_id or post_id in self.seen_posts:
                        continue

                    analysis = self.ai_processor.score_lead(title)
                    time_tag = res.select_one("time")
                    posted_date = (
                        time_tag["datetime"].split(" ")[0]
                        if time_tag and time_tag.has_attr("datetime")
                        else datetime.now().strftime("%Y-%m-%d")
                    )

                    lead = {
                        "id": post_id,
                        "title": title,
                        "link": link,
                        "price": res.select_one(".priceinfo, .price").get_text(
                            strip=True
                        )
                        if res.select_one(".priceinfo, .price")
                        else "N/A",
                        "region": region_name,
                        "score": analysis["score"],
                        "classification": analysis["classification"],
                        "analysis": analysis["analysis"],
                        "image": "https://www.craigslist.org/images/peace.jpg",
                        "posted_date": posted_date,
                        "scraped_at": datetime.now().isoformat(),
                        "is_new": True,
                    }
                    self.all_leads.insert(0, lead)
                    self.seen_posts.add(post_id)
                    logger.info(f"  + New: {title}")
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Error scraping: {e}")
        finally:
            await page.close()

    async def run(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            await stealth_async(context)
            try:
                with open("leads-v2.json", "r") as f:
                    self.all_leads = json.load(f)
                    for l in self.all_leads:
                        l["is_new"] = False
            except:
                pass

            for region, base_url in SEARCH_REGIONS.items():
                for keyword in KEYWORDS:
                    await self.scrape_region(context, region, base_url, keyword)
                    await asyncio.sleep(random.uniform(2, 4))

            await browser.close()
            self.save_data()
            logger.info("Local scrape completed!")


if __name__ == "__main__":
    asyncio.run(PhonographScraper().run())
