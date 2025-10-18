
import requests
import json

url = "https://api.coresignal.com/cdapi/v2/company_multi_source/search/es_dsl"


payload = json.dumps({
    "query": {
        "bool": {
            "must": [
                {
                    "match": {
                        "key_executive_arrivals.arrival_date": "Apr 2025"
                    }
                },
                {
                    "match_phrase": {
                        "key_executive_arrivals.position_title": "Senator"
                    }
                }
            ]
        }
    }
})


#payload = json.dumps({
#    "query": {
#        "bool": {
#            "must": [
#                {
#                    "match": {
#                        "key_executive_arrivals": "Apr 2025"
#                    }
#                }
#            ]
#        }
#    }
#})

print(f"payload = |{payload}|")

headers = {
    'Content-Type': 'application/json',
    'apikey': 'U3UG17rFdQ0jv47caYoTIjwyKnnmtAtH'
}

response = requests.request("POST", url, headers=headers, data=payload)

#print(len(response.text))
print(response.text)


