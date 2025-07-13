#!/usr/bin/env python3
"""
Enhanced Autonomous LinkedIn Scraper with Multiple Search Queries
Handles login automation with CAPTCHA solving using Google's Gemini
"""

import time
import csv
import random
import os
import base64
import json
from datetime import datetime
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains

import google.generativeai as genai
from bs4 import BeautifulSoup as bs

class GeminiHelper:
    """Simple Gemini API helper for autonomous scraping"""
    
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.vision_model = genai.GenerativeModel('gemini-1.5-flash')
    
    def solve_captcha(self, screenshot_base64):
        """Analyze CAPTCHA and provide solution steps"""
        try:
            # Convert base64 to image
            import io
            from PIL import Image
            
            image_data = base64.b64decode(screenshot_base64)
            image = Image.open(io.BytesIO(image_data))
            
            prompt = """
            I need to solve a LinkedIn login CAPTCHA. Look at this screenshot and tell me:
            
            1. What type of CAPTCHA is this? (puzzle, image selection, text, etc.)
            2. What specific action do I need to take?
            3. If it's a puzzle: describe the pieces and where they should go
            4. If it's image selection: what images should I click?
            5. If it's text: what text should I type?
            
            Be very specific about locations and actions. If you see a puzzle piece, describe its shape and where it should be moved.
            
            Format your response as JSON with keys:
            - "type": type of CAPTCHA
            - "action": specific action to take
            - "details": detailed description
            - "coordinates": if applicable, relative positions
            """
            
            response = self.vision_model.generate_content([prompt, image])
            return response.text
            
        except Exception as e:
            return f"Error analyzing CAPTCHA: {str(e)}"
    
    def find_elements(self, html_content, element_description):
        """Find elements when standard selectors fail"""
        prompt = f"""
        I'm looking for {element_description} in this HTML content.
        
        HTML (first 3000 chars):
        {html_content[:3000]}
        
        Please provide:
        1. The best CSS selector to find this element
        2. Alternative selectors if the first one might fail
        3. XPath if CSS won't work
        
        Return as JSON:
        {{
            "primary_selector": "css selector",
            "alternatives": ["alt1", "alt2"],
            "xpath": "xpath if needed"
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error finding elements: {str(e)}"

class EnhancedLinkedInScraper:
    """Enhanced autonomous LinkedIn scraper with multiple search queries"""
    
    def __init__(self, gemini_api_key):
        self.gemini = GeminiHelper(gemini_api_key)
        self.browser = None
        self.wait = None
        self.scraped_post_ids = set()  # Track scraped posts to avoid duplicates
        self.session_start_time = datetime.now()
    
    def setup_browser(self):
        """Setup Chrome browser"""
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        self.browser = webdriver.Chrome(options=options)
        self.browser.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.browser.set_window_size(1200, 800)
        self.wait = WebDriverWait(self.browser, 10)
    
    def take_screenshot(self):
        """Take screenshot and return as base64"""
        screenshot = self.browser.get_screenshot_as_png()
        return base64.b64encode(screenshot).decode('utf-8')
    
    def human_type(self, element, text):
        """Type like a human"""
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))
    
    def solve_login_captcha(self):
        """Solve login CAPTCHA using Gemini"""
        print("[*] CAPTCHA detected, analyzing with Gemini...")
        
        # Take screenshot
        screenshot = self.take_screenshot()
        
        # Get Gemini's analysis
        captcha_solution = self.gemini.solve_captcha(screenshot)
        print(f"[GEMINI] CAPTCHA Analysis: {captcha_solution}")
        
        try:
            # Try to parse as JSON
            if captcha_solution.startswith('{'):
                solution = json.loads(captcha_solution)
                captcha_type = solution.get('type', '').lower()
                action = solution.get('action', '')
                
                if 'puzzle' in captcha_type:
                    return self.solve_puzzle_captcha(solution)
                elif 'image' in captcha_type:
                    return self.solve_image_captcha(solution)
                elif 'text' in captcha_type:
                    return self.solve_text_captcha(solution)
            
        except json.JSONDecodeError:
            print("[!] Could not parse Gemini response as JSON")
        
        # Fallback: manual intervention
        print("[!] Could not solve CAPTCHA automatically")
        input("Please solve the CAPTCHA manually and press Enter...")
        return True
    
    def solve_puzzle_captcha(self, solution):
        """Solve puzzle-type CAPTCHA"""
        print("[*] Attempting to solve puzzle CAPTCHA...")
        
        try:
            # Look for puzzle pieces (common LinkedIn CAPTCHA)
            puzzle_pieces = self.browser.find_elements(By.CSS_SELECTOR, "[data-cy='puzzle-piece']")
            if not puzzle_pieces:
                # Try alternative selectors
                puzzle_pieces = self.browser.find_elements(By.CSS_SELECTOR, ".captcha-puzzle-piece")
            
            if puzzle_pieces:
                # Simple approach: try dragging the first piece to different positions
                piece = puzzle_pieces[0]
                actions = ActionChains(self.browser)
                
                # Try different drag positions based on Gemini's analysis
                details = solution.get('details', '')
                if 'right' in details.lower():
                    actions.drag_and_drop_by_offset(piece, 100, 0).perform()
                elif 'left' in details.lower():
                    actions.drag_and_drop_by_offset(piece, -100, 0).perform()
                elif 'down' in details.lower():
                    actions.drag_and_drop_by_offset(piece, 0, 100).perform()
                elif 'up' in details.lower():
                    actions.drag_and_drop_by_offset(piece, 0, -100).perform()
                
                time.sleep(2)
                return True
            
        except Exception as e:
            print(f"[!] Error solving puzzle: {e}")
        
        return False
    
    def solve_image_captcha(self, solution):
        """Solve image selection CAPTCHA"""
        print("[*] Attempting to solve image CAPTCHA...")
        
        # This would need more sophisticated image recognition
        # For now, fallback to manual
        return False
    
    def solve_text_captcha(self, solution):
        """Solve text-based CAPTCHA"""
        print("[*] Attempting to solve text CAPTCHA...")
        
        try:
            # Look for text input field
            text_input = self.browser.find_element(By.CSS_SELECTOR, "input[type='text']")
            text_to_type = solution.get('details', '')
            
            if text_to_type:
                self.human_type(text_input, text_to_type)
                return True
                
        except Exception as e:
            print(f"[!] Error solving text CAPTCHA: {e}")
        
        return False
    
    def autonomous_login(self, email, password):
        """Automated login with CAPTCHA handling"""
        print("[*] Starting autonomous login...")
        
        try:
            # Go to login page
            self.browser.get('https://www.linkedin.com/login')
            time.sleep(random.uniform(2, 4))
            
            # Enter email
            email_field = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            self.human_type(email_field, email)
            
            # Enter password
            password_field = self.browser.find_element(By.ID, "password")
            self.human_type(password_field, password)
            
            # Click login
            login_button = self.browser.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Wait and check for CAPTCHA or success
            time.sleep(random.uniform(3, 6))
            
            # Check if we're logged in
            current_url = self.browser.current_url
            if 'feed' in current_url or 'mynetwork' in current_url:
                print("[*] Login successful!")
                return True
            
            # Check for CAPTCHA
            page_source = self.browser.page_source.lower()
            captcha_indicators = ['captcha', 'puzzle', 'security check', 'verify']
            
            if any(indicator in page_source for indicator in captcha_indicators):
                if self.solve_login_captcha():
                    # Check again after solving
                    time.sleep(3)
                    if 'feed' in self.browser.current_url:
                        print("[*] Login successful after CAPTCHA!")
                        return True
            
            print("[!] Login failed or requires manual intervention")
            return False
            
        except Exception as e:
            print(f"[ERROR] Login error: {e}")
            return False
    
    def build_search_url(self, query_config):
        """Build search URL with proper parameters"""
        base_url = "https://www.linkedin.com/search/results/content/"
        keywords = query_config.get('keywords', '')
        date_posted = query_config.get('date_posted', '')
        
        # URL parameters
        params = {
            'keywords': keywords,
            'origin': 'FACETED_SEARCH',
            'sortBy': '"date_posted"'
        }
        
        # Add date filter if specified
        if date_posted:
            date_filter_map = {
                'past-24h': 'r86400',
                'past-week': 'r604800',
                'past-month': 'r2592000'
            }
            if date_posted in date_filter_map:
                params['datePosted'] = date_filter_map[date_posted]
        
        # Build URL
        url = base_url + '?' + '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
        return url
    
    def scrape_search_results(self, query_config, max_posts=50):
        """Scrape search results for a specific query"""
        query_name = query_config.get('name', 'unknown')
        keywords = query_config.get('keywords', '')
        
        print(f"\n[*] Scraping posts for query: {query_name}")
        print(f"[*] Keywords: {keywords}")
        
        # Build search URL
        search_url = self.build_search_url(query_config)
        
        # Navigate to search
        self.browser.get(search_url)
        time.sleep(random.uniform(3, 5))
        
        # Create CSV file for this query
        csv_file = f"linkedin_{query_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Query_Name', 'Post_ID', 'Author', 'Content', 'Time', 'URL', 'Scraped_At'])
        
        posts_found = 0
        scroll_attempts = 0
        max_scroll_attempts = 8
        
        while posts_found < max_posts and scroll_attempts < max_scroll_attempts:
            # Parse page
            soup = bs(self.browser.page_source, 'html.parser')
            
            # Find posts (try multiple selectors)
            posts = soup.find_all('div', {'class': 'feed-shared-update-v2'})
            if not posts:
                posts = soup.find_all('div', {'data-urn': lambda x: x and 'activity:' in x})
            if not posts:
                posts = soup.find_all('div', {'class': lambda x: x and 'update-v2' in x})
            
            new_posts = 0
            for post in posts:
                try:
                    # Extract post ID
                    post_id = post.get('data-urn', '').split(':')[-1] if post.get('data-urn') else None
                    if not post_id:
                        # Generate a unique ID based on content
                        content_preview = post.get_text()[:50] if post.get_text() else ""
                        post_id = f"post_{hash(content_preview)}_{posts_found}"
                    
                    # Skip if already scraped
                    if post_id in self.scraped_post_ids:
                        continue
                    
                    # Author
                    author_elem = post.find('span', {'class': 'update-components-actor__title'})
                    if not author_elem:
                        author_elem = post.find('span', {'class': lambda x: x and 'actor' in x and 'title' in x})
                    author = author_elem.get_text(strip=True) if author_elem else "Unknown"
                    
                    # Content
                    content_elem = post.find('div', {'class': 'update-components-text'})
                    if not content_elem:
                        content_elem = post.find('div', {'class': lambda x: x and 'text' in x})
                    content = content_elem.get_text(strip=True) if content_elem else ""
                    
                    # Time
                    time_elem = post.find('span', {'class': 'update-components-actor__sub-description'})
                    if not time_elem:
                        time_elem = post.find('span', {'class': lambda x: x and 'sub-description' in x})
                    post_time = time_elem.get_text(strip=True) if time_elem else ""
                    
                    # URL
                    post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{post_id}/"
                    
                    # Skip if content is too short (likely not a real post)
                    if len(content.strip()) < 20:
                        continue
                    
                    # Save to CSV
                    with open(csv_file, 'a', newline='', encoding='utf-8') as file:
                        writer = csv.writer(file)
                        writer.writerow([
                            query_name, 
                            post_id, 
                            author, 
                            content, 
                            post_time, 
                            post_url, 
                            datetime.now().isoformat()
                        ])
                    
                    # Add to scraped set
                    self.scraped_post_ids.add(post_id)
                    posts_found += 1
                    new_posts += 1
                    
                    if posts_found >= max_posts:
                        break
                        
                except Exception as e:
                    print(f"[!] Error processing post: {e}")
                    continue
            
            print(f"[*] Found {new_posts} new posts for {query_name}, total: {posts_found}")
            
            # Scroll for more posts
            if posts_found < max_posts:
                self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(3, 5))
                scroll_attempts += 1
                
                # Add some randomness to avoid detection
                if scroll_attempts % 3 == 0:
                    time.sleep(random.uniform(5, 10))
        
        print(f"[*] Query '{query_name}' complete! Found {posts_found} posts")
        return posts_found, csv_file
    
    def run_multiple_searches(self, email, password, search_queries, max_posts_per_query=50):
        """Run multiple search queries"""
        try:
            self.setup_browser()
            
            # Login
            if not self.autonomous_login(email, password):
                print("[ERROR] Login failed!")
                return
            
            # Wait a bit after login
            time.sleep(random.uniform(5, 10))
            
            # Create summary file
            summary_file = f"linkedin_scraping_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(summary_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['Query_Name', 'Keywords', 'Posts_Found', 'CSV_File', 'Scraped_At'])
            
            total_posts = 0
            successful_queries = 0
            
            # Process each query
            for i, query_config in enumerate(search_queries):
                query_name = query_config.get('name', f'query_{i+1}')
                
                try:
                    print(f"\n{'='*50}")
                    print(f"Processing query {i+1}/{len(search_queries)}: {query_name}")
                    print(f"{'='*50}")
                    
                    # Scrape posts for this query
                    posts_count, csv_file = self.scrape_search_results(query_config, max_posts_per_query)
                    
                    # Update summary
                    with open(summary_file, 'a', newline='', encoding='utf-8') as file:
                        writer = csv.writer(file)
                        writer.writerow([
                            query_name,
                            query_config.get('keywords', ''),
                            posts_count,
                            csv_file,
                            datetime.now().isoformat()
                        ])
                    
                    total_posts += posts_count
                    successful_queries += 1
                    
                    # Wait between queries to avoid being blocked
                    if i < len(search_queries) - 1:  # Don't wait after last query
                        wait_time = random.uniform(10, 20)
                        print(f"[*] Waiting {wait_time:.1f} seconds before next query...")
                        time.sleep(wait_time)
                
                except Exception as e:
                    print(f"[ERROR] Failed to process query '{query_name}': {e}")
                    continue
            
            print(f"\n{'='*50}")
            print(f"SCRAPING COMPLETE!")
            print(f"{'='*50}")
            print(f"Total queries processed: {successful_queries}/{len(search_queries)}")
            print(f"Total posts scraped: {total_posts}")
            print(f"Unique posts: {len(self.scraped_post_ids)}")
            print(f"Summary file: {summary_file}")
            print(f"Session duration: {datetime.now() - self.session_start_time}")
            
        except Exception as e:
            print(f"[ERROR] Scraping failed: {e}")
        finally:
            if self.browser:
                input("\nPress Enter to close browser...")
                self.browser.quit()

def main():
    """Main function with multiple search queries"""
    
    # Configuration
    GEMINI_API_KEY = 'AIzaSyBlqj1hHoN8VxzYmabE65pBQDIt-s4d7JA'
    EMAIL = 'abhifor1x@gmail.com'
    PASSWORD = 'Rahil@4500'
    
    # Multiple search queries
    SEARCH_QUERIES = [
        {
            "name": "ML_Hiring_Ahmedabad",
            "keywords": '#hiring "machine learning" Ahmedabad',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "AI_Jobs_Ahmedabad",
            "keywords": '#hiring "artificial intelligence" Ahmedabad',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "ML_Hiring",
            "keywords": '#hiring "Machine Learning"',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "AI_Jobs",
            "keywords": '#hiring "artificial intelligence"',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Computer_Vision_Engineer_India",
            "keywords": '#hiring ("computer vision" OR "OpenCV" OR "image processing") India',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "ML_Engineer_Gujarat",
            "keywords": '#hiring ("machine learning engineer" OR "ML engineer") (Gujarat OR Ahmedabad OR Rajkot)',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Data_Scientist_Entry_Level",
            "keywords": '#hiring ("data scientist" OR "data science") ("entry level" OR "junior" OR "fresher")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Python_Developer_ML",
            "keywords": '#hiring "python developer" AND ("machine learning" OR "deep learning" OR "AI")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "AI_Research_Intern",
            "keywords": '#hiring ("AI research" OR "machine learning research" OR "research intern")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Deep_Learning_Engineer",
            "keywords": '#hiring ("deep learning" OR "neural networks" OR "TensorFlow" OR "PyTorch")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Computer_Vision_Ahmedabad",
            "keywords": '#hiring ("computer vision" OR "facial recognition" OR "image processing") Ahmedabad',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Full_Stack_ML_Developer",
            "keywords": '#hiring "full stack" AND ("machine learning" OR "AI" OR "Django")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Time_Series_Analyst",
            "keywords": '#hiring ("time series" OR "stock prediction" OR "financial modeling" OR "quantitative analyst")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Data_Engineer_ML",
            "keywords": '#hiring "data engineer" AND ("machine learning" OR "ML pipeline" OR "data preprocessing")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "AI_Startup_India",
            "keywords": '#hiring ("AI startup" OR "ML startup" OR "artificial intelligence startup") India',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Computer_Vision_Remote",
            "keywords": '#hiring ("computer vision" OR "OpenCV" OR "image recognition") ("remote" OR "work from home")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "NLP_Engineer",
            "keywords": '#hiring ("NLP" OR "natural language processing" OR "LLM" OR "RAG")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Business_Intelligence_Analyst",
            "keywords": '#hiring ("business intelligence" OR "BI analyst" OR "data visualization" OR "Tableau")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "ML_Internship_2025",
            "keywords": '#hiring ("machine learning intern" OR "AI intern" OR "data science intern") 2025',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Django_Developer_ML",
            "keywords": '#hiring "Django" AND ("machine learning" OR "AI" OR "data science")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Fintech_ML_Engineer",
            "keywords": '#hiring "fintech" AND ("machine learning" OR "AI" OR "data science" OR "quantitative")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Research_Scientist_AI",
            "keywords": '#hiring ("research scientist" OR "AI researcher" OR "ML researcher")',
            "location": None,
            "date_posted": "past-24h"
        },
        {
            "name": "Software_Engineer_AI",
            "keywords": '#hiring "software engineer" AND ("AI" OR "machine learning" OR "computer vision")',
            "location": None,
            "date_posted": "past-24h"
        }
    ]
    
    # Configuration
    MAX_POSTS_PER_QUERY = 50
    
    print(f"[*] Starting LinkedIn scraper with {len(SEARCH_QUERIES)} search queries")
    print(f"[*] Max posts per query: {MAX_POSTS_PER_QUERY}")
    
    # Run scraper
    scraper = EnhancedLinkedInScraper(GEMINI_API_KEY)
    scraper.run_multiple_searches(EMAIL, PASSWORD, SEARCH_QUERIES, MAX_POSTS_PER_QUERY)

if __name__ == "__main__":
    main()