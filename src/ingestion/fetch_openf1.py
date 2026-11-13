import requests
from urllib.parse import urlencode
from pathlib import Path
from time import sleep
import json

session_id = 9558
year = 2024

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
    "session_name",
    "max_sessions"]

for req in required:
    if req not in config:
        raise ValueError(f"Config error: '{req}' required configuration variable is missing")

    
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

print("Preliminary check: Endpoints and required fields verified and passed\n")

def discover_sessions(year, session_name, landingp, session_timeout, max_retry, gap_bw_retry, base_url, repo_root):

    params = urlencode({
        "year" : year,
        "session_name" : session_name
    })

    session_path = repo_root/landingp/"sessions"/str(year)
    session_path.mkdir(parents=True, exist_ok=True)
    session_path = session_path/"sessions.json"

    session_call_response = get_with_retry(base_url, f"sessions?{params}", session_timeout, max_retry, gap_bw_retry)

    if session_call_response.status_code == 200:
        json_session_response = session_call_response.json()
        safe_write(session_path, session_call_response.text)
        print("Saved sessions")
        session_list = []
        for session in json_session_response:
            if not session["is_cancelled"]:
                session_list.append(session["session_key"])
            else:
                print(f"skipping session_key: {session['session_key']}\n----Info: Circuit Name: {session['location']}, Country: {session['country_name']} and year: {session['year']}; as it is cancelled----")
        if not session_list:
            raise ValueError(f"List is empty, please change parameters, {year}")
        else:
            return session_list
    elif session_call_response.status_code == 404:
        raise ValueError(f"No data for {year} with session: {session_name}")
    else:
        raise ValueError(f"Exited with {session_call_response.status_code} for {year}")


def get_with_retry(base_url, query_url, timeout, max_retries, retry_wait):
    for attempt in range (1, max_retries+1):
        print(f"Attempt {attempt} of {max_retries}...")
        try:
            response = requests.get(url=base_url+query_url,timeout=timeout)
            return response
        except(requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            print(f"Request failed on {base_url+query_url}")
            print("retrying....")
            sleep(retry_wait)
    raise ConnectionError(f"Request failed after {max_retries} retries on url:{base_url+query_url}")

    
def safe_write(path, text):
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def fetch_and_save(endpoint_name, session_key, year, delay_bw_req, base_api_url, landing_dir, request_timeout, checkpoint_path, checkpoint_list, max_retries, sleep_time_retry, driver_number=None):

    file_name = f"{endpoint_name}.json"
    base_path = landing_dir/endpoint_name/str(year)
    path_with_session_id = base_path/str(session_key)

    params = {
        "session_key":session_key
        }
    
    if driver_number is not None:
        params["driver_number"] = driver_number
        file_name = f"driver_{driver_number}.json"

    built_checkpoint_id = f"{endpoint_name}/{year}/{session_key}/{file_name}"
    if built_checkpoint_id in checkpoint_list:
        if driver_number is not None:
            print(f"File already found, skipping {endpoint_name} for driver {driver_number}\n")
            return
        else:
            print(f"File already found, skipping {endpoint_name}\n")
            return
    
    query_url = f"{endpoint_name}?" + urlencode(params)
    build_file_path = path_with_session_id/file_name

    print(f"Fetching endpoint: {endpoint_name}\n")

    response = get_with_retry(base_api_url,query_url,request_timeout, max_retries, sleep_time_retry)
    sleep(delay_bw_req)
    status = response.status_code

    print(f"API responded with status: {status}\n")
    if status == 200:
        data = response.json()
        path_with_session_id.mkdir(parents=True, exist_ok=True)
        safe_write(build_file_path,response.text)
        
        print(f"json saved at path {path_with_session_id} with file name {file_name}\n")
        print(f"rows fetched in {file_name}: {len(data)}")
  
    elif status == 404:
        print(f"No data found for the parameters: endpoint: {endpoint_name}, year: {year}, session: {session_key}")
    else:
        raise ValueError(f"Exited with status {status} for endpoint {endpoint_name}")
    checkpoint_list.append(built_checkpoint_id)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    safe_write(checkpoint_path, json.dumps(checkpoint_list))

# main-call-----
print("Discovering sessions.....")

sessions_all = discover_sessions(year, config["session_name"], config["landing_dir"], config["request_timeout"], config["max_retries"], config["retry_wait"], config["base_api_url"], repo_root)

selected_sessions = sessions_all[:config["max_sessions"]]

print(f"\n{len(selected_sessions)} out of {len(sessions_all)} sessions stored in selected_sessions\n")
if session_id in sessions_all:
    print(f"Check passed: Found {session_id} in sessions list")
else:
    print(f"Check failed: {session_id} not found in discovery")

for s_selected in selected_sessions:
    print(f"-----fetching session_id: {s_selected}-----\n")
    for endpoint in config["openf1_endpoints"]:
        fetch_and_save(endpoint,s_selected,year,config["delay_between_requests"],config["base_api_url"], repo_root/config["landing_dir"],config["request_timeout"], checkpoint_path, check, config["max_retries"], config["retry_wait"])

    driver_num_list = []
    driver_num_append = repo_root / config["landing_dir"] / "drivers" / str(year) / str(s_selected) / "drivers.json"
    read_driver_num = driver_num_append.read_text(encoding="utf-8")
    driver_num_info = json.loads(read_driver_num)

    for number in driver_num_info:
        driver_num_list.append(number["driver_number"])
    print(len(driver_num_list))

    for t_endpoint in config["openf1_telemetry_ends"]:
        for driver in driver_num_list:
            fetch_and_save(t_endpoint,s_selected,year,config["delay_between_requests"],config["base_api_url"], repo_root/config["landing_dir"],config["request_timeout"],checkpoint_path, check, config["max_retries"], config["retry_wait"], driver)

