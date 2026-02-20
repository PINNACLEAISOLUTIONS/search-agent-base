import asyncio
import random
import json
import re
import csv
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright  # type: ignore
from playwright_stealth import stealth_async  # type: ignore
from ai_lead_processor import AIAntiqueProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SEARCH_REGIONS = {
    "Miami": "https://miami.craigslist.org",
    "South Florida": "https://miami.craigslist.org",
    "Broward": "https://fortlauderdale.craigslist.org",
    "Palm Beach": "https://treasure.craigslist.org",
    "Space Coast": "https://spacecoast.craigslist.org",
    "Tampa": "https://tampa.craigslist.org",
    "Orlando": "https://orlando.craigslist.org",
    "Sarasota": "https://sarasota.craigslist.org",
    "Fort Myers": "https://fortmyers.craigslist.org",
    "Naples": "https://fortmyers.craigslist.org",
    "Keys": "https://keys.craigslist.org",
    "Treasure Coast": "https://treasure.craigslist.org",
    "Gold Coast": "https://miami.craigslist.org",
    "Daytona": "https://daytona.craigslist.org",
    "St. Augustine": "https://staugustine.craigslist.org",
    "Lakeland": "https://lakeland.craigslist.org",
    "Ocala": "https://ocala.craigslist.org",
    "Gainesville": "https://gainesville.craigslist.org",
}

KEYWORDS = [
    "victrola",
    "phonograph",
    "gramophone",
    "talking machine",
    "antique record player",
    "edison phonograph",
    "columbia grafonola",
]


