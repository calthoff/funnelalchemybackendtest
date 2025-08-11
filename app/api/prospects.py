from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List, Union
from openai import OpenAI
import os
import json
import re
import numpy as np
from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.prospects import ProspectRead, ProspectUpdate
from app.utils.db_utils import get_table
from pydantic import BaseModel

router = APIRouter(prefix="/prospects", tags=["prospects"], redirect_slashes=False)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class DuplicateProspectResponse(BaseModel):
    message: str
    skipped: bool

def normalize_job_title(title):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Normalize job titles to standard roles. Return only the normalized title."},
                {"role": "user", "content": f"Normalize this job title: {title}"}
            ],
            temperature=0.1,
            max_tokens=50
        )
        return response.choices[0].message.content.strip()
    except:
        return title

def get_embedding(text):
    """Get embedding for semantic similarity"""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except:
        return None

def calculate_similarity(embedding1, embedding2):
    """Calculate cosine similarity between embeddings"""
    if not embedding1 or not embedding2:
        return 0
    
    try:
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        return float(similarity)
    except:
        return 0

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
    
    scoring_guidance = ""
    if profile_type == "company":
        scoring_guidance = """
SCORING GUIDANCE:
- Strong match (90-100): Matches multiple criteria (industry, size, ARR)
- Partial match (60-80): Matches some criteria (e.g., one industry or close ARR)
- Weak match (40-59): Limited alignment
- No match (0-39): No significant alignment
"""
    else:
        scoring_guidance = """
SCORING GUIDANCE:
- Exact match or strong title overlap (90-100): Perfect role match
- Semantic similarity or adjacent role (70-89): Related role or department
- Low seniority or off-department (0-69): Limited role relevance
"""
    
    prompt = f"""You are a lead scoring expert. Score this prospect (0-100) against these {profile_type} profiles.

{prospect_info}{profiles_info}{scoring_guidance}

Return only a JSON object with this exact format:
{{
  "score": 85,
  "component_scores": {{
    "profile_match_score": 90,
    "criteria_alignment": 80
  }},
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
  "component_scores": {{
    "business_alignment": 80,
    "role_relevance": 70,
    "market_fit": 75
  }},
  "reason": "Strong potential: Mid-market SaaS company, VP-level decision maker, growing industry, good data quality"
}}

Score 0-100 based on how well this prospect fits YOUR specific business context and sales goals."""
    
    return prompt

async def score_with_openai(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Score prospects 0-100. Return only valid JSON objects with component_scores."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500,
            timeout=10
        )
        
        result = response.choices[0].message.content.strip()
        
        # Handle empty or malformed responses
        if not result:
            print("OpenAI returned empty response")
            return {"score": 50, "component_scores": {}, "reason": "No response from AI"}
        
        # Try to parse JSON, with fallback for common issues
        try:
            parsed_result = json.loads(result)
            # Ensure we have the expected structure
            if isinstance(parsed_result, dict):
                if "score" not in parsed_result:
                    parsed_result["score"] = 50
                if "component_scores" not in parsed_result:
                    parsed_result["component_scores"] = {}
                if "reason" not in parsed_result:
                    parsed_result["reason"] = "AI analysis"
                return parsed_result
            else:
                return {"score": 50, "component_scores": {}, "reason": "Invalid response format"}
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Raw response: {result}")
            
            # Try to extract JSON from the response if it's wrapped in text
            json_match = re.search(r'\{.*\}', result)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            return {"score": 50, "component_scores": {}, "reason": "JSON parsing failed"}
            
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return {"score": 50, "component_scores": {}, "reason": "API error"}

