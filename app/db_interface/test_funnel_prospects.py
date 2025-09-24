"""
testing the funnelprospects library of functions
:Author: Michel Eric Levy _mel_
:Creation date: September 2nd, 2025
:Last updated: 9/19/2025 (_mel_)

"""
import json
import datetime
import logging
import time
import json
import timeit

import funnelprospects as fp
#from prospect_scoring_api import score_prospects

#prospects criteria
company_industries =  ["Technology", "Software", "SaaS"] 
company_employee_size_range = ["1-10","10-50", "51-200", "201-500"] 
company_revenue_range =  ["1M-10M", "10M-50M", "50M-100M"]
company_funding_stage =  ["Series A", "Series B", "Series C", "Seed"] 
company_location =  ["United States", "Canada", "United Kingdom"]
additional_preferences = "some additional information"

personas_title_keywords =  ["CEO", "CTO", "VP Engineering", "Head of Engineering"]
personas_seniority_levels = ["C-Level", "VP", "Director"]
personas_buying_roles =  ["Decision Maker", "Influencer"]

company_description =  "Technology companies with engineering teams"
company_exclusion_criteria =  "Non-profit and Government"




if __name__ == "__main__":

    
    #####################################################################################
    #1 test creating a user (change the email address to perform a test)
    def test1():
        result = fp.create_customer("test6@test1.com", "michel", "levy", "IBM")

        if result["status"] == "error":
            print(f"Error occurred: {result['message']}")
            # Handle the error as needed
        else:
            print(f"Success: customer_id=|{result['customer_id']}| and comp_uniuqe_id = |{result['company_unique_id']}|")
    

    
    #####################################################################################
    #2. testing the customer_propsects update criteria list functions
    def test2():
        result = fp.updateCustomerProspectCriteria("MLevy-20250922-5440373832", 
                                                "default",
                                                company_industries,
                                                company_employee_size_range,
                                                company_revenue_range,
                                                company_funding_stage,
                                                company_location,
                                                personas_title_keywords,
                                                personas_seniority_levels,
                                                personas_buying_roles,
                                                company_description,
                                                company_exclusion_criteria,
                                                additional_preferences)
        if result["status"] == "error":
            print(f"Error occurred: {result['message']}")
            # Handle the error as needed
        else:
            print(f"Success: {result['message']}")


    #####################################################################################
    #3 test getting a customer data 
    # lets use test customer with customer_id : "mlevy-20250905-5730756828"
    def test3():
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
    def test4():
        start_time = timeit.default_timer()
        prospect_id_list = fp.find_matching_prospects("mlevy-20250905-5730756828", "prospectid_001")
        #prospect_id_list = fp.find_matching_prospects("CAlthoff-20250911-7008066352", "default")
        print(f"size of prospect list returned = |{len(prospect_id_list)}| and list = |{prospect_id_list}|")
        end_time = timeit.default_timer()
        print(f"\n\nTIME to find prospects = |{(end_time - start_time)*1000} milliseconds|")


        start_time = timeit.default_timer()
        result = fp.findAndUpdateCustomerProspect("mlevy-20250905-5730756828", "prospectid_001", 500)
        #result = fp.findAndUpdateCustomerProspect("CAlthoff-20250911-7008066352", "default", 500)
        print(f" status = |{result['status']}| and message = |{result['message']}|")
        end_time = timeit.default_timer()
        print(f"\n\nTIME to find_and_update = |{(end_time - start_time)*1000} milliseconds|")



    #####################################################################################
    #5 test getting prospects options and their counts
    #  and inspecting the dict being returned.
    #
    def test5():
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
    def test6():
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
    #
    def test7():
        # Example 1: Add multiple prospects to daily list
        multiple_prospects = ["coresignal434550710", "coresignal182874843", "coresignal236777753"]
        result2 = fp.remove_from_daily_list(customer_id, multiple_prospects)
        print("Multiple prospects result:", result2)



    #####################################################################################
    #8 test retrieving the json/dict corresponding at the dataset criteria for a customer/profile_id
    #  lets use : customer_id = "coresignal434550710", prospect_profile_id = 'default'
    #  
    def test8():
        #result = fp.get_customer_prospect_criteria("CAlthoff-20250911-7008066352","default")
        result = fp.get_customer_prospect_criteria("mlevy-20250905-5730756828", "prospectid_001")
        formatted_json = json.dumps(result['criteria_dataset'], indent=4, ensure_ascii=False)
        print("\nJSON criteria dataset is", formatted_json)


    #####################################################################################
    #9 test changing the status of a customer prospects to "connected" 
    #  lets use : customer_id = "mlevy-20250905-5730756828", prospect_id = "coresignal267051946"
    #  
    def test9():
        activity_history = json.dumps({
        "date": "2025-09-10",
        "action": "Called prospect, left voicemail"
        })
        result = fp.update_daily_list_prospect_status("mlevy-20250905-5730756828", "coresignal267051946", "contacted", activity_history)
        print("\nresult dict from updating status", result)



    #####################################################################################
    #10 test changing the status of the has_replied to True, 
    #   done, when customer moved the reply item to the REPLIED section (to the right)
    #   lets use : customer_id = "mlevy-20250905-5730756828", prospect_id = "coresignal267051946"
    #  
    def test10():
        activity_history = json.dumps({
        "date": "2025-09-10",
        "action": "The prospect has replied"
        })
        result = fp.update_has_replied_status("mlevy-20250905-5730756828", "coresignal267051946", True, activity_history)
        print("\nresult dict from updating has_replied", result)




    #####################################################################################
    #11 test retrieving the propect list of a given customer.
    #   this data will come from the "customer_proepcts" tabble and will be displayed on the
    #   "Find Prospects" page
    #   lets use : customer_id = "mlevy-20250905-5730756828", prospect_id = "coresignal267051946"
    #  
    def test11():
        result = fp.get_customer_prospects_list("mlevy-20250905-5730756828","prospectid_001") 
        print("\nresult dict from retrieving prospects", result['message'])
        if(result['status']=="success"):
            print(f" number of prospects eturned = |{result['nb_prospects_returned']}|")
            print(f" prospects #1 = |{result['prospect_list'][0]}|")
            print(f" prospects #1 headshot url = |{result['prospect_list'][0]['headshot_url']}|")


    #####################################################################################
    #12 test retrieving prospect data and converting it into the prospect scoring JSON format
    #   lets use : porspect_id = prospect_id = "coresignal267051946"
    #  
    def test12():
        result = sc.get_scoring_json_prospects("coresignal267051946") 
        print("\nresult dict from retrieving prospects", result['message'])
        if(result['status']=="success"):
            #formatted_json = json.dumps(result['prospect_data'], indent=4, sort_keys=True, ensure_ascii=False)
            formatted_json = json.dumps(result['prospect_data'], indent=4, ensure_ascii=False)
            print(f" prospect dtaa returned = |{formatted_json}|")
        else:
            print(f"get scoring prospect was NOT successfuul becuse : |{result['message']}|")    


    #####################################################################################
    #13 test retrieving  criteria dataset for a customer and converting them to the 
    #   format that is exepected by the scoring library 
    #   lets use : customer_id = 
    #
    def test13():
        #first we get the criteria from the db
        result = fp.get_customer_prospect_criteria("mlevy-20250905-5730756828", "prospectid_001")

        #second we convert it and display for tetsing
        scoring_settings = sc.convert_to_scoring_format(result['criteria_dataset'])
        print("\n\n SCORE SETTINGSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS")
        print(json.dumps(scoring_settings['scoring_data']['scoring_settings'], indent=4, ensure_ascii=False))
      

    #####################################################################################
    #13 test retrieving  the daily list prospects for a given customer
    #   lets use : customer_id = ("CAlthoff-20250911-7008066352","default")
    #
    def test14():
        #first we get the prospect list
        #result = fp.get_daily_list_prospects("mlevy-20250905-5730756828", "prospectid_001")
        result = fp.get_daily_list_prospects("CAlthoff-20250911-7008066352","default")

        # second, lets display the first one
        if(result['status'] ==  "success"):
            prospect_list = result['prospect_list']
            for p in prospect_list:
                print(json.dumps(p, indent=4, ensure_ascii=False))
                break
        else:
            print(result['message'])        



    #####################################################################################
    #13 test retrieving  the list of contacted 
    #   lets use : customer_id = ("CAlthoff-20250911-7008066352","default")
    #
    def test15_get_contacted():
        result = fp.get_contacted_list("CAlthoff-20250911-7008066352","default")

        # second, lets display the first one
        if(result['status'] ==  "success"):
            prospect_list = result['prospect_list']
            for p in prospect_list:
                print(json.dumps(p, indent=4, ensure_ascii=False))
                break
        else:
            print(f"un-successsful: |{result['message']}|")        


    #test15_get_contacted()




    # test getting and updating criteria dataset & scoring too
    test2()

    #test8()
    #test13()