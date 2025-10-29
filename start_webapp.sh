#!/bin/bash
# Start the MergeDepSched Web Application

echo "MergeDepSched Web Application"
echo "=============================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if Flask is installed
if ! python3 -c "import flask" &> /dev/null; then
    echo "Flask is not installed. Installing dependencies..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies"
        exit 1
    fi
fi

# Check for required data files
if [ ! -f "erratum_cumulative.csv" ]; then
    echo "Warning: erratum_cumulative.csv not found"
    echo "The application may not work correctly without this file"
fi

if [ ! -d "data" ]; then
    echo "Warning: data directory not found"
    echo "Creating data directory..."
    mkdir -p data
fi

# Create uploads directory if it doesn't exist
mkdir -p uploads

echo ""
echo "Starting web application..."
echo "Once started, open your browser to: http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the Flask application
python3 app.py
