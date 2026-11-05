import requests

subdomains = [
    'https://demo.delta.exchange',
    'https://api.delta.exchange',
    'https://api.india.delta.exchange',
    'https://cdn.india.delta.exchange',
    'https://cdn-ind.deltaex.org',
    'https://cdn-ind.testnet.deltaex.org',
    'https://cdn.testnet.deltaex.org',
    'https://testnet-api.delta.exchange',
    'https://testnet.delta.exchange',
    'https://demo-api.delta.exchange',
    'https://api-demo.delta.exchange',
    'https://cdn-demo.delta.exchange',
    'https://india-api.delta.exchange'
]

for s in subdomains:
    try:
        r = requests.get(f'{s}/v2/products', timeout=3)
        print(f"{s} -> {r.status_code}")
    except Exception as e:
        pass

