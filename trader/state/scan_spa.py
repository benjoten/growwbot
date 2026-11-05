import requests
import re

r = requests.get('https://demo.delta.exchange/app', timeout=6)
# find all js urls in index.html
js_files = re.findall(r'src="(/[^"]+\.js)"', r.text)
print("JS files:", js_files)

for f in js_files:
    js_text = requests.get('https://demo.delta.exchange' + f, timeout=8).text
    for match in re.findall(r'https?://[a-zA-Z0-9.-]+\.(?:deltaex|delta)\.[a-zA-Z0-9.-/]+', js_text):
        print("Found in", f, ":", match)

