# optum_scripts
transfer landing area for public scripts


-rwxr-xr-x 1 jay jay 13830 Jun 27 18:51 run_llms_web.py
-rwxr-xr-x 1 jay jay  1432 Jun 27 18:51 run_all_llms.py
-rwxr-xr-x 1 jay jay  2662 Jun 27 18:51 ask_local_llama.py
-rwxr-xr-x 1 jay jay  4761 Jun 27 18:51 ask_llm.py
-rw-r--r-- 1 jay jay  3051 Jun 27 18:51 README.md
-rwxr-x--- 1 jay jay 11939 Jun 27 18:55 authlog_collector_agents.py

ask_llm.py: general script for LM query, specify -H chatgpt, gemini, claude, local

run_llms_web.py: simple web form generator that will call prompt on multiple LLMs, logging times and tokens and graphing results.

run_all_llms.py: command line tool to run prompt on multiple llms

ask_local_llama.py:  local llama3 LM query script example

authlog_collector_agents.py:  example script that uses AI agents coordinating tasks



Notes on using Ollama to install and run a local LLM:
-----------------------------------------------------
Here’s a concrete, step-by-step on Ubuntu (or any Debian-based Linux) to get Ollama up and running, then pull and run Llama 3.


# 1. Update package list & install curl (if missing)
sudo apt update
sudo apt install -y curl unzip

# 2. Install Ollama via their official installer
curl -fsSL https://ollama.com/install.sh | sh

– This will fetch the latest Ollama CLI and daemon, install under /usr/local/bin/ollama and set up necessary service files.

# 3. Verify Ollama is installed
ollama --version
# e.g. “ollama version 0.4.1” prints out


# 4. Pull the Llama 3 model
ollama pull llama3
# downloads ~4 GB of model files into ~/.ollama/models/llama3


# 5. Start an interactive session with Llama 3
ollama run llama3

# You’ll see a prompt:
#    Llama 3 ready. Input your query below.
# Type, e.g.: “What is the capital of France?”
# and get instant, local replies.


Behind the scenes, ollama pull fetches and unpacks a pre-tokenized binary of the model, while ollama run spins up the lightweight Ollama server that runs inference via optimized Metal/CUDA kernels or pure-CPU fallbacks depending on your hardware.
Tips:

- If you want to serve it as a local HTTP API:

ollama serve

- then POST to http://localhost:11434/api/generate with your JSON payload.

- To list/download other variants (e.g. llama3:3b for a 3 B-param flavor):
ollama pull llama3:3b
ollama run llama3:3b


Notes on environmental variables and keys needed:
-------------------------------------------------

Have these env variables set in your login env, and/or create .llm_config in same dir as ask_llm.py script with these API keys set

export OPENAI_API_KEY=...
export GOOGLE_API_KEY=...
export ANTHROPIC_API_KEY=...

Here’s how you can generate API keys for the three major public LLM providers—OpenAI (ChatGPT), Google (Gemini), and Anthropic (Claude):

🔑 OpenAI (ChatGPT)
- Go to the OpenAI API platform and sign in or create an account.
- https://platform.openai.com/api-keys
- Click your profile icon in the top-right corner and select "View API Keys."
- Click "Create new secret key" and copy it immediately—OpenAI won’t show it again.
- Set it as an environment variable:
export OPENAI_API_KEY="your-key-here"

🔑 Google Gemini
- Visit Google AI Studio and sign in with your Google account.
- https://ai.google.dev/gemini-api/docs/api-key
- Create a new project if needed.
- Click "Get API Key" and follow the prompts.
- Save the key and set it:
export GOOGLE_API_KEY="your-key-here"

🔑 Anthropic (Claude)
- Go to Anthropic Console and sign up or log in.
- https://console.anthropic.com/dashboard
- In the bottom-left corner, click the key icon and select "API Keys."
- Click "Create Key", name it, and copy it immediately.
- Set it like this:
export ANTHROPIC_API_KEY="your-key-here"

Each provider may require billing info or usage limits depending on your plan





