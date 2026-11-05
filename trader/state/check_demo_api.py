import requests
import re
import time
import hmac
import hashlib

api_key = 'u7SrQxD6rzNG5DIhrJ2Qy4VRXhCmNi'
api_secret = '70Zf7A3MBz8MdlKI4UK3Lh5Axelatl4oTTp5Smu2nJjs9l9Jvhrvz81kl279'

# 1. Let's inspect demo.delta.exchange/app/account/manageapikeys HTML / config
r = requests.get('https://demo.delta.exchange/app/account/manageapikeys', timeout=6)
print("Page length:", len(r.text))
matches = set(re.findall(r'https://[^"\'\s<>]+', r.text))
print("Found HTTP links in page:")
for m in matches:
    if 'delta' in m:
        print(" ", m)

# 2. Test signature on different paths
paths = ['/v2/wallet/balances', '/v2/profile', '/v2/orders']
endpoints = [
    'https://cdn-ind.testnet.deltaex.org',
    'https://cdn.testnet.deltaex.org',
    'https://api.india.delta.exchange',
    'https://testnet-api.delta.exchange',
    'https://api.delta.exchange'
]

for base in endpoints:
    ts = str(int(time.time()))
    path = '/v2/profile'
    msg = 'GET' + ts + path
    sig = hmac.new(api_secret.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {
        'api-key': api_key,
        'timestamp': ts,
        'signature': sig,
        'Content-Type': 'application/json'
    }
    try:
        resp = requests.get(base + path, headers=headers, timeout=4)
        print(f"{base}{path} -> {resp.status_code} : {resp.text[:120]}")
    except Exception as e:
        print(f"{base}{path} -> Error: {e}")
