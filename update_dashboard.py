# update_dashboard.py
import subprocess
import datetime

COMMIT_MESSAGE = f"Automated data update: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"

def run_command(command):
    print(f"\n> Running: {' '.join(command)}")
    try:
        subprocess.run(command, check=True, text=True, encoding='utf-8')
        return True
    except subprocess.CalledProcessError as e:
        print(f"[!] Error running command: {e}")
        return False

def main():
    print("--- Starting Dashboard Update Process ---")
    if not run_command(["git", "add", "."]): return
    if not run_command(["git", "commit", "-m", COMMIT_MESSAGE]): 
        print("[*] INFO: Commit failed, likely no new files to commit.")
    if not run_command(["git", "push"]): return
    print("\n✅ UPDATE COMPLETE! Your dashboard is now updating online.")

if __name__ == "__main__":
    main()