import httpx

try:
    r = httpx.get("https://dadosabertos.cgu.gov.br/api/3/action/package_search?q=emendas+parlamentares")
    if r.status_code == 200:
        data = r.json()
        for res in data.get('result', {}).get('results', []):
            if 'emendas' in res.get('title', '').lower():
                print(f"Title: {res.get('title')}")
                for resource in res.get('resources', []):
                    if resource.get('format', '').lower() == 'csv':
                        print(f"  CSV URL: {resource.get('url')}")
except Exception as e:
    print(e)
