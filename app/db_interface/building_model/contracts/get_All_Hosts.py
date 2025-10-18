import requests
import json

def getWhoisData(domainName: str) -> dict:
    url = "https://www.whoisxmlapi.com/whoisserver/WhoisService"
    headers = {"Content-Type": "application/json"}
    data = {
        "domainName": domainName,
        "apiKey": "at_9YO66ZXIfBaChVkeXVTgmhmlkju1p",
        "outputFormat": "JSON"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"error": f"Failed to fetch WHOIS data: {str(e)}"}


def getDomainsData(domainName: str) -> dict:
    url = "https://domains-subdomains-discovery.whoisxmlapi.com/api/v1"
    headers = {"Content-Type": "application/json"}
    data = {
        "apiKey": "at_9YO66ZXIfBaChVkeXVTgmhmlkju1p",
        "domains": {
            "include": ["lacounty.gov"]
        }
    }    
    
    try:
        response = requests.post(url, headers=headers, json=data)
        #response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"error": f"Failed to fetch subdomains data: {str(e)}"}




def getSubdomainsData(domainName: str) -> dict:
    url = "https://domains-subdomains-discovery.whoisxmlapi.com/api/v1"
    headers = {"Content-Type": "application/json"}
    data = {
        "apiKey": "at_9YO66ZXIfBaChVkeXVTgmhmlkju1p",
        "subdomains": {
            "include": ["lacounty.gov"]
        },

    }    

    
    try:
        response = requests.post(url, headers=headers, json=data)
        #response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"error": f"Failed to fetch subdomains data: {str(e)}"}

if __name__ == "__main__":
    #domain = "lacounty.gov"
    domain = "lacounty.gov"
    #domain = "google.com"
#    domains_data = getDomainsData(domain)
#    print("list of domains")
#    print(json.dumps(domains_data, indent=4))

    subdomains_data = getSubdomainsData(domain)
    #print(f"type of subdomains_data = |{type(subdomains_data)}|")
#    print(f"len of subdomains_data = |{len(subdomains_data)}|")
    print("\n\nlist of sub-domains")
    print(json.dumps(subdomains_data, indent=4))





#domain = "lacounty.gov"
#domain = "google.com"

#whois_data = getWhoisData(domain)
#print(f"type of whoisdata = |{type(whois_data)}|")
#print(f"len of whoisdata = |{len(whois_data)}|")
#print(json.dumps(whois_data, indent=4))

