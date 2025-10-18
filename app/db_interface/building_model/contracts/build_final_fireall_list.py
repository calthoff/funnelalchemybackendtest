"""
generate the final csv document
_ml_ Oct 2025
"""

import csv
import time
from requests.exceptions import RequestException
import requests
# ---------------------- Given API functions ----------------------

def fetch_usaspending_award(award_id):
    """
    Fetch award data from USAspending API using award_id.
    """
    base_url = "https://api.usaspending.gov/api/v2/awards/"
    url = f"{base_url}{award_id}/"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except RequestException as e:
        print(f"Error fetching data for {award_id}: {e}")
        return None


def get_contract_values(contract_id):
    cvalues = {}
    response = fetch_usaspending_award(contract_id)
    if not response:
        # return default values when request fails
        return {
            'award_amount': 'unknown',
            'start_date': 'unknown',
            'end_date': 'unknown',
            'award_agency': 'unknown',
            'award_id': 'unknown',
            'award_website': 'unknown',
            'award_domain': 'unknown',
            'naic_code': 'unknown',
            'naics_description': 'unknown',
            'place_of_performance': 'unknown/unknown/unknown',
            'agency_id': 'unknown'
        }

    try:
        response_keys = response.keys()
        cvalues['award_amount'] = response.get('total_obligation', 'unknown')
        cvalues['start_date'] = response.get('period_of_performance', {}).get('start_date', 'unknown')
        cvalues['end_date'] = response.get('period_of_performance', {}).get('end_date', 'unknown')
        cvalues['award_agency'] = (
            response.get('awarding_agency', {})
            .get('toptier_agency', {})
            .get('name', 'unknown')
        )

        if 'latest_transaction_contract_data' in response_keys:
            ltd = response['latest_transaction_contract_data']
            cvalues['naic_code'] = ltd.get('naics', 'unknown')
            cvalues['naics_description'] = ltd.get('naics_description', 'unknown')
        else:
            cvalues['naic_code'] = "unknown"
            cvalues['naics_description'] = "unknown"

        if 'place_of_performance' in response:
            pop = response['place_of_performance']
            country_code = pop.get('location_country_code') or "unknown-country"
            state_name = pop.get('state_name') or "unknown-state"
            zipcode = pop.get('zip5') or "unknown-zip"
            cvalues['place_of_performance'] = f"{country_code}/{state_name}/{zipcode}"
        else:
            cvalues['place_of_performance'] = "unknown/unknown/unknown"

        if ('funding_agency' in response_keys and response['funding_agency'] != None):
            if('id' in response['funding_agency'].keys()):
                cvalues['agency_id'] = response['funding_agency']['id']
            else:    
                cvalues['agency_id'] = "unknown"
        else:
            cvalues['agency_id'] = "unknown"


    except Exception as e:
        print(f"Error parsing response for {contract_id}: {e}")
        cvalues = {
            'award_amount': 'unknown',
            'start_date': 'unknown',
            'end_date': 'unknown',
            'award_agency': 'unknown',
            'award_id': 'unknown',
            'award_website': 'unknown',
            'award_domain': 'unknown',
            'naic_code': 'unknown',
            'naics_description': 'unknown',
            'place_of_performance': 'unknown/unknown/unknown',
            'agency_id': 'unknown'
        }
    return cvalues


def fetch_funding_agency_website(agency_id):
    url = f"https://api.usaspending.gov/api/v2/references/agency/{agency_id}/"

    try:
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            return  data['results']['website'] # Returns URL like "https://www.example.gov"
    except Exception as e:
        print(f"Error getting agency website : |{str(e)}|")
        return "unknown-website"




from urllib.parse import urlparse

def get_domain_from_website(agency_website):
    """
    Extract the domain name from a URL.
    
    Args:
        agency_website (str): The URL to extract the domain from (e.g., "https://www.usda.gov/")
        
    Returns:
        str: The domain name (e.g., "usda.gov"), or None if the URL is invalid
    """
    try:
        # Parse the URL to extract the netloc (network location)
        parsed_url = urlparse(agency_website)
        # netloc includes hostname and port (if any); we only want hostname
        domain = parsed_url.netloc
        # Remove 'www.' prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception as e:
        print(f"Error parsing URL to get domain: {e}")
        return "unknown-domain"



# ---------------------- Main driver ----------------------

INPUT_FILE = "firewall_items.csv"
OUTPUT_FILE = "firewall_items_final.csv"

def main():
    print("Starting enrichment process...\n")

    agency_websites = {}

    with open(INPUT_FILE, newline='', encoding="utf-8") as infile, \
         open(OUTPUT_FILE, "w", newline='', encoding="utf-8") as outfile:

        reader = csv.DictReader(infile)
        fieldnames = [
            "contract_award_id", "Recipient_name", "transaction_description",
            "award_amount", "start_date", "end_date", "award_agency","agency_id","agency_website", "agency_domain",
            "naic_code", "naics_description", "place_of_performance", "usaid_url"
        ]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for i, row in enumerate(reader, start=1):
            contract_id = row["contract_award_id"].strip()
            if not contract_id:
                continue

            print(f"[{i}] Fetching details for: {contract_id} ...")
            contract_values = get_contract_values(contract_id)
            time.sleep(0.5)  # polite delay to avoid rate limiting

            agency_id = contract_values.get("agency_id", "unknown")
            agency_website = "unknown"
            agency_domain = "unknown"
            #get website and domain if not already in agency_websites dict
            if(agency_id and agency_id != "unknown"):
                if(agency_id in agency_websites):
                    agency_website = agency_websites[agency_id][0] 
                    agency_domain = agency_websites[agency_id][1] 
                else:
                    agency_websites[agency_id] = []
                    agency_website = fetch_funding_agency_website(agency_id)
                    agency_domain = get_domain_from_website(agency_website)
                    agency_websites[agency_id].append(agency_website)
                    agency_websites[agency_id].append(agency_domain)




            output_row = {
                "contract_award_id": contract_id,
                "Recipient_name": row.get("Recipient_name", ""),
                "transaction_description": row.get("transaction_description", ""),
                "award_amount": contract_values.get("award_amount", "unknown"),
                "start_date": contract_values.get("start_date", "unknown"),
                "end_date": contract_values.get("end_date", "unknown"),
                "award_agency": contract_values.get("award_agency", "unknown"),
                "agency_id": agency_id,
                "agency_website": agency_website,
                "agency_domain": agency_domain,
                "naic_code": contract_values.get("naic_code", "unknown"),
                "naics_description": contract_values.get("naics_description", "unknown"),
                "place_of_performance": contract_values.get("place_of_performance", "unknown/unknown/unknown"),
                "usaid_url": row.get("usaid_url", "")
            }

            writer.writerow(output_row)
            #break
    
    print(f"\n Done! Enriched data written to: {OUTPUT_FILE}")
    print(f"length of dict agency_websites = |{len(agency_websites)}|")


if __name__ == "__main__":
    main()


