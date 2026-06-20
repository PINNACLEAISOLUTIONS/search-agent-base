import os
import sqlite3
import logging
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fetch_listings import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("app")

app = FastAPI(title="OldTimeCrank Search Engine")

# Get database path from environment variable or default to local path
DATABASE_PATH = os.environ.get("DATABASE_PATH", "./data/listings.db")

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    logger.info("Initializing database on startup...")
    init_db()

@app.get("/")
def read_root():
    """Serves the static index.html dashboard."""
    index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return JSONResponse(
            status_code=404,
            content={"error": "index.html dashboard file not found in root directory."}
        )

@app.get("/api/listings")
def get_listings():
    """Queries the SQLite listings table and returns all listings sorted by posted_at DESC."""
    if not os.path.exists(DATABASE_PATH):
        return []

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, price, location, source, url, image_url, posted_at, first_seen_at, seen, keyword 
            FROM listings 
            ORDER BY datetime(posted_at) DESC, id DESC
        """)
        
        rows = cursor.fetchall()
        listings = [dict(row) for row in rows]
        conn.close()
        return listings
    except Exception as e:
        logger.error(f"Error reading listings: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to retrieve listings from database."}
        )

@app.get("/api/status")
def get_status():
    """Retrieves the last execution status and statistics from update_logs."""
    if not os.path.exists(DATABASE_PATH):
        return {"status": "pending", "message": "Database not populated yet."}

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT status, checked_count, inserted_count, skipped_count, error_message, run_at 
            FROM update_logs 
            ORDER BY id DESC 
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        else:
            return {"status": "pending", "message": "No update logs found."}
    except Exception as e:
        logger.error(f"Error reading status logs: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to retrieve update status from database."}
        )

@app.post("/api/seen/{listing_id}")
def mark_as_seen(listing_id: str):
    """Updates the database entry to mark a listing as seen."""
    if not os.path.exists(DATABASE_PATH):
        return JSONResponse(status_code=404, content={"error": "Database not found."})

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE listings SET seen = 1 WHERE listing_id = ?", (listing_id,))
        conn.commit()
        updated = cursor.rowcount
        conn.close()
        
        if updated > 0:
            return {"status": "success", "message": f"Listing {listing_id} marked as seen."}
        else:
            return JSONResponse(status_code=404, content={"error": "Listing ID not found."})
    except Exception as e:
        logger.error(f"Error updating listing seen state: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to update seen state."}
        )

@app.post("/api/fetch")
def trigger_fetch(background_tasks: BackgroundTasks, token: str = None):
    """Triggers the listing fetch process in the background, authenticated by FETCH_TOKEN."""
    expected_token = os.environ.get("FETCH_TOKEN")
    if expected_token and token != expected_token:
        return JSONResponse(status_code=401, content={"error": "Unauthorized. Invalid token."})

    from fetch_listings import fetch_and_save
    background_tasks.add_task(fetch_and_save)
    return {"status": "success", "message": "Fetch job triggered in background."}
