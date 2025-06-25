#!/usr/bin/env python3

"""
run_all_llms.py

Cycles through all LLM_PROVIDERS in ask_llm.py, sends the same prompt to each,
writes each response to a separate output file, and prints each response to stdout.
"""
import sys
import os
import importlib.util
from pathlib import Path

PROMPT_FILE = sys.argv[1] if len(sys.argv) > 1 else None
if not PROMPT_FILE or not os.path.isfile(PROMPT_FILE):
    print("Usage: python run_all_llms.py <prompt_file>")
    sys.exit(1)

with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
    prompt = f.read().strip()

# Dynamically import ask_llm.py
ask_llm_path = Path(__file__).parent / 'ask_llm.py'
spec = importlib.util.spec_from_file_location('ask_llm', ask_llm_path)
ask_llm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ask_llm)

LLM_PROVIDERS = ask_llm.LLM_PROVIDERS
fetch_response = ask_llm.fetch_response

for label in LLM_PROVIDERS:
    print(f"\n=== {label.upper()} ===")
    # Capture stdout to also write to file
    from io import StringIO
    import contextlib
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            fetch_response(label, prompt)
        except Exception as e:
            print(f"Error for {label}: {e}")
    output = buf.getvalue()
    print(output)
    out_path = f"output_{label}.txt"
    with open(out_path, 'w', encoding='utf-8') as outf:
        outf.write(output)
    print(f"[Saved response to {out_path}]")
