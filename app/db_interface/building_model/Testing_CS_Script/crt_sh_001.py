import os
import requests

# Make HTTP GET request to crt.sh API
url = "https://crt.sh/?q=%.lacounty.gov&output=json"
#url = "https://crt.sh/?q=%.ssa.gov&output=json"
#url = "https://crt.sh/?q=%.commerce.gov&output=json"
#url = "https://crt.sh/?q=vpn.camsic.commerce.gov&output=json"

#https://crt.sh/?q=vpn.camsic.commerce.gov



response = requests.get(url)

firewall_word_list = ["vpn", "ssl-vpn", "globalprotect", "anyconnect", "fortigate", "meraki", "zscaler", "firewall"]
def find_words_in_string(word_list, text):
    for word in word_list:
        if word in text:
            return True
    return False

# Check if the request was successful
if response.status_code == 200:
    data = response.json()  # Parse JSON response
    print(f"Type of response = |{type(data)}|\n")
    for item in data:
        name_value = item['name_value'].replace("\n", " || ")
        print(f"|{item['common_name']}| --- |{name_value}|")
#        name_value = item['name_value'].replace("\n", " || ")
#        if(find_words_in_string(firewall_word_list, name_value)):
#            print(f"|{item['entry_timestamp']}| || |NB: {item['not_before']}| || |{item['common_name']}| --- |{name_value}|")

else:
    print(f"Error: HTTP {response.status_code}")

