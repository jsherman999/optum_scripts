# optum_scripts
transfer landing area for public scripts

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





