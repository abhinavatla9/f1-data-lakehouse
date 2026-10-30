import requests
from urllib.parse import urlencode
from pathlib import Path
from time import sleep
import json

session_id = 9558
year = 2024


repo_root = Path(__file__).resolve().parents[2]
checkpoint_path = repo_root / "data" / "_checkpoint"
if checkpoint_path.exists():
    print("checkpoint found, resuming")
else:
    checkpoint_path = checkpoint_path / "snapshot.json"
check_read = checkpoint_path.read_text(encoding="utf-8")
check = json.loads(check_read)



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

verified_endps = ["laps", "stints", "pit", "position", "intervals", "weather", "race_control", "drivers", "car_data", "location"]
joined_config_list = config["openf1_telemetry_ends"] + config["openf1_endpoints"]
for c_end in joined_config_list:
    if c_end not in verified_endps:
        raise ValueError(f"Endpoint names not accurate: {c_end}")

print("Endpoints and required fields verified and passed")


def fetch_and_save(endpoint_name, sess_key, year, delay_bw_req, base_api_url, landing_dir, request_timeout, driver_number=None):

    file_name = f"{endpoint_name}.json"
    base_path = landing_dir/endpoint_name/str(year)
    path_with_session_id = base_path/str(sess_key)

    params = {
        "session_key":sess_key
        }
    
    if driver_number is not None:
        params["driver_number"] = driver_number
        file_name = f"driver_{driver_number}.json"
    
    query_url = f"{endpoint_name}?" + urlencode(params)
    file_path = path_with_session_id/file_name

    print(f"Fetching endpoint: {endpoint_name}")

    response = requests.get(url=base_api_url+query_url,timeout=request_timeout)
    sleep(delay_bw_req)
    status = response.status_code

    print(f"API responded with status: {status}")
    if status == 200:
        data = response.json()
        path_with_session_id.mkdir(parents=True, exist_ok=True)
        file_path.write_text(response.text, encoding="utf-8")
        
        print(f"json saved at path {path_with_session_id} with file name {file_name}")
        print(f"rows fetched in {file_name}: {len(data)}")
    elif status == 404:
        print(f"No data found for the parameters: endpoint: {endpoint_name}, year: {year}, session: {sess_key}")
    else:
        raise ValueError(f"Exited with status {status} for endpoint {endpoint_name}")
            
    
   
for endpoint in config["openf1_endpoints"]:
    fetch_and_save(endpoint,session_id,year,config["delay_between_requests"],config["base_api_url"], repo_root/config["landing_dir"],config["request_timeout"])

driver_num = []
numbers = repo_root / config["landing_dir"] / "drivers" / str(year) / str(session_id) / "drivers.json"
text_num = numbers.read_text(encoding="utf-8")
data_n = json.loads(text_num)

for drn in data_n:
    driver_num.append(drn["driver_number"])
print(len(driver_num))

for endp in config["openf1_telemetry_ends"]:
    for driver in driver_num:
        fetch_and_save(endp,session_id,year,config["delay_between_requests"],config["base_api_url"], repo_root/config["landing_dir"],config["request_timeout"],driver)
