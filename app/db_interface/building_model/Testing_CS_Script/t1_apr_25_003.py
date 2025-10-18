
import requests
import json

url = "https://api.coresignal.com/cdapi/v2/company_multi_source/search/es_dsl"

payload = json.dumps({
    "query": {
        "bool": {
            "must": [
                {
                    "match": {
                        "key_executive_arrivals.arrival_date": "Sep 2025"
                    }
                },
                {
                    "match_phrase": {
                        "key_executive_arrivals.member_position_title": "Senator"
                    }
                }
            ]
        }
    }
})

headers = {
    'Content-Type': 'application/json',
    'apikey': 'U3UG17rFdQ0jv47caYoTIjwyKnnmtAtH'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)


