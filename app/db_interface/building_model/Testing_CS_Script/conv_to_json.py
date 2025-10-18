import re
import json

raw = """
[FORTINET]
   Company: robisontaxlaw.com
   Provider: Fuse Internet Access
   Hostnames: mail.robisontaxlaw.com, mail.spe1031.com
   IP: 216.196.241.154  Port: 8443  ASN: AS6181  Country: US
   Product/title: Fortinet FortiWiFi-60E
   Last seen: 2025-10-04T22:55:49.840898
"""

def conv_shodan_company_to_json(raw_shodan: str):
    data = {
        "vendor": re.search(r"\[(.*?)\]", raw).group(1),
        "company": re.search(r"Company:\s*(.*)", raw).group(1),
        "provider": re.search(r"Provider:\s*(.*)", raw).group(1),
        "hostnames": [h.strip() for h in re.search(r"Hostnames:\s*(.*)", raw).group(1).split(",")],
        "ip": re.search(r"IP:\s*([\d\.]+)", raw).group(1),
        "port": int(re.search(r"Port:\s*(\d+)", raw).group(1)),
        "asn": re.search(r"ASN:\s*(\S+)", raw).group(1),
        "country": re.search(r"Country:\s*(\S+)", raw).group(1),
        "product_title": re.search(r"Product/title:\s*(.*)", raw).group(1),
        "last_seen": re.search(r"Last seen:\s*(.*)", raw).group(1)
    }
    return data

shodan_details = conv_shodan_company_to_json(raw)
print(f"json result is |{json.dumps(shodan_details, indent=2)}| ")    

