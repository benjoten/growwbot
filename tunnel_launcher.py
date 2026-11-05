import subprocess
import re
import sys
import time

cmd = ["cloudflared.exe", "tunnel", "--url", "http://127.0.0.1:5000"]
print("[Tunnel] Starting Cloudflare Tunnel...")

proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding="utf-8", errors="replace")

url_found = None
url_regex = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

for line in iter(proc.stdout.readline, ''):
    match = url_regex.search(line)
    if match and not url_found:
        url_found = match.group(0)
        with open("tunnel_url.txt", "w", encoding="utf-8") as f:
            f.write(url_found)
        print("\n" + "="*60)
        print(f">> LIVE PUBLIC URL GENERATED: {url_found}")
        print("="*60 + "\n", flush=True)

proc.wait()
