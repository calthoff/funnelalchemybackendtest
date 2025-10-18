"""
testing the scoring api functions
:Author: Michel Eric Levy _mel_
:Creation date: September 16, 2025
:Last updated: 9/19/2025 (_mel_)

"""
import json
import datetime
import logging
import time
import json
import timeit
import random
import string

from scoring_module import score_prospects
import scoring_prospects as sp

import funnelprospects as fp

import asyncio



def generate_random_string(length=5):
    """Generate a random string of specified length using digits and letters."""
    # Define the character set: digits + lowercase + uppercase letters
    characters = string.ascii_letters + string.digits  # includes a-z, A-Z, 0-9
    # Generate random string
    return ''.join(random.choice(characters) for _ in range(length))


#####################################################################################
#15 test  the basic scoring API funcitons with sampler provided by Bohdan
#
async def test15_test_scoring():
    """
    This function is used to test the scoring API wih hardcoded values and then 
    we will use values/data coming from the database
    """
    #first lets define fixed score_settings and sample prospects list
    scoring_settings = '{ \
        "company_description": "We are a B2B SaaS company specializing in sales automation and CRM solutions for mid-market and enterprise companies. Our platform helps sales teams increase productivity, improve lead management, and drive revenue growth through intelligent automation and analytics.",\
        "exclusion_criteria": "We don''t sell to companies with less than 50 employees, companies in the healthcare industry due to compliance requirements, or companies that are not B2B focused. We also exclude companies that are in financial distress or have recently laid off significant portions of their sales team.",\
        "industries": [\
        "Technology",\
        "Financial Services",\
        "Manufacturing",\
        "Professional Services",\
        "Real Estate",\
        "Insurance",\
        "Consulting",\
        "Software Development",\
        "E-commerce",\
        "Telecommunications"\
        ],\
        "employee_range": [\
        "51-200",\
        "201-500",\
        "501-1000",\
        "1001-5000",\
        "5001-10000"\
        ],\
        "revenue_range": [\
        "$10M-$50M",\
        "$50M-$100M",\
        "$100M-$500M",\
        "$500M-$1B",\
        "$1B+"\
        ],\
        "funding_stages": [\
        "Series A",\
        "Series B",\
        "Series C",\
        "Series D",\
        "IPO",\
        "Private Equity"\
        ],\
        "title_keywords": [\
        "Sales Director",\
        "VP of Sales",\
        "Chief Revenue Officer",\
        "Sales Manager",\
        "Revenue Manager",\
        "Business Development Director",\
        "Sales Operations Manager",\
        "Account Executive",\
        "Sales Representative",\
        "Sales Executive"\
        ],\
        "seniority_levels": [\
        "Senior Management",\
        "Executive",\
        "Middle Management",\
        "Senior Individual Contributor"\
        ],\
        "buying_roles": [\
        "Decision Maker",\
        "Influencer",\
        "Budget Holder",\
        "Technical Evaluator",\
        "End User"\
        ],\
        "locations": [\
        "United States",\
        "Canada"\
        ],\
        "other_preferences": "Prefer technical founders and candidates with strong B2B SaaS experience. Prioritize prospects with recent funding rounds and high growth metrics."\
        }'
    print(f"length of score settings = |{len(scoring_settings)}|")

    prospects = []
    prospect1 = { "prospect_id": "12346", "full_name": "Sarah Johnson", "headline": "VP of Sales at TechFlow Solutions", "summary": "Strategic sales leader with 12+ years experience in B2B SaaS, specializing in scaling sales operations and driving revenue growth for high-growth technology companies.", "location_country": "United States", "location_full": "San Francisco, California, United States", "inferred_skills": ["Sales Strategy", "Revenue Operations", "Team Building", "B2B SaaS", "Sales Process Optimization"], "connections_count": 1200, "followers_count": 1800, "is_working": True, "active_experience_title": "VP of Sales", "active_experience_description": "Leading sales organization of 50+ reps, managing $50M+ annual revenue, implementing sales enablement programs", "active_experience_department": "Sales", "active_experience_management_level": "Executive", "is_decision_maker": True, "position_title": "VP of Sales", "department": "Sales", "management_level": "Executive", "duration_months": 18, "location": "San Francisco, CA", "company_id": "comp_790", "company_name": "TechFlow Solutions", "company_industry": "Technology", "company_followers_count": 25000, "company_size_range": "501-1000", "company_employees_count": 750, "company_categories_and_keywords": ["SaaS", "Sales Automation", "CRM", "B2B", "Enterprise"], "company_hq_country": "United States", "company_last_funding_round_date": "2023-12-01", "company_last_funding_round_amount_raised": 75000000, "company_employees_count_change_yearly_percentage": 60, "company_hq_full_address": "456 Innovation Drive, San Francisco, CA 94105", "company_is_b2b": True, "total_experience_duration_months": 144, "total_experience_duration_months_breakdown_department": [ {"department": "Sales", "total_experience_duration_months": 120}, {"department": "Marketing", "total_experience_duration_months": 18}, {"department": "Business Development", "total_experience_duration_months": 6} ], "total_experience_duration_months_breakdown_management_level": [ {"management_level": "Executive", "total_experience_duration_months": 24}, {"management_level": "Senior Management", "total_experience_duration_months": 48}, {"management_level": "Middle Management", "total_experience_duration_months": 48}, {"management_level": "Individual Contributor", "total_experience_duration_months": 24} ], "education_degrees": [ "Master''s degree, Structural Engineering and Engineering Mechanics", "Mathematics", "Bachelor''s degree, Civil & Environmental Engineering" ], "languages": [ { "language": "English", "proficiency": "Native" }, { "language": "French", "proficiency": "Fluent" } ], "awards": [ "Sales Leader of the Year 2023", "Top 40 Under 40 Sales Leaders" ], "certifications": [ "Salesforce Certified Sales Cloud Consultant", "Gong Sales Enablement Certification", "Revenue Operations Professional" ], "courses": [ "Executive Sales Leadership", "Revenue Operations Strategy" ], "primary_professional_email": "sarah.johnson@techflow.com", "linkedin_url": "https://linkedin.com/in/sarahjohnson-techflow" }
    prospect2 = { "prospect_id": "12347", "full_name": "Michael Chen", "headline": "Sales Director at TechFlow Solutions", "summary": "Results-driven sales leader with 8+ years in B2B technology sales, specializing in enterprise account management and team development.", "location_country": "United States", "location_full": "San Francisco, California, United States", "inferred_skills": ["Enterprise Sales", "Account Management", "Team Leadership", "Sales Strategy", "Customer Success"], "connections_count": 650, "followers_count": 950, "is_working": True, "active_experience_title": "Sales Director", "active_experience_description": "Managing team of 12 enterprise sales reps, focusing on Fortune 500 accounts and strategic partnerships", "active_experience_department": "Sales", "active_experience_management_level": "Senior Management", "is_decision_maker": True, "position_title": "Sales Director", "department": "Sales", "management_level": "Senior Management", "duration_months": 12, "location": "San Francisco, CA", "company_id": "comp_790", "company_name": "TechFlow Solutions", "company_industry": "Technology", "company_followers_count": 25000, "company_size_range": "501-1000", "company_employees_count": 750, "company_categories_and_keywords": ["SaaS", "Sales Automation", "CRM", "B2B", "Enterprise"], "company_hq_country": "United States", "company_last_funding_round_date": "2023-12-01", "company_last_funding_round_amount_raised": 75000000, "company_employees_count_change_yearly_percentage": 60, "company_hq_full_address": "456 Innovation Drive, San Francisco, CA 94105", "company_is_b2b": True, "total_experience_duration_months": 96, "total_experience_duration_months_breakdown_department": [ {"department": "Sales", "total_experience_duration_months": 84}, {"department": "Business Development", "total_experience_duration_months": 12} ], "total_experience_duration_months_breakdown_management_level": [ {"management_level": "Senior Management", "total_experience_duration_months": 24}, {"management_level": "Middle Management", "total_experience_duration_months": 48}, {"management_level": "Individual Contributor", "total_experience_duration_months": 24} ], "education_degrees": [ "Bachelor''s degree, Business Administration", "Mathematics" ], "languages": [ { "language": "English", "proficiency": "Native" }, { "language": "Mandarin", "proficiency": "Fluent" } ], "awards": [ "Top Sales Director 2023", "Excellence in Leadership Award" ], "certifications": [ "Salesforce Certified Administrator", "LinkedIn Sales Navigator Certification", "Enterprise Sales Professional" ], "courses": [ "Advanced Sales Management", "Enterprise Account Strategy" ], "primary_professional_email": "michael.chen@techflow.com", "linkedin_url": "https://linkedin.com/in/michaelchen-sales" }
    prospect3 = { "prospect_id": "12348", "full_name": "Jennifer Williams", "headline": "Senior Account Executive at TechFlow Solutions", "summary": "High-performing sales professional with 6+ years in B2B SaaS sales, specializing in mid-market and enterprise client acquisition.", "location_country": "United States", "location_full": "Los Angeles, California, United States", "inferred_skills": ["B2B Sales", "Account Management", "Solution Selling", "Pipeline Management", "Client Relations"], "connections_count": 450, "followers_count": 720, "is_working": True, "active_experience_title": "Senior Account Executive", "active_experience_description": "Managing $5M+ sales pipeline, focusing on mid-market technology companies and enterprise prospects", "active_experience_department": "Sales", "active_experience_management_level": "Senior Individual Contributor", "is_decision_maker": False, "position_title": "Senior Account Executive", "department": "Sales", "management_level": "Senior Individual Contributor", "duration_months": 24, "location": "Los Angeles, CA", "company_id": "comp_790", "company_name": "TechFlow Solutions", "company_industry": "Technology", "company_followers_count": 25000, "company_size_range": "501-1000", "company_employees_count": 750, "company_categories_and_keywords": ["SaaS", "Sales Automation", "CRM", "B2B", "Enterprise"], "company_hq_country": "United States", "company_last_funding_round_date": "2023-12-01", "company_last_funding_round_amount_raised": 75000000, "company_employees_count_change_yearly_percentage": 60, "company_hq_full_address": "456 Innovation Drive, San Francisco, CA 94105", "company_is_b2b": True, "total_experience_duration_months": 72, "total_experience_duration_months_breakdown_department": [ {"department": "Sales", "total_experience_duration_months": 60}, {"department": "Business Development", "total_experience_duration_months": 12} ], "total_experience_duration_months_breakdown_management_level": [ {"management_level": "Senior Individual Contributor", "total_experience_duration_months": 36}, {"management_level": "Individual Contributor", "total_experience_duration_months": 36} ], "education_degrees": [ "Bachelor''s degree, Marketing", "Mathematics" ], "languages": [ { "language": "English", "proficiency": "Native" }, { "language": "Spanish", "proficiency": "Conversational" } ], "awards": [ "Top Performer 2023", "President''s Club 2022" ], "certifications": [ "Salesforce Certified Sales Representative", "HubSpot Sales Software Certification", "Solution Selling Professional" ], "courses": [ "Advanced B2B Sales Techniques", "Solution Selling Methodology" ], "primary_professional_email": "jennifer.williams@techflow.com", "linkedin_url": "https://linkedin.com/in/jenniferwilliams-ae" }
    prospects.append(prospect1)
    prospects.append(prospect2)
    prospects.append(prospect3)
    
    print(f"type of prospect1 = |{type(prospect1)}|")
    print(f"type of prospect1 = |{type(prospect2)}|")
    print(f"type of prospect1 = |{type(prospect3)}|")

    print(f"length of prospects = |{len(prospects)}|")
    # Call function
    start_time = timeit.default_timer()
    results = score_prospects(scoring_settings, prospects)
    end_time = timeit.default_timer()
    print(f"\n\nTIME to score prospects = |{(end_time - start_time)*1000} milliseconds|")

    for i in range(20):
        new_id = generate_random_string(5)
        prospect3['prospect_id'] = new_id
        prospects.append(prospect3)

    print(f"length of prospects = |{len(prospects)}|")
    start_time = timeit.default_timer()


    #all_scores = sp.process_json_batch_prospects(scoring_settings, prospects)
    all_scores = await sp.process_json_batch_prospects(scoring_settings, prospects)  
    print(f"size of all scores = |{len(all_scores)}|")

    #results = score_prospects(scoring_settings, prospects)
    end_time = timeit.default_timer()
    print(f"TIME to score prospects = |{(end_time - start_time)*1000} milliseconds|\n")
    

    """
    for i in range(100):
        new_id = generate_random_string(5)
        prospect3['prospect_id'] = new_id
        prospects.append(prospect3)

    print(f"length of prospects = |{len(prospects)}|")
    start_time = timeit.default_timer()
    results = score_prospects(scoring_settings, prospects)
    end_time = timeit.default_timer()
    print(f"TIME to score prospects = |{(end_time - start_time)*1000} milliseconds|\n")


    for i in range(500):
        new_id = generate_random_string(5)
        prospect3['prospect_id'] = new_id
        prospects.append(prospect3)

    print(f"length of prospects = |{len(prospects)}|")
    start_time = timeit.default_timer()
    results = score_prospects(scoring_settings, prospects)
    end_time = timeit.default_timer()
    print(f"TIME to score prospects = |{(end_time - start_time)*1000} milliseconds|\n")

    # Print result
    #print(results)        
    """

