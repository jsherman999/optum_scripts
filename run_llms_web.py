#!/usr/bin/env python3
"""
run_llms_web.py

Runs the prompt on all LLM_PROVIDERS in ask_llm.py and displays the results in a simple web page.
"""
import sys
import os
import importlib.util
from pathlib import Path
from flask import Flask, render_template_string, request

# Dynamically import ask_llm.py
ask_llm_path = Path(__file__).parent / 'ask_llm.py'
spec = importlib.util.spec_from_file_location('ask_llm', ask_llm_path)
ask_llm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ask_llm)

LLM_PROVIDERS = ask_llm.LLM_PROVIDERS
fetch_response = ask_llm.fetch_response

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>LLM Multi-Provider Results</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 2em; }
        .llm-result { border: 1px solid #ccc; border-radius: 8px; margin-bottom: 2em; padding: 1em; }
        .llm-label { font-weight: bold; font-size: 1.2em; margin-bottom: 0.5em; }
        textarea { width: 100%; height: 80px; }
        .prompt-form { margin-bottom: 2em; }
    </style>
</head>
<body>
    <h1>LLM Multi-Provider Results</h1>
    <form method="post" class="prompt-form">
        <label for="prompt">Enter your prompt:</label><br>
        <textarea name="prompt" id="prompt">{{ prompt|default('') }}</textarea><br>
        <button type="submit">Run on all LLMs</button>
    </form>
    {% if results %}
        {% for label, result in results.items() %}
            <div class="llm-result">
                <div class="llm-label">{{ label }}</div>
                <pre>{{ result }}</pre>
            </div>
        {% endfor %}
    {% endif %}
</body>
</html>
'''

def run_llm(label, prompt):
    from io import StringIO
    import contextlib
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            fetch_response(label, prompt)
        except Exception as e:
            print(f"Error for {label}: {e}")
    return buf.getvalue().strip()

@app.route('/', methods=['GET', 'POST'])
def index():
    results = {}
    prompt = ''
    if request.method == 'POST':
        prompt = request.form.get('prompt', '').strip()
        if prompt:
            for label in LLM_PROVIDERS:
                results[label] = run_llm(label, prompt)
    return render_template_string(HTML_TEMPLATE, results=results, prompt=prompt)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
