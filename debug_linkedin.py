#!/usr/bin/env python3
"""
Debug script to help identify LinkedIn page structure issues
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup as bs
import time

def debug_linkedin_structure():
    """Debug LinkedIn page structure to understand what's available"""
    
    # Set up Chrome driver with stealth options
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    print("[*] Initializing Chrome driver...")
    browser = webdriver.Chrome(options=chrome_options)
    browser.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    browser.set_window_size(1200, 800)
    
    try:
        # Manual login
        print("[*] Navigating to LinkedIn login...")
        browser.get('https://www.linkedin.com/login')
        input("Please log in manually and press Enter when done...")
        
        # Navigate to search page
        search_url = "https://www.linkedin.com/search/results/content/?keywords=%23hiring%20%22machine%20learning%22%20Ahmedabad&origin=FACETED_SEARCH&sid=90E&sortBy=%22date_posted%22"
        print(f"[*] Navigating to search page...")
        browser.get(search_url)
        
        # Wait a bit for page to load
        time.sleep(5)
        
        print(f"[*] Current URL: {browser.current_url}")
        print(f"[*] Page title: {browser.title}")
        
        # Parse with BeautifulSoup
        soup = bs(browser.page_source, "html.parser")
        
        # Look for various container patterns
        print("\n[DEBUG] Analyzing page structure...")
        
        # 1. Look for any divs with 'search' in class name
        search_divs = soup.find_all("div", {"class": lambda x: x and "search" in x.lower()})
        print(f"[DEBUG] Found {len(search_divs)} divs with 'search' in class name")
        
        # 2. Look for any divs with 'result' in class name
        result_divs = soup.find_all("div", {"class": lambda x: x and "result" in x.lower()})
        print(f"[DEBUG] Found {len(result_divs)} divs with 'result' in class name")
        
        # 3. Look for any divs with 'feed' in class name
        feed_divs = soup.find_all("div", {"class": lambda x: x and "feed" in x.lower()})
        print(f"[DEBUG] Found {len(feed_divs)} divs with 'feed' in class name")
        
        # 4. Look for any divs with 'update' in class name
        update_divs = soup.find_all("div", {"class": lambda x: x and "update" in x.lower()})
        print(f"[DEBUG] Found {len(update_divs)} divs with 'update' in class name")
        
        # 5. Look for any divs with data-urn attribute
        urn_divs = soup.find_all("div", {"data-urn": True})
        print(f"[DEBUG] Found {len(urn_divs)} divs with data-urn attribute")
        
        # 6. Look for specific known classes
        known_classes = [
            "reusable-search__result-container",
            "feed-shared-update-v2",
            "update-components-text",
            "update-components-actor__container"
        ]
        
        for class_name in known_classes:
            elements = soup.find_all("div", {"class": class_name})
            print(f"[DEBUG] Found {len(elements)} elements with class '{class_name}'")
        
        # Sample some class names
        print("\n[DEBUG] Sample class names found on page:")
        all_divs = soup.find_all("div", {"class": True})[:20]  # First 20 divs
        for div in all_divs:
            classes = div.get("class", [])
            if classes:
                print(f"  - {' '.join(classes)}")
        
        # Save debug info
        with open("debug_analysis.html", "w", encoding="utf-8") as f:
            f.write(browser.page_source)
        print("\n[DEBUG] Full page source saved to debug_analysis.html")
        
        # Interactive mode
        print("\n[DEBUG] Browser will stay open for manual inspection...")
        input("Press Enter to close browser...")
        
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        browser.quit()

if __name__ == "__main__":
    debug_linkedin_structure()
