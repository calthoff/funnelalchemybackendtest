"""
testing the funnelprospects library of functions
:Author: Michel Eric Levy _mel_
:Creation date: September 2nd, 2025
:Last updated: 9/3/2025 (_mel_)

"""
import json
import datetime
import logging
import time
import json

import funnelprospects as fp

#prospects criteria
company_industries =  ["Technology", "Software", "SaaS"] 
company_employee_size_range = ["1-10","10-50", "51-200", "201-500"] 
company_revenue_range =  ["1M-10M", "10M-50M", "50M-100M"]
company_funding_stage =  ["Series A", "Series B", "Series C", "Seed"] 
company_location =  ["United States", "Canada", "United Kingdom"]

personas_title_keywords =  ["CEO", "CTO", "VP Engineering", "Head of Engineering"]
personas_seniority_levels = ["C-Level", "VP", "Director"]
personas_buying_roles =  ["Decision Maker", "Influencer"]

company_description =  "Technology companies with engineering teams"
company_exclusion_criteria =  ["Non-profit", "Government"]




if __name__ == "__main__":

    """
    #####################################################################################
    #1 test creating a user (change the email address to perform a test)
    result = fp.create_customer("test6@test1.com", "michel", "levy", "IBM")

    if result["status"] == "error":
        print(f"Error occurred: {result['message']}")
        # Handle the error as needed
    else:
        print(f"Success: customer_id=|{result['customer_id']}| and comp_uniuqe_id = |{result['company_unique_id']}|")
    """

    
    #####################################################################################
    #2. testing the customer_propsects update criteria list functions
    result = fp.updateCustomerProspectCriteria("mlevy-20250905-5730756828", 
                                            "prospectid_001",
                                            company_industries,
                                            company_employee_size_range,
                                            company_revenue_range,
                                            company_funding_stage,
                                            company_location,
                                            personas_title_keywords,
                                            personas_seniority_levels,
                                            personas_buying_roles,
                                            company_description,
                                            company_exclusion_criteria)
    if result["status"] == "error":
        print(f"Error occurred: {result['message']}")
        # Handle the error as needed
    else:
        print(f"Success: {result['message']}")

    """

    """
    #####################################################################################
    #3 test getting a customer data 
    # lets use test customer with customer_id : "mlevy-20250905-5730756828"
    result = fp.get_customer("mlevy-20250905-5730756828")
    if result["status"] == "error":
        print(f"Error occurred: {result['message']}")
        # Handle the error as needed
    else:
        print(f"Success: customer_id=|{result['customer_id']}| ")
        print(f"comp_unique_id = |{result['company_unique_id']}|")
        print(f"First name=|{result['first_name']}| and last_name = |{result['last_name']}|")
        print(f"company name=|{result['company_name']}| and email_address = |{result['email_address']}|")
        print(f"List of prospect_profile_ids =|{result['prospect_profiles_ids']}| ")

    

    #####################################################################################
    #4 test getting matching prospects for a customer
    # lets use test customer with customer_id : "mlevy-20250905-5730756828"
    #
    prospect_id_list = fp.find_matching_prospects("mlevy-20250905-5730756828")
    print(f"size of prospect list returned = |{len(prospect_id_list)}| and list = |{prospect_id_list}|")

    result = fp.findAndUpdateCustomerProspect("mlevy-20250905-5730756828")
    print(f" status = |{result['status']}| and message = |{result['message']}|")



    #####################################################################################
    #5 test getting prospects options and their counts
    #  and inspecting the dict being returned.
    #
    stats = fp.get_prospects_stats()
    criterias = stats['data']
    skeys = criterias.keys()
    for sk in skeys:
        print(f"type of |{sk}| = |{type(criterias[sk])}|")
        sk2 = criterias[sk].keys()
        print(f"list keys of |{sk}| = |{type(list(sk2))}|")
        print(f"list keys of |{sk}| = |{list(sk2)[0:3]}|")

    print(f"count for sof dev = |{criterias['company_industry']['Software Development']}|")     

    # uncomment next line if you want to display the comprehensive list of options and their counts
    #fp.display_prospects_stats(stats)

    #####################################################################################
    #6 test adding prospects into the daily list of a customer
    #  "coresignal434550710", "coresignal182874843", "coresignal236777753" are real prospect_id
    #
    
    customer_id = "mlevy-20250905-5730756828"
    
    # Example 1: Add single prospect to daily list
    single_prospect = ["coresignal434550710"]
    result1 = fp.add_to_daily_list(customer_id, single_prospect)
    print("Single prospect result:", result1)
    
    # Example 2: Add multiple prospects to daily list
    multiple_prospects = ["coresignal434550710", "coresignal182874843", "coresignal236777753"]
    result2 = fp.add_to_daily_list(customer_id, multiple_prospects)
    print("Multiple prospects result:", result2)
    
    # Example 3: Error case - empty list
    empty_list = []
    result3 = fp.add_to_daily_list(customer_id, empty_list)
    print("Empty list result:", result3)
    
    # Example 4: Error case - empty customer_id
    result4 = fp.add_to_daily_list("", ["coresignal236777753"])
    print("Empty customer_id result:", result4)


    #####################################################################################
    #7 test "removing" prospects from the daily list of a customer
    #  "coresignal434550710", "coresignal182874843", "coresignal236777753" are real prospect_id
    #  that were previously added to the daily_list

    # Example 1: Add multiple prospects to daily list
    multiple_prospects = ["coresignal434550710", "coresignal182874843", "coresignal236777753"]
    result2 = fp.remove_from_daily_list(customer_id, multiple_prospects)
    print("Multiple prospects result:", result2)


