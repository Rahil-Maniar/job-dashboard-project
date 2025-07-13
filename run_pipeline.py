#!/usr/bin/env python3
"""
Job Processing Pipeline Runner
Runs job extraction followed by Telegram notifications
"""

import subprocess
import sys
import os
from datetime import datetime

def run_command(command, description):
    """Run a command and handle output"""
    print(f"\n{'='*50}")
    print(f"[*] {description}")
    print(f"{'='*50}")
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        # Print output
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print(f"[!] Errors: {result.stderr}")
        
        if result.returncode == 0:
            print(f"[*] ✅ {description} completed successfully")
            return True
        else:
            print(f"[!] ❌ {description} failed with return code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"[!] Error running {description}: {e}")
        return False

def main():
    """Main pipeline runner"""
    print(f"[*] Starting Job Processing Pipeline")
    print(f"[*] Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Extract jobs
    python_exe = ".\\authenv\\Scripts\\python.exe"
    extract_command = f"{python_exe} job_extractor.py"
    
    if not run_command(extract_command, "Job Extraction"):
        print("[!] Job extraction failed. Stopping pipeline.")
        return
    
    # Step 2: Find the most recent CSV file
    import glob
    csv_files = glob.glob("processed_jobs_*.csv")
    summary_files = glob.glob("job_summary_*.txt")
    
    if not csv_files:
        print("[!] No processed jobs CSV file found. Cannot send notifications.")
        return
    
    # Get the most recent files
    latest_csv = max(csv_files, key=os.path.getctime)
    latest_summary = max(summary_files, key=os.path.getctime) if summary_files else None
    
    print(f"[*] Found latest CSV file: {latest_csv}")
    if latest_summary:
        print(f"[*] Found latest summary file: {latest_summary}")
    
    # Step 3: Send Telegram notifications
    if latest_summary:
        telegram_command = f"{python_exe} telegram_bot.py \"{latest_csv}\" \"{latest_summary}\""
    else:
        telegram_command = f"{python_exe} telegram_bot.py \"{latest_csv}\""
    
    if not run_command(telegram_command, "Telegram Notifications"):
        print("[!] Telegram notifications failed.")
        return
    
    print(f"\n{'='*50}")
    print("[*] ✅ PIPELINE COMPLETED SUCCESSFULLY!")
    print(f"[*] Jobs processed and notifications sent")
    print(f"[*] CSV file: {latest_csv}")
    if latest_summary:
        print(f"[*] Summary file: {latest_summary}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
