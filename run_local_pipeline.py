import subprocess
import sys
import os

def main():
    print("=== STARTING CRAIGSLIST PHONOGRAPH SCRAPER ===")
    
    # 1. Run local scraper
    scraper_cmd = [sys.executable, "phonograph_scraper.py"]
    print(f"Running command: {' '.join(scraper_cmd)}")
    scraper_res = subprocess.run(scraper_cmd)
    
    if scraper_res.returncode != 0:
        print("Error: Craigslist scraper failed or exited with non-zero code.")
        sys.exit(scraper_res.returncode)
    
    print("\n=== SCRAPING COMPLETED SUCCESSFULLY ===")
    
    # 2. Sync to global leads
    sync_cmd = [sys.executable, "sync_to_global.py"]
    print(f"Running command: {' '.join(sync_cmd)}")
    sync_res = subprocess.run(sync_cmd)
    
    if sync_res.returncode != 0:
        print("Error: Syncing to global workspace leads failed.")
        sys.exit(sync_res.returncode)

    # 3. Deploy to Netlify
    print("\n=== DEPLOYING TO NETLIFY ===")
    # On Windows, we run netlify via shell to locate the global npm binary
    deploy_cmd = ["netlify", "deploy", "--prod", "--dir=."]
    deploy_res = subprocess.run(deploy_cmd, shell=True)
    
    if deploy_res.returncode != 0:
        print("Error: Netlify deployment failed.")
        sys.exit(deploy_res.returncode)
        
    print("\n=== PIPELINE RUN, SYNC, AND DEPLOY COMPLETED SUCCESSFULLY! ===")

if __name__ == "__main__":
    main()
