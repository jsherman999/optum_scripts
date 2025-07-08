#!/usr/bin/env python3

import os
import sys
import shutil
import socket
import subprocess
import datetime
import argparse
from config_utils import lookup_config_entry

LOG_FILE = "action.log"

def get_cksum(filepath):
    try:
        out = subprocess.check_output(["cksum", filepath], universal_newlines=True)
        return out.strip()
    except:
        return "N/A"

def get_mtime(filepath):
    try:
        ts = os.path.getmtime(filepath)
        return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return "N/A"

def log_entry(action, host, target, repo, path, is_dir):
    with open(LOG_FILE, "a") as f:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{now}] ACTION: {action}, Host: {host}, Target: {target}, Repo: {repo}\n")
        if is_dir:
            for root, _, files in os.walk(path):
                for file in files:
                    fp = os.path.join(root, file)
                    rel = os.path.relpath(fp, path)
                    cksum = get_cksum(fp)
                    mtime = get_mtime(fp)
                    f.write(f"    File: {rel}, CKSUM: {cksum}, Datestamp: {mtime}\n")
        else:
            cksum = get_cksum(path)
            mtime = get_mtime(path)
            f.write(f"    File: {os.path.basename(path)}, CKSUM: {cksum}, Datestamp: {mtime}\n")

def deploy_to_host(host, source, dest, is_dir):
    local = socket.gethostname()
    if host in ['localhost', '127.0.0.1', local]:
        if is_dir:
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(source, dest)
        else:
            shutil.copy(source, dest)
    else:
        cmd = ["scp", "-r" if is_dir else "", source, f"{host}:{dest}"]
        subprocess.check_call([arg for arg in cmd if arg])

def find_all_config_matches(target_path, config_file="config.txt"):
    """Return a list of all (hostname, target, reponame) entries matching the given path."""
    matches = []
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file '{config_file}' not found.")
    
    normalized_input = os.path.normpath(target_path.strip())

    with open(config_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) != 3:
                continue
            hostname, target, reponame = map(str.strip, parts)
            if os.path.normpath(target) == normalized_input:
                matches.append((hostname, target, reponame))
    return matches

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target_path", help="File or directory path to deploy")
    parser.add_argument("-d", "--directory", action="store_true", help="Target is a directory")
    args = parser.parse_args()

    target_input = os.path.normpath(args.target_path)
    is_directory = args.directory

    try:
        matches = find_all_config_matches(target_input)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    if not matches:
        print(f"[ERROR] '{target_input}' not found in config.txt.")
        return

    # Use the first match to determine the repo and source path
    _, _, repo = matches[0]
    base = os.path.basename(target_input.rstrip("/"))
    source = os.path.join(repo, base)

    if not os.path.exists(repo):
        print(f"[ERROR] Local repo '{repo}' not found.")
        return

    os.chdir(repo)
    subprocess.call(["git", "pull"])
    os.chdir("..")

    if not os.path.exists(source):
        print(f"[ERROR] Source '{source}' not found in repo.")
        return

    for host, target, reponame in matches:
        try:
            deploy_to_host(host, source, target, is_directory)
            log_entry("DEPLOYED TO HOST", host, target, reponame, source, is_directory)
            print(f"[INFO] Deployed to {host}:{target}")
        except Exception as e:
            print(f"[ERROR] Failed to deploy to {host}:{target}: {e}")

if __name__ == "__main__":
    main()
