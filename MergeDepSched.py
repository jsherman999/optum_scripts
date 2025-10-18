#!/usr/bin/env python3
"""
MergeDepSched.py - Merge server patching data from multiple sources

This script reads data from:
- Tenable.csv (vulnerability scan data)
- erratum_cumulative.csv (CVE insert dates)
- data/<hostname>_DeploySched.json (deployment schedule data)
- data/<hostname>_Infrared.json (server metadata)

And creates a Merged.csv file combining relevant fields from all sources.
"""

import csv
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set


def standardize_date(date_str: str) -> str:
    """
    Convert various date formats to YYYY-MM-DD format.

    Args:
        date_str: Date string in various formats

    Returns:
        Standardized date string in YYYY-MM-DD format
    """
    if not date_str or date_str == 'N/A':
        return ''

    # Try common formats
    date_formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',  # 2025-08-24T01:03:37.793Z
        '%Y-%m-%dT%H:%M:%S',       # 2024-02-08T23:00:00
        '%Y-%m-%d',                # 2024-06-10
    ]

    for fmt in date_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue

    # If no format matches, return as-is
    return date_str


def clean_countdown(countdown_str: str) -> str:
    """
    Remove ' days' suffix from countdown field and return just the integer.

    Args:
        countdown_str: String like '-20 days' or 'N/A'

    Returns:
        Integer string or empty string
    """
    if not countdown_str or countdown_str == 'N/A':
        return ''

    # Remove ' days' suffix and any whitespace
    return countdown_str.replace(' days', '').replace('days', '').strip()


def load_erratum_dates(csv_path: str) -> Dict[str, tuple]:
    """
    Load CVE/RHSA insert dates from erratum_cumulative.csv.

    Args:
        csv_path: Path to erratum_cumulative.csv

    Returns:
        Dictionary mapping vulnerability ID to (Redhat_insert_date, Optum_insert_date)
    """
    erratum_dates = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            vuln_id = row['Vulnerability']
            redhat_date = standardize_date(row['Redhat_insert_date'])
            optum_date = standardize_date(row['Optum_insert_date'])
            erratum_dates[vuln_id] = (redhat_date, optum_date)

    return erratum_dates


def get_earliest_dates(cve_ids: str, erratum_dates: Dict[str, tuple]) -> tuple:
    """
    Get the earliest Redhat and Optum insert dates for a list of CVE IDs.

    Args:
        cve_ids: Comma-separated list of CVE IDs
        erratum_dates: Dictionary of vulnerability dates

    Returns:
        Tuple of (earliest_redhat_date, earliest_optum_date)
    """
    if not cve_ids or cve_ids == 'N/A':
        return ('', '')

    # Parse CVE IDs - they might be comma-separated
    cve_list = [cve.strip() for cve in cve_ids.split(',')]

    earliest_redhat = None
    earliest_optum = None

    for cve in cve_list:
        if cve in erratum_dates:
            redhat_date, optum_date = erratum_dates[cve]

            if redhat_date:
                if earliest_redhat is None or redhat_date < earliest_redhat:
                    earliest_redhat = redhat_date

            if optum_date:
                if earliest_optum is None or optum_date < earliest_optum:
                    earliest_optum = optum_date

    return (earliest_redhat or '', earliest_optum or '')


def load_infrared_data(hostname: str, data_dir: str = 'data') -> Optional[Dict]:
    """
    Load Infrared JSON data for a hostname.

    Args:
        hostname: Server hostname
        data_dir: Directory containing JSON files

    Returns:
        Dictionary with Infrared data or None if not found
    """
    json_path = os.path.join(data_dir, f"{hostname}_Infrared.json")

    # If file doesn't exist, try to generate it
    if not os.path.exists(json_path):
        print(f"Warning: {json_path} not found. Would call 'seered {hostname} -json > {json_path}'")
        return None

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract fields from first result
    if 'results' in data and len(data['results']) > 0:
        result = data['results'][0]
        return {
            'support_stage_std': result.get('support_stage_std', ''),
            'support_group': result.get('support_group', ''),
            'support_stage_src': result.get('support_stage_src', ''),
            'server_support_model': result.get('server_support_model', ''),
            'supported_by': result.get('supported_by', ''),
            'os_remediation': result.get('os_remediation', ''),
            'insert_timestamp': standardize_date(result.get('insert_timestamp', '')),
        }

    return None


