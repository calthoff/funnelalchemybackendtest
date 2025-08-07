from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List, Union
from openai import OpenAI
import os
import json
import re
from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.prospects import ProspectRead, ProspectUpdate
from app.utils.db_utils import get_table
from pydantic import BaseModel
from app.core.config import settings

router = APIRouter(prefix="/prospects", tags=["prospects"], redirect_slashes=False)

client = OpenAI(api_key=settings.OPENAI_API_KEY)

class DuplicateProspectResponse(BaseModel):
    message: str
    skipped: bool

def create_scoring_prompt(prospect, profiles, profile_type):
    prospect_info = f"""
PROSPECT:
- Name: {prospect.get('name', 'N/A')}
- Company: {prospect.get('company', 'N/A')}
- Title: {prospect.get('title', 'N/A')}
- Email: {prospect.get('email', 'N/A')}
"""
    
    profiles_info = f"\n{profile_type.upper()} PROFILES:\n"
    for i, profile in enumerate(profiles, 1):
        if profile_type == "company":
            profile_data = profile._mapping
            industries = profile_data.get('industries', 'N/A')
            arr_range = profile_data.get('arr_range', 'N/A')
            employee_size = profile_data.get('employee_size_range', 'N/A')
            profiles_info += f"{i}. \"{profile_data.get('name', 'Unknown')}\": Industries: {industries}, ARR: {arr_range}, Employee Size: {employee_size}\n"
        else:
            profile_data = profile._mapping
            title_keywords = profile_data.get('title_keywords', 'N/A')
            departments = profile_data.get('departments', 'N/A')
            profiles_info += f"{i}. \"{profile_data.get('name', 'Unknown')}\": Title Keywords: {title_keywords}, Departments: {departments}\n"
    
    prompt = f"""You are a lead scoring expert. Score this prospect (0-100) against these {profile_type} profiles.

{prospect_info}{profiles_info}

Return only a JSON object with this exact format:
{{
  "score": 85,
  "reason": "TechCorp is a SaaS company with 200 employees, matching the SaaS Companies profile criteria"
}}

Score 0-100 based on how well the prospect matches each profile. Consider the best match and return that score with reasoning."""
    
    return prompt

def create_ai_intelligence_prompt(prospect, company_description=None, sales_data=None):
    prospect_info = f"""
PROSPECT DATA:
- Name: {prospect.get('name', 'N/A')}
- Company: {prospect.get('company', 'N/A')}
- Title: {prospect.get('title', 'N/A')}
- Email: {prospect.get('email', 'N/A')}
- Department: {prospect.get('department', 'N/A')}
- Seniority: {prospect.get('seniority', 'N/A')}
- Location: {prospect.get('location', 'N/A')}
- Source: {prospect.get('source', 'N/A')}
"""

    company_context = ""
    if company_description:
        company_context = f"""
YOUR COMPANY CONTEXT:
{company_description}

Use this description to understand what makes a prospect valuable to this specific business.
"""

    sales_context = ""
    if sales_data:
        sales_context = f"""
SALES CONTEXT:
- Past closed deals pattern: {sales_data.get('closed_deals_pattern', 'N/A')}
- Rep performance history: {sales_data.get('rep_performance', 'N/A')}
- Industry success rates: {sales_data.get('industry_success', 'N/A')}
"""

    prompt = f"""You are an AI sales intelligence expert. Analyze this prospect based on the provided company context.

{prospect_info}{company_context}{sales_context}

Based on the prospect's information and your company's specific business context, evaluate their potential as a sales lead.

Consider factors like:
- How well the prospect's company aligns with your business model and target market
- Whether the prospect's role and authority level matches your ideal customer profile
- Industry and market fit based on your company's focus areas
- Geographic and market factors relevant to your business
- Source quality and data completeness

Return only a JSON object with this exact format:
{{
  "score": 75,
  "reason": "Strong potential: Mid-market SaaS company, VP-level decision maker, growing industry, good data quality"
}}

Score 0-100 based on how well this prospect fits YOUR specific business context and sales goals."""
    
    return prompt

async def score_with_openai(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Score prospects 0-100. Return only valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500,
            timeout=10
        )
        
        result = response.choices[0].message.content.strip()
        
        if not result:
            print("OpenAI returned empty response")
            return []
        
        try:
            parsed_result = json.loads(result)
            if isinstance(parsed_result, dict):
                return [parsed_result]
            elif isinstance(parsed_result, list):
                return parsed_result
            else:
                return []
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Raw response: {result}")
            
            json_match = re.search(r'\[.*\]', result)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            return []
            
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return []

