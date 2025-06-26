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
import json as pyjson

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
PROMPT_LOG_PATH = "/var/log/run_llms_web_prompts.jsonl"
logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format='%(message)s')

def log_run(llm_name, real, user, sys_, token_count):
    epoch = int(pytime.time())
    log_line = f"{llm_name},{real:.2f},{user:.2f},{sys_:.2f},{token_count},{epoch}"
    try:
        logging.info(log_line)
    except Exception:
        pass

def log_prompt(llm_name, prompt, real, user, sys_, token_count):
    epoch = int(pytime.time())
    log_entry = {
        "llm": llm_name,
        "prompt": prompt,
        "real": real,
        "user": user,
        "sys": sys_,
        "tokens": token_count,
        "epoch": epoch
    }
    try:
        with open(PROMPT_LOG_PATH, 'a') as f:
            f.write(pyjson.dumps(log_entry) + "\n")
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
    log_prompt(label, prompt, real, user, sys_, token_count)
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
    log_prompt("local", prompt, real, user, sys_, token_count)
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
    function showStats() {
        fetch('/stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('stats-panel').style.display = 'block';
            let ctx = document.getElementById('stats-chart').getContext('2d');
            if(window.statsChart) window.statsChart.destroy();
            let chartData = data.chart;
            let details = data.details;
            // Collect all unique token counts
            let tokenSet = new Set();
            for(const llm in chartData) {
                for(const pt of chartData[llm]) {
                    tokenSet.add(pt.tokens);
                }
            }
            let allTokens = Array.from(tokenSet).sort((a,b)=>a-b);
            // Build datasets for stacked bar (average real time)
            let colors = ['#ff6384','#36a2eb','#ffce56','#4bc0c0','#9966ff','#ff9f40'];
            let datasets = [];
            let idx = 0;
            for(const llm in chartData) {
                let barData = allTokens.map(tok => {
                    let found = chartData[llm].find(pt => pt.tokens == tok);
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
                    onClick: function(evt, elements) {
                        if (elements.length > 0) {
                            let chart = elements[0].element.$context.raw;
                            let tokenIdx = elements[0].index;
                            let tokenVal = allTokens[tokenIdx];
                            let html = '';
                            for(const llm in chartData) {
                                let key = `[\"${llm}\",${tokenVal}]`;
                                let entries = details[key] || [];
                                if(entries.length > 0) {
                                    html += `<div style='margin-bottom:0.5em;'><b>${llm} (tokens: ${tokenVal})</b><ul style='font-size:0.8em;'>`;
                                    for(const entry of entries) {
                                        html += `<li>real: ${entry.real}s<br>prompt: <span style='font-family:monospace;'>${escapeHtml(entry.prompt)}</span></li>`;
                                    }
                                    html += '</ul></div>';
                                }
                            }
                            document.getElementById('bar-details').innerHTML = html;
                            document.getElementById('bar-details').style.display = 'block';
                        }
                    },
                    onHover: function(evt, elements) {
                        // Prevent default context menu on right click
                        document.getElementById('stats-chart').oncontextmenu = function(e) { e.preventDefault(); };
                    },
                    scales: {
                        x: { title: { display: true, text: 'Tokens', color: '#fff' }, ticks: { color: '#fff' }, stacked: true },
                        y: { title: { display: true, text: 'Avg Real Time (s)', color: '#fff' }, ticks: { color: '#fff' }, stacked: true }
                    }
                }
            });
            // Add right click handler for bar
            document.getElementById('stats-chart').addEventListener('contextmenu', function(e) {
                let points = window.statsChart.getElementsAtEventForMode(e, 'nearest', { intersect: true }, true);
                if(points.length > 0) {
                    let point = points[0];
                    let datasetIndex = point.datasetIndex;
                    let tokenIdx = point.index;
                    let llm = window.statsChart.data.datasets[datasetIndex].label;
                    let tokenVal = allTokens[tokenIdx];
                    let key = '["' + llm + '",' + tokenVal + ']';
                    let entries = details[key] || [];
                    if(entries.length > 0) {
                        // Sort by real time
                        entries.sort((a, b) => a.real - b.real);
                        let html = `<div style='margin-bottom:0.5em;'><b>${llm} (tokens: ${tokenVal})</b><table style='font-size:0.8em; color:#fff; background:#222a44; border-radius:8px;'><tr><th>LLM</th><th>Tokens</th><th>Real Time (s)</th><th>Prompt</th></tr>`;
                        for(const entry of entries) {
                            html += `<tr><td>${entry.llm}</td><td>${entry.tokens}</td><td>${entry.real}</td><td style='max-width:400px;overflow-x:auto;white-space:pre;font-family:monospace;'>${escapeHtml(entry.prompt)}</td></tr>`;
                        }
                        html += '</table></div>';
                        document.getElementById('bar-details').innerHTML = html;
                        document.getElementById('bar-details').style.display = 'block';
                    }
                }
                e.preventDefault();
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
        <div id="bar-details" style="display:none; background:#222a44; color:#fff; border-radius:8px; margin-top:1em; padding:1em;"></div>
    </div>
</body>
</html>
'''

@app.route('/stats')
def stats():
    # Parse the log file and return JSON for plotting and for click details
    stats_data = {}
    prompt_details = {}
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
                    stats_data[llm] = {}
                if tokens not in stats_data[llm]:
                    stats_data[llm][tokens] = []
                stats_data[llm][tokens].append(real)
        # Compute averages
        for llm in stats_data:
            for tokens in stats_data[llm]:
                avg_real = sum(stats_data[llm][tokens]) / len(stats_data[llm][tokens])
                stats_data[llm][tokens] = avg_real
        # Load prompt details
        with open(PROMPT_LOG_PATH, 'r') as f:
            for line in f:
                try:
                    entry = pyjson.loads(line)
                    llm = entry['llm']
                    tokens = entry['tokens']
                    if (llm, tokens) not in prompt_details:
                        prompt_details[(llm, tokens)] = []
                    prompt_details[(llm, tokens)].append(entry)
                except Exception:
                    continue
    except Exception:
        pass
    # Format for chart.js: {llm: [{tokens: t, real: avg}, ...]}
    chart_data = {}
    for llm in stats_data:
        chart_data[llm] = []
        for tokens in sorted(stats_data[llm]):
            chart_data[llm].append({'tokens': tokens, 'real': stats_data[llm][tokens]})
    # Prompt details: {(llm, tokens): [entry, ...]}
    return jsonify({'chart': chart_data, 'details': prompt_details})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