@router.post("/score")
async def score_prospects(
    prospects: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if not prospects:
            return {"prospects": []}
        
        company_table = get_table('icps', current_user.schema_name, db.bind)
        persona_table = get_table('personas', current_user.schema_name, db.bind)
        scoring_weights_table = get_table('scoring_weights', current_user.schema_name, db.bind)
        company_description_table = get_table('company_descriptions', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            company_profiles = conn.execute(company_table.select()).fetchall()
            persona_profiles = conn.execute(persona_table.select()).fetchall()
            scoring_weights = conn.execute(scoring_weights_table.select()).fetchone()
            company_description = conn.execute(company_description_table.select()).fetchone()
        
        company_profiles = company_profiles or []
        persona_profiles = persona_profiles or []
        
        if not scoring_weights:
            weights = {
                "company_fit": 0.4,
                "persona_fit": 0.4,
                "ai_intelligence": 0.2
            }
        else:
            weights = {
                "company_fit": float(scoring_weights.company_fit_weight) / 100 if scoring_weights.company_fit_weight else 0.0,
                "persona_fit": float(scoring_weights.persona_fit_weight) / 100 if scoring_weights.persona_fit_weight else 0.0,
                "ai_intelligence": float(scoring_weights.sales_data_weight) / 100 if scoring_weights.sales_data_weight else 0.0
            }
        
        company_description_text = company_description.description if company_description and company_description.description else None
        company_embedding = get_embedding(company_description_text) if company_description_text else None
        
        scored_prospects = []
        for prospect in prospects:
            normalized_title = normalize_job_title(prospect.get('title', ''))
            prospect['normalized_title'] = normalized_title
            
            # Only calculate scores for non-zero weights
            company_score = None
            persona_score = None
            ai_score = None
            score_reason_parts = []
            component_scores = {}
            final_score = 0
            total_weight = 0
            
            # Company scoring
            if weights["company_fit"] > 0 and company_profiles:
                company_prompt = create_scoring_prompt(prospect, company_profiles, "company")
                company_score = await score_with_openai(company_prompt)
                final_score += company_score["score"] * weights["company_fit"]
                total_weight += weights["company_fit"]
                score_reason_parts.append(f"Company: {company_score['reason']}")
                component_scores["company"] = company_score.get("component_scores", {})
            
            # Persona scoring
            if weights["persona_fit"] > 0 and persona_profiles:
                persona_prompt = create_scoring_prompt(prospect, persona_profiles, "persona")
                persona_score = await score_with_openai(persona_prompt)
                final_score += persona_score["score"] * weights["persona_fit"]
                total_weight += weights["persona_fit"]
                score_reason_parts.append(f"Persona: {persona_score['reason']}")
                component_scores["persona"] = persona_score.get("component_scores", {})
            
            # AI intelligence scoring
            if weights["ai_intelligence"] > 0:
                ai_prompt = create_ai_intelligence_prompt(prospect, company_description_text)
                ai_score = await score_with_openai(ai_prompt)
                final_score += ai_score["score"] * weights["ai_intelligence"]
                total_weight += weights["ai_intelligence"]
                score_reason_parts.append(f"AI: {ai_score['reason']}")
                component_scores["ai"] = ai_score.get("component_scores", {})
            
            # Semantic similarity boost (only if any weight > 0)
            similarity_boost = 0
            if total_weight > 0 and company_embedding and prospect.get('company') and prospect.get('title'):
                prospect_text = f"{prospect.get('company')} {normalized_title}"
                prospect_embedding = get_embedding(prospect_text)
                similarity = calculate_similarity(company_embedding, prospect_embedding)
                if similarity > 0.8:
                    similarity_boost = 10
                elif similarity > 0.6:
                    similarity_boost = 5
                final_score += similarity_boost
                # score_reason_parts.append(f"Similarity boost: +{similarity_boost}")
            
            # If all weights are zero, return default
            if total_weight == 0:
                scored_prospect = {
                    **prospect,
                    "score": 50,
                    "score_reason": "All weights are zero, no scoring performed.",
                    "company_score": None,
                    "persona_score": None,
                    "ai_score": None,
                    "similarity_boost": 0,
                    "component_scores": {}
                }
            else:
                final_score = round(min(final_score, 100))
                scored_prospect = {
                    **prospect,
                    "score": final_score,
                    "score_reason": " | ".join(score_reason_parts),
                    "company_score": company_score["score"] if company_score else None,
                    "persona_score": persona_score["score"] if persona_score else None,
                    "ai_score": ai_score["score"] if ai_score else None,
                    "similarity_boost": similarity_boost,
                    "component_scores": component_scores
                }
            scored_prospects.append(scored_prospect)
        return {"prospects": scored_prospects}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")

async def score_prospect_background(prospect_id: str, schema_name: str):
    """Background task to score a prospect"""
    try:
        print(f"\n🔄 Starting background scoring for prospect {prospect_id}")
        
        # Get DB session
        db = next(get_db())
        prospect_table = get_table('prospects', schema_name, db.bind)
        
        print(f"📊 Getting prospect data...")
        # Get prospect data
        with db.bind.connect() as conn:
            prospect = conn.execute(
                select([prospect_table]).where(prospect_table.c.id == prospect_id)
            ).fetchone()

            if not prospect:
                print(f"Prospect {prospect_id} not found")
                return

            # Format prospect data for scoring
            prospect_data = {
                "name": f"{prospect.first_name} {prospect.last_name}",
                "company": prospect.company_name,
                "title": prospect.job_title,
                "email": prospect.email
            }

            print(f"🧮 Calculating score for {prospect_data['name']} at {prospect_data['company']}...")
            # Score the prospect
            score_result = await score_prospects([prospect_data], db, None)
            if score_result and score_result.get("prospects"):
                scored_prospect = score_result["prospects"][0]
                print(f"✨ Score calculated: {scored_prospect['score']}")
                print(f"📝 Reason: {scored_prospect['score_reason']}")
                
                # Update prospect with score
                conn.execute(
                    prospect_table.update()
                    .where(prospect_table.c.id == prospect_id)
                    .values(
                        current_score=scored_prospect["score"],
                        initial_score=scored_prospect["score"],
                        score_reason=scored_prospect["score_reason"],
                        updated_at=func.now()
                    )
                )
                conn.commit()
                print(f"✅ Successfully updated prospect {prospect_id} with new score\n")

    except Exception as e:
        print(f"❌ Background scoring error for prospect {prospect_id}: {e}\n")

@router.post("/batch", response_model=List[Union[ProspectRead, DuplicateProspectResponse]])
def create_prospects_batch(
    prospects_data: List[dict],
    background_tasks: BackgroundTasks,
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
                    
                    # Queue background scoring task
                    print(f"\n📋 Queuing background scoring for prospect {prospect_id}")
                    background_tasks.add_task(
                        score_prospect_background,
                        str(prospect_id),
                        current_user.schema_name
                    )

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