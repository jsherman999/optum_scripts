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

try:
    import tiktoken
    def count_tokens(prompt, model="gpt-3.5-turbo"):
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(prompt))
except ImportError:
    def count_tokens(prompt, model=None):
        # Fallback: estimate 1 token per 4 chars (very rough)
        return max(1, len(prompt) // 4)
import time as pytime
import logging

LOG_PATH = "/var/log/run_llms_web.log"
logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format='%(message)s')

def log_run(llm_name, real, user, sys_, token_count):
    epoch = int(pytime.time())
    log_line = f"{llm_name},{real:.2f},{user:.2f},{sys_:.2f},{token_count},{epoch}"
    try:
        logging.info(log_line)
    except Exception:
        pass

def run_llm_with_time(label, prompt):
    from io import StringIO
    import contextlib
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
    token_count = count_tokens(prompt)
    log_run(label, real, user, sys_, token_count)
    timing = f"real {real:.2f}s  user {user:.2f}s  sys {sys_:.2f}s  tokens: {token_count}"
    return timing, buf.getvalue().strip(), token_count

def run_local_ollama_with_time(prompt):
    from io import StringIO
    import contextlib
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
    token_count = count_tokens(prompt)
    log_run("local", real, user, sys_, token_count)
    timing = f"real {real:.2f}s  user {user:.2f}s  sys {sys_:.2f}s  tokens: {token_count}"
    return timing, buf.getvalue().strip(), token_count

@app.route('/run_llms', methods=['POST'])
def run_llms():
    data = request.get_json()
    prompt = data.get('prompt', '').strip()
    results = {}
    timings = {}
    token_counts = {}
    local_result = None
    local_timing = None
    local_token_count = None
    if prompt:
        for label in LLM_PROVIDERS:
            timing, result, token_count = run_llm_with_time(label, prompt)
            results[label] = result
            timings[label] = timing
            token_counts[label] = token_count
        local_timing, local_result, local_token_count = run_local_ollama_with_time(prompt)
    return jsonify({'results': results, 'timings': timings, 'token_counts': token_counts, 'local_result': local_result, 'local_timing': local_timing, 'local_token_count': local_token_count})

@app.route('/run_single_llm', methods=['POST'])
def run_single_llm():
    data = request.get_json()
    prompt = data.get('prompt', '').strip()
    label = data.get('label', '').strip()
    if not prompt or not label:
        return jsonify({'error': 'Missing prompt or label'}), 400
    timing, result, token_count = run_llm_with_time(label, prompt)
    return jsonify({'label': label, 'result': result, 'timing': timing, 'token_count': token_count})

@app.route('/run_local_ollama', methods=['POST'])
def run_local_ollama():
    data = request.get_json()
    prompt = data.get('prompt', '').strip()
    if not prompt:
        return jsonify({'error': 'Missing prompt'}), 400
    timing, result, token_count = run_local_ollama_with_time(prompt)
    return jsonify({'label': 'local', 'result': result, 'timing': timing, 'token_count': token_count})

@app.route('/get_llm_providers', methods=['GET'])
def get_llm_providers():
    return jsonify({'providers': list(LLM_PROVIDERS)})

@app.route('/', methods=['GET'])
def index():
    return render_template_string(HTML_TEMPLATE, results=None, prompt='', timings={}, local_timing=None)

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
        #stats-panel { display: none; background: #101c33; border: 2px solid #ffe066; border-radius: 10px; margin-top: 2em; padding: 1em; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
    async function submitPrompt(event) {
        event.preventDefault();
        document.getElementById('results').innerHTML = '';
        var prompt = document.getElementById('prompt').value;
        // Fetch LLM providers
        let resp = await fetch('/get_llm_providers');
        let data = await resp.json();
        let providers = data.providers;
        let results = [];
        for (let i = 0; i < providers.length; i++) {
            let label = providers[i];
            document.getElementById('progress').innerText = 'Working on: ' + label;
            let llmResp = await fetch('/run_single_llm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: prompt, label: label })
            });
            let llmData = await llmResp.json();
            results.push(llmData);
            // Show partial results as they come in
            let html = '';
            for (let j = 0; j < results.length; j++) {
                let r = results[j];
                let boxId = `llm-output-${j}`;
                html += `<div class=\"llm-result\"><div class=\"llm-label\">${r.label}</div><div class=\"llm-timing\">${r.timing || ''}</div><button class=\"copy-btn\" onclick=\"copyToClipboard('${boxId}')\">Copy</button><pre id=\"${boxId}\">${escapeHtml(r.result)}</pre></div>`;
            }
            document.getElementById('results').innerHTML = html;
        }
        // Local Ollama
        document.getElementById('progress').innerText = 'Working on: LOCAL (Ollama)';
        let localResp = await fetch('/run_local_ollama', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: prompt })
        });
        let localData = await localResp.json();
        let boxId = `llm-output-local`;
        let html = document.getElementById('results').innerHTML;
        html += `<div class=\"llm-result\" style=\"background:#1a2b4c;\"><div class=\"llm-label\">LOCAL (Ollama)</div><div class=\"llm-timing\">${localData.timing || ''}</div><button class=\"copy-btn\" onclick=\"copyToClipboard('${boxId}')\">Copy</button><pre id=\"${boxId}\">${escapeHtml(localData.result)}</pre></div>`;
        document.getElementById('results').innerHTML = html;
        document.getElementById('progress').innerText = '';
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
    function showStats() {
        fetch('/stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('stats-panel').style.display = 'block';
            let ctx = document.getElementById('stats-chart').getContext('2d');
            if(window.statsChart) window.statsChart.destroy();
            // Collect all unique token counts
            let tokenSet = new Set();
            for(const llm in data) {
                for(const pt of data[llm]) {
                    tokenSet.add(pt.tokens);
                }
            }
            let allTokens = Array.from(tokenSet).sort((a,b)=>a-b);
            // Build datasets for stacked bar
            let colors = ['#ff6384','#36a2eb','#ffce56','#4bc0c0','#9966ff','#ff9f40'];
            let datasets = [];
            let idx = 0;
            for(const llm in data) {
                let barData = allTokens.map(tok => {
                    let found = data[llm].find(pt => pt.tokens === tok);
                    return found ? found.real : 0;
                });
                datasets.push({
                    label: llm,
                    data: barData,
                    backgroundColor: colors[idx % colors.length],
                    stack: 'Stack 0',
                    borderWidth: 1
                });
                idx++;
            }
            window.statsChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: allTokens,
                    datasets: datasets
                },
                options: {
                    plugins: { legend: { labels: { color: '#fff' } } },
                    responsive: true,
                    scales: {
                        x: { title: { display: true, text: 'Tokens', color: '#fff' }, ticks: { color: '#fff' }, stacked: true },
                        y: { title: { display: true, text: 'Real Time (s)', color: '#fff' }, ticks: { color: '#fff' }, stacked: true }
                    }
                }
            });
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
    <button onclick="showStats()" style="margin-bottom:1em;">Show Stats</button>
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
    <div id="stats-panel">
        <canvas id="stats-chart" width="800" height="400"></canvas>
    </div>
</body>
</html>
'''

@app.route('/stats')
def stats():
    # Parse the log file and return JSON for plotting
    stats_data = {}
    try:
        with open(LOG_PATH, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) != 6:
                    continue
                llm, real, user, sys_, tokens, epoch = parts
                real = float(real)
                tokens = int(tokens)
                if llm not in stats_data:
                    stats_data[llm] = []
                stats_data[llm].append({'tokens': tokens, 'real': real})
    except Exception:
        pass
    return jsonify(stats_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
