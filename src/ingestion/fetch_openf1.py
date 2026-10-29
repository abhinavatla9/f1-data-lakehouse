import requests
from urllib.parse import urlencode
from pathlib import Path
from time import sleep

f1_endpoints = ["laps", "stints", "pit", "position", "intervals", "weather", "race_control", "drivers"]

def fetch_and_save(endpoint_name, sess_key, year):
    base_url = "https://api.openf1.org/v1/"
    file_name = f"{endpoint_name}.json"
    base_path = f"data/landing/openf1/{endpoint_name}/{year}"
    full_path = Path(base_path)/str(sess_key)
    file_path = full_path/str(file_name)
    query_url = f"{endpoint_name}?" + urlencode({"session_key":sess_key})

    print(f"Fetching endpoint: {endpoint_name}")

    response = requests.get(url=base_url+query_url,timeout=30)
    status = response.status_code

    print(f"API responded with status: {status}")

    if status == 200:
        data = response.json()
        full_path.mkdir(parents=True, exist_ok=True)
        file_path.write_text(response.text, encoding="utf-8")
        
        print(f"json saved at path {full_path} with file name {file_name}")
        print(f"rows fetched in {file_name}: {len(data)}")
    elif status == 404:
        print(f"No data found for the paramaters: endpoint: {endpoint_name}, year: {year}, session: {sess_key}")
    else:
        raise ValueError(f"Exited with status {status} for endpoint {endpoint_name}")
    

for endpoint in f1_endpoints:
    fetch_and_save(endpoint,9558,2024)
    sleep(3)
