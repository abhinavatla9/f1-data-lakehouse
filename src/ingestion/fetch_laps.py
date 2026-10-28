import requests
from urllib.parse import urlencode
from pathlib import Path

session = 9558
base_landing_path = "data/landing/openf1/laps/2024"

params = urlencode({
    "session_key": session
})
url = f"https://api.openf1.org/v1/laps?{params}"

response = requests.get(url=url, timeout=30)
data = response.json()
list_len = len(data)
print(list_len)
print(response.status_code)

path_w_session = Path(base_landing_path)/str(session)
path_w_session.mkdir(parents=True,exist_ok=True)

file_path = path_w_session/"laps.json"
file_path.write_text(response.text,encoding="utf-8")