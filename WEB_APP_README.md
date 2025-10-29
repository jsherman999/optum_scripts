# MergeDepSched Web Application

A Flask-based web application for merging vulnerability data from Tenable scans with deployment schedules and infrastructure metadata.

## Features

- **Easy File Upload**: Drag-and-drop or click to upload Tenable.csv files
- **Automated Processing**: Automatically merges data from multiple sources
- **Interactive Results**: View merged data in a searchable, sortable table
- **Data Visualization**: Quick statistics dashboard showing vulnerability counts
- **Export Capability**: Download the merged results as CSV

## Prerequisites

- Python 3.7 or higher
- Required data files:
  - `erratum_cumulative.csv` - CVE insert dates
  - `data/` directory - Contains JSON files for infrastructure and deployment data

## Installation

1. Install required dependencies:

```bash
pip install -r requirements.txt
```

2. Ensure you have the required data files in place:
   - `erratum_cumulative.csv` should be in the root directory
   - `data/` directory should contain the JSON data files

## Running the Application

1. Start the Flask development server:

```bash
python3 app.py
```

2. Open your web browser and navigate to:

```
http://localhost:5000
```

## Usage

### Uploading Files

1. Click on the upload area or drag a Tenable.csv file onto it
2. Click "Process File" to begin merging
3. Wait for the processing to complete (may take a few minutes depending on file size)

### Viewing Results

The results page displays:

- **Interactive Table**: All merged data with sortable columns
  - Search and filter capabilities
  - Pagination for large datasets
  - Column-specific filtering

- **Statistics Dashboard**: Quick overview showing:
  - Count of vulnerabilities by severity (Critical, High, Medium, Low)
  - Number of known exploits
  - Unique host count

- **Color-Coded Badges**:
  - Severity levels (Critical, High, Medium, Low)
  - Known exploit status
  - Deployment status

### Downloading Results

Click the "Download CSV" button to save the merged data to your local machine.

## Data Sources

The application merges data from:

1. **Tenable.csv** (uploaded by user)
   - Vulnerability scan data
   - Resource names, severity levels, CVE IDs
   - Detection dates and status

2. **erratum_cumulative.csv** (server-side)
   - Red Hat insert dates
   - Optum insert dates
   - CVE/RHSA mappings

3. **JSON Files in data/** (server-side)
   - `<hostname>_Infrared.json` - Infrastructure metadata
   - `<hostname>_DeplySched.json` - Deployment schedules

## Output Format

The merged CSV includes:

### From Tenable
- Name, ID, Category, Severity
- Resource Name, Domain Name
- Related CVE IDs
- Description, Remediation
- Detection dates and status

### From Erratum
- Redhat_insert_date
- Optum_insert_date

### From Deployment Schedule
- deployment_name
- start_date
- CurrentStatus
- is_opted_out

### From Infrared
- support_stage_std
- support_group
- server_support_model
- supported_by
- os_remediation

### Calculated Fields
- scan_after_build (Y/N)

## File Storage

Uploaded files and generated results are stored in the `uploads/` directory with timestamps to prevent conflicts:

- `Tenable_YYYYMMDD_HHMMSS.csv` - Uploaded files
- `Merged_YYYYMMDD_HHMMSS.csv` - Generated results
- `data_YYYYMMDD_HHMMSS/` - Working directory for JSON files

## Security Considerations

- Maximum file size: 50MB
- Only CSV files are accepted
- Files are validated before processing
- Uploaded files are stored with secure filenames

## Troubleshooting

### "Error: erratum_cumulative.csv not found"
Ensure the erratum file is in the application root directory.

### "Processing timed out"
The file may be too large. Try splitting it into smaller chunks or increase the timeout in `app.py`.

### Missing data in results
Check that the corresponding JSON files exist in `data/` directory for the hostnames in your Tenable.csv.

## Production Deployment

For production use:

1. Change the secret key in `app.py`:
   ```python
   app.secret_key = 'your-secure-random-secret-key'
   ```

2. Disable debug mode:
   ```python
   app.run(debug=False, host='0.0.0.0', port=5000)
   ```

3. Use a production WSGI server like Gunicorn:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

## Support

For issues or questions about the web application, refer to the main README.md or contact the development team.
