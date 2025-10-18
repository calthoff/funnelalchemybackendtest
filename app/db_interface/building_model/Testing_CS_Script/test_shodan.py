import shodan
import json
import os

from dotenv import load_dotenv

def load_env_local() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(here, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)

def shodan_IP_search(ip_address):
    # --- Setup ---
    load_env_local()
    api_key = os.environ.get("SHODAN_API_KEY")
    if not api_key:
        print("ERROR: Set SHODAN_API_KEY in your environment or a .env file next to this script.")
        return

    # Initialize Shodan API client
    try:
        api = shodan.Shodan(api_key)
        
        # Perform the host lookup with history=True
        host_info = api.host(ip_address, history=True)
        
        return host_info

    except shodan.APIError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def main():
    #ip_address = "50.31.130.189"
    ip_address = "8.8.8.8"
    IP_info = shodan_IP_search(ip_address)
        
    # Convert the response to JSON and print it
    json_output = json.dumps(IP_info, indent=2)
    print("\nShodan Host Lookup Response:")
    print(json_output)
        
if __name__ == "__main__":
    main()
