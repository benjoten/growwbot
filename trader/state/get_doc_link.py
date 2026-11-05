import requests
import re

r = requests.get('https://demo.delta.exchange/app/account/manageapikeys', timeout=6)
# look for doc links or api links
for link in re.findall(r'href="([^"]+)"', r.text):
    if 'api' in link.lower() or 'doc' in link.lower():
        print("Link:", link)

