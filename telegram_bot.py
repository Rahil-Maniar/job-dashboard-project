#!/usr/bin/env python3
"""
Telegram Job Notification Bot
Sends job notifications via Telegram from processed job data
"""

import os
import sys
import json
import time
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class TelegramJobBot:
    """Send job notifications via Telegram"""
    
    def __init__(self, bot_token: str, chat_id: str):
        """Initialize Telegram bot"""
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        # Test bot connection
        self._test_connection()
    
    def _test_connection(self):
        """Test Telegram bot connection"""
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url)
            
            if response.status_code == 200:
                bot_info = response.json()
                print(f"[*] Bot connected: @{bot_info['result']['username']}")
            else:
                print(f"[!] Bot connection failed: {response.text}")
                sys.exit(1)
                
        except Exception as e:
            print(f"[!] Error testing bot connection: {e}")
            sys.exit(1)
    
    def load_jobs_from_csv(self, csv_file: str) -> List[Dict]:
        """Load processed jobs from CSV file"""
        try:
            df = pd.read_csv(csv_file)
            jobs = df.to_dict('records')
            print(f"[*] Loaded {len(jobs)} jobs from {csv_file}")
            return jobs
        except Exception as e:
            print(f"[!] Error loading jobs from CSV: {e}")
            return []
    
    def send_message(self, message: str) -> bool:
        """Send a single message via Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                return True
            else:
                print(f"[!] Failed to send message: {response.text}")
                return False
                
        except Exception as e:
            print(f"[!] Error sending message: {e}")
            return False
    
    def send_document(self, file_path: str, caption: str = "") -> bool:
        """Send a document via Telegram"""
        try:
            url = f"{self.base_url}/sendDocument"
            
            with open(file_path, 'rb') as file:
                files = {'document': file}
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption
                }
                
                response = requests.post(url, data=data, files=files)
                
                if response.status_code == 200:
                    print(f"[*] Document sent: {file_path}")
                    return True
                else:
                    print(f"[!] Failed to send document: {response.text}")
                    return False
                    
        except Exception as e:
            print(f"[!] Error sending document: {e}")
            return False
    
    def format_job_message(self, job: Dict, job_number: int) -> str:
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
            app_method = job.get('application_method', '')
            if len(app_method) > 100:
                app_method = app_method[:100] + "..."
            message += f"📨 Apply: {app_method}\n"
        
        if job.get('post_url', 'Not available') != 'Not available':
            message += f"🔗 [View Post]({job.get('post_url')})\n"
        
        message += "─" * 25
        
        return message
    
    def create_summary_message(self, jobs: List[Dict]) -> str:
        """Create a summary message of all jobs"""
        urgent_jobs = [job for job in jobs if job.get('urgency') == 'Urgent']
        
        summary = f"🔥 *NEW JOB ALERT* 🔥\n"
        summary += f"📊 Found {len(jobs)} jobs total\n"
        summary += f"⚡ {len(urgent_jobs)} urgent positions\n\n"
        summary += f"📱 Sending each job separately...\n"
        summary += f"📋 Complete CSV report will follow\n"
        summary += "─" * 30
        
        return summary
    
    def create_completion_message(self, jobs: List[Dict], success_count: int) -> str:
        """Create a completion message"""
        completion = f"✅ *JOB DELIVERY COMPLETE*\n"
        completion += f"📤 Sent {success_count}/{len(jobs)} jobs successfully\n"
        completion += f"📋 CSV file attached for full details\n"
        completion += f"⏰ Delivered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return completion
    
    def send_job_notifications(self, jobs: List[Dict], csv_file: str = None, summary_file: str = None) -> bool:
        """Send individual job notifications via Telegram"""
        try:
            # Send initial summary
            summary_msg = self.create_summary_message(jobs)
            self.send_message(summary_msg)
            print("[*] Summary message sent")
            
            # Send individual job messages
            success_count = 0
            for i, job in enumerate(jobs, 1):
                job_message = self.format_job_message(job, i)
                
                if self.send_message(job_message):
                    success_count += 1
                else:
                    print(f"[!] Failed to send job {i}")
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            print(f"[*] Sent {success_count}/{len(jobs)} job messages")
            
            # Send CSV file if provided
            if csv_file and os.path.exists(csv_file):
                if self.send_document(csv_file, '📋 Complete job report (CSV format)'):
                    print("[*] CSV file sent")
                else:
                    print("[!] Failed to send CSV file")
            
            # Send summary file if provided
            if summary_file and os.path.exists(summary_file):
                if self.send_document(summary_file, '📊 Job processing summary'):
                    print("[*] Summary file sent")
                else:
                    print("[!] Failed to send summary file")
            
            # Send completion message
            completion_msg = self.create_completion_message(jobs, success_count)
            self.send_message(completion_msg)
            
            return success_count > 0
            
        except Exception as e:
            print(f"[!] Error sending job notifications: {e}")
            return False

def main():
    """Main function to send job notifications"""
    
    # Check if CSV file is provided as argument
    if len(sys.argv) < 2:
        print("Usage: python telegram_bot.py <csv_file> [summary_file]")
        print("Example: python telegram_bot.py processed_jobs_20250712_034751.csv job_summary_20250712_034751.txt")
        return
    
    csv_file = sys.argv[1]
    summary_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Verify CSV file exists
    if not os.path.exists(csv_file):
        print(f"[!] CSV file not found: {csv_file}")
        return
    
    # Configuration from environment variables
    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not telegram_bot_token or not telegram_chat_id:
        print("[!] Telegram bot configuration missing!")
        print(f"[!] TELEGRAM_BOT_TOKEN found: {'Yes' if telegram_bot_token else 'No'}")
        print(f"[!] TELEGRAM_CHAT_ID found: {'Yes' if telegram_chat_id else 'No'}")
        return
    
    # Initialize bot
    print("[*] Initializing Telegram bot...")
    bot = TelegramJobBot(telegram_bot_token, telegram_chat_id)
    
    # Load jobs from CSV
    jobs = bot.load_jobs_from_csv(csv_file)
    
    if not jobs:
        print("[!] No jobs found in CSV file")
        return
    
    # Send notifications
    print(f"[*] Sending notifications for {len(jobs)} jobs...")
    success = bot.send_job_notifications(jobs, csv_file, summary_file)
    
    if success:
        print("[*] ✅ Job notifications sent successfully!")
    else:
        print("[!] ❌ Failed to send job notifications")

if __name__ == "__main__":
    main()
