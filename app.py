import os
import uuid
import pandas as pd
from utils.ai_insights import generate_ai_insights
from flask import Flask, render_template, request, jsonify, send_from_directory, after_this_request


# Import our custom utility modules for data cleaning and dashboard helper calculations
from utils.data_processor import clean_and_preprocess
from utils.analytics_engine import generate_dataset_info, generate_kpis, generate_insights

app = Flask(__name__)

# Configuration details
# The folder where uploaded and cleaned files will be stored temporarily
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Set maximum upload size to 16 Megabytes to protect the server
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Ensure the uploads directory exists on startup
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """
    Checks if the uploaded file ends with '.csv' to ensure we only accept CSVs.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'

@app.route('/')
def index():
    """
    Renders the homepage. This is our single page dashboard interface.
    """
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Accepts an uploaded CSV file, inspects/cleans/preprocesses it,
    generates dynamic KPIs and key insights, saves the cleaned copy,
    and returns a full dashboard payload in JSON format.
    """
    # 1. VALIDATE THAT A FILE WAS UPLOADED
    if 'file' not in request.files:
        return jsonify({"error": "No file portion in the request."}), 400
        
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No file selected for uploading."}), 400
        
    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Please upload a CSV file."}), 400
        
    # Generate a unique ID for this processing request to prevent name collisions
    original_filename = file.filename
    unique_id = str(uuid.uuid4())
    temp_filename = f"raw_{unique_id}.csv"
    temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
    
    try:
        # Save the raw file temporarily to disk
        file.save(temp_filepath)
        
        # 2. PARSE THE CSV USING PANDAS
        try:
            df_raw = pd.read_csv(temp_filepath)
        except Exception as e:
            # If the CSV is corrupted, clean up the file and return an error
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            return jsonify({"error": f"Failed to parse CSV: {str(e)}"}), 400
            
        if df_raw.empty:
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            return jsonify({"error": "The uploaded CSV file contains no data."}), 400

        # Calculate initial missing value percentage of the raw dataset
        total_cells = df_raw.size
        total_missing = df_raw.isna().sum().sum()
        original_missing_pct = (total_missing / total_cells) * 100 if total_cells > 0 else 0.0

        # 3. RUN INTELLIGENT PREPROCESSING
        # Clean duplicates, impute missing values adaptively, parse dates
        cleaned_df, column_types, summary_logs = clean_and_preprocess(df_raw)

        # 4. GENERATE METADATA, KPIs, AND INSIGHTS
        # Get dataset information panel data
        dataset_info = generate_dataset_info(cleaned_df, original_filename, original_missing_pct)

        # Calculate dynamic KPIs based on the columns
        kpis = generate_kpis(cleaned_df, column_types)

        # Generate analytical insights from the cleaned dataset
        insights = generate_ai_insights(cleaned_df)

        # 5. PREPARE THE DATA PREVIEW
        # Select first 20 rows and convert Datetimes/Booleans to strings for clean JSON serialization
        preview_df = cleaned_df.head(20).copy()
        for col, col_type in column_types.items():
            if col_type == 'date':
                preview_df[col] = preview_df[col].dt.strftime('%Y-%m-%d').fillna('')
            elif col_type == 'boolean':
                preview_df[col] = preview_df[col].astype(str)
                
        preview_headers = list(cleaned_df.columns)
        preview_rows = preview_df.to_dict(orient='records')

        # 6. EXPORT THE CLEANED FILE FOR DOWNLOAD
        # Save the cleaned dataframe to a separate CSV file
        cleaned_filename = f"cleaned_{unique_id}.csv"
        cleaned_filepath = os.path.join(app.config['UPLOAD_FOLDER'], cleaned_filename)
        cleaned_df.to_csv(cleaned_filepath, index=False)

        # Assemble the full response structure
        response_payload = {
            "success": True,
            "dataset_info": dataset_info,
            "summary_logs": summary_logs,
            "kpis": kpis,
            "insights": insights,
            "preview_headers": preview_headers,
            "preview_rows": preview_rows,
            "download_url": f"/download/{cleaned_filename}"
        }

        # 7. CLEAN UP THE ORIGINAL UPLOADED FILE
        # Since we have processed the data and saved the cleaned copy, we can delete the raw upload
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)

        return jsonify(response_payload)

    except Exception as e:
        # Fallback safety clean up in case something fails in the process
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        return jsonify({"error": f"An error occurred while processing the file: {str(e)}"}), 500


@app.route('/download/<filename>')
def download_file(filename):
    """
    Downloads the cleaned CSV file, and schedules it for deletion 
    immediately after serving to keep disk usage to zero.
    """
    # Prevent directory traversal attacks by checking path string
    if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
        return "Access denied.", 400
        
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if os.path.exists(filepath):
        # We use Flask's @after_this_request decorator. This registers a function
        # to run AFTER the response (the file download) is fully sent to the user.
        # This allows us to serve the file and immediately remove it from disk.
        @after_this_request
        def remove_file(response):
            try:
                os.remove(filepath)
            except Exception as error:
                app.logger.error("Error removing file: %s", error)
            return response
            
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    else:
        return "Cleaned file not found. It may have expired or already been downloaded.", 404

if __name__ == '__main__':
    # Run the server on port 5000 in debug mode
    app.run(debug=True)
