
import requests
import json

url = "https://api.coresignal.com/cdapi/v2/company_multi_source/collect/4968360"

headers = {
    'Content-Type': 'application/json',
    'apikey': 'U3UG17rFdQ0jv47caYoTIjwyKnnmtAtH'
}

response = requests.request("GET", url, headers=headers)

print(response.text)