def load_deploy_sched_data(hostname: str, data_dir: str = 'data') -> List[Dict]:
    """
    Load DeploymentSchedule JSON data for a hostname.

    Args:
        hostname: Server hostname
        data_dir: Directory containing JSON files

    Returns:
        List of deployment schedule records
    """
    json_path = os.path.join(data_dir, f"{hostname}_DeplySched.json")

    # If file doesn't exist, try to generate it
    if not os.path.exists(json_path):
        print(f"Warning: {json_path} not found. Would call './pull_deployment_schedule.sh {hostname} > {json_path}'")
        return []

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract relevant fields from each deployment
    deployments = []
    for record in data:
        deployments.append({
            'deployment_name': record.get('deployment_name', ''),
            'start_date': standardize_date(record.get('start_date', '')),
            'CurrentStatus': record.get('CurrentStatus', ''),
            'is_opted_out': record.get('is_opted_out', 0),
        })

    return deployments


def extract_hostnames(tenable_csv: str) -> Set[str]:
    """
    Extract unique hostnames from Tenable.csv Resource Name field.

    Args:
        tenable_csv: Path to Tenable.csv file

    Returns:
        Set of unique hostnames
    """
    hostnames = set()

    with open(tenable_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            resource_name = row['Resource Name']
            if resource_name and resource_name != 'N/A':
                hostnames.add(resource_name)

    return hostnames


def create_merged_csv(tenable_csv: str, erratum_csv: str, output_csv: str):
    """
    Main function to create the merged CSV file.

    Args:
        tenable_csv: Path to Tenable.csv
        erratum_csv: Path to erratum_cumulative.csv
        output_csv: Path to output Merged.csv
    """
    # Load erratum dates
    print("Loading erratum dates...")
    erratum_dates = load_erratum_dates(erratum_csv)

    # Extract unique hostnames from Tenable.csv
    print("Extracting hostnames from Tenable.csv...")
    hostnames = extract_hostnames(tenable_csv)
    print(f"Found {len(hostnames)} unique hostnames")

    # Load Infrared and DeploySched data for each hostname
    print("Loading Infrared and DeploymentSchedule data...")
    infrared_cache = {}
    deploy_sched_cache = {}

    for hostname in hostnames:
        infrared_data = load_infrared_data(hostname)
        if infrared_data:
            infrared_cache[hostname] = infrared_data

        deploy_sched_data = load_deploy_sched_data(hostname)
        if deploy_sched_data:
            deploy_sched_cache[hostname] = deploy_sched_data

    # Define output CSV fields
    output_fields = [
        # From Tenable.csv
        'Name', 'Associated Apps', 'ID', 'Category', 'Countdown', 'Tool Identified',
        'ID Date', 'Tool Initial Detection', 'Last Authenticated Scan', 'Status',
        'Known Exploit', 'Severity', 'Resource Name', 'Domain Name', 'Related CVE IDs',
        'Description', 'Remediation',
        # From erratum_cumulative.csv
        'Redhat_insert_date', 'Optum_insert_date',
        # From DeploySched.json
        'deployment_name', 'start_date', 'CurrentStatus', 'is_opted_out',
        # From Infrared.json
        'support_stage_std', 'support_group', 'support_stage_src', 'server_support_model',
        'supported_by', 'os_remediation', 'insert_timestamp',
        # Calculated field
        'scan_after_build'
    ]

    # Process Tenable.csv and create merged records
    print(f"Creating {output_csv}...")

    with open(tenable_csv, 'r', encoding='utf-8') as infile, \
         open(output_csv, 'w', encoding='utf-8', newline='') as outfile:

        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=output_fields)
        writer.writeheader()

        for row in reader:
            hostname = row['Resource Name']

            # Get Infrared data
            infrared_data = infrared_cache.get(hostname, {})

            # Get DeploymentSchedule data
            deploy_schedules = deploy_sched_cache.get(hostname, [])

            # Get earliest CVE dates
            redhat_date, optum_date = get_earliest_dates(row['Related CVE IDs'], erratum_dates)

            # Standardize dates from Tenable
            id_date = standardize_date(row['ID Date'])
            tool_initial_detection = standardize_date(row['Tool Initial Detection'])
            last_auth_scan = standardize_date(row['Last Authenticated Scan'])

            # Clean countdown
            countdown = clean_countdown(row['Countdown'])

            # Create base merged record
            base_record = {
                'Name': row['Name'],
                'Associated Apps': row['Associated Apps'],
                'ID': row['ID'],
                'Category': row['Category'],
                'Countdown': countdown,
                'Tool Identified': row['Tool Identified'],
                'ID Date': id_date,
                'Tool Initial Detection': tool_initial_detection,
                'Last Authenticated Scan': last_auth_scan,
                'Status': row['Status'],
                'Known Exploit': row['Known Exploit'],
                'Severity': row['Severity'],
                'Resource Name': hostname,
                'Domain Name': row['Domain Name'],
                'Related CVE IDs': row['Related CVE IDs'],
                'Description': row['Description'],
                'Remediation': row['Remediation'],
                'Redhat_insert_date': redhat_date,
                'Optum_insert_date': optum_date,
                'support_stage_std': infrared_data.get('support_stage_std', ''),
                'support_group': infrared_data.get('support_group', ''),
                'support_stage_src': infrared_data.get('support_stage_src', ''),
                'server_support_model': infrared_data.get('server_support_model', ''),
                'supported_by': infrared_data.get('supported_by', ''),
                'os_remediation': infrared_data.get('os_remediation', ''),
                'insert_timestamp': infrared_data.get('insert_timestamp', ''),
            }

            # If we have deployment schedules, create a record for each one
            if deploy_schedules:
                for deploy in deploy_schedules:
                    merged_record = base_record.copy()
                    merged_record.update({
                        'deployment_name': deploy['deployment_name'],
                        'start_date': deploy['start_date'],
                        'CurrentStatus': deploy['CurrentStatus'],
                        'is_opted_out': deploy['is_opted_out'],
                    })

                    # Calculate scan_after_build
                    # Y if start_date is before Last Authenticated Scan
                    scan_after_build = 'N'
                    if deploy['start_date'] and last_auth_scan:
                        if deploy['start_date'] < last_auth_scan:
                            scan_after_build = 'Y'
                    merged_record['scan_after_build'] = scan_after_build

                    writer.writerow(merged_record)
            else:
                # No deployment schedules, write record with empty deployment fields
                merged_record = base_record.copy()
                merged_record.update({
                    'deployment_name': '',
                    'start_date': '',
                    'CurrentStatus': '',
                    'is_opted_out': '',
                    'scan_after_build': '',
                })
                writer.writerow(merged_record)

    print(f"Successfully created {output_csv}")


def main():
    """Main entry point."""
    tenable_csv = 'Tenable.csv'
    erratum_csv = 'erratum_cumulative.csv'
    output_csv = 'Merged.csv'

    # Check input files exist
    if not os.path.exists(tenable_csv):
        print(f"Error: {tenable_csv} not found")
        return 1

    if not os.path.exists(erratum_csv):
        print(f"Error: {erratum_csv} not found")
        return 1

    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)

    # Create merged CSV
    create_merged_csv(tenable_csv, erratum_csv, output_csv)

    return 0


if __name__ == '__main__':
    exit(main())
