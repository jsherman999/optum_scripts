#!/usr/bin/python3

import argparse
import requests
import json
import sys
import os

from pathlib import Path
from dotenv import load_dotenv

# Load .llm_config if it exists in the script's directory
config_path = Path(__file__).resolve().parent / ".llm_config"
if config_path.exists():
    load_dotenv(dotenv_path=config_path, override=False)


LLM_PROVIDERS = {
    "chatgpt": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-3.5-turbo",
        "headers": lambda: {
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Content-Type": "application/json"
        },
        "build_payload": lambda prompt: {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}]
        },
        "extract_response": lambda data: data['choices'][0]['message']['content']
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro:generateContent",
        "headers": lambda: {
            "Content-Type": "application/json"
        },
        "build_payload": lambda prompt: {
            "contents": [{"parts": [{"text": prompt}]}],
            "apiKey": os.getenv("GOOGLE_API_KEY")
        },
        "extract_response": lambda data: data['candidates'][0]['content']['parts'][0]['text']
    },
    "claude": {
        "url": "https://api.anthropic.com/v1/messages",
        "headers": lambda: {
            "x-api-key": os.getenv("ANTHROPIC_API_KEY"),
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        },
        "build_payload": lambda prompt: {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000
        },
        "extract_response": lambda data: data['content'][0]['text']
    }
}

def fetch_response(label, prompt):
    if label not in LLM_PROVIDERS:
        print(f"Error: Unknown LLM label '{label}'. Try one of: {', '.join(LLM_PROVIDERS)}.")
        sys.exit(1)

    provider = LLM_PROVIDERS[label]
    url = provider["url"]
    headers = provider["headers"]()
    payload = provider["build_payload"](prompt)

    try:
        if label == "gemini":
            api_key = payload.pop("apiKey", None)
            url += f"?key={api_key}"
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        print(provider["extract_response"](data))
    except Exception as e:
        print(f"Request to {label} failed: {e}")


def ask_ollama_local(prompt):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3",
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
            print(json.dumps(data, indent=2))
    except requests.exceptions.RequestException as e:
        print(f"Ollama local error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Query a public LLM or local Ollama server.")
    parser.add_argument('-H', '--host', help="LLM provider label (chatgpt, gemini, claude)")
    parser.add_argument('--file', help="Path to a file containing the prompt")
    parser.add_argument('question', nargs='*', help="Prompt text (if no --file or stdin)")
    args = parser.parse_args()

    if args.file:
        if not os.path.isfile(args.file):
            print(f"File not found: {args.file}")
            sys.exit(1)
        prompt = open(args.file, 'r', encoding='utf-8').read()
    elif args.question:
        prompt = " ".join(args.question)
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
    else:
        print("Provide a prompt via --file, arguments, or stdin.")
        sys.exit(1)

    # Validate required API keys
    REQUIRED_KEYS = {
        "chatgpt": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "claude": "ANTHROPIC_API_KEY"
    }

    if args.host:
        label = args.host.lower()
        required_key = REQUIRED_KEYS.get(label)
        if required_key and not os.getenv(required_key):
            print(f"Missing required environment variable: {required_key}")
            print(f"Set it in your shell or in .llm_config in the script directory.")
            sys.exit(1)

    if args.host and args.host.lower() == "local":
        ask_ollama_local(prompt)
    elif args.host:
        fetch_response(args.host.lower(), prompt)
    else:
        print("Error: Specify -H local or -H <provider>")
        sys.exit(1)

if __name__ == "__main__":
    main()
