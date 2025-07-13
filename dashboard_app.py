# dashboard_app.py

import pandas as pd
import glob
from flask import Flask, render_template, request

app = Flask(__name__)

def load_and_process_data():
    """
    Loads all CSVs, combines them, converts dates, and returns a clean DataFrame.
    """
    csv_files = glob.glob("processed_jobs_*.csv")
    if not csv_files:
        return pd.DataFrame()
        
    all_dfs = [pd.read_csv(file) for file in csv_files]
    combined_df = pd.concat(all_dfs, ignore_index=True)
    
    unique_jobs_df = combined_df.drop_duplicates(subset=['post_url'], keep='last')
    
    # --- MODIFIED: Convert 'processed_at' to a real datetime object ---
    # This is crucial for date-based filtering. 'errors=coerce' will turn any
    # bad date formats into 'NaT' (Not a Time), which we can safely ignore.
    unique_jobs_df['processed_at'] = pd.to_datetime(unique_jobs_df['processed_at'], errors='coerce')
    
    # Sort by the processing date to show newest jobs first
    return unique_jobs_df.sort_values(by='processed_at', ascending=False)

@app.route('/')
def dashboard():
    """
    Main route that now handles all filters, including recency.
    """
    jobs_df = load_and_process_data()
    
    # --- Get all filter values from the URL ---
    search_query = request.args.get('query', '')
    selected_location = request.args.get('location', '')
    selected_job_type = request.args.get('job_type', '')
    selected_recency = request.args.get('recency', 'all_time') # --- NEW ---

    # --- Apply filters to the DataFrame ---
    filtered_df = jobs_df.copy()
    
    if search_query:
        filtered_df = filtered_df[
            filtered_df['job_title'].str.contains(search_query, case=False, na=False) |
            filtered_df['skills_required'].str.contains(search_query, case=False, na=False)
        ]
        
    if selected_location:
        filtered_df = filtered_df[filtered_df['location'] == selected_location]
        
    if selected_job_type:
        filtered_df = filtered_df[filtered_df['job_type'] == selected_job_type]

    # --- NEW: Apply the Recency Filter ---
    if selected_recency != 'all_time':
        now = pd.Timestamp.now() # Get the current time
        if selected_recency == 'today':
            filtered_df = filtered_df[filtered_df['processed_at'] >= (now - pd.Timedelta(days=1))]
        elif selected_recency == 'this_week':
            filtered_df = filtered_df[filtered_df['processed_at'] >= (now - pd.Timedelta(days=7))]
        elif selected_recency == 'this_month':
            filtered_df = filtered_df[filtered_df['processed_at'] >= (now - pd.Timedelta(days=30))]

    # --- Prepare data for the template ---
    all_locations = sorted(jobs_df['location'].dropna().unique().tolist())
    all_job_types = sorted(jobs_df['job_type'].dropna().unique().tolist())
    filtered_jobs_list = filtered_df.to_dict('records')
    
    # --- MODIFIED: Add recency to the sticky filters ---
    current_filters = {
        'query': search_query,
        'location': selected_location,
        'job_type': selected_job_type,
        'recency': selected_recency 
    }

    return render_template(
        'dashboard.html', 
        jobs=filtered_jobs_list, 
        job_count=len(filtered_jobs_list),
        locations=all_locations,
        job_types=all_job_types,
        filters=current_filters
    )

if __name__ == '__main__':
    app.run(debug=True)