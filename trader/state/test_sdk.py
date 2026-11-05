from delta_rest_client import DeltaRestClient

api_key = 'u7SrQxD6rzNG5DIhrJ2Qy4VRXhCmNi'
api_secret = '70Zf7A3MBz8MdlKI4UK3Lh5Axelatl4oTTp5Smu2nJjs9l9Jvhrvz81kl279'

urls = [
    ('India Testnet / Demo', 'https://cdn-ind.testnet.deltaex.org'),
    ('Global Testnet', 'https://testnet-api.delta.exchange'),
    ('India Live', 'https://api.india.delta.exchange'),
    ('Global Live', 'https://api.delta.exchange'),
]

for name, base_url in urls:
    print(f"\n--- Testing {name} ({base_url}) ---")
    try:
        client = DeltaRestClient(
            base_url=base_url,
            api_key=api_key,
            api_secret=api_secret
        )
        bal = client.get_balances(asset_id=1)
        print(f"SUCCESS! Result: {bal}")
    except Exception as e:
        print(f"FAILED: {e}")
