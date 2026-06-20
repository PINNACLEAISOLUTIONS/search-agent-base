import os
import asyncio
import logging
import zipfile
import io
import requests
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from phonograph_scraper import PhonographScraper

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("render_app")

app = FastAPI(title="OldTimeCrank Scraper Service")

# Netlify credentials from environment variables
NETLIFY_AUTH_TOKEN = os.environ.get("NETLIFY_AUTH_TOKEN")
NETLIFY_SITE_ID = os.environ.get("NETLIFY_SITE_ID")

def deploy_to_netlify():
    """ZIPs the workspace static files and deploys to Netlify using their REST API."""
    if not NETLIFY_AUTH_TOKEN or not NETLIFY_SITE_ID:
        logger.error("Missing NETLIFY_AUTH_TOKEN or NETLIFY_SITE_ID environment variables!")
        return False
        
    logger.info("Preparing ZIP file for Netlify deployment...")
    zip_buffer = io.BytesIO()
    
    # Files to include in the deployment
    files_to_deploy = ["index.html", "leads-v2.json", "leads.json", "leads.csv", "metadata.json", "seen_posts.json"]
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename in files_to_deploy:
            if os.path.exists(filename):
                zip_file.write(filename, arcname=filename)
                logger.info(f"  Added {filename} to ZIP")
            else:
                logger.warning(f"  File {filename} not found, skipping")
                
    zip_buffer.seek(0)
    zip_data = zip_buffer.read()
    
    logger.info("Uploading ZIP to Netlify...")
    url = f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys"
    headers = {
        "Authorization": f"Bearer {NETLIFY_AUTH_TOKEN}",
        "Content-Type": "application/zip"
    }
    
    try:
        response = requests.post(url, headers=headers, data=zip_data, timeout=60)
        if response.status_code in [200, 201]:
            logger.info("Successfully deployed to Netlify!")
            return True
        else:
            logger.error(f"Failed to deploy: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error calling Netlify API: {e}")
        return False

async def run_scraper_and_deploy():
    logger.info("Starting background Craigslist scraper run...")
    try:
        scraper = PhonographScraper()
        await scraper.run()
        logger.info("Scrape complete. Deploying to Netlify...")
        deploy_to_netlify()
    except Exception as e:
        logger.error(f"Error during background scrape: {e}")

@app.get("/")
def home():
    return {
        "status": "online", 
        "message": "OldTimeCrank Scraper Service is running.",
        "netlify_site_id": NETLIFY_SITE_ID,
        "has_token": bool(NETLIFY_AUTH_TOKEN)
    }

@app.get("/scrape")
def trigger_scrape(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scraper_and_deploy)
    return {"status": "accepted", "message": "Scraper run triggered in background."}