@router.post("/score")
async def score_prospects(
    prospects: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        company_table = get_table('icps', current_user.schema_name, db.bind)
        persona_table = get_table('personas', current_user.schema_name, db.bind)
        scoring_weights_table = get_table('scoring_weights', current_user.schema_name, db.bind)
        company_description_table = get_table('company_descriptions', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            company_profiles = conn.execute(company_table.select()).fetchall()
            persona_profiles = conn.execute(persona_table.select()).fetchall()
            scoring_weights = conn.execute(scoring_weights_table.select()).fetchone()
            company_description = conn.execute(company_description_table.select()).fetchone()
        
        weights = {
            "company_fit": float(scoring_weights.company_fit_weight) / 100 if scoring_weights and scoring_weights.company_fit_weight else 0.4,
            "persona_fit": float(scoring_weights.persona_fit_weight) / 100 if scoring_weights and scoring_weights.persona_fit_weight else 0.4,
            "ai_intelligence": float(scoring_weights.sales_data_weight) / 100 if scoring_weights and scoring_weights.sales_data_weight else 0.2
        }
        
        scored_prospects = []
        
        for prospect in prospects:
            company_score = {"score": 50, "reason": "No company profiles available"}
            persona_score = {"score": 50, "reason": "No persona profiles available"}
            ai_score = {"score": 50, "reason": "AI intelligence analysis"}
            
            if company_profiles:
                company_prompt = create_scoring_prompt(prospect, company_profiles, "company")
                company_result = await score_with_openai(company_prompt)
                if company_result and len(company_result) > 0:
                    company_score = company_result[0]
            
            if persona_profiles:
                persona_prompt = create_scoring_prompt(prospect, persona_profiles, "persona")
                persona_result = await score_with_openai(persona_prompt)
                if persona_result and len(persona_result) > 0:
                    persona_score = persona_result[0]
            
            company_description_text = company_description.description if company_description and company_description.description else None
            ai_prompt = create_ai_intelligence_prompt(prospect, company_description_text)
            ai_result = await score_with_openai(ai_prompt)
            if ai_result and len(ai_result) > 0:
                ai_score = ai_result[0]
            
            final_score = round(
                (company_score["score"] * weights["company_fit"]) + 
                (persona_score["score"] * weights["persona_fit"]) + 
                (ai_score["score"] * weights["ai_intelligence"])
            )
            
            scored_prospect = {
                **prospect,
                "score": final_score,
                "score_reason": f"Company: {company_score['reason']} Persona: {persona_score['reason']} AI: {ai_score['reason']}",
                "company_score": company_score["score"],
                "persona_score": persona_score["score"],
                "ai_score": ai_score["score"]
            }
            
            scored_prospects.append(scored_prospect)
        
        return {"prospects": scored_prospects}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")

@router.post("/batch", response_model=List[Union[ProspectRead, DuplicateProspectResponse]])
def create_prospects_batch(
    prospects_data: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            all_sdrs = conn.execute(sdr_table.select()).fetchall()
            
            last_prospect = conn.execute(
                prospect_table.select().order_by(prospect_table.c.created_at.desc())
            ).fetchone()
        
        assigned_sdr_id = None
        if all_sdrs:
            if last_prospect and last_prospect.sales_rep_id:
                last_sdr_index = next((i for i, sdr in enumerate(all_sdrs) 
                                     if str(sdr.id) == str(last_prospect.sales_rep_id)), -1)
                next_sdr_index = (last_sdr_index + 1) % len(all_sdrs)
                assigned_sdr_id = str(all_sdrs[next_sdr_index].id)
            else:
                assigned_sdr_id = str(all_sdrs[0].id)
        
        results = []
        current_sdr_index = 0
        
        for prospect_data in prospects_data:
            import uuid
            prospect_id = str(uuid.uuid4())
            
            from datetime import datetime
            current_time = datetime.utcnow()
            
            insert_data = {
                'id': prospect_id,
                'first_name': prospect_data.get('first_name', ''),
                'last_name': prospect_data.get('last_name', ''),
                'email': prospect_data.get('email', ''),
                'company_name': prospect_data.get('company_name', ''),
                'job_title': prospect_data.get('job_title', ''),
                'linkedin_url': prospect_data.get('linkedin_url', ''),
                'phone_number': prospect_data.get('phone_number', ''),
                'location': prospect_data.get('location', ''),
                'department': prospect_data.get('department', ''),
                'seniority': prospect_data.get('seniority', ''),
                'source': prospect_data.get('source', 'csv_upload'),
                'source_id': prospect_data.get('source_id', ''),
                'current_score': prospect_data.get('current_score', 0),
                'initial_score': prospect_data.get('initial_score', 0),
                'score_reason': prospect_data.get('score_reason', ''),
                'score_period': prospect_data.get('score_period', ''),
                'suggested_sales_rep_reason': f"Round robin assignment from {prospect_data.get('source', 'csv_upload')}",
                'suggested_sales_rep_date': current_time,
                'sales_rep_id': assigned_sdr_id,
                'headshot_url': prospect_data.get('headshot_url', ''),
                'headshot_filename': prospect_data.get('headshot_filename', ''),
                'created_at': func.now(),
                'updated_at': func.now()
            }
            
            with db.bind.connect() as conn:
                existing_prospect = conn.execute(
                    prospect_table.select().where(
                        prospect_table.c.email == insert_data['email'] and 
                        prospect_table.c.source == insert_data['source']
                    )
                ).fetchone()
                
                if existing_prospect:
                    results.append(DuplicateProspectResponse(message="Prospect already exists", skipped=True))
                else:
                    insert_stmt = prospect_table.insert().values(**insert_data)
                    conn.execute(insert_stmt)
                    conn.commit()
                    
                    result = conn.execute(
                        prospect_table.select().where(prospect_table.c.id == prospect_id)
                    )
                    created_prospect = result.fetchone()
                    
                    results.append(ProspectRead(**{k: created_prospect._mapping[k] for k in created_prospect._mapping.keys() if k in ProspectRead.__fields__}))
            if all_sdrs:
                current_sdr_index = (current_sdr_index + 1) % len(all_sdrs)
                assigned_sdr_id = str(all_sdrs[current_sdr_index].id)
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create prospects: {str(e)}")

@router.get("/", response_model=List[ProspectRead])
def get_prospects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                prospect_table.select()
                .limit(limit)
                .offset(offset)
                .order_by(prospect_table.c.created_at.desc())
            )
            prospects = result.fetchall()
        
        prospect_list = []
        for prospect in prospects:
            try:
                prospect_data = {k: prospect._mapping[k] for k in prospect._mapping.keys() if k in ProspectRead.__fields__}
                prospect_list.append(ProspectRead(**prospect_data))
            except Exception as e:
                print(f"Error converting prospect {prospect._mapping.get('id', 'unknown')}: {e}")
                print(f"Prospect data: {prospect._mapping}")
                continue
        
        return prospect_list
    except Exception as e:
        print(f"Error in get_prospects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch prospects: {str(e)}")

@router.get("/{prospect_id}", response_model=ProspectRead)
def get_prospect(
    prospect_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                prospect_table.select().where(prospect_table.c.id == prospect_id)
            )
            prospect = result.fetchone()
        if not prospect:
            raise HTTPException(status_code=404, detail="Prospect not found")
        return ProspectRead(**{k: prospect._mapping[k] for k in prospect._mapping.keys() if k in ProspectRead.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch prospect")

@router.put("/{prospect_id}", response_model=ProspectRead)
def update_prospect(
    prospect_id: str,
    prospect_data: ProspectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            update_data = {k: v for k, v in prospect_data.dict().items() if v is not None}
            if update_data:
                update_stmt = prospect_table.update().where(prospect_table.c.id == prospect_id).values(**update_data)
                result = conn.execute(update_stmt)
                conn.commit()
            updated_prospect = conn.execute(
                prospect_table.select().where(prospect_table.c.id == prospect_id)
            ).fetchone()
        if not updated_prospect:
            raise HTTPException(status_code=404, detail="Prospect not found")
        return ProspectRead(**{k: updated_prospect._mapping[k] for k in updated_prospect._mapping.keys() if k in ProspectRead.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update prospect")

@router.delete("/{prospect_id}")
def delete_prospect(
    prospect_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                prospect_table.select().where(prospect_table.c.id == prospect_id)
            )
            prospect = result.fetchone()
            if not prospect:
                raise HTTPException(status_code=404, detail="Prospect not found")
            delete_stmt = prospect_table.delete().where(prospect_table.c.id == prospect_id)
            conn.execute(delete_stmt)
            conn.commit()
        return {"message": "Prospect deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete prospect") 