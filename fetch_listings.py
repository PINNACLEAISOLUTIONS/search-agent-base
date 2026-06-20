import os
import re
import json
import sqlite3
import logging
import urllib.request
import xml.etree.ElementTree as ET
import time
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("fetch_listings")

# Get database path from environment variable or default to local path
DATABASE_PATH = os.environ.get("DATABASE_PATH", "./data/listings.db")

def init_db():
    """Initializes the SQLite database tables if they do not exist."""
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"Created database directory: {db_dir}")

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Create listings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            price TEXT,
            location TEXT,
            source TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            image_url TEXT,
            posted_at TEXT,
            first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
            listing_id TEXT UNIQUE NOT NULL,
            seen INTEGER DEFAULT 0,
            keyword TEXT
        );
    """)

    # Index for speed
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_listings_posted_at ON listings (posted_at DESC);")

    # Create update_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS update_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL,
            checked_count INTEGER DEFAULT 0,
            inserted_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            error_message TEXT,
            run_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")

# Abstract Base Class for Listing Sources
class ListingSource:
    def __init__(self, config):
        self.id = config.get("id")
        self.name = config.get("name")
        self.enabled = config.get("enabled", True)
        self.url = config.get("url")
        self.region = config.get("region", "Unknown")
        self.keyword = config.get("keyword", "")
        self.source_type = config.get("type", "rss")

    def fetch(self) -> list:
        raise NotImplementedError("fetch() must be implemented by subclasses.")

# RSS Listing Source Subclass
class RssListingSource(ListingSource):
    def fetch(self) -> list:
        if not self.enabled:
            logger.info(f"Source '{self.name}' is disabled. Skipping.")
            return []

        logger.info(f"Fetching listings from feed: {self.name} ({self.url})")
        
        # Standard browser headers to make legitimate requests
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "application/xml,text/xml,application/xhtml+xml,text/html;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }

        try:
            req = urllib.request.Request(self.url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read()
        except Exception as e:
            logger.error(f"Failed to fetch feed {self.name} from {self.url}: {e}")
            raise e

        # If Craigslist returned a block page in html
        if b"Your request has been blocked" in content or b"<title>blocked</title>" in content:
            err_msg = f"Request to Craigslist source '{self.name}' was blocked by Craigslist firewall (403/Forbidden)."
            logger.warning(err_msg)
            raise PermissionError(err_msg)

        try:
            return self.parse_rdf_or_rss(content)
        except Exception as e:
            logger.error(f"Failed to parse XML content for feed {self.name}: {e}")
            raise e

    def parse_rdf_or_rss(self, xml_content: bytes) -> list:
        ns = {
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'rss': 'http://purl.org/rss/1.0/',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'enc': 'http://purl.org/rss/1.0/modules/enc/'
        }

        root = ET.fromstring(xml_content)
        items = root.findall('.//item')
        if not items:
            items = root.findall('.//{http://purl.org/rss/1.0/}item')
            if not items:
                items = root.findall('item')

        normalized_listings = []

        for item in items:
            def find_text(tag, default=""):
                for prefix, uri in ns.items():
                    elem = item.find(f"{prefix}:{tag}", ns)
                    if elem is not None:
                        return elem.text or default
                    elem = item.find(f"{{{uri}}}{tag}")
                    if elem is not None:
                        return elem.text or default
                elem = item.find(tag)
                return elem.text if elem is not None else default

            raw_title = find_text('title')
            clean_title = find_text('title')
            
            price = "N/A"
            location = self.region

            dc_title_elem = item.find('{http://purl.org/dc/elements/1.1/}title')
            if dc_title_elem is not None and dc_title_elem.text:
                clean_title = dc_title_elem.text
            
            if raw_title:
                price_match = re.search(r'\$([0-9,]+)', raw_title)
                if price_match:
                    price = f"${price_match.group(1)}"
                
                loc_match = re.search(r'\(([^)]+)\)\s*$', raw_title)
                if loc_match:
                    location = loc_match.group(1)
                
                if clean_title == raw_title:
                    clean_title = re.sub(r'\s+-\s+\$[0-9,]+.*$', '', raw_title)
                    clean_title = re.sub(r'\s*\([^)]+\)\s*$', '', clean_title).strip()

            url = find_text('link')
            if not url:
                url = item.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about', '')

            image_url = ""
            enclosure = item.find('{http://purl.org/rss/1.0/modules/enc/}enclosure')
            if enclosure is not None:
                image_url = enclosure.attrib.get('resource', '')
            else:
                enclosure = item.find('enclosure')
                if enclosure is not None:
                    image_url = enclosure.attrib.get('url', '')

            posted_at = find_text('date')
            if not posted_at:
                posted_at = datetime.utcnow().isoformat()

            listing_id = ""
            if url:
                id_match = re.search(r'/(\d+)\.html', url)
                if id_match:
                    listing_id = id_match.group(1)
                else:
                    import hashlib
                    listing_id = hashlib.md5(url.encode('utf-8')).hexdigest()

            if not clean_title or not url:
                continue

            normalized_listings.append({
                "title": clean_title,
                "price": price,
                "location": location,
                "source": self.name,
                "url": url,
                "image_url": image_url or "https://www.transparenttextures.com/patterns/aged-paper.png",
                "posted_at": posted_at,
                "listing_id": listing_id,
                "keyword": self.keyword
            })

        return normalized_listings

# Craigslist Browser Scraping Source Subclass
class CraigslistListingSource(ListingSource):
    def fetch(self) -> list:
        if not self.enabled:
            logger.info(f"Source '{self.name}' is disabled. Skipping.")
            return []

        logger.info(f"Fetching listings from Craigslist browser view: {self.name} ({self.url})")
        from playwright.sync_api import sync_playwright
        from playwright_stealth import stealth_sync
        from bs4 import BeautifulSoup

        normalized_listings = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-infobars",
                        "--window-position=0,0",
                        "--ignore-certificate-errors"
                    ]
                )
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    locale="en-US",
                    timezone_id="America/New_York"
                )
                
                # Remove webdriver property
                context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                stealth_sync(context)

                page = context.new_page()
                page.goto(self.url, wait_until="domcontentloaded", timeout=60000)
                
                # Wait 2 seconds for JS hydration
                time.sleep(2)
                
                # Check for block
                page_title = page.title()
                if "blocked" in page_title.lower():
                    browser.close()
                    raise PermissionError(f"Craigslist blocked browser session for '{self.name}'.")

                content = page.content()
                browser.close()

            # Parse DOM
            soup = BeautifulSoup(content, "html.parser")
            items = soup.select(".cl-search-result, .cl-static-search-result, .result-row")
            logger.info(f"  Parsed {len(items)} items from HTML")

            for item in items:
                try:
                    title_elem = item.select_one("a.posting-title, .title, .result-title")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    
                    # Extract link
                    a_tag = item.select_one("a[href]")
                    if not a_tag:
                        continue
                    link = a_tag["href"]
                    if not link.startswith("http"):
                        match = re.match(r"(https?://[^/]+)", self.url)
                        base = match.group(1) if match else "https://craigslist.org"
                        link = base + link

                    # Extract price
                    price_elem = item.select_one(".priceinfo, .price, .result-price")
                    price = price_elem.get_text(strip=True) if price_elem else "N/A"

                    # Location
                    location_elem = item.select_one(".location, .nearby")
                    location = location_elem.get_text(strip=True) if location_elem else self.region

                    # Listing ID
                    post_id = item.get("data-pid")
                    if not post_id:
                        id_match = re.search(r'/(\d+)\.html', link)
                        if id_match:
                            post_id = id_match.group(1)
                        else:
                            import hashlib
                            post_id = hashlib.md5(link.encode('utf-8')).hexdigest()

                    # Posted Date
                    posted_date = datetime.now().strftime("%Y-%m-%d")
                    time_elem = item.select_one("time")
                    if time_elem and time_elem.get("datetime"):
                        posted_date = time_elem["datetime"].split(" ")[0]
                    else:
                        meta = item.select_one(".meta")
                        if meta:
                            date_match = re.search(r"(\d{1,2}/\d{1,2})", meta.get_text())
                            if date_match:
                                try:
                                    dt = datetime.strptime(date_match.group(1), "%m/%d")
                                    dt = dt.replace(year=datetime.now().year)
                                    posted_date = dt.strftime("%Y-%m-%d")
                                except:
                                    pass

                    normalized_listings.append({
                        "title": title,
                        "price": price,
                        "location": location,
                        "source": self.name,
                        "url": link,
                        "image_url": "https://www.transparenttextures.com/patterns/aged-paper.png",
                        "posted_at": posted_date,
                        "listing_id": post_id,
                        "keyword": self.keyword
                    })
                except Exception as row_err:
                    logger.warning(f"Error parsing Craigslist row: {row_err}")
                    continue

        except Exception as e:
            logger.error(f"Error fetching from Craigslist source '{self.name}': {e}")
            raise e

        return normalized_listings

def fetch_and_save():
    init_db()

    # Load sources.json
    sources_path = "./sources.json"
    if not os.path.exists(sources_path):
        logger.error(f"Sources config file not found: {sources_path}")
        return

    with open(sources_path, "r", encoding="utf-8") as f:
        sources_config = json.load(f)

    checked_total = 0
    inserted_total = 0
    skipped_total = 0
    failures = []

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    for config in sources_config:
        source_type = config.get("type", "rss")
        if source_type == "craigslist":
            source = CraigslistListingSource(config)
        else:
            source = RssListingSource(config)

        if not source.enabled:
            continue

        try:
            listings = source.fetch()
            checked_count = len(listings)
            checked_total += checked_count
            
            source_inserted = 0
            source_skipped = 0

            for listing in listings:
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO listings (title, price, location, source, url, image_url, posted_at, listing_id, keyword)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        listing["title"],
                        listing["price"],
                        listing["location"],
                        listing["source"],
                        listing["url"],
                        listing["image_url"],
                        listing["posted_at"],
                        listing["listing_id"],
                        listing["keyword"]
                    ))
                    if cursor.rowcount > 0:
                        source_inserted += 1
                    else:
                        source_skipped += 1
                except Exception as e:
                    logger.error(f"Failed to insert listing {listing.get('url')}: {e}")

            inserted_total += source_inserted
            skipped_total += source_skipped
            logger.info(f"Source '{source.name}' complete. Checked: {checked_count}, Inserted: {source_inserted}, Skipped: {source_skipped}")

        except Exception as e:
            error_msg = str(e)
            clean_error = re.sub(r'token=[^&\s]+', 'token=REDACTED', error_msg)
            failures.append(f"{source.name}: {clean_error}")
            logger.error(f"Source '{source.name}' failed: {clean_error}")

    status = "success"
    error_message = None
    if failures:
        status = "failure"
        error_message = "; ".join(failures)

    try:
        cursor.execute("""
            INSERT INTO update_logs (status, checked_count, inserted_count, skipped_count, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (status, checked_total, inserted_total, skipped_total, error_message))
        conn.commit()
        logger.info(f"Execution logged. Status: {status}, Inserted: {inserted_total}, Skipped: {skipped_total}")
    except Exception as log_err:
        logger.error(f"Failed to write execution log to database: {log_err}")

    conn.close()

    print("\n" + "="*40)
    print(f"FETCH RUN SUMMARY: {status.upper()}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Checked Listings:  {checked_total}")
    print(f"New Inserted:      {inserted_total}")
    print(f"Duplicates Skipped:{skipped_total}")
    if failures:
        print("\nFailures:")
        for fail in failures:
            print(f" - {fail}")
    print("="*40)

if __name__ == "__main__":
    fetch_and_save()
