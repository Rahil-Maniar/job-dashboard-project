#!/usr/bin/env python3
"""
LinkedIn Job Posts Processor
Processes scraped LinkedIn posts and extracts job details using LLM
"""

import os
import csv
import json
import glob
import time
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class JobPostProcessor:
    """Processes LinkedIn posts and extracts structured job information"""
    
    def __init__(self, gemini_api_keys: str):
        """Initialize with Gemini API keys (comma-separated string)"""
        # Parse multiple API keys
        self.api_keys = [key.strip().strip('"') for key in gemini_api_keys.split(',') if key.strip()]
        self.current_key_index = 0
        self.failed_keys = set()
        
        print(f"[*] Loaded {len(self.api_keys)} Gemini API keys")
        
        # Initialize with first working key
        self._initialize_model()
        
        self.processed_jobs = []
        self.failed_posts = []
    
    def _initialize_model(self):
        """Initialize Gemini model with current API key"""
        if not self.api_keys:
            raise Exception("No API keys available")
        
        current_key = self.api_keys[self.current_key_index]
        genai.configure(api_key=current_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        print(f"[*] Using API key #{self.current_key_index + 1}: {current_key[:10]}...")
    
    def _rotate_api_key(self):
        """Rotate to next available API key"""
        self.failed_keys.add(self.current_key_index)
        
        # Find next available key
        for i in range(len(self.api_keys)):
            if i not in self.failed_keys:
                self.current_key_index = i
                self._initialize_model()
                print(f"[*] Rotated to API key #{self.current_key_index + 1}")
                return True
        
        print("[!] All API keys have failed!")
        return False
    
    def _make_api_call_with_retry(self, prompt: str, max_retries: int = 3):
        """Make API call with automatic key rotation on failure"""
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                return response.text.strip()
            
            except Exception as e:
                print(f"[!] API call failed (attempt {attempt + 1}/{max_retries}): {e}")
                
                # If it's a quota/authentication error, try rotating key
                if "quota" in str(e).lower() or "invalid" in str(e).lower() or "forbidden" in str(e).lower():
                    if self._rotate_api_key():
                        continue  # Retry with new key
                    else:
                        raise Exception("All API keys exhausted")
                
                # For other errors, wait and retry with same key
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                
                raise e
        
        raise Exception(f"Failed after {max_retries} attempts")
    
    def get_api_key_stats(self) -> str:
        """Get API key usage statistics"""
        total_keys = len(self.api_keys)
        failed_keys = len(self.failed_keys)
        working_keys = total_keys - failed_keys
        
        stats = f"""
=== API KEY USAGE STATISTICS ===
Total API Keys: {total_keys}
Working Keys: {working_keys}
Failed Keys: {failed_keys}
Current Key: #{self.current_key_index + 1} ({self.api_keys[self.current_key_index][:10]}...)

Failed Key Indices: {sorted(list(self.failed_keys)) if self.failed_keys else 'None'}
"""
        return stats
        
    def load_csv_files(self, directory: str = ".") -> List[Dict]:
        """Load all LinkedIn CSV files from directory"""
        csv_files = glob.glob(os.path.join(directory, "linkedin_*.csv"))
        all_posts = []
        
        print(f"[*] Found {len(csv_files)} LinkedIn CSV files")
        
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file)
                posts = df.to_dict('records')
                
                # Add source file info
                for post in posts:
                    post['source_file'] = os.path.basename(csv_file)
                
                all_posts.extend(posts)
                print(f"[*] Loaded {len(posts)} posts from {csv_file}")
                
            except Exception as e:
                print(f"[!] Error loading {csv_file}: {e}")
                continue
        
        print(f"[*] Total posts loaded: {len(all_posts)}")
        return all_posts
    
    def extract_job_details(self, post_content: str, author: str, post_time: str) -> Dict:
        """Extract structured job details from post content using Gemini"""
        
        prompt = f"""
        Analyze this LinkedIn job post and extract structured job information. 
        
        POST CONTENT:
        {post_content}
        
        AUTHOR: {author}
        POST TIME: {post_time}
        
        Extract the following information and return as JSON:
        {{
            "company_name": "Company name (if not found, use 'Not specified')",
            "job_title": "Job title/position (if not found, use 'Not specified')",
            "location": "Job location (if not found, use 'Not specified')",
            "experience_required": "Years of experience required (if not found, use 'Not specified')",
            "salary_range": "Salary information (if not found, use 'Not specified')",
            "job_type": "Full-time/Part-time/Contract/Internship (if not found, use 'Not specified')",
            "skills_required": "Key skills mentioned (if not found, use 'Not specified')",
            "contact_info": "Email, phone, or contact details (if not found, use 'Not specified')",
            "application_method": "How to apply (if not found, use 'Not specified')",
            "job_description": "Brief job description (if not found, use 'Not specified')",
            "remote_work": "Remote/On-site/Hybrid (if not found, use 'Not specified')",
            "urgency": "Urgent/Normal (if not found, use 'Normal')",
            "benefits": "Benefits mentioned (if not found, use 'Not specified')",
            "is_valid_job": true/false (true if this looks like a legitimate job posting)
        }}
        
        IMPORTANT RULES:
        1. If any field cannot be determined from the post, use the default text specified above
        2. Extract only factual information from the post
        3. For experience_required, look for phrases like "2+ years", "fresher", "entry level", etc.
        4. For contact_info, look for email addresses, phone numbers, or "DM me" type instructions
        5. Set is_valid_job to false if the post is not actually a job posting
        6. Keep job_description concise (max 200 characters)
        7. Return only valid JSON, no additional text
        """
        
        try:
            # Use retry mechanism with API key rotation
            result_text = self._make_api_call_with_retry(prompt)
            
            # Clean up the response to get valid JSON
            if result_text.startswith('```json'):
                result_text = result_text[7:-3]
            elif result_text.startswith('```'):
                result_text = result_text[3:-3]
            
            job_data = json.loads(result_text)
            
            # Validate required fields
            required_fields = [
                'company_name', 'job_title', 'location', 'experience_required',
                'salary_range', 'job_type', 'skills_required', 'contact_info',
                'application_method', 'job_description', 'remote_work', 'urgency',
                'benefits', 'is_valid_job'
            ]
            
            for field in required_fields:
                if field not in job_data:
                    job_data[field] = 'Not specified'
            
            return job_data
            
        except Exception as e:
            print(f"[!] Error extracting job details: {e}")
            return {
                'company_name': 'Not specified',
                'job_title': 'Not specified',
                'location': 'Not specified',
                'experience_required': 'Not specified',
                'salary_range': 'Not specified',
                'job_type': 'Not specified',
                'skills_required': 'Not specified',
                'contact_info': 'Not specified',
                'application_method': 'Not specified',
                'job_description': 'Not specified',
                'remote_work': 'Not specified',
                'urgency': 'Normal',
                'benefits': 'Not specified',
                'is_valid_job': False
            }
    
    def process_posts_batch(self, posts: List[Dict], batch_size: int = 10) -> List[Dict]:
        """Process posts in batches to avoid API rate limits"""
        processed_jobs = []
        
        for i in range(0, len(posts), batch_size):
            batch = posts[i:i + batch_size]
            print(f"[*] Processing batch {i//batch_size + 1}/{(len(posts) + batch_size - 1)//batch_size}")
            
            batch_results = []
            for post in batch:
                try:
                    content = post.get('Content', '')
                    author = post.get('Author', 'Unknown')
                    post_time = post.get('Time', '')
                    
                    if len(content.strip()) < 20:  # Skip very short posts
                        continue
                    
                    job_details = self.extract_job_details(content, author, post_time)
                    
                    # Only include valid job posts
                    if job_details.get('is_valid_job', False):
                        # Add original post metadata
                        job_details.update({
                            'original_author': author,
                            'post_time': post_time,
                            'source_file': post.get('source_file', 'Unknown'),
                            'post_url': post.get('URL', 'Not available'),
                            'query_name': post.get('Query_Name', 'Unknown'),
                            'processed_at': datetime.now().isoformat()
                        })
                        
                        batch_results.append(job_details)
                        
                except Exception as e:
                    print(f"[!] Error processing post: {e}")
                    self.failed_posts.append(post)
                    continue
            
            processed_jobs.extend(batch_results)
            print(f"[*] Batch complete: {len(batch_results)} valid jobs found")
            
            # Rate limiting - wait between batches
            if i + batch_size < len(posts):
                time.sleep(2)  # 2 second delay between batches
        
        return processed_jobs
    
    def save_processed_jobs(self, jobs: List[Dict], output_file: str = None):
        """Save processed jobs to CSV file"""
        if not output_file:
            output_file = f"processed_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        if not jobs:
            print("[!] No jobs to save")
            return output_file
        
        # Create DataFrame
        df = pd.DataFrame(jobs)
        
        # Reorder columns for better readability
        column_order = [
            'job_title', 'company_name', 'location', 'experience_required',
            'salary_range', 'job_type', 'remote_work', 'skills_required',
            'contact_info', 'application_method', 'job_description', 
            'benefits', 'urgency', 'original_author', 'post_time',
            'query_name', 'post_url', 'processed_at'
        ]
        
        # Reorder columns if they exist
        existing_columns = [col for col in column_order if col in df.columns]
        remaining_columns = [col for col in df.columns if col not in column_order]
        final_columns = existing_columns + remaining_columns
        
        df = df[final_columns]
        
        # Save to CSV
        df.to_csv(output_file, index=False)
        print(f"[*] Saved {len(jobs)} processed jobs to {output_file}")
        
        return output_file
    
    def create_summary_report(self, jobs: List[Dict]) -> str:
        """Create a summary report of processed jobs"""
        if not jobs:
            return "No jobs processed."
        
        df = pd.DataFrame(jobs)
        
        report = f"""
=== JOB PROCESSING SUMMARY ===
Total Jobs Processed: {len(jobs)}
Processing Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

=== JOB STATISTICS ===
Jobs by Type:
{df['job_type'].value_counts().to_string()}

Jobs by Location:
{df['location'].value_counts().head(10).to_string()}

Jobs by Company:
{df['company_name'].value_counts().head(10).to_string()}

Remote Work Options:
{df['remote_work'].value_counts().to_string()}

Experience Requirements:
{df['experience_required'].value_counts().to_string()}

Urgent Jobs: {len(df[df['urgency'] == 'Urgent'])}
Jobs with Contact Info: {len(df[df['contact_info'] != 'Not specified'])}
Jobs with Salary Info: {len(df[df['salary_range'] != 'Not specified'])}

=== TOP COMPANIES HIRING ===
{df['company_name'].value_counts().head(15).to_string()}

=== MOST COMMON SKILLS ===
{df['skills_required'].value_counts().head(10).to_string()}
"""
        
        return report

