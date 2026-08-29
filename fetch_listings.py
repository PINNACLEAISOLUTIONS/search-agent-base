import os
import re
import csv
import json
import sqlite3
import logging
import urllib.request
import urllib.parse
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
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "application/xml,text/xml,application/xhtml+xml,text/html;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }

        try:
            if self.url.startswith("file://"):
                parsed_url = urllib.parse.urlparse(self.url)
                file_path = urllib.request.url2pathname(parsed_url.path)
                if not os.path.exists(file_path):
                    basename = os.path.basename(file_path)
                    if os.path.exists(basename):
                        file_path = basename
                logger.info(f"Reading local feed file from: {file_path}")
                with open(file_path, "rb") as f:
                    content = f.read()
            else:
                req = urllib.request.Request(self.url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    content = response.read()
        except Exception as e:
            logger.error(f"Failed to fetch feed {self.name} from {self.url}: {e}")
            raise e

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

# Helper function to parse Craigslist HTML
def parse_craigslist_html(content: str, source_name: str, source_url: str, region: str, keyword: str) -> list:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        import importlib
        BeautifulSoup = getattr(importlib.import_module("bs4"), "BeautifulSoup")
    soup = BeautifulSoup(content, "html.parser")
    items = soup.select(".cl-search-result, .cl-static-search-result, .result-row, .gallery-card")
    logger.info(f"  Parsed {len(items)} items from HTML for '{source_name}'")

    normalized_listings = []
    for item in items:
        try:
            title_elem = item.select_one("a.posting-title, .title, .result-title, .label, .titlestring")
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            
            a_tag = item.select_one("a[href]")
            if not a_tag:
                continue
            link = a_tag["href"]
            if not link.startswith("http"):
                match = re.match(r"(https?://[^/]+)", source_url)
                base = match.group(1) if match else "https://craigslist.org"
                link = base + link

            price_elem = item.select_one(".priceinfo, .price, .result-price, .price-blob")
            price = price_elem.get_text(strip=True) if price_elem else "N/A"

            location_elem = item.select_one(".location, .nearby, .superregion")
            location = location_elem.get_text(strip=True) if location_elem else region

            post_id = item.get("data-pid")
            if not post_id:
                id_match = re.search(r'/(\d+)\.html', link)
                if id_match:
                    post_id = id_match.group(1)
                else:
                    import hashlib
                    post_id = hashlib.md5(link.encode('utf-8')).hexdigest()

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
                        except Exception:
                            pass

                        # Robust Craigslist image extraction (data-ids, data-src, srcset, or img tag)
            img_url = ""
            data_ids = item.get("data-ids")
            if not data_ids:
                d_elem = item.select_one("[data-ids]")
                if d_elem:
                    data_ids = d_elem.get("data-ids")

            if data_ids:
                first_id = data_ids.split(",")[0].split(":")[-1].strip()
                if first_id:
                    img_url = f"https://images.craigslist.org/{first_id}_600x450.jpg"

            if not img_url:
                img_elem = item.select_one("img[src*='craigslist'], img[data-src], img")
                if img_elem:
                    cand = img_elem.get("data-src") or img_elem.get("src") or ""
                    if cand and not cand.endswith(".gif") and "transparent" not in cand:
                        img_url = cand
                    elif img_elem.get("srcset"):
                        img_url = img_elem.get("srcset").split(",")[0].split(" ")[0]

            if not img_url or "transparent" in img_url:
                img_url = "https://images.unsplash.com/photo-1545454675-3531b543be5d?auto=format&fit=crop&w=600&q=80" 

            normalized_listings.append({
                "title": title,
                "price": price,
                "location": location,
                "source": source_name,
                "url": link,
                "image_url": img_url,
                "posted_at": posted_date,
                "listing_id": post_id,
                "keyword": keyword
            })
        except Exception as row_err:
            logger.warning(f"Error parsing Craigslist row: {row_err}")
            continue

    return normalized_listings

def fetch_craigslist_batch(cl_sources: list) -> dict:
    """Fetches multiple Craigslist sources using a shared Playwright browser instance."""
    results = {}
    if not cl_sources:
        return results

    try:
        import importlib
        playwright_mod = importlib.import_module("playwright.sync_api")
        sync_playwright = getattr(playwright_mod, "sync_playwright")
        stealth_mod = importlib.import_module("playwright_stealth")
        stealth_sync = getattr(stealth_mod, "stealth_sync")
    except (ImportError, ModuleNotFoundError, AttributeError):
        logger.warning("Playwright or playwright-stealth not installed, skipping browser scrape.")
        return results

    logger.info(f"Launching shared Playwright Chromium for {len(cl_sources)} Craigslist sources...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--ignore-certificate-errors"
            ]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York"
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        stealth_sync(context)
        page = context.new_page()

        for config in cl_sources:
            source_name = config.get("name")
            source_url = config.get("url")
            region = config.get("region", "Unknown")
            keyword = config.get("keyword", "")

            if not config.get("enabled", True):
                continue

            logger.info(f"Visiting Craigslist source: {source_name} ({source_url})")
            try:
                page.goto(source_url, wait_until="domcontentloaded", timeout=25000)
                time.sleep(1.5)
                
                page_title = page.title()
                if "blocked" in page_title.lower():
                    logger.warning(f"Blocked by Craigslist for '{source_name}'.")
                    results[config["id"]] = {"error": "Blocked by Craigslist anti-bot firewall", "items": []}
                    continue

                content = page.content()
                items = parse_craigslist_html(content, source_name, source_url, region, keyword)
                results[config["id"]] = {"error": None, "items": items}
            except Exception as e:
                logger.error(f"Error fetching Craigslist source '{source_name}': {e}")
                results[config["id"]] = {"error": str(e), "items": []}

        browser.close()

    return results

def export_static_data(conn, status: str, checked_total: int, inserted_total: int, skipped_total: int, error_message: str):
    """Exports SQLite records to data/listings.json, data/status.json, metadata.json, leads.json, and leads.csv."""
    os.makedirs("./data", exist_ok=True)
    cursor = conn.cursor()
    
    # 1. Fetch all listings sorted by posted_at DESC
    cursor.execute("""
        SELECT id, title, price, location, source, url, image_url, posted_at, first_seen_at, seen, keyword, listing_id
        FROM listings 
        ORDER BY datetime(posted_at) DESC, id DESC
    """)
    rows = cursor.fetchall()
    columns = [col[0] for col in cursor.description]
    all_listings = [dict(zip(columns, row)) for row in rows]

    # Save to data/listings.json and root listings.json
    with open("./data/listings.json", "w", encoding="utf-8") as f:
        json.dump(all_listings, f, indent=2)
    with open("./listings.json", "w", encoding="utf-8") as f:
        json.dump(all_listings, f, indent=2)
    logger.info(f"Exported {len(all_listings)} listings to ./data/listings.json and ./listings.json")

    # 2. Save status to data/status.json
    status_obj = {
        "status": status,
        "checked_count": checked_total,
        "inserted_count": inserted_total,
        "skipped_count": skipped_total,
        "error_message": error_message,
        "run_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open("./data/status.json", "w", encoding="utf-8") as f:
        json.dump(status_obj, f, indent=2)

    # 3. Save metadata to metadata.json
    metadata_obj = {
        "last_updated": datetime.utcnow().isoformat(),
        "total_leads": len(all_listings),
        "new_leads_this_run": inserted_total,
        "status": status
    }
    with open("./metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata_obj, f, indent=2)

    # 4. Save leads.json & leads.csv for workspace standard compatibility
    with open("./leads.json", "w", encoding="utf-8") as f:
        json.dump(all_listings, f, indent=2)

    if all_listings:
        keys = ["id", "listing_id", "title", "price", "location", "source", "url", "posted_at", "keyword"]
        with open("./leads.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_listings)

    # Also mirror to C:/Users/futur/gemini_workspace if it exists
    gemini_ws = r"C:\Users\futur\gemini_workspace"
    if os.path.exists(gemini_ws):
        try:
            with open(os.path.join(gemini_ws, "leads.json"), "w", encoding="utf-8") as f:
                json.dump(all_listings, f, indent=2)
            if all_listings:
                with open(os.path.join(gemini_ws, "leads.csv"), "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(all_listings)
        except Exception as ws_err:
            logger.warning(f"Could not mirror leads to gemini_workspace: {ws_err}")

    logger.info("Exported static files: data/listings.json, data/status.json, metadata.json, leads.json, leads.csv")

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

    # Separate Craigslist and RSS sources
    cl_sources = [c for c in sources_config if c.get("type") == "craigslist" and c.get("enabled", True)]
    rss_sources = [c for c in sources_config if c.get("type") != "craigslist" and c.get("enabled", True)]

    # Fetch Craigslist sources in a pooled browser session
    cl_results = {}
    if cl_sources:
        try:
            cl_results = fetch_craigslist_batch(cl_sources)
        except Exception as cl_err:
            logger.error(f"Batch Craigslist scraping error: {cl_err}")
            failures.append(f"Craigslist Batch: {cl_err}")

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Process Craigslist results
    for config in cl_sources:
        source_id = config.get("id")
        source_name = config.get("name")
        res = cl_results.get(source_id, {})
        err = res.get("error")
        listings = res.get("items", [])

        if err:
            clean_error = re.sub(r'token=[^&\s]+', 'token=REDACTED', str(err))
            failures.append(f"{source_name}: {clean_error}")

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
        logger.info(f"Source '{source_name}' complete. Checked: {checked_count}, Inserted: {source_inserted}, Skipped: {source_skipped}")

    # Process RSS sources
    for config in rss_sources:
        source = RssListingSource(config)
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
        status = "partial_success" if (inserted_total > 0 or checked_total > 0) else "failure"
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

    # Export static data files for static website hosting (Netlify)
    try:
        export_static_data(conn, status, checked_total, inserted_total, skipped_total, error_message)
    except Exception as exp_err:
        logger.error(f"Failed to export static data files: {exp_err}")

    conn.close()

    print("\n" + "="*40)
    print(f"FETCH RUN SUMMARY: {status.upper()}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Checked Listings:  {checked_total}")
    print(f"New Inserted:      {inserted_total}")
    print(f"Duplicates Skipped:{skipped_total}")
    if failures:
        print("\nFailures / Warnings:")
        for fail in failures:
            print(f" - {fail}")
    print("="*40)

if __name__ == "__main__":
    fetch_and_save()
