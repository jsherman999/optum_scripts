#!/usr/bin/python3

import argparse
import requests
import json
import sys
import os

DEFAULT_HOST = "localhost"
OLLAMA_PORT = 11434
OLLAMA_ENDPOINT = "/api/generate"
DEFAULT_MODEL_NAME = "llama3"
CONFIG_FILE = ".llm_config"

def load_env_config(config_path):
    if not os.path.isfile(config_path):
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip()

def ask_ollama(host, prompt, model_name):
    url = f"http://{host}:{OLLAMA_PORT}{OLLAMA_ENDPOINT}"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        if "response" in data:
            print(data["response"])
        else:
            print("Unexpected response format:", json.dumps(data, indent=2))
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Ollama server at {host}: {e}")

def main():
    # Load config file and set environment variables
    load_env_config(CONFIG_FILE)

    # Read from env or use defaults
    default_host = os.environ.get("HOST", DEFAULT_HOST)
    default_model = os.environ.get("MODEL_NAME", DEFAULT_MODEL_NAME)

    parser = argparse.ArgumentParser(description="Ask a question to the Ollama server via CLI, file, or stdin.")
    parser.add_argument('-H', '--host', default=default_host, help=f"Hostname or IP (default: {default_host})")
    parser.add_argument('--model', default=default_model, help=f"Model name (default: {default_model})")
    parser.add_argument('--file', help="Path to a file containing the prompt to submit")
    parser.add_argument('question', nargs='*', help="Question to submit (ignored if --file is provided)")
    args = parser.parse_args()

    if args.file:
        if not os.path.isfile(args.file):
            print(f"Error: File '{args.file}' does not exist.")
            sys.exit(1)
        with open(args.file, 'r', encoding='utf-8') as f:
            prompt = f.read()
    elif args.question:
        prompt = " ".join(args.question)
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
    else:
        print("Error: Provide a question, use --file, or pipe input via stdin.")
        sys.exit(1)

    ask_ollama(args.host, prompt, args.model)

if __name__ == "__main__":
    main()

