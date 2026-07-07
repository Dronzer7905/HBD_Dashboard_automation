import os
import time
import random
import json
import requests
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from fake_useragent import UserAgent
import re
from urllib.parse import unquote
import datetime

# --- App & DB Imports ---
from extensions import db
from model.scraper_task import ScraperTask
from model.product_model.amazon_product import AmazonProduct

ua = UserAgent()
BASE_URL = 'https://www.amazon.in'
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STATE_FILE = os.path.join(BACKEND_DIR, "output", "amazon_scrape_state.json")

def log_msg(level, msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{ts} | {level.upper()} | {msg}", flush=True)

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        log_msg("ERROR", f"Failed to save state: {e}")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "products_scraped": 0,
        "products_inserted": 0,
        "products_updated": 0,
        "duplicates_prevented": 0,
        "is_complete": False,
        "started_at": "",
        "last_updated": ""
    }

def get_headers():
    return {
        'User-Agent': ua.random,
        'Accept-Language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': 'https://www.amazon.in/',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

def get_product_details(url):
    try:
        time.sleep(random.uniform(1, 3))
        response = requests.get(url, headers=get_headers())
        
        if response.status_code != 200:
            log_msg("WARNING", f"Failed to fetch URL: {url} (Status: {response.status_code})")
            return None
        
        if 'captcha' in response.text.lower():
            log_msg("WARNING", "Captcha encountered. Skipping.")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        asin = None
        clean_url = unquote(url)
        match = re.search(r'(?:/dp/|/gp/product/)([A-Z0-9]{10})', clean_url)
            
        if match:
            asin = match.group(1)
        else:
            log_msg("WARNING", f"No ASIN found in URL: {url[:60]}...")
            return None

        name_elem = soup.select_one("#productTitle") or \
                soup.select_one("h1#title") or \
                soup.select_one("h1.a-size-large") or \
                soup.select_one("h1.a-size-medium") or \
                soup.select_one("#titleSection h1")
        name = name_elem.get_text().strip() if name_elem else "Unknown Product"

        price_elem = soup.select_one('.a-price-whole')
        price = '₹' + price_elem.get_text().strip().replace(',', '') if price_elem else "₹0"

        rating_elem = soup.select_one('.a-icon-alt')
        rating_str = rating_elem.get_text().split()[0] if rating_elem else "0"
        try:
            rating = float(rating_str)
        except:
            rating = 0.0
            
        brand_elem = soup.select_one('#bylineInfo')
        brand = brand_elem.get_text().strip() if brand_elem else "Unknown Brand"

        try:
            price_num = float(price.replace('₹', '').replace(',', '').strip())
        except:
            price_num = 0.0

        return {
            'asin': asin,
            'title': name,
            'imgUrl': "",
            'productUrl': url,
            'stars': rating,
            'reviews': 0,
            'price': price_num,
            'listPrice': price_num,
            'categoryName': brand,
            'isBestSeller': False,
            'boughtInLastMonth': 0
        }
    except Exception as e:
        log_msg("ERROR", f"Error scraping {url}: {e}")
        return None

def scrape_amazon_search(search_term, pages=1, limit=1000, task_id=None, resume=False):
    from app import app 
    
    with app.app_context():
        try:
            state = load_state() if resume else {
                "products_scraped": 0,
                "products_inserted": 0,
                "products_updated": 0,
                "duplicates_prevented": 0,
                "is_complete": False,
                "started_at": datetime.datetime.now().isoformat(),
                "last_updated": ""
            }

            task = None
            if task_id:
                task = ScraperTask.query.get(task_id)
            
            if not task:
                task = ScraperTask(
                    platform="Amazon",
                    search_query=search_term, 
                    status="RUNNING",
                    progress=0,
                    total_found=0
                )
                db.session.add(task)
                db.session.commit()
            else:
                task.status = "RUNNING"
                db.session.commit()
            
            log_msg("SYSTEM", f"=== STARTING AMAZON SCRAPER ===")
            log_msg("INFO", f"Task ID: {task.id} | Query: '{search_term}' | Pages: {pages}")
            
            all_products_count = state["products_scraped"]
            
            for page in range(1, pages + 1):
                db.session.refresh(task)
                if task.status in ["STOPPED", "CANCELLED"] or getattr(task, 'should_stop', False):
                    log_msg("WARNING", f"Task {task.id} Stopped by User")
                    task.status = "STOPPED"
                    db.session.commit()
                    break

                search_url = f"{BASE_URL}/s?k={requests.utils.quote(search_term)}&page={page}"
                log_msg("SYSTEM", f"--- Phase {page}/{pages}: Scraping Page ---")
                
                try:
                    response = requests.get(search_url, headers=get_headers())
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        links = [urljoin(BASE_URL, a['href']) for a in soup.select('a.a-link-normal.s-no-outline') if a.get('href')]
                        
                        log_msg("INFO", f"Found {len(links)} product links on Page {page}.")
                        
                        page_saved_count = 0
                        for link in links:
                            if all_products_count >= limit: break
                            
                            p_data = get_product_details(link)
                            if p_data:
                                existing = AmazonProduct.query.filter_by(asin=p_data['asin']).first()
                                if not existing:
                                    new_prod = AmazonProduct(**p_data)
                                    db.session.add(new_prod)
                                    all_products_count += 1
                                    page_saved_count += 1
                                    state["products_inserted"] += 1
                                    log_msg("SUCCESS", f"Saved: {p_data['title'][:40]}...")
                                else:
                                    state["duplicates_prevented"] += 1
                                    log_msg("INFO", f"Duplicate ASIN skipped: {p_data['asin']}")
                                state["products_scraped"] += 1
                            
                        task.progress = int((page / pages) * 100)
                        task.total_found = all_products_count
                        db.session.commit()
                        
                        state["last_updated"] = datetime.datetime.now().isoformat()
                        save_state(state)
                        log_msg("SUCCESS", f"Page {page} Commit Success. Total Saved: {all_products_count}")
                    
                    else:
                        log_msg("ERROR", f"Failed to load Search Page {page}. Status: {response.status_code}")

                except Exception as e:
                    log_msg("ERROR", f"Critical Error on Page {page}: {e}")

                if all_products_count >= limit: 
                    log_msg("INFO", "--- Limit Reached ---")
                    break

            if task.status not in ["STOPPED", "CANCELLED"]:
                task.status = "COMPLETED"
                task.progress = 100
                state["is_complete"] = True
                db.session.commit()
                log_msg("SUCCESS", f"=== TASK COMPLETED: ID {task.id} | Total Products: {all_products_count} ===")
            
            save_state(state)

        except Exception as e:
            db.session.rollback()
            log_msg("ERROR", f"TASK FAILED: {e}")
            if task:
                task.status = "FAILED"
                task.error_message = str(e)
                db.session.commit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Subprocess Scraper")
    parser.add_argument("--search_term", type=str, required=True, help="Search query")
    parser.add_argument("--pages", type=int, default=1, help="Number of pages to scrape")
    parser.add_argument("--task_id", type=int, default=None, help="ScraperTask DB ID")
    parser.add_argument("--resume", action="store_true", help="Resume from last state")
    
    args = parser.parse_args()
    
    scrape_amazon_search(
        search_term=args.search_term,
        pages=args.pages,
        limit=1000,
        task_id=args.task_id,
        resume=args.resume
    )