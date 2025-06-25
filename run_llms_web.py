#!/usr/bin/env python3
"""
run_llms_web.py

Runs the prompt on all LLM_PROVIDERS in ask_llm.py and displays the results in a simple web page.
"""
import sys
import os
import importlib.util
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify
import threading
import time
import resource

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
        body { background: #0a1833; color: #fff; font-family: Arial, sans-serif; margin: 2em; }
        .llm-result { border: 1px solid #ccc; border-radius: 8px; margin-bottom: 2em; padding: 1em; background: #172a4a; position: relative; }
        .llm-label { font-weight: bold; font-size: 1.2em; margin-bottom: 0.5em; }
        .llm-timing { border: 1px solid #ff0; border-radius: 6px; background: #222a44; color: #ff0; padding: 0.3em 0.8em; margin-bottom: 0.7em; display: inline-block; font-family: monospace; font-size: 1em; }
        textarea, input[type="text"] { width: 100%; height: 80px; background: #fff; color: #000; border-radius: 4px; border: 1px solid #888; padding: 0.5em; }
        .prompt-form { margin-bottom: 2em; }
        button { background: #1a2b4c; color: #fff; border: none; border-radius: 4px; padding: 0.5em 1.5em; font-size: 1em; cursor: pointer; }
        button:hover { background: #27406b; }
        label { color: #fff; }
        #progress { margin: 1em 0; font-size: 1.1em; color: #ff0; }
        .copy-btn { position: absolute; top: 1em; right: 1em; background: #ff0; color: #222a44; border: none; border-radius: 4px; padding: 0.2em 0.8em; font-size: 0.95em; cursor: pointer; }
        .copy-btn:hover { background: #ffe066; }
    </style>
    <script>
    function submitPrompt(event) {
        event.preventDefault();
        document.getElementById('progress').innerText = 'Working...';
        document.getElementById('results').innerHTML = '';
        var prompt = document.getElementById('prompt').value;
        fetch('/run_llms', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: prompt })
        })
        .then(response => response.json())
        .then(data => {
            document.getElementById('progress').innerText = '';
            let html = '';
            let idx = 0;
            for (const [label, result] of Object.entries(data.results)) {
                let timing = data.timings[label] || '';
                let boxId = `llm-output-${idx}`;
                html += `<div class=\"llm-result\"><div class=\"llm-label\">${label}</div><div class=\"llm-timing\">${timing}</div><button class=\"copy-btn\" onclick=\"copyToClipboard('${boxId}')\">Copy</button><pre id=\"${boxId}\">${escapeHtml(result)}</pre></div>`;
                idx++;
            }
            if (data.local_result) {
                let boxId = `llm-output-local`;
                html += `<div class=\"llm-result\" style=\"background:#1a2b4c;\"><div class=\"llm-label\">LOCAL (Ollama)</div><div class=\"llm-timing\">${data.local_timing || ''}</div><button class=\"copy-btn\" onclick=\"copyToClipboard('${boxId}')\">Copy</button><pre id=\"${boxId}\">${escapeHtml(data.local_result)}</pre></div>`;
            }
            document.getElementById('results').innerHTML = html;
        });
        // Simulate progress
        let dots = 0;
        let interval = setInterval(() => {
            if (document.getElementById('progress').innerText === '') { clearInterval(interval); return; }
            document.getElementById('progress').innerText = 'Working' + '.'.repeat((dots++ % 4) + 1);
        }, 500);
    }
    function copyToClipboard(elementId) {
        var text = document.getElementById(elementId).innerText;
        navigator.clipboard.writeText(text).then(function() {
            // Optionally show a message
        }, function(err) {
            alert('Failed to copy: ' + err);
        });
    }
    function escapeHtml(text) {
        if (!text) return '';
        return text.replace(/[&<>"']/g, function(m) {
            return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m];
        });
    }
    </script>
</head>
<body>
    <h1>LLM Multi-Provider Results</h1>
    <form method="post" class="prompt-form" onsubmit="submitPrompt(event)">
        <label for="prompt">Enter your prompt:</label><br>
        <textarea name="prompt" id="prompt">{{ prompt|default('') }}</textarea><br>
        <button type="submit">Run on all LLMs</button>
    </form>
    <div id="progress"></div>
    <div id="results">
    {% if results %}
        {% for label, result in results.items() %}
            <div class="llm-result">
                <div class="llm-label">{{ label }}</div>
                <div class="llm-timing">{{ timings[label] }}</div>
                <button class="copy-btn" onclick="copyToClipboard('llm-output-{{ loop.index0 }}')">Copy</button>
                <pre id="llm-output-{{ loop.index0 }}">{{ result }}</pre>
            </div>
        {% endfor %}
        {% if local_result %}
            <div class="llm-result" style="background:#1a2b4c;">
                <div class="llm-label">LOCAL (Ollama)</div>
                <div class="llm-timing">{{ local_timing }}</div>
                <button class="copy-btn" onclick="copyToClipboard('llm-output-local')">Copy</button>
                <pre id="llm-output-local">{{ local_result }}</pre>
            </div>
        {% endif %}
    {% endif %}
    </div>
</body>
</html>
'''

def run_llm_with_time(label, prompt):
    from io import StringIO
    import contextlib
    import time as pytime
    buf = StringIO()
    start_real = pytime.time()
    start_usage = resource.getrusage(resource.RUSAGE_SELF)
    with contextlib.redirect_stdout(buf):
        try:
            fetch_response(label, prompt)
        except Exception as e:
            print(f"Error for {label}: {e}")
    end_real = pytime.time()
    end_usage = resource.getrusage(resource.RUSAGE_SELF)
    real = end_real - start_real
    user = end_usage.ru_utime - start_usage.ru_utime
    sys_ = end_usage.ru_stime - start_usage.ru_stime
    timing = f"real {real:.2f}s  user {user:.2f}s  sys {sys_:.2f}s"
    return timing, buf.getvalue().strip()

def run_local_ollama_with_time(prompt):
    from io import StringIO
    import contextlib
    import time as pytime
    buf = StringIO()
    start_real = pytime.time()
    start_usage = resource.getrusage(resource.RUSAGE_SELF)
    with contextlib.redirect_stdout(buf):
        try:
            ask_llm.ask_ollama_local(prompt)
        except Exception as e:
            print(f"Error for local ollama: {e}")
    end_real = pytime.time()
    end_usage = resource.getrusage(resource.RUSAGE_SELF)
    real = end_real - start_real
    user = end_usage.ru_utime - start_usage.ru_utime
    sys_ = end_usage.ru_stime - start_usage.ru_stime
    timing = f"real {real:.2f}s  user {user:.2f}s  sys {sys_:.2f}s"
    return timing, buf.getvalue().strip()

@app.route('/run_llms', methods=['POST'])
def run_llms():
    data = request.get_json()
    prompt = data.get('prompt', '').strip()
    results = {}
    timings = {}
    local_result = None
    local_timing = None
    if prompt:
        for label in LLM_PROVIDERS:
            timing, result = run_llm_with_time(label, prompt)
            results[label] = result
            timings[label] = timing
        local_timing, local_result = run_local_ollama_with_time(prompt)
    return jsonify({'results': results, 'timings': timings, 'local_result': local_result, 'local_timing': local_timing})

@app.route('/', methods=['GET'])
def index():
    return render_template_string(HTML_TEMPLATE, results=None, prompt='', timings={}, local_timing=None)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