class PhonographScraper:
    def __init__(self):
        self.ai_processor = AIAntiqueProcessor()
        self.seen_posts = self.load_seen_posts()
        self.all_leads = []

    def load_seen_posts(self):
        try:
            with open("seen_posts.json", "r") as f:
                return set(json.load(f))
        except FileNotFoundError:
            return set()

    def save_seen_posts(self):
        with open("seen_posts.json", "w") as f:
            json.dump(list(self.seen_posts), f)

    def save_leads(self):
        # Sort by date (newest first) before saving
        # Ensure we are sorting by YYYY-MM-DD string comparison
        self.all_leads.sort(
            key=lambda x: x.get("posted_date", "1970-01-01"), reverse=True
        )

        # JSON-V2 (Frontend)
        with open("leads-v2.json", "w") as f:
            json.dump(self.all_leads, f, indent=2)

        # Legacy JSON (Backup)
        with open("leads.json", "w") as f:
            json.dump(self.all_leads, f, indent=2)

        # CSV (Analysis)
        keys = (
            self.all_leads[0].keys()
            if self.all_leads
            else ["id", "title", "price", "region", "score", "classification", "link"]
        )
        with open("leads.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.all_leads)

        # Metadata
        with open("metadata.json", "w") as f:
            json.dump(
                {
                    "last_updated": datetime.now().isoformat(),
                    "total_leads": len(self.all_leads),
                    "new_leads_this_run": len(
                        [lead for lead in self.all_leads if lead.get("is_new", False)]
                    ),
                },
                f,
            )

    async def scrape_region(self, context, region_name, base_url, keyword):
        logger.info(f"Scraping {region_name} for '{keyword}'...")
        search_url = f"{base_url}/search/atq?query={keyword}"

        page = await context.new_page()
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(random.uniform(2, 5))

            # Wait a bit for potential JS hydration
            try:
                await page.wait_for_selector(".cl-search-result", timeout=5000)
            except Exception:  # Timeout or other error
                pass

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            # DEBUG: Check if blocked
            page_title = await page.title()
            if "blocked" in page_title.lower() or len(content) < 1000:
                logger.error(
                    f"  Possible block! Title: {page_title}, Content Len: {len(content)}"
                )

            # --- STRATEGY 1: JSON-LD (Structured Data) ---
            ld_script = soup.select_one("#ld_searchpage_results")
            json_results = []
            if ld_script:
                try:
                    data = json.loads(ld_script.text)
                    if "itemListElement" in data:
                        json_results = data["itemListElement"]
                        logger.info(f"  Found {len(json_results)} JSON-LD items")
                except Exception as e:
                    logger.error(f"JSON-LD parse error: {e}")

            dom_results = soup.select(".cl-search-result, .cl-static-search-result")
            logger.info(f"  Found {len(dom_results)} DOM items")

            if len(dom_results) == 0:
                logger.error("  0 DOM items found! Dumping HTML...")
                with open("debug.html", "w", encoding="utf-8") as f:
                    f.write(soup.prettify())

            for res in dom_results:
                try:
                    # Title & Link
                    # Standard DOM uses <a class="posting-title">...</a>
                    # Static DOM uses <a href="..."> <div class="title">...</div> </a>
                    title_elem = res.select_one("a.posting-title")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.get("href")
                    else:
                        a_tag = res.select_one("a")
                        title_div = res.select_one("div.title")
                        if a_tag and title_div:
                            title = title_div.get_text(strip=True)
                            link = a_tag.get("href")
                        else:
                            continue

                    if not link.startswith("http"):
                        link = base_url + link

                    # ID
                    post_id = res.get("data-pid")
                    if not post_id:
                        match = re.search(r"/(\d+)\.html", link)
                        if match:
                            post_id = match.group(1)

                    if not post_id or post_id in self.seen_posts:
                        continue

                    # Price
                    price_elem = res.select_one(".priceinfo, div.price")
                    price = price_elem.get_text(strip=True) if price_elem else "N/A"

                    # Image - Advanced Logic
                    image_url = "https://www.craigslist.org/images/peace.jpg"

                    # Gallery check
                    gallery_card = res.select_one(".gallery-card")
                    if gallery_card:
                        img_tag = gallery_card.select_one("img")
                        if img_tag and img_tag.get("src"):
                            src = img_tag["src"]
                            if "images.craigslist.org" in src:
                                image_url = src
                            elif src.startswith("data:"):
                                pass

                    # JSON-LD Reference for Image
                    for j_item in json_results:
                        j_product = j_item.get("item", {})
                        if j_product.get("name") == title:
                            images = j_product.get("image", [])
                            if isinstance(images, list) and len(images) > 0:
                                image_url = images[0]
                            elif isinstance(images, str):
                                image_url = images
                            break

                    # Posted Date Logic (Targeting datetime attribute)
                    posted_date = "1970-01-01"
                    time_elem = res.select_one("time.date.timeago")
                    if time_elem and time_elem.has_attr("datetime"):
                        # Format: 2026-02-11 17:15
                        raw_date = time_elem["datetime"]
                        if raw_date:
                            # Keep just YYYY-MM-DD
                            posted_date = raw_date.split(" ")[0]
                    else:
                        # Fallback to meta text if time tag missing
                        meta_div = res.select_one(".meta")
                        if meta_div:
                            meta_text = meta_div.get_text()
                            date_match = re.search(r"(\d{1,2}/\d{1,2})", meta_text)
                            if date_match:
                                m_d = date_match.group(1)
                                now = datetime.now()
                                try:
                                    dt = datetime.strptime(
                                        f"{m_d}/{now.year}", "%m/%d/%Y"
                                    )
                                    if dt > now + timedelta(days=2):
                                        dt = dt.replace(year=now.year - 1)
                                    posted_date = dt.strftime("%Y-%m-%d")
                                except ValueError:
                                    pass

                    if posted_date == "1970-01-01":
                        # If date is still missing (like in static HTML), use today's date
                        posted_date = datetime.now().strftime("%Y-%m-%d")

                    # AI Score
                    analysis = self.ai_processor.score_lead(title)

                    lead = {
                        "id": post_id,
                        "title": title,
                        "link": link,
                        "price": price,
                        "region": region_name,
                        "score": analysis["score"],
                        "classification": analysis["classification"],
                        "analysis": analysis["analysis"],
                        "image": image_url,
                        "posted_date": posted_date,  # Normalized YYYY-MM-DD
                        "scraped_at": datetime.now().isoformat(),
                        "is_new": True,
                    }

                    if analysis["score"] >= 0:
                        self.all_leads.append(lead)
                        self.seen_posts.add(post_id)
                        logger.info(f"  + Saved: {title} ({price})")

                except Exception as e:
                    logger.error(f"  Error processing item: {e}")
                    continue

            # --- FALLBACK: Use JSON-LD if DOM failed ---
            if len(dom_results) == 0 and len(json_results) > 0:
                logger.info("  Falling back to JSON-LD processing...")
                for item in json_results:
                    try:
                        product = item.get("item", {})
                        title = product.get("name")
                        if not title:
                            continue

                        link = product.get(
                            "url", base_url
                        )  # unlikely to be empty but safe fallback

                        # ID extraction from URL
                        post_id = None
                        match = re.search(r"/(\d+)\.html", link)
                        if match:
                            post_id = match.group(1)

                        if not post_id or post_id in self.seen_posts:
                            continue

                        # Price
                        offers = product.get("offers", {})
                        price = "N/A"
                        if isinstance(offers, dict):
                            p_val = offers.get("price")
                            curr = offers.get("priceCurrency", "$")
                            if p_val:
                                price = f"${p_val}"

                        # Image
                        image_url = "https://www.craigslist.org/images/peace.jpg"
                        images = product.get("image", [])
                        if isinstance(images, list) and len(images) > 0:
                            image_url = images[0]
                        elif isinstance(images, str):
                            image_url = images

                        # AI Score (Reuse existing logic)
                        analysis = self.ai_processor.score_lead(title)

                        lead = {
                            "id": post_id,
                            "title": title,
                            "link": link,
                            "price": price,
                            "region": region_name,
                            "score": analysis["score"],
                            "classification": analysis["classification"],
                            "analysis": analysis["analysis"],
                            "image": image_url,
                            "posted_date": datetime.now().strftime(
                                "%Y-%m-%d"
                            ),  # JSON-LD usually lacks date, default to now for freshness
                            "scraped_at": datetime.now().isoformat(),
                            "is_new": True,
                        }

                        if analysis["score"] >= 0:
                            self.all_leads.append(lead)
                            self.seen_posts.add(post_id)
                            logger.info(f"  + Saved (JSON-LD): {title} ({price})")

                    except Exception as e:
                        logger.error(f"  Error processing JSON-LD item: {e}")

        except Exception as e:
            logger.error(f"Error scraping region {region_name}: {e}")
        finally:
            await page.close()

    async def run(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-position=0,0",
                    "--ignore-certifcate-errors",
                    "--ignore-certifcate-errors-spki-list",
                    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["geolocation"],
                geolocation={"latitude": 25.7617, "longitude": -80.1918},  # Miami
            )

            # Remove webdriver property
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            await stealth_async(context)

            # Load previous leads
            try:
                with open("leads-v2.json", "r") as f:
                    existing = json.load(f)
                    for x in existing:
                        x["is_new"] = False

                        # --- FIX: Normalize Dates ---
                        # If date is a long ISO string, truncate it to YYYY-MM-DD
                        p_date = x.get("posted_date", "")
                        if p_date and len(p_date) > 10 and "T" in p_date:
                            try:
                                # Try parsing as ISO
                                dt = datetime.fromisoformat(p_date)
                                x["posted_date"] = dt.strftime("%Y-%m-%d")
                            except ValueError:
                                # Simple truncation fallback
                                x["posted_date"] = p_date[:10]
                        elif not p_date:
                            x["posted_date"] = "1970-01-01"

                    self.all_leads.extend(existing)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

            # Aggressive Date Check
            for x in self.all_leads:
                pd = x.get("posted_date", "")
                if pd and len(pd) >= 10 and pd.startswith("20"):
                    # Truncate to YYYY-MM-DD
                    x["posted_date"] = pd[:10]
                else:
                    x["posted_date"] = "1970-01-01"

            for region, base_url in SEARCH_REGIONS.items():
                for keyword in KEYWORDS:
                    await self.scrape_region(context, region, base_url, keyword)
                    await asyncio.sleep(random.uniform(1, 3))

                # INCREMENTAL SAVE
                logger.info(f"Incremental save after {region}...")
                self.save_leads()
                self.save_seen_posts()

            await browser.close()

            # De-duplicate just in case (by ID)
            unique_vals = {lead["id"]: lead for lead in self.all_leads}.values()
            self.all_leads = list(unique_vals)

            self.save_leads()
            self.save_seen_posts()
            logger.info("Scraping completed!")


if __name__ == "__main__":
    scraper = PhonographScraper()
    asyncio.run(scraper.run())
