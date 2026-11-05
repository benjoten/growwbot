import requests

for f in ['static/js/urls.D6mLNrCf.chunk.js', 'static/js/config.C12ugxG4.chunk.js', 'static/js/api.DxE0lYfN.chunk.js']:
    url = 'https://demo.delta.exchange/app/' + f
    try:
        t = requests.get(url, timeout=10).text
        print(f"\n=== {f} ===")
        for line in t.split(','):
            if any(k in line.lower() for k in ('http', 'api', 'url', 'base')):
                print(" ", line[:120])
    except Exception as e:
        print("Error fetching", f, e)

