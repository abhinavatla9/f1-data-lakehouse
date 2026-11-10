import requests
from urllib.parse import urlencode
from pathlib import Path
from time import sleep
import json

session_id = 9558
year = 2028

repo_root = Path(__file__).resolve().parents[2]

config_path = repo_root / "config" / "openf1.json"
config_text = config_path.read_text(encoding="utf-8")
config = json.loads(config_text)
required = ["base_api_url",
    "landing_dir",
    "delay_between_requests",
    "request_timeout",
    "openf1_endpoints",
    "openf1_telemetry_ends",
    "max_retries",
    "retry_wait",
    "sessions",
    "max_sessions"]

for req in required:
    if req not in config:
        raise ValueError(f"Config error: '{req}' missing in openf1.json")

def discover_sessions(year, session_name):
    params = urlencode({
        "year" : year,
        "session_name" : session_name
    })
    path_sess = Path(__file__).resolve().parents[2]/config["landing_dir"]/"sessions"/str(year)
    path_sess.mkdir(parents=True, exist_ok=True)
    path_sess = path_sess/"sessions.json"
    sess_response = get_with_retry("https://api.openf1.org/v1/", f"sessions?{params}", 30, 3, 2)
    if sess_response.status_code == 200:
        safe_write(path_sess, sess_response.text)
        print("Saved sessions")
    elif sess_response.status_code == 404:
        print("No data for given params")
    else:
        raise ValueError(f"Exited with {sess_response.status_code}")
    
checkpoint_path = repo_root / config["data_path"] / "_checkpoint" / "snapshot.json"
if checkpoint_path.exists():
    print("checkpoint found, resuming")
    check_read = checkpoint_path.read_text(encoding="utf-8")
    check = json.loads(check_read)
else:
    check = []

for req in required:
    if req not in config:
        raise ValueError(f"Config error: '{req}' missing in openf1.json")

verified_endps = ["laps", "stints", "pit", "position", "intervals", "weather", "race_control", "drivers", "car_data", "location"]
joined_config_list = config["openf1_telemetry_ends"] + config["openf1_endpoints"]
for c_end in joined_config_list:
    if c_end not in verified_endps:
        raise ValueError(f"Endpoint names not accurate: {c_end}")

print("Endpoints and required fields verified and passed")

def get_with_retry(base_url, query_url, timeout, max_retries, retry_wait):
    for attempt in range (1, max_retries+1):
        print(f"Attempt {attempt} of {max_retries}")
        try:
            response = requests.get(url=base_url+query_url,timeout=timeout)
            return response
        except(requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            print(f"Request failed on {base_url+query_url}")
            print("retrying....")
            sleep(retry_wait)
    raise ConnectionError(f"request failed after {max_retries} on {base_url+query_url}")

    
def safe_write(path, text):
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def fetch_and_save(endpoint_name, sess_key, year, delay_bw_req, base_api_url, landing_dir, request_timeout, checkpoint_path, checkpoint_list, max_retries, sleep_time_retry, driver_number=None):

    file_name = f"{endpoint_name}.json"
    base_path = landing_dir/endpoint_name/str(year)
    path_with_session_id = base_path/str(sess_key)

    params = {
        "session_key":sess_key
        }
    
    if driver_number is not None:
        params["driver_number"] = driver_number
        file_name = f"driver_{driver_number}.json"

    build_string = f"{endpoint_name}/{year}/{sess_key}/{file_name}"
    if build_string in checkpoint_list:
        if driver_number is not None:
            print(f"File already found, skipping {endpoint_name} for driver {driver_number}")
            return
        else:
            print(f"File already found, skipping {endpoint_name}")
            return
    
    query_url = f"{endpoint_name}?" + urlencode(params)
    file_path = path_with_session_id/file_name

    print(f"Fetching endpoint: {endpoint_name}")

    response = get_with_retry(base_api_url,query_url,request_timeout, max_retries, sleep_time_retry)
    sleep(delay_bw_req)
    status = response.status_code

    print(f"API responded with status: {status}")
    if status == 200:
        data = response.json()
        path_with_session_id.mkdir(parents=True, exist_ok=True)
        safe_write(file_path,response.text)
        
        print(f"json saved at path {path_with_session_id} with file name {file_name}")
        print(f"rows fetched in {file_name}: {len(data)}")
  
    elif status == 404:
        print(f"No data found for the parameters: endpoint: {endpoint_name}, year: {year}, session: {sess_key}")
    else:
        raise ValueError(f"Exited with status {status} for endpoint {endpoint_name}")
    checkpoint_list.append(build_string)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    safe_write(checkpoint_path, json.dumps(checkpoint_list))
            
      
for endpoint in config["openf1_endpoints"]:
    fetch_and_save(endpoint,session_id,year,config["delay_between_requests"],config["base_api_url"], repo_root/config["landing_dir"],config["request_timeout"], checkpoint_path, check, config["max_retries"], config["retry_wait"])

driver_num = []
numbers = repo_root / config["landing_dir"] / "drivers" / str(year) / str(session_id) / "drivers.json"
text_num = numbers.read_text(encoding="utf-8")
data_n = json.loads(text_num)

# for drn in data_n:
#     driver_num.append(drn["driver_number"])
# print(len(driver_num))

# for endp in config["openf1_telemetry_ends"]:
#     for driver in driver_num:
#         fetch_and_save(endp,session_id,year,config["delay_between_requests"],config["base_api_url"], repo_root/config["landing_dir"],config["request_timeout"],checkpoint_path, check, config["max_retries"], config["retry_wait"], driver)

discover_sessions(year, config["sessions"])