#####################################################################################
#16 More comprehensive test of the Cory customer_id 
#
async def test16_test_scoring():

    #first: we get the scoring from Cory user
    customer_id = 'CAlthoff-20250911-7008066352'
    scoring_customer = fp.get_customer_prospect_criteria(customer_id)

    #second: convert to scoring format used by Bohdan
    scoring_settings = sp.convert_to_scoring_format(scoring_customer)

    #third: get all prospects from that user  that needs scoring 
    prospect_list_dict = fp.get_customer_prospects_list(customer_id)

    all_prospect_list = [p["prospect_id"] for p in prospect_list_dict['prospect_list']]

    prospects_formated = sp.get_scoring_json_prospects(all_prospect_list)
    print(f"size of all_prospect_list = |{len(all_prospect_list)}|")
    if(prospects_formated['status']=="success"):
        start_time = timeit.default_timer()
        all_scores = await sp.process_json_batch_prospects(scoring_settings, prospects_formated['prospects_data'])  

        # would only score the first 12 prospects in the list - done just for testing
        #all_scores = await sp.process_json_batch_prospects(scoring_settings, prospects_formated['prospects_data'][:12])  
        end_time = timeit.default_timer()
        print(f"TTTTTTTTTTTTTTTTTIME to score prospects = |{(end_time - start_time)*1000} milliseconds|\n")
        print(f"size of all scorest16 = |{len(all_scores)}|")    
        print(f"type of all scores =|{type(all_scores)}|")
        if(all_scores['status']== "success"):
            print(f"message returned = |{all_scores['message']}|")
            print(f"first elelement for all _score = |{all_scores['scores_list'][0]}|")
            print(f"first element porspwect_id=|{all_scores['scores_list'][0]['prospect_id']}|")
            print(f"first element score=|{all_scores['scores_list'][0]['score']}|")
            print(f"first element justification=|{all_scores['scores_list'][0]['justification']}|")
            for pitem in all_scores['scores_list']:
                print(f"prospect element porspwect_id=|{pitem['prospect_id']}|")
                print(f"prospect element score=|{pitem['score']}|")
                print(f"prospect element justification=|{pitem['justification']}|\n\n")

        else:    
            print(f"keys of all_scores = |{all_scores.keys()}|")
            print(f"error message = |{all_scores['message']}|")
        #print(f"error message = |{all_scores['error_type']}|")

        #SAVE all scores
        result_save = sp.update_score_in_customer_prospects(customer_id, all_scores['scores_list'], "default", min_score=60)
    else:    
        print(f"unexpected issue with get_scoring_json_prospects = |{prospects_formated['message']}|")    






if __name__ == "__main__":

    asyncio.run(test16_test_scoring())

