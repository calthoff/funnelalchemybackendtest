import threading
import asyncio
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List, Union, Optional
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

background_scoring_running = False
background_thread = None

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

async def score_with_openai(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI assistant that scores prospects. Return only valid JSON objects with score (0-100) and detailed reason. Provide comprehensive explanations including specific factors that influenced the score, company fit analysis, role relevance, and business potential. Do not wrap in markdown code blocks."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=800,
            timeout=10
        )
        
        result = response.choices[0].message.content.strip()
        
        if not result:
            print("OpenAI returned empty response")
            return {"score": 50, "reason": "Unable to analyze prospect due to empty AI response. Default score assigned based on neutral assessment."}
        
        if result.startswith("```json"):
            result = result[7:]
        if result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]
        
        result = result.strip()
        
        try:
            parsed_result = json.loads(result)
            if isinstance(parsed_result, dict):
                score = parsed_result.get("score", 50)
                score = max(0, min(100, int(score)))
                parsed_result["score"] = score
                if "reason" not in parsed_result:
                    parsed_result["reason"] = "AI analysis completed but no specific reasoning provided. Score based on general prospect assessment criteria."
                return parsed_result
            else:
                return {"score": 50, "reason": "Invalid response format received from AI. Unable to parse detailed analysis. Default score assigned."}
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Raw response: {result}")
            
            json_match = re.search(r'\{.*\}', result)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    score = parsed.get("score", 50)
                    score = max(0, min(100, int(score)))
                    parsed["score"] = score
                    return parsed
                except:
                    pass
            
            return {"score": 50, "reason": "Failed to parse AI response due to JSON formatting issues. Unable to extract detailed analysis. Default score assigned."}
            
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return {"score": 50, "reason": f"AI scoring service unavailable due to technical error: {str(e)}. Default score assigned based on neutral assessment."}

