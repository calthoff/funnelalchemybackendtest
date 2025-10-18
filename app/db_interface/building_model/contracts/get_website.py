"""
use the usaid api to get website/domain for a particualr agency
_ml_ Oct 2025
"""
import requests

def fetch_funding_agency_website(agency_id):
    url = f"https://api.usaspending.gov/api/v2/references/agency/{agency_id}/"
    print(f"url agency = |{url}|")

    try:
        response = requests.get(url)

        if response.status_code == 200:
            print(f"response is 200")
            print(f" type of response = |{type(response)}|")
            #print(f"val of website = |{response['results']['website']}|")
            data = response.json()
            print(f" type of data = |{type(data)}|")
            #return data.get('website')  # Returns URL like "https://www.example.gov"
            return  data['results']['website'] # Returns URL like "https://www.example.gov"
    except Exception as e:
        print(f"Error getting website : |{str(e)}|")
        return "unknown-website"

website = fetch_funding_agency_website("168")
print(f"website of 168 = |{website}|")

