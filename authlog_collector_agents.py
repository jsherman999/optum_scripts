#!/usr/bin/python3

import glob
import re



import autogen
import os
import datetime
import sys
import subprocess



# Prefer API key from .llm_config in current directory, else from env, else error
llm_config_path = os.path.join(os.getcwd(), ".llm_config")
api_key = None
if os.path.exists(llm_config_path):
    with open(llm_config_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == "OPENAI_API_KEY":
                        api_key = v.strip()
                        break
if not api_key:
    api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Error: OPENAI_API_KEY not found in .llm_config or environment. Please provide your OpenAI API key.")
    sys.exit(1)
os.environ["OPENAI_API_KEY"] = api_key

os.environ["AUTOGEN_USE_DOCKER"] = "0"


# Configure for OpenAI paid tier model (e.g., gpt-4o or gpt-4-turbo)
config_list = [
    {
        "model": "gpt-4o",  # Or "gpt-4-turbo" for the first paid tier
        "api_key": os.getenv("OPENAI_API_KEY"),
    }
]

# Define the ReAct prompt for the ping/ssh checker agent
ping_ssh_prompt = """
You are a network assistant. Your job is to check if a given hostname is reachable via ping and ssh (without a password).

{{hostname}}

Respond with "reachable" if both ping and ssh succeed (without needing a password). Respond with "unreachable" if either fails. If you cannot complete the check for any reason, respond with "error: <reason>" (replace <reason> with a brief explanation). Do not provide any other output. Perform actual checks using ping and ssh commands.
"""

# Define the ReAct prompt for the authlog retriever agent
authlog_retrieval_prompt = """
You are a log retrieval assistant. Your job is to connect to a reachable host via ssh (assuming no password is required) and retrieve the /var/log/auth.log file.

{{hostname}}

Retrieve the file and save it locally as {hostname}_auth.log.YYYYMMDDhhmmss, replacing YYYYMMDDhhmmss with the current timestamp. Return "success" upon successful retrieval and save. If you cannot complete the task for any reason, respond with "error: <reason>" (replace <reason> with a brief explanation).
"""


def main():
    llm_config = {"config_list": config_list, "seed": 42}


    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        system_message="You are a user. Provide hostnames one at a time to be checked.",
        llm_config=llm_config,
    )

    network_assistant = autogen.AssistantAgent(
        name="network_assistant",
        system_message=ping_ssh_prompt,
        llm_config=llm_config,
        code_execution_config={"work_dir": "workspace"},
    )

    log_retrieval_assistant = autogen.AssistantAgent(
        name="log_retrieval_assistant",
        system_message=authlog_retrieval_prompt,
        llm_config=llm_config,
        code_execution_config={"work_dir": "workspace"},
    )

    # Get hostname from command line or ask via proxy agent
    if len(sys.argv) > 1:
        hostname = sys.argv[1]
    else:
        print("No hostname supplied on command line. Please provide a hostname when prompted.")
        user_proxy.initiate_chat(network_assistant, message="Please provide a hostname to check.")
        last_msg = user_proxy.last_message["content"] if hasattr(user_proxy, "last_message") else ""
        if ":" in last_msg:
            hostname = last_msg.split(":", 1)[1].strip()
        else:
            hostname = last_msg.strip()

    # --- Actual OS actions for ping and ssh ---
    def is_reachable(host):
        try:
            # Ping
            ping_result = subprocess.run(["ping", "-c", "1", host], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if ping_result.returncode != 0:
                return False, "Ping failed"
            # SSH (BatchMode to avoid password prompt)
            ssh_result = subprocess.run(["ssh", "-o", "BatchMode=yes", host, "exit"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            if ssh_result.returncode != 0:
                return False, "SSH failed"
            return True, ""
        except Exception as e:
            return False, f"Exception: {e}"

    def retrieve_auth_log(host):
        try:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
            localfile = f"{host}_auth.log.{date_str}"
            # Download the remote auth.log to a temp file
            tmpfile = f"{localfile}.tmp"
            scp_result = subprocess.run(["scp", f"{host}:/var/log/auth.log", tmpfile], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
            if scp_result.returncode != 0:
                if os.path.exists(tmpfile):
                    os.remove(tmpfile)
                return False, scp_result.stderr.decode().strip()
            # Append only new lines to the local log
            existing = set()
            if os.path.exists(localfile):
                with open(localfile, "r") as f:
                    for line in f:
                        existing.add(line.rstrip("\n"))
            new_lines = []
            with open(tmpfile, "r") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if line not in existing:
                        new_lines.append(line)
            if new_lines:
                with open(localfile, "a") as f:
                    for line in new_lines:
                        f.write(line + "\n")
            os.remove(tmpfile)
            return True, localfile
        except Exception as e:
            return False, f"Exception: {e}"


    # --- Use the agent for messaging, but do real checks ---
    reachable, reason = is_reachable(hostname)
    if reachable:
        user_proxy.send(f"Host {hostname} is reachable via ping and ssh.", user_proxy)
        success, result = retrieve_auth_log(hostname)
        if success:
            user_proxy.send(f"Successfully retrieved /var/log/auth.log from {hostname} and saved as {result}.", user_proxy)
        else:
            user_proxy.send(f"Log retrieval assistant error for {hostname}: {result}", user_proxy)
    else:
        user_proxy.send(f"Network assistant error for {hostname}: {reason}", user_proxy)

    # --- New agent: Extract SSH connections from new auth logs ---
    class SSHLogExtractorAgent:
        def __init__(self, log_dir="."):
            self.log_dir = log_dir
            self.ssh_log_file = os.path.join(log_dir, "ssh_log")
            self.seen_auth_entries = set()
            self.seen_ssh_entries = set()
            self._load_seen_entries()

        def _load_seen_entries(self):
            # Always create ssh_log if it doesn't exist
            if not os.path.exists(self.ssh_log_file):
                with open(self.ssh_log_file, "w") as f:
                    pass
            # Load previously seen entries from ssh_log
            with open(self.ssh_log_file, "r") as f:
                for line in f:
                    self.seen_ssh_entries.add(line.strip())
            # Load previously seen entries from all hostname_authlog.* files
            for authlog in glob.glob(os.path.join(self.log_dir, "*_auth.log.*")):
                with open(authlog, "r") as f:
                    for line in f:
                        self.seen_auth_entries.add(line.strip())

        def extract_new_ssh_entries(self):
            new_ssh_entries = set()
            # Match any line containing 'sshd'
            for authlog in glob.glob(os.path.join(self.log_dir, "*_auth.log.*")):
                with open(authlog, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line not in self.seen_auth_entries:
                            self.seen_auth_entries.add(line)
                        if "sshd" in line and line not in self.seen_ssh_entries:
                            new_ssh_entries.add(line)
                            self.seen_ssh_entries.add(line)
            return new_ssh_entries

        def update_ssh_log(self, new_ssh_entries):
            if new_ssh_entries:
                with open(self.ssh_log_file, "a") as f:
                    for entry in sorted(new_ssh_entries):
                        f.write(entry + "\n")


    # Run the SSHLogExtractorAgent
    extractor = SSHLogExtractorAgent()
    new_ssh_entries = extractor.extract_new_ssh_entries()
    extractor.update_ssh_log(new_ssh_entries)
    if new_ssh_entries:
        user_proxy.send(f"Extracted {len(new_ssh_entries)} new SSH log entries to ssh_log.", user_proxy)
    else:
        user_proxy.send("No new SSH log entries found.", user_proxy)

    # --- New agent: Find and log duplicate private key usage ---
    class PrivateKeyDupAgent:
        def __init__(self, ssh_log_file="ssh_log", output_file="private_key_dups"):
            self.ssh_log_file = ssh_log_file
            self.output_file = output_file
            self.fingerprint_to_sources = {}
            self.dup_lines = set()
            self._load_existing_dups()

        def _load_existing_dups(self):
            if os.path.exists(self.output_file):
                with open(self.output_file, "r") as f:
                    for line in f:
                        self.dup_lines.add(line.strip())

        def find_dups(self):
            # Improved regex for log lines like:
            # 2025-06-27T18:05:53.060626-05:00 j-snapdragon sshd[296384]: Accepted publickey for jay from 127.0.0.1 port 41420 ssh2: ED25519 SHA256:70DIz9llHmJm+a5r59YR/faj53zV+k/GGS+a6rLgHrI
            key_pattern = re.compile(r"^(?P<ts>\S+)\s+\S+\s+sshd\[\d+\]: Accepted publickey for (?P<user>\S+) from (?P<src>[^ ]+) port \d+ ssh2: \S+ (?P<fp>SHA256:[A-Za-z0-9+/=]+)")
            # Map: fingerprint -> set of (source, user, timestamp)
            for line in open(self.ssh_log_file, "r"):
                line = line.strip()
                m = key_pattern.search(line)
                if m:
                    ts = m.group("ts")
                    user = m.group("user")
                    source = m.group("src")
                    fingerprint = m.group("fp")
                    key = fingerprint
                    if key not in self.fingerprint_to_sources:
                        self.fingerprint_to_sources[key] = set()
                    self.fingerprint_to_sources[key].add((source, user, ts))

        def log_dups(self):
            new_dups = set()
            for fingerprint, sources in self.fingerprint_to_sources.items():
                # If the same fingerprint is used from more than one source address
                srcs = set(s[0] for s in sources)
                if len(srcs) > 1:
                    # For each (source, user, ts), only log if this (source, fingerprint) is not already in the log
                    for s in sources:
                        log_line = f"{s[0]},{s[1]},{s[2]},{fingerprint}"
                        # Only add if this source+fp combo is not already in the log
                        if log_line not in self.dup_lines:
                            new_dups.add(log_line)
                            self.dup_lines.add(log_line)
            if new_dups:
                with open(self.output_file, "a") as f:
                    for entry in sorted(new_dups):
                        f.write(entry + "\n")
            return new_dups

    # Run the PrivateKeyDupAgent
    privdup_agent = PrivateKeyDupAgent()
    privdup_agent.find_dups()
    new_dups = privdup_agent.log_dups()
    if new_dups:
        user_proxy.send(f"Found {len(new_dups)} new duplicate private key usages. See private_key_dups.", user_proxy)
    else:
        user_proxy.send("No new duplicate private key usages found.", user_proxy)

if __name__ == "__main__":
    os.makedirs("workspace", exist_ok=True) # Create workspace if doesn't exist.
    main()
