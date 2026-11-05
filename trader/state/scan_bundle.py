import requests
import re

url = 'https://demo.delta.exchange/app/static/js/index.CI0-RKOe.js'
r = requests.get(url, timeout=15)
print("Bundle size:", len(r.text))

# Search for api domains
domains = set(re.findall(r'https://[a-zA-Z0-9.-]+\.[a-z]{2,5}', r.text))
print("Domains found in bundle:")
for d in sorted(domains):
    if any(k in d for k in ('delta', 'api', 'cdn')):
        print("  *", d)

# Search for /v2/wallet or /v2/orders
print("\nEndpoints context:")
for m in re.finditer(r'/v2/[a-zA-Z_/]+', r.text):
    start = max(0, m.start() - 60)
    end = min(len(r.text), m.end() + 60)
    context = r.text[start:end]
    if 'http' in context:
        print("  ->", context)

