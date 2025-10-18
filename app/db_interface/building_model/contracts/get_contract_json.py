import requests


def fetch_usaspending_award(award_id):
    """
    Fetch award data from USAspending API using award_id.
    
    Args:
        award_id (str): The award ID (e.g., CONT_AWD_H907_9700_SPE2DX16D1500_9700)
        
    Returns:
        dict: JSON response from the API, or None if request fails
    """
    base_url = "https://api.usaspending.gov/api/v2/awards/"
    url = f"{base_url}{award_id}/"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None



def get_contract_values(contract_id):
    cvalues = {}
    response = fetch_usaspending_award(contract_id)

    response_keys= response.keys()
    print(f"type of reponse =|{type(response)}|")
    print(f" len of reponse =|{len(response)}|")

    cvalues['award_amount'] = response['total_obligation']
    cvalues['start_date'] = response['period_of_performance']['start_date']
    cvalues['end_date'] = response['period_of_performance']['end_date']
    cvalues['award_agency'] = response['awarding_agency']['toptier_agency']['name']

    if('latest_transaction_contract_data' in response_keys):
        cvalues['naic_code'] = response['latest_transaction_contract_data']['naics']
        cvalues['naics_description'] = response['latest_transaction_contract_data']['naics_description']
    else:
        cvalues['naic_code'] = "unknown"
        cvalues['naics_description'] = "unknown"

    if('place_of_performance' in response):
        if(response['place_of_performance']['location_country_code']):
            country_code = response['place_of_performance']['location_country_code']
        else:
            country_code = "unknown-country"    
        if(response['place_of_performance']['state_name']):
            state_name = response['place_of_performance']['state_name']
        else:
            state_name = "unknown-state"    
        if(response['place_of_performance']['zip5']):
            zipcode = response['place_of_performance']['zip5']
        else:
            zipcode = "unknown-zip"    

    cvalues['place_of_performance'] = country_code + "/" + state_name + "/" + zipcode
    return cvalues


contract_award_id = "ASST_NON_19FXHFL001_485"
co_values = get_contract_values(contract_award_id)

print(f"keys of cvalues = |{co_values.keys()}|")

"""
response_keys= response.keys()
print(f"type of reponse =|{type(response)}|")
print(f" len of reponse =|{len(response)}|")
print(f"value of award_amount = |{response['total_obligation']}|")
print(f"value of start_date = |{response['period_of_performance']['start_date']}|")
print(f"value of end_date = |{response['period_of_performance']['end_date']}|")
print(f"value of awarding_agency = |{response['awarding_agency']['toptier_agency']['name']}|")
if('latest_transaction_contract_data' in response_keys):
    naic_code = response['latest_transaction_contract_data']['naics']
    naics_description = response['latest_transaction_contract_data']['naics_description']
else:
    naic_code = "unknown"
    naics_description = "unknown"

print(f"value of naics code = |{naic_code}|")
print(f"value of naics descripti = |{naics_description}|")
if('place_of_performance' in response):
    if(response['place_of_performance']['location_country_code']):
        country_code = response['place_of_performance']['location_country_code']
    else:
        country_code = "unknown-country"    
    if(response['place_of_performance']['state_name']):
        state_name = response['place_of_performance']['state_name']
    else:
        state_name = "unknown-state"    
    if(response['place_of_performance']['zip5']):
        zipcode = response['place_of_performance']['zip5']
    else:
        zipcode = "unknown-zip"    

place_of_performance = country_code + "/" + state_name + "/" + zipcode

print(f"value of place of performacne = |{place_of_performance}|")

"""


