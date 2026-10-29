import requests
from urllib.parse import urlencode
from pathlib import Path
from time import sleep
import json

repo_root = Path(__file__).resolve().parents[2]
config_path = repo_root / "config" / "openf1.json"
config_text = config_path.read_text(encoding="utf-8")
config = json.loads(config_text)
required = ["base_api_url",
    "landing_dir",
    "delay_between_requests",
    "request_timeout",
    "openf1_endpoints",
    "openf1_telemetry_ends"]

for req in required:
    if req not in config:
        raise ValueError(f"Config error: '{req}' missing in openf1.json")

def fetch_and_save(endpoint_name, sess_key, year, base_api_url, landing_dir, request_timeout):

    file_name = f"{endpoint_name}.json"
    base_path = landing_dir/endpoint_name/str(year)

    full_path = base_path/str(sess_key)
    file_path = full_path/file_name
    query_url = f"{endpoint_name}?" + urlencode({"session_key":sess_key})

    print(f"Fetching endpoint: {endpoint_name}")

    response = requests.get(url=base_api_url+query_url,timeout=request_timeout)
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
    
for endpoint in config["openf1_endpoints"]:
    fetch_and_save(endpoint,9558,2024,config["base_api_url"], repo_root/config["landing_dir"],config["request_timeout"])
    sleep(config["delay_between_requests"])