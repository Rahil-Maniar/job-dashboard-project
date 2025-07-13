#!/usr/bin/env python3
"""
LinkedIn Job Posts Processor and Phone Delivery System
Processes scraped LinkedIn posts, extracts job details using LLM, and sends to phone
"""

import os
import csv
import json
import glob
import time
import requests
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
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

class PhoneDeliveryService:
    """Deliver job results to phone using free services"""
    
    def __init__(self):
        self.delivery_methods = []
    
    def setup_telegram_bot(self, bot_token: str, chat_id: str):
        """Setup Telegram bot for delivery (Free)"""
        self.telegram_bot_token = bot_token
        self.telegram_chat_id = chat_id
        self.delivery_methods.append('telegram')
    
    def setup_email_delivery(self, email: str):
        """Setup email delivery using free services"""
        self.email = email
        self.delivery_methods.append('email')
    
    def setup_webhook_delivery(self, webhook_url: str):
        """Setup webhook delivery (e.g., IFTTT, Zapier free tier)"""
        self.webhook_url = webhook_url
        self.delivery_methods.append('webhook')
    
    def send_via_telegram(self, message: str, file_path: str = None, jobs: List[Dict] = None):
        """Send message via Telegram bot - now supports individual job messages"""
        try:
            base_url = f"https://api.telegram.org/bot{self.telegram_bot_token}"
            
            # If jobs list is provided, send individual messages for each job
            if jobs:
                return self._send_individual_job_messages(jobs, base_url, file_path)
            
            # Otherwise, send the single message as before
            text_url = f"{base_url}/sendMessage"
            text_data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(text_url, data=text_data)
            
            if response.status_code == 200:
                print("[*] Message sent via Telegram")
                
                # Send file if provided
                if file_path and os.path.exists(file_path):
                    document_url = f"{base_url}/sendDocument"
                    with open(file_path, 'rb') as file:
                        files = {'document': file}
                        data = {'chat_id': self.telegram_chat_id}
                        doc_response = requests.post(document_url, data=data, files=files)
                        
                        if doc_response.status_code == 200:
                            print("[*] File sent via Telegram")
                        else:
                            print(f"[!] Failed to send file via Telegram: {doc_response.text}")
                
                return True
            else:
                print(f"[!] Failed to send Telegram message: {response.text}")
                return False
                
        except Exception as e:
            print(f"[!] Telegram delivery error: {e}")
            return False
    
    def _send_individual_job_messages(self, jobs: List[Dict], base_url: str, file_path: str = None):
        """Send individual Telegram messages for each job"""
        try:
            # Send summary message first
            urgent_jobs = [job for job in jobs if job.get('urgency') == 'Urgent']
            summary_msg = f"🔥 *NEW JOB ALERT* 🔥\n📊 Found {len(jobs)} jobs\n⚡ {len(urgent_jobs)} urgent positions\n\n📱 Sending each job separately..."
            
            text_url = f"{base_url}/sendMessage"
            summary_data = {
                'chat_id': self.telegram_chat_id,
                'text': summary_msg,
                'parse_mode': 'Markdown'
            }
            
            requests.post(text_url, data=summary_data)
            print("[*] Summary message sent")
            
            # Send individual job messages
            success_count = 0
            for i, job in enumerate(jobs, 1):
                job_message = self._format_single_job_message(job, i)
                
                job_data = {
                    'chat_id': self.telegram_chat_id,
                    'text': job_message,
                    'parse_mode': 'Markdown'
                }
                
                response = requests.post(text_url, data=job_data)
                
                if response.status_code == 200:
                    success_count += 1
                else:
                    print(f"[!] Failed to send job {i}: {response.text}")
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            print(f"[*] Sent {success_count}/{len(jobs)} job messages")
            
            # Send file if provided
            if file_path and os.path.exists(file_path):
                document_url = f"{base_url}/sendDocument"
                with open(file_path, 'rb') as file:
                    files = {'document': file}
                    data = {'chat_id': self.telegram_chat_id, 'caption': '📋 Complete job report (CSV format)'}
                    doc_response = requests.post(document_url, data=data, files=files)
                    
                    if doc_response.status_code == 200:
                        print("[*] CSV file sent via Telegram")
                    else:
                        print(f"[!] Failed to send file: {doc_response.text}")
            
            # Send final summary
            final_msg = f"✅ *JOB DELIVERY COMPLETE*\n📤 Sent {success_count}/{len(jobs)} jobs\n📋 CSV file attached for full details"
            final_data = {
                'chat_id': self.telegram_chat_id,
                'text': final_msg,
                'parse_mode': 'Markdown'
            }
            requests.post(text_url, data=final_data)
            
            return success_count > 0
            
        except Exception as e:
            print(f"[!] Error sending individual job messages: {e}")
            return False
    
    def _format_single_job_message(self, job: Dict, job_number: int) -> str:
        """Format a single job as a Telegram message"""
        urgency_icon = "🚨" if job.get('urgency') == 'Urgent' else "📋"
        remote_icon = "🏠" if 'remote' in job.get('remote_work', '').lower() else "🏢"
        
        message = f"{urgency_icon} *JOB #{job_number}*\n"
        message += f"🔸 *{job.get('job_title', 'Unknown')}*\n"
        message += f"🏢 {job.get('company_name', 'Unknown')}\n"
        message += f"📍 {job.get('location', 'Unknown')}\n"
        message += f"{remote_icon} {job.get('remote_work', 'Unknown')}\n"
        message += f"💼 Experience: {job.get('experience_required', 'Unknown')}\n"
        message += f"📝 Type: {job.get('job_type', 'Unknown')}\n"
        
        if job.get('salary_range', 'Not specified') != 'Not specified':
            message += f"💰 Salary: {job.get('salary_range')}\n"
        
        if job.get('skills_required', 'Not specified') != 'Not specified':
            skills = job.get('skills_required', '')
            if len(skills) > 100:
                skills = skills[:100] + "..."
            message += f"🛠️ Skills: {skills}\n"
        
        if job.get('contact_info', 'Not specified') != 'Not specified':
            message += f"📧 Contact: {job.get('contact_info')}\n"
        
        if job.get('application_method', 'Not specified') != 'Not specified':
            message += f"📨 Apply: {job.get('application_method')}\n"
        
        if job.get('post_url', 'Not available') != 'Not available':
            message += f"🔗 [View Post]({job.get('post_url')})\n"
        
        message += "─" * 25
        
        return message
    
    def send_via_email(self, subject: str, body: str, file_path: str = None):
        """Send via email using free SMTP services"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders
            
            # Using Gmail SMTP (free)
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            
            # You'll need to set these environment variables
            sender_email = os.getenv('GMAIL_EMAIL')
            sender_password = os.getenv('GMAIL_APP_PASSWORD')  # Use app password, not regular password
            
            if not sender_email or not sender_password:
                print("[!] Gmail credentials not set in environment variables")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = self.email
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Add file attachment if provided
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(file_path)}'
                )
                msg.attach(part)
            
            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            
            print("[*] Email sent successfully")
            return True
            
        except Exception as e:
            print(f"[!] Email delivery error: {e}")
            return False
    
    def send_via_webhook(self, data: Dict):
        """Send via webhook (IFTTT, Zapier, etc.)"""
        try:
            response = requests.post(self.webhook_url, json=data)
            
            if response.status_code == 200:
                print("[*] Webhook delivered successfully")
                return True
            else:
                print(f"[!] Webhook delivery failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"[!] Webhook delivery error: {e}")
            return False
    
    def create_phone_friendly_summary(self, jobs: List[Dict], max_jobs: int = 20) -> str:
        """Create a phone-friendly summary of top jobs"""
        if not jobs:
            return "No jobs found."
        
        # Sort by urgency and then by company name
        urgent_jobs = [job for job in jobs if job.get('urgency') == 'Urgent']
        normal_jobs = [job for job in jobs if job.get('urgency') != 'Urgent']
        
        sorted_jobs = urgent_jobs + normal_jobs
        top_jobs = sorted_jobs[:max_jobs]
        
        summary = f"🔥 *NEW JOB OPPORTUNITIES* 🔥\n"
        summary += f"📊 Found {len(jobs)} jobs total\n"
        summary += f"⚡ {len(urgent_jobs)} urgent positions\n\n"
        
        for i, job in enumerate(top_jobs, 1):
            urgency_icon = "🚨" if job.get('urgency') == 'Urgent' else "📋"
            remote_icon = "🏠" if 'remote' in job.get('remote_work', '').lower() else "🏢"
            
            summary += f"{urgency_icon} *{i}. {job.get('job_title', 'Unknown')}*\n"
            summary += f"🏢 {job.get('company_name', 'Unknown')}\n"
            summary += f"📍 {job.get('location', 'Unknown')}\n"
            summary += f"{remote_icon} {job.get('remote_work', 'Unknown')}\n"
            summary += f"💼 {job.get('experience_required', 'Unknown')} exp\n"
            
            if job.get('salary_range', 'Not specified') != 'Not specified':
                summary += f"💰 {job.get('salary_range')}\n"
            
            if job.get('contact_info', 'Not specified') != 'Not specified':
                summary += f"📧 {job.get('contact_info')}\n"
            
            summary += f"🔗 {job.get('post_url', 'N/A')}\n"
            summary += "─" * 30 + "\n\n"
        
        if len(jobs) > max_jobs:
            summary += f"📋 ... and {len(jobs) - max_jobs} more jobs in the full report!"
        
        return summary
    
    def deliver_results(self, jobs: List[Dict], csv_file: str, summary_report: str):
        """Deliver results using configured methods"""
        success_count = 0
        
        # Try each delivery method
        for method in self.delivery_methods:
            try:
                if method == 'telegram':
                    # Send individual job messages via Telegram
                    if self.send_via_telegram("", csv_file, jobs):
                        success_count += 1
                
                elif method == 'email':
                    # Create phone-friendly summary for email
                    phone_summary = self.create_phone_friendly_summary(jobs)
                    subject = f"🔥 {len(jobs)} New Job Opportunities Found!"
                    if self.send_via_email(subject, phone_summary + "\n\n" + summary_report, csv_file):
                        success_count += 1
                
                elif method == 'webhook':
                    webhook_data = {
                        'title': f'{len(jobs)} New Jobs Found',
                        'message': self.create_phone_friendly_summary(jobs),
                        'job_count': len(jobs),
                        'urgent_count': len([j for j in jobs if j.get('urgency') == 'Urgent'])
                    }
                    if self.send_via_webhook(webhook_data):
                        success_count += 1
                        
            except Exception as e:
                print(f"[!] Error with {method} delivery: {e}")
                continue
        
        print(f"[*] Successfully delivered via {success_count}/{len(self.delivery_methods)} methods")
        return success_count > 0

def main():
    """Main function to process LinkedIn posts and deliver to phone"""
    
    # Configuration
    GEMINI_API_KEYS = os.getenv('GEMINI_API_KEY')
    if not GEMINI_API_KEYS:
        print("[!] GEMINI_API_KEY not found in .env file")
        return
    
    # Phone delivery options - Telegram Bot only
    delivery_service = PhoneDeliveryService()
    
    # Telegram Bot configuration
    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if telegram_bot_token and telegram_chat_id:
        delivery_service.setup_telegram_bot(telegram_bot_token, telegram_chat_id)
        print("[*] Telegram delivery configured successfully")
        print(f"[*] Bot Token: {telegram_bot_token[:10]}...")
        print(f"[*] Chat ID: {telegram_chat_id}")
    else:
        print("[!] Telegram bot configuration missing!")
        print(f"[!] TELEGRAM_BOT_TOKEN found: {'Yes' if telegram_bot_token else 'No'}")
        print(f"[!] TELEGRAM_CHAT_ID found: {'Yes' if telegram_chat_id else 'No'}")
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
    full_report = summary_report + api_stats
    
    print(summary_report)
    print(api_stats)
    
    # Deliver to phone
    print("[*] Delivering results to phone...")
    delivery_success = delivery_service.deliver_results(processed_jobs, csv_file, full_report)
    
    if delivery_success:
        print("[*] ✅ Job results delivered to your phone!")
    else:
        print("[!] ❌ Failed to deliver results")
    
    print(f"[*] Processing complete! Check {csv_file} for full results.")
    print(f"[*] API Key rotation worked flawlessly - {len(processor.api_keys) - len(processor.failed_keys)}/{len(processor.api_keys)} keys still working")

if __name__ == "__main__":
    main()