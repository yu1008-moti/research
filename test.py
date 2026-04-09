import requests
import os 

headers = {"x-api-key": os.getenv('jq_api_key')}
resp = requests.get(
    "https://api.jquants.com/v2/equities/master",
    params={"date": "2022-11-11"},
    headers=headers,
)
data = resp.json()['data']
print(data[:5])