@router.post("/score")
async def score_prospects(
    prospects: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if not prospects:
            return {"prospects": []}
        
        prospect_settings_table = get_table('prospect_settings', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            prospect_settings_result = conn.execute(prospect_settings_table.select())
            prospect_settings = prospect_settings_result.fetchall()
            
            if not prospect_settings:
                raise HTTPException(
                    status_code=400,
                    detail="Please configure prospect scoring settings before scoring prospects"
                )
            
            setting = dict(prospect_settings[0]._mapping)
            # Default scoring logic without custom prompt
            scoring_prompt = "Score this prospect from 0-100 based on their role, company, and fit for our solution. Provide a brief reason for the score."
        
        scored_prospects = []
        for prospect in prospects:
            try:
                formatted_prompt = scoring_prompt.format(
                    first_name=prospect.get('first_name', ''),
                    last_name=prospect.get('last_name', ''),
                    company_name=prospect.get('company_name', ''),
                    job_title=prospect.get('job_title', ''),
                    industry=prospect.get('industry', ''),
                    company_size=prospect.get('company_size', ''),
                    revenue=prospect.get('revenue', ''),
                    location=prospect.get('location', ''),
                    linkedin_url=prospect.get('linkedin_url', ''),
                    department=prospect.get('department', ''),
                    seniority=prospect.get('seniority', '')
                )
                
                score_result = await score_with_openai(formatted_prompt)
                
                prospect['current_score'] = score_result.get('score', 50)
                prospect['score_reason'] = score_result.get('reason', 'AI analysis completed with comprehensive evaluation of prospect fit and business potential.')
                
                scored_prospects.append(prospect)
                
            except Exception as e:
                print(f"Error scoring prospect {prospect.get('id', 'unknown')}: {str(e)}")
                prospect['current_score'] = 50
                prospect['score_reason'] = f"Scoring process failed due to technical error: {str(e)}. Unable to complete detailed prospect analysis. Default score assigned."
                scored_prospects.append(prospect)
        
        return {"prospects": scored_prospects}
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to score prospects: {str(e)}")

async def score_prospect_background(prospect_id: str, schema_name: str):
    try:
        print(f"\n🔄 Starting background scoring for prospect {prospect_id}")
        
        from app.db import SessionLocal
        db = SessionLocal()
        
        try:
            prospect_table = get_table('prospects', schema_name, db.bind)
            prospect_settings_table = get_table('prospect_settings', schema_name, db.bind)
            
            print(f"📊 Getting prospect data...")
            with db.bind.connect() as conn:
                prospect = conn.execute(
                    prospect_table.select().where(prospect_table.c.id == prospect_id)
                ).fetchone()

                if not prospect:
                    print(f"Prospect {prospect_id} not found")
                    return

                prospect_settings_result = conn.execute(prospect_settings_table.select())
                prospect_settings = prospect_settings_result.fetchall()
                
                if not prospect_settings:
                    print(f"No prospect settings found for schema {schema_name}")
                    return
                
                setting = dict(prospect_settings[0]._mapping)
                # Default scoring logic without custom prompt
                scoring_prompt = "Score this prospect from 0-100 based on their role, company, and fit for our solution. Provide a brief reason for the score."

            prospect_data = dict(prospect._mapping)
            
            formatted_prompt = scoring_prompt.format(
                first_name=prospect_data.get('first_name', ''),
                last_name=prospect_data.get('last_name', ''),
                company_name=prospect_data.get('company_name', ''),
                job_title=prospect_data.get('job_title', ''),
                industry=prospect_data.get('industry', ''),
                company_size=prospect_data.get('company_size', ''),
                revenue=prospect_data.get('revenue', ''),
                location=prospect_data.get('location', ''),
                linkedin_url=prospect_data.get('linkedin_url', ''),
                department=prospect_data.get('department', ''),
                seniority=prospect_data.get('seniority', '')
            )
            
            score_result = await score_with_openai(formatted_prompt)
            
            with db.bind.connect() as conn:
                conn.execute(
                    prospect_table.update().where(prospect_table.c.id == prospect_id).values(
                        current_score=score_result.get('score', 50),
                        score_reason=score_result.get('reason', 'AI analysis completed with comprehensive evaluation of prospect fit and business potential.')
                    )
                )
                conn.commit()
            
            print(f"✅ Successfully scored prospect {prospect_id} with score {score_result.get('score', 50)}")
            
        finally:
            db.close()
            
    except Exception as e:
        try:
            from app.db import SessionLocal
            db = SessionLocal()
            prospect_table = get_table('prospects', schema_name, db.bind)
            
            with db.bind.connect() as conn:
                conn.execute(
                    prospect_table.update().where(prospect_table.c.id == prospect_id).values(
                        current_score=50,
                        score_reason=f"Scoring process failed due to technical error: {str(e)}. Unable to complete detailed prospect analysis. Default score assigned."
                    )
                )
                conn.commit()
            db.close()
        except Exception as update_error:
            print(f"Failed to update prospect {prospect_id} with error status: {str(update_error)}")

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
                'current_score': prospect_data.get('current_score', -1),
                'initial_score': prospect_data.get('initial_score', -1),
                'score_reason': prospect_data.get('score_reason', 'Generating...'),
                'score_period': prospect_data.get('score_period', ''),
                'suggested_sales_rep_reason': f"Round robin assignment from {prospect_data.get('source', 'csv_upload')}",
                'suggested_sales_rep_date': current_time,
                'sales_rep_id': assigned_sdr_id,
                'headshot_url': prospect_data.get('headshot_url', ''),
                'headshot_filename': prospect_data.get('headshot_filename', ''),
                'funding_stage': prospect_data.get('funding_stage', ''),
                'funding_amount': prospect_data.get('funding_amount', ''),
                'funding_date': prospect_data.get('funding_date', ''),
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
                    
                    prospect_data = {k: created_prospect._mapping[k] for k in created_prospect._mapping.keys() if k in ProspectRead.__fields__ and k != 'activities'}
                    prospect_data['activities'] = []
                    
                    results.append(ProspectRead(**prospect_data))

            if all_sdrs:
                current_sdr_index = (current_sdr_index + 1) % len(all_sdrs)
                assigned_sdr_id = str(all_sdrs[current_sdr_index].id)
        
        def start_scoring_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(trigger_immediate_scoring_background(current_user.schema_name))
            except Exception as e:
                print(f"Error in scoring thread: {e}")
        
        scoring_thread = threading.Thread(target=start_scoring_thread)
        scoring_thread.daemon = True
        scoring_thread.start()
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create prospects: {str(e)}")

async def trigger_immediate_scoring_background(schema_name: str):
    try:
        from app.db import SessionLocal
        db = SessionLocal()
        
        try:
            prospect_table = get_table('prospects', schema_name, db.bind)
            
            with db.bind.connect() as conn:
                prospects_to_score = conn.execute(
                    prospect_table.select().where(
                        (prospect_table.c.current_score == -1) &
                        (prospect_table.c.score_reason == 'Generating...')
                    ).order_by(prospect_table.c.created_at.desc()).limit(20)
                ).fetchall()
            
            if not prospects_to_score:
                print("No prospects need immediate scoring")
                return
            
            for prospect in prospects_to_score:
                try:
                    await score_prospect_background(str(prospect.id), schema_name)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Error scoring prospect {prospect.id}: {e}")
                    continue
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error in immediate scoring background task: {e}")

@router.get("/", response_model=List[ProspectRead])
def get_prospects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        
        prospect_list = []
        
        with db.bind.connect() as conn:
            # First, get all prospects
            result = conn.execute(
                prospect_table.select()
                .limit(limit)
                .offset(offset)
                .order_by(prospect_table.c.created_at.desc())
            )
            prospects = result.fetchall()
            
            try:
                prospect_activities_table = get_table('prospect_activities', current_user.schema_name, db.bind)
                activities_table_exists = True
            except Exception:
                activities_table_exists = False
                print("prospect_activities table not found, returning prospects without activities")
            
            for prospect in prospects:
                try:
                    prospect_data = {k: prospect._mapping[k] for k in ProspectRead.__fields__ if k != 'activities'}
                    activities_list = []
                    if activities_table_exists:
                        try:
                            activities_result = conn.execute(
                                prospect_activities_table.select()
                                .where(prospect_activities_table.c.prospect_id == str(prospect.id))
                                .order_by(prospect_activities_table.c.timestamp.desc())
                            )
                            activities = activities_result.fetchall()
                            for activity in activities:
                                activities_list.append({
                                    "id": str(activity.id),
                                    "prospect_id": str(activity.prospect_id),
                                    "type": activity.type,
                                    "source": activity.source,
                                    "description": activity.description,
                                    "timestamp": activity.timestamp
                                })
                        except Exception as activity_error:
                            print(f"Error fetching activities for prospect {prospect.id}: {activity_error}")
                            activities_list = []
                    
                    prospect_data['activities'] = activities_list
                    prospect_list.append(ProspectRead(**prospect_data))
                    
                except Exception as e:
                    print(f"Error converting prospect {prospect._mapping.get('id', 'unknown')}: {e}")
                    print(f"Prospect data: {prospect._mapping}")
                    try:
                        prospect_data = {k: prospect._mapping[k] for k in ProspectRead.__fields__ if k != 'activities'}
                        prospect_data['activities'] = []
                        prospect_list.append(ProspectRead(**prospect_data))
                    except Exception as fallback_error:
                        print(f"Fallback error for prospect {prospect._mapping.get('id', 'unknown')}: {fallback_error}")
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
            
            prospect_data = {k: prospect._mapping[k] for k in prospect._mapping.keys() if k in ProspectRead.__fields__ and k != 'activities'}
            
            # Check if prospect_activities table exists
            try:
                prospect_activities_table = get_table('prospect_activities', current_user.schema_name, db.bind)
                activities_table_exists = True
            except Exception:
                activities_table_exists = False
                print("prospect_activities table not found, returning prospect without activities")
            
            # Fetch activities for this prospect if table exists
            activities_list = []
            if activities_table_exists:
                try:
                    activities_result = conn.execute(
                        prospect_activities_table.select()
                        .where(prospect_activities_table.c.prospect_id == prospect_id)
                        .order_by(prospect_activities_table.c.timestamp.desc())
                    )
                    activities = activities_result.fetchall()
                    
                    # Convert activities to ActivityRead format
                    for activity in activities:
                        activities_list.append({
                            "id": str(activity.id),
                            "prospect_id": str(activity.prospect_id),
                            "type": activity.type,
                            "source": activity.source,
                            "description": activity.description,
                            "timestamp": activity.timestamp
                        })
                except Exception as activity_error:
                    print(f"Error fetching activities for prospect {prospect_id}: {activity_error}")
                    activities_list = []
            
            prospect_data['activities'] = activities_list
            return ProspectRead(**prospect_data)
            
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
            
            prospect_data_response = {k: updated_prospect._mapping[k] for k in updated_prospect._mapping.keys() if k in ProspectRead.__fields__ and k != 'activities'}
            
            # Check if prospect_activities table exists
            try:
                prospect_activities_table = get_table('prospect_activities', current_user.schema_name, db.bind)
                activities_table_exists = True
            except Exception:
                activities_table_exists = False
                print("prospect_activities table not found, returning prospect without activities")
            
            # Fetch activities for this prospect if table exists
            activities_list = []
            if activities_table_exists:
                try:
                    activities_result = conn.execute(
                        prospect_activities_table.select()
                        .where(prospect_activities_table.c.prospect_id == prospect_id)
                        .order_by(prospect_activities_table.c.timestamp.desc())
                    )
                    activities = activities_result.fetchall()
                    
                    # Convert activities to ActivityRead format
                    for activity in activities:
                        activities_list.append({
                            "id": str(activity.id),
                            "prospect_id": str(activity.prospect_id),
                            "type": activity.type,
                            "source": activity.source,
                            "description": activity.description,
                            "timestamp": activity.timestamp
                        })
                except Exception as activity_error:
                    print(f"Error fetching activities for prospect {prospect_id}: {activity_error}")
                    activities_list = []
            
            prospect_data_response['activities'] = activities_list
            return ProspectRead(**prospect_data_response)
            
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

class BatchDeleteRequest(BaseModel):
    prospect_ids: List[str]

@router.post("/batch-delete")
def delete_prospects_batch(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_ids = request.prospect_ids
        print(f"DEBUG: Received prospect_ids: {prospect_ids}")
        print(f"DEBUG: Schema name: {current_user.schema_name}")
        
        if not prospect_ids:
            return {
                "message": "No prospects to delete",
                "deleted_count": 0,
                "prospect_ids": []
            }
        
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        print(f"DEBUG: Got prospect table")
        
        with db.bind.connect() as conn:
            print(f"DEBUG: Connected to database")
            
            try:
                delete_stmt = prospect_table.delete().where(prospect_table.c.id.in_(prospect_ids))
                result = conn.execute(delete_stmt)
                conn.commit()
                deleted_count = result.rowcount
                
                return {
                    "message": f"Successfully deleted {deleted_count} prospect(s)",
                    "deleted_count": deleted_count,
                    "prospect_ids": prospect_ids
                }
                
            except Exception as batch_error:
                conn.rollback()
                
                deleted_count = 0
                for prospect_id in prospect_ids:
                    try:
                        delete_stmt = prospect_table.delete().where(prospect_table.c.id == prospect_id)
                        result = conn.execute(delete_stmt)
                        if result.rowcount > 0:
                            deleted_count += 1
                    except Exception as e:
                        print(f"DEBUG: Failed to delete prospect {prospect_id}: {str(e)}")
                        continue
                
                conn.commit()
                
                return {
                    "message": f"Successfully deleted {deleted_count} prospect(s)",
                    "deleted_count": deleted_count,
                    "prospect_ids": prospect_ids
                }
                
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete prospects: {str(e)}")

@router.post("/trigger-scoring")
async def trigger_scoring(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            prospects_to_score = conn.execute(
                select([prospect_table]).where(
                    (prospect_table.c.current_score == 0) | 
                    (prospect_table.c.score_reason.is_(None)) |
                    (prospect_table.c.score_reason == '')
                ).limit(5)
            ).fetchall()
        
        if not prospects_to_score:
            return {"message": "No prospects need scoring", "processed": 0}
        
        processed_count = 0
        for prospect in prospects_to_score:
            try:
                await score_prospect_background(str(prospect.id), current_user.schema_name)
                processed_count += 1
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Error scoring prospect {prospect.id}: {e}")
                continue
        
        return {
            "message": f"Successfully processed {processed_count} prospects",
            "processed": processed_count,
            "total_found": len(prospects_to_score)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger scoring: {str(e)}") 

@router.post("/trigger-immediate-scoring")
async def trigger_immediate_scoring(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            prospects_to_score = conn.execute(
                prospect_table.select().where(
                    (prospect_table.c.current_score == -1) &
                    (prospect_table.c.score_reason == 'Generating...')
                ).order_by(prospect_table.c.created_at.desc()).limit(20)
            ).fetchall()
        
        if not prospects_to_score:
            return {"message": "No prospects need immediate scoring", "processed": 0}
        
        processed_count = 0
        for prospect in prospects_to_score:
            try:
                await score_prospect_background(str(prospect.id), current_user.schema_name)
                processed_count += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Error scoring prospect {prospect.id}: {e}")
                continue
        
        return {
            "message": f"Successfully processed {processed_count} prospects",
            "processed": processed_count,
            "total_found": len(prospects_to_score)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger immediate scoring: {str(e)}")

@router.get("/scoring-status")
async def get_scoring_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            prospects_needing_scoring = conn.execute(
                prospect_table.select().where(
                    (prospect_table.c.current_score == 0) | 
                    (prospect_table.c.current_score == -1) |
                    (prospect_table.c.score_reason.is_(None)) |
                    (prospect_table.c.score_reason == '') |
                    (prospect_table.c.score_reason == 'Generating...')
                )
            ).fetchall()
            
            total_prospects = conn.execute(prospect_table.select()).fetchall()
            
            scored_prospects = conn.execute(
                prospect_table.select().where(
                    (prospect_table.c.current_score > 0) & 
                    (prospect_table.c.score_reason.isnot(None)) &
                    (prospect_table.c.score_reason != '') &
                    (prospect_table.c.score_reason != 'Generating...')
                )
            ).fetchall()
        
        return {
            "total_prospects": len(total_prospects),
            "scored_prospects": len(scored_prospects),
            "prospects_needing_scoring": len(prospects_needing_scoring),
            "scoring_progress": f"{len(scored_prospects)}/{len(total_prospects)}" if len(total_prospects) > 0 else "0/0"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scoring status: {str(e)}") 

@router.post("/trigger-rescoring")
async def trigger_rescoring(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            all_prospects = conn.execute(
                prospect_table.select().where(
                    prospect_table.c.current_score > 0
                )
            ).fetchall()
        
        if not all_prospects:
            return {"message": "No prospects to re-score", "processed": 0}
        
        processed_count = 0
        for prospect in all_prospects:
            try:
                await score_prospect_background(str(prospect.id), current_user.schema_name)
                processed_count += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Error re-scoring prospect {prospect.id}: {e}")
                continue
        
        return {
            "message": f"Successfully re-scored {processed_count} prospects with updated criteria",
            "processed": processed_count,
            "total_found": len(all_prospects)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger re-scoring: {str(e)}") 

@router.get("/replies/status/{status}")
def get_prospects_by_reply_status(
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    date_filter: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)")
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            try:
                query = prospect_table.select().where(prospect_table.c.reply_status == status)
                
                if date_filter:
                    try:
                        filter_date = datetime.strptime(date_filter, '%Y-%m-%d')
                        next_day = filter_date + timedelta(days=1)
                        query = query.where(
                            (prospect_table.c.contacted_date >= filter_date) &
                            (prospect_table.c.contacted_date < next_day)
                        )
                    except ValueError:
                        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
                
                result = conn.execute(
                    query
                    .limit(limit)
                    .offset(offset)
                    .order_by(prospect_table.c.contacted_date.desc() if status == 'no_reply' else prospect_table.c.reply_date.desc())
                )
                prospects = result.fetchall()
                
            except Exception as column_error:
                # If reply_status column doesn't exist, return empty list
                print(f"Reply status column not found, returning empty list: {column_error}")
                return []
            
            # Check if prospect_activities table exists
            try:
                prospect_activities_table = get_table('prospect_activities', current_user.schema_name, db.bind)
                activities_table_exists = True
            except Exception:
                activities_table_exists = False
                print("prospect_activities table not found, returning prospects without activities")
        
        prospect_list = []
        for prospect in prospects:
            try:
                prospect_data = {k: prospect._mapping[k] for k in ProspectRead.__fields__ if k != 'activities'}
                
                # Fetch activities for this prospect if table exists
                activities_list = []
                if activities_table_exists:
                    try:
                        activities_result = conn.execute(
                            prospect_activities_table.select()
                            .where(prospect_activities_table.c.prospect_id == str(prospect.id))
                            .order_by(prospect_activities_table.c.timestamp.desc())
                        )
                        activities = activities_result.fetchall()
                        
                        # Convert activities to ActivityRead format
                        for activity in activities:
                            activities_list.append({
                                "id": str(activity.id),
                                "prospect_id": str(activity.prospect_id),
                                "type": activity.type,
                                "source": activity.source,
                                "description": activity.description,
                                "timestamp": activity.timestamp
                            })
                    except Exception as activity_error:
                        print(f"Error fetching activities for prospect {prospect.id}: {activity_error}")
                        activities_list = []
                
                prospect_data['activities'] = activities_list
                prospect_list.append(ProspectRead(**prospect_data))
            except Exception as e:
                print(f"Error converting prospect {prospect._mapping.get('id', 'unknown')}: {e}")
                continue
        
        return prospect_list
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch prospects by reply status: {str(e)}")

@router.put("/{prospect_id}/reply")
def update_prospect_reply(
    prospect_id: str,
    reply_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            try:
                existing_prospect = conn.execute(
                    prospect_table.select().where(prospect_table.c.id == prospect_id)
                ).fetchone()
                
                if not existing_prospect:
                    raise HTTPException(status_code=404, detail="Prospect not found")
                
                update_data = {}
                
                if 'reply_status' in reply_data:
                    reply_status = reply_data['reply_status']
                    if reply_status == '' or reply_status in ['no_reply', 'replied'] or reply_status is None:
                        update_data['reply_status'] = reply_status if reply_status != '' else None
                
                if 'reply_content' in reply_data:
                    reply_content = reply_data['reply_content']
                    update_data['reply_content'] = reply_content if reply_content else None
                
                if 'reply_sentiment' in reply_data:
                    reply_sentiment = reply_data['reply_sentiment']
                    if reply_sentiment == '' or reply_sentiment in ['positive', 'negative', 'neutral'] or reply_sentiment is None:
                        update_data['reply_sentiment'] = reply_sentiment if reply_sentiment != '' else None

                if 'reply_date' in reply_data:
                    update_data['reply_date'] = datetime.utcnow()
                
                if update_data:
                    print(f"Updating prospect {prospect_id} with data: {update_data}")
                    update_stmt = prospect_table.update().where(
                        prospect_table.c.id == prospect_id
                    ).values(**update_data)
                    conn.execute(update_stmt)
                    conn.commit()
                    print(f"Successfully updated prospect {prospect_id}")
                
                updated_prospect = conn.execute(
                    prospect_table.select().where(prospect_table.c.id == prospect_id)
                ).fetchone()
                
                prospect_data_response = {k: updated_prospect._mapping[k] for k in updated_prospect._mapping.keys() if k in ProspectRead.__fields__ and k != 'activities'}
                
                # Check if prospect_activities table exists
                try:
                    prospect_activities_table = get_table('prospect_activities', current_user.schema_name, db.bind)
                    activities_table_exists = True
                except Exception:
                    activities_table_exists = False
                    print("prospect_activities table not found, returning prospect without activities")
                
                # Fetch activities for this prospect if table exists
                activities_list = []
                if activities_table_exists:
                    try:
                        activities_result = conn.execute(
                            prospect_activities_table.select()
                            .where(prospect_activities_table.c.prospect_id == prospect_id)
                            .order_by(prospect_activities_table.c.timestamp.desc())
                        )
                        activities = activities_result.fetchall()
                        
                        # Convert activities to ActivityRead format
                        for activity in activities:
                            activities_list.append({
                                "id": str(activity.id),
                                "prospect_id": str(activity.prospect_id),
                                "type": activity.type,
                                "source": activity.source,
                                "description": activity.description,
                                "timestamp": activity.timestamp
                            })
                    except Exception as activity_error:
                        print(f"Error fetching activities for prospect {prospect_id}: {activity_error}")
                        activities_list = []
                
                prospect_data_response['activities'] = activities_list
                return ProspectRead(**prospect_data_response)
                
            except Exception as column_error:
                print(f"Reply columns not found: {column_error}")
                raise HTTPException(status_code=500, detail="Reply tracking columns not available. Please run database migration first.")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating prospect reply: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update prospect reply: {str(e)}")

@router.put("/{prospect_id}/mark-contacted")
def mark_prospect_contacted(
    prospect_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            try:
                existing_prospect = conn.execute(
                    prospect_table.select().where(prospect_table.c.id == prospect_id)
                ).fetchone()
                
                if not existing_prospect:
                    raise HTTPException(status_code=404, detail="Prospect not found")
                
                update_stmt = prospect_table.update().where(
                    prospect_table.c.id == prospect_id
                ).values(
                    contacted_date=datetime.utcnow(),
                    reply_status='no_reply'
                )
                conn.execute(update_stmt)
                conn.commit()
                
                return {"message": "Prospect marked as contacted successfully"}
                
            except Exception as column_error:
                print(f"Reply columns not found: {column_error}")
                raise HTTPException(status_code=500, detail="Reply tracking columns not available. Please run database migration first.")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark prospect as contacted: {str(e)}") 