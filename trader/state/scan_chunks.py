import requests
import re

url = 'https://demo.delta.exchange/app/static/js/index.CI0-RKOe.js'
js = requests.get(url, timeout=15).text

# find chunk names e.g. /app/static/js/...
chunks = re.findall(r'\"([^\"]+\.js)\"', js)
print("Chunks in loader:", chunks)

# also search for api strings or env configs
for line in js.split(';'):
    if 'api' in line.lower() or 'delta' in line.lower():
        print("Line:", line[:150])

