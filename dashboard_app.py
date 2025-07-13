# dashboard_app.py
import pandas as pd
import glob
from flask import Flask, render_template

app = Flask(__name__)

def load_and_clean_job_data():
    csv_files = glob.glob("processed_jobs_*.csv")
    if not csv_files: return []
    
    all_dfs = [pd.read_csv(file) for file in csv_files]
    combined_df = pd.concat(all_dfs, ignore_index=True)
    
    unique_jobs_df = combined_df.drop_duplicates(subset=['post_url'], keep='last')
    final_df = unique_jobs_df.sort_values(by='processed_at', ascending=False)
    
    return final_df.to_dict('records')

@app.route('/')
def dashboard():
    jobs = load_and_clean_job_data()
    return render_template('dashboard.html', jobs=jobs, job_count=len(jobs))

if __name__ == '__main__':
    app.run(debug=True)