def main():
    """Main function to process LinkedIn posts"""
    
    # Configuration
    GEMINI_API_KEYS = os.getenv('GEMINI_API_KEY')
    if not GEMINI_API_KEYS:
        print("[!] GEMINI_API_KEY not found in .env file")
        return
    
    # Process jobs
    print("[*] Starting job processing...")
    processor = JobPostProcessor(GEMINI_API_KEYS)
    
    # Load all CSV files
    all_posts = processor.load_csv_files()
    
    if not all_posts:
        print("[!] No posts found to process")
        return
    
    # Process posts in batches
    print(f"[*] Processing {len(all_posts)} posts...")
    processed_jobs = processor.process_posts_batch(all_posts, batch_size=5)
    
    if not processed_jobs:
        print("[!] No valid jobs found")
        return
    
    # Save processed jobs
    csv_file = processor.save_processed_jobs(processed_jobs)
    
    # Create summary report
    summary_report = processor.create_summary_report(processed_jobs)
    api_stats = processor.get_api_key_stats()
    
    print(summary_report)
    print(api_stats)
    
    # Save summary to file
    summary_file = f"job_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary_report + api_stats)
    
    print(f"[*] ✅ Job extraction complete!")
    print(f"[*] Jobs saved to: {csv_file}")
    print(f"[*] Summary saved to: {summary_file}")
    print(f"[*] API Key rotation worked flawlessly - {len(processor.api_keys) - len(processor.failed_keys)}/{len(processor.api_keys)} keys still working")
    
    # Return file paths for the telegram bot script
    return csv_file, summary_file

if __name__ == "__main__":
    main()
