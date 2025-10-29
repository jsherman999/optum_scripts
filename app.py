#!/usr/bin/env python3
"""
Flask web application for MergeDepSched
Allows users to upload Tenable.csv and view the merged results
"""

import os
import csv
import shutil
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import subprocess

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'csv'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def read_csv_data(filepath):
    """Read CSV file and return data as list of dictionaries"""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


@app.route('/')
def index():
    """Home page with upload form"""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and processing"""
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('index'))

    file = request.files['file']

    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('index'))

    if not allowed_file(file.filename):
        flash('Invalid file type. Please upload a CSV file.', 'error')
        return redirect(url_for('index'))

    # Save uploaded file
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    upload_filename = f"Tenable_{timestamp}.csv"
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_filename)
    file.save(upload_path)

    # Copy to working directory for processing
    tenable_path = os.path.join(app.config['UPLOAD_FOLDER'], f'Tenable_{timestamp}_working.csv')
    shutil.copy(upload_path, tenable_path)

    # Check if erratum_cumulative.csv exists
    erratum_csv = 'erratum_cumulative.csv'
    if not os.path.exists(erratum_csv):
        flash(f'Error: {erratum_csv} not found in the application directory', 'error')
        return redirect(url_for('index'))

    # Run MergeDepSched.py with custom paths
    output_csv = os.path.join(app.config['UPLOAD_FOLDER'], f'Merged_{timestamp}.csv')

    try:
        # Create data directory in uploads folder if needed
        data_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'data_{timestamp}')
        os.makedirs(data_dir, exist_ok=True)

        # Check if data directory exists and copy to working data directory
        if os.path.exists('data'):
            # Copy all files from data to the working data directory
            for item in os.listdir('data'):
                src = os.path.join('data', item)
                dst = os.path.join(data_dir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)

        # Run the merge script
        result = subprocess.run(
            ['python3', 'MergeDepSched.py', tenable_path, erratum_csv, output_csv, data_dir],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            flash(f'Error processing file: {result.stderr}', 'error')
            return redirect(url_for('index'))

        # Check if output file was created
        if not os.path.exists(output_csv):
            flash('Error: Merged.csv was not created', 'error')
            return redirect(url_for('index'))

        # Read the merged data
        merged_data = read_csv_data(output_csv)

        if not merged_data:
            flash('Warning: Merged.csv is empty', 'warning')
            return redirect(url_for('index'))

        # Get column names
        columns = list(merged_data[0].keys()) if merged_data else []

        # Store the output filename for download
        session_data = {
            'output_file': output_csv,
            'timestamp': timestamp,
            'row_count': len(merged_data)
        }

        return render_template('results.html',
                             data=merged_data,
                             columns=columns,
                             session_data=session_data)

    except subprocess.TimeoutExpired:
        flash('Error: Processing timed out. The file may be too large.', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.route('/download/<timestamp>')
def download_file(timestamp):
    """Allow downloading the merged CSV file"""
    from flask import send_file
    output_csv = os.path.join(app.config['UPLOAD_FOLDER'], f'Merged_{timestamp}.csv')

    if not os.path.exists(output_csv):
        flash('File not found', 'error')
        return redirect(url_for('index'))

    return send_file(output_csv,
                    as_attachment=True,
                    download_name=f'Merged_{timestamp}.csv',
                    mimetype='text/csv')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
