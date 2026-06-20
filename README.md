# OLDTIMECRANK — Curated Antique Listing Alert Engine

A robust, simple, and decoupled system for tracking and alerting on antique listings (phonographs, victrolas, talking machines) for your dad, using **SQLite** on a **Render Persistent Disk**.

---

## Architecture Overview
1. **Frontend / API**: Hosted as a **Render Web Service** running a lightweight FastAPI (Python) server. It serves a gorgeous, responsive vanilla HTML/CSS/JS dashboard (`index.html`) at the root `/` and provides JSON API endpoints at `/api/listings` and `/api/status`.
2. **Scheduled Ingestion**: Hosted as a **Render Cron Job** running every 4 hours (`npm run fetch` or `python fetch_listings.py`).
3. **Database / Storage**: A single SQLite database (`listings.db`) stored on a Render **Persistent Disk** mounted to `/data/`. Both the Web Service and the Cron Job mount this same disk, ensuring they read/write from the same database instance.
4. **Feeds Ingestion**: Fetches updates using standard XML/RSS feed urls (defined in `sources.json`) without heavy browser automation or bot bypass tools.

---

## Database Schemas (SQLite)

The system automatically initializes these tables on startup if they do not exist.

### `listings` Table
Stores normalized listing records.
```sql
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
CREATE INDEX IF NOT EXISTS idx_listings_posted_at ON listings (posted_at DESC);
```

### `update_logs` Table
Stores execution logs for health checks.
```sql
CREATE TABLE IF NOT EXISTS update_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL,          -- 'success' or 'failure'
    checked_count INTEGER DEFAULT 0,
    inserted_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    error_message TEXT,
    run_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## Local Development & Test Guide

### 1. Setup Environment
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. By default, `DATABASE_PATH` points to `./data/listings.db`. This folder and file will be created automatically.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Manual Ingest (Test Run)
To trigger a manual feed check and database update:
```bash
npm run fetch
```
This runs `fetch_listings.py` and outputs a summary of checked, inserted, and skipped listings:
```
========================================
FETCH RUN SUMMARY: SUCCESS
Time: 2026-06-20 12:45:00
Checked Listings:  2
New Inserted:      2
Duplicates Skipped:0
========================================
```

### 4. Run Web Dashboard locally
```bash
npm start
```
Open [http://localhost:8000](http://localhost:8000) in your browser. The dashboard lets you:
- Filter listings dynamically by keyword, feed source, and price.
- Toggle "Seen/Unseen" status (tracked locally using browser `localStorage` and optionally updated in the database).
- Inspect the last sync status at the top, showing errors or successes.

---

## Render Deployment Guide

Follow these steps to deploy to Render:

### Step A: Deploy the Web Service (Dashboard & API)
1. Go to the **Render Dashboard** and click **New > Web Service**.
2. Select your GitHub repository.
3. Configuration:
   - **Runtime**: `Docker`
   - **Instance Type**: `Free` or `Starter`
4. Add a **Persistent Disk** (under the "Disk" section):
   - **Name**: `listings-db-disk`
   - **Mount Path**: `/data`
   - **Size**: `1 GB`
5. Configure **Environment Variables**:
   - Add Key: `DATABASE_PATH` with Value: `/data/listings.db`
6. Deploy the Web Service. Once built, it will be available at your Render URL.

### Step B: Deploy the Scheduled Cron Job
1. Go to the **Render Dashboard** and click **New > Cron Job**.
2. Select your GitHub repository.
3. Configuration:
   - **Runtime**: `Docker`
   - **Command**: `npm run fetch`
   - **Schedule**: `0 */4 * * *` (Runs every 4 hours)
4. Configure **Environment Variables**:
   - Add Key: `DATABASE_PATH` with Value: `/data/listings.db`
5. Connect the same **Persistent Disk**:
   - Under the "Disk" section, mount the exact same disk (`listings-db-disk`) to `/data`.
6. Save and deploy.

Now, the Cron Job will execute every 4 hours, write new listings directly to `/data/listings.db`, and the Web Service will instantly serve them to the web dashboard.
