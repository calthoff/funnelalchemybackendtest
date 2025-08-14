from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List
import random
import uuid
from datetime import datetime
from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.calibration import (
    CalibrationSessionCreate, CalibrationSessionRead, CalibrationSampleRead,
    CalibrationFeedbackRequest, CalibrationCompleteRequest, CalibrationSampleResponse
)
from app.utils.db_utils import get_table
from app.api.prospects import score_prospects
from app.api.scoring_weights import update_scoring_weights
from app.schemas.scoring_weights import ScoringWeightUpdate

router = APIRouter(prefix="/calibration", tags=["calibration"], redirect_slashes=False)

@router.post("/session", response_model=CalibrationSessionRead)
async def create_calibration_session(
    session_data: CalibrationSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a virtual calibration session (no database table needed)"""
    try:
        scoring_weights_table = get_table('scoring_weights', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            scoring_weights = conn.execute(scoring_weights_table.select()).fetchone()
        
        # Get current weights
        if scoring_weights:
            current_weights = {
                "company_fit": float(scoring_weights.company_fit_weight) / 100 if scoring_weights.company_fit_weight else 0.0,
                "persona_fit": float(scoring_weights.persona_fit_weight) / 100 if scoring_weights.persona_fit_weight else 0.0,
                "ai_intelligence": float(scoring_weights.sales_data_weight) / 100 if scoring_weights.sales_data_weight else 0.0
            }
        else:
            current_weights = {
                "company_fit": 0.4,
                "persona_fit": 0.4,
                "ai_intelligence": 0.2
            }
        
        # Create virtual session (no database storage)
        session_id = str(uuid.uuid4())
        virtual_session = {
            'id': session_id,
            'user_id': str(current_user.id),
            'status': 'active',
            'sample_size': session_data.sample_size or 10,
            'original_weights': current_weights,
            'current_weights': current_weights,
            'feedback_count': 0,
            'approved_count': 0,
            'rejected_count': 0,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        return CalibrationSessionRead(**virtual_session)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create calibration session: {str(e)}")

@router.post("/session/{session_id}/samples", response_model=CalibrationSampleResponse)
async def generate_calibration_samples(
    session_id: str,
    prospects: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate calibration samples using current scoring weights"""
    try:
        sample_size = 10
        if len(prospects) <= sample_size:
            sample_prospects = prospects
        else:
            sample_prospects = random.sample(prospects, sample_size)
        formatted_prospects = []
        for prospect in sample_prospects:
            formatted_prospect = {
                "name": f"{prospect.get('first_name', '')} {prospect.get('last_name', '')}".strip(),
                "company": prospect.get('company_name', ''),
                "title": prospect.get('job_title', ''),
                "email": prospect.get('email', ''),
                "department": prospect.get('department', ''),
                "seniority": prospect.get('seniority', ''),
                "location": prospect.get('location', ''),
                "source": prospect.get('source', ''),
                "notes": prospect.get('notes', ''),
                "personalization": prospect.get('personalization', ''),
                "first_name": prospect.get('first_name', ''),
                "last_name": prospect.get('last_name', ''),
                "company_name": prospect.get('company_name', ''),
                "job_title": prospect.get('job_title', ''),
                "linkedin_url": prospect.get('linkedin_url', ''),
                "phone_number": prospect.get('phone_number', ''),
                "current_score": prospect.get('current_score', 0),
                "initial_score": prospect.get('initial_score', 0),
                "score_reason": prospect.get('score_reason', ''),
                "id": prospect.get('id', '')
            }
            formatted_prospects.append(formatted_prospect)
        
        print(f"🔧 Scoring {len(formatted_prospects)} sample prospects for calibration...")
        
        # Score the prospects using current weights
        scored_prospects = await score_prospects(formatted_prospects, db, current_user)
        
        # Create virtual samples (no database storage)
        samples = []
        for i, prospect in enumerate(scored_prospects['prospects']):
            sample_id = str(uuid.uuid4())
            virtual_sample = {
                'id': sample_id,
                'session_id': session_id,
                'prospect_data': sample_prospects[i],  # Original prospect data
                'original_score': prospect.get('score', 0),
                'score_reason': prospect.get('score_reason', ''),
                'component_scores': prospect.get('component_scores', {}),
                'user_feedback': None,
                'feedback_reason': None,
                'feedback_at': None,
                'created_at': datetime.now()
            }
            samples.append(CalibrationSampleRead(**virtual_sample))
        
        # Create virtual session response
        virtual_session = {
            'id': session_id,
            'user_id': str(current_user.id),
            'status': 'active',
            'sample_size': len(samples),
            'feedback_count': 0,
            'approved_count': 0,
            'rejected_count': 0,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        return CalibrationSampleResponse(
            session=CalibrationSessionRead(**virtual_session),
            samples=samples,
            total_samples=len(samples),
            feedback_count=0,
            approved_count=0,
            rejected_count=0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate calibration samples: {str(e)}")

@router.post("/sample/feedback")
async def submit_calibration_feedback(
    feedback_data: CalibrationFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit feedback for a calibration sample (virtual - no database storage)"""
    try:
        # This is a virtual feedback submission - we don't store it in database
        # The feedback will be used when the user completes the calibration
        return {"message": "Feedback submitted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")

@router.post("/session/{session_id}/complete")
async def complete_calibration_session(
    session_id: str,
    complete_data: CalibrationCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Complete calibration and update scoring weights based on feedback"""
    try:
        scoring_weights_table = get_table('scoring_weights', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            scoring_weights = conn.execute(scoring_weights_table.select()).fetchone()
        
        # Get current weights
        if scoring_weights:
            current_weights = {
                "company_fit": float(scoring_weights.company_fit_weight) / 100 if scoring_weights.company_fit_weight else 0.0,
                "persona_fit": float(scoring_weights.persona_fit_weight) / 100 if scoring_weights.persona_fit_weight else 0.0,
                "ai_intelligence": float(scoring_weights.sales_data_weight) / 100 if scoring_weights.sales_data_weight else 0.0
            }
        else:
            current_weights = {
                "company_fit": 0.4,
                "persona_fit": 0.4,
                "ai_intelligence": 0.2
            }
        
        if complete_data.action == 'approve':
            # Apply weight adjustments based on feedback
            adjusted_weights = current_weights.copy()
            
            # Parse the feedback summary to understand what was approved/rejected
            feedback_summary = complete_data.feedback_summary or ""
            print(f"📝 Received feedback summary: '{feedback_summary}'")
            print(f"📝 Feedback summary length: {len(feedback_summary)}")
            print(f"📝 Feedback summary type: {type(feedback_summary)}")
            feedback_parts = feedback_summary.split(';')
            print(f"📝 Feedback parts: {feedback_parts}")
            print(f"📝 Number of feedback parts: {len(feedback_parts)}")
            
            # Count approved and rejected
            approved_count = 0
            rejected_count = 0
            company_feedback = []
            persona_feedback = []
            ai_feedback = []
            
            for part in feedback_parts:
                part = part.strip()
                print(f"   Processing part: '{part}'")
                if 'approved:' in part.lower():
                    approved_count += 1
                    reason = part.split(':', 1)[1] if ':' in part else ''
                    print(f"     Found approved with reason: '{reason}'")
                    if 'company' in reason.lower() or 'business' in reason.lower():
                        company_feedback.append('positive')
                        print(f"     Added positive company feedback")
                    if 'persona' in reason.lower() or 'role' in reason.lower() or 'title' in reason.lower():
                        persona_feedback.append('positive')
                        print(f"     Added positive persona feedback")
                    if 'ai' in reason.lower() or 'intelligence' in reason.lower() or 'data' in reason.lower():
                        ai_feedback.append('positive')
                        print(f"     Added positive AI feedback")
                elif 'rejected:' in part.lower():
                    rejected_count += 1
                    reason = part.split(':', 1)[1] if ':' in part else ''
                    print(f"     Found rejected with reason: '{reason}'")
                    if 'company' in reason.lower() or 'business' in reason.lower():
                        company_feedback.append('negative')
                        print(f"     Added negative company feedback")
                    if 'persona' in reason.lower() or 'role' in reason.lower() or 'title' in reason.lower():
                        persona_feedback.append('negative')
                        print(f"     Added negative persona feedback")
                    if 'ai' in reason.lower() or 'intelligence' in reason.lower() or 'data' in reason.lower():
                        ai_feedback.append('negative')
                        print(f"     Added negative AI feedback")
                else:
                    print(f"     No approved/rejected found in: '{part}'")
            
            print(f"📊 Feedback Analysis:")
            print(f"   Approved: {approved_count}, Rejected: {rejected_count}")
            print(f"   Company feedback: {company_feedback}")
            print(f"   Persona feedback: {persona_feedback}")
            print(f"   AI feedback: {ai_feedback}")
            
            # Adjust weights based on feedback
            total_feedback = approved_count + rejected_count
            if total_feedback > 0:
                approval_rate = approved_count / total_feedback
                print(f"   Approval rate: {approval_rate:.2f}")
                
                if approval_rate > 0.5:
                    # More approved than rejected - increase weights proportionally
                    print(f"   More approved than rejected - increasing weights")
                    # Increase all weights slightly, but more for components that had positive feedback
                    if company_feedback.count('positive') > 0:
                        adjusted_weights['company_fit'] = min(adjusted_weights['company_fit'] * 1.2, 0.6)
                    if persona_feedback.count('positive') > 0:
                        adjusted_weights['persona_fit'] = min(adjusted_weights['persona_fit'] * 1.2, 0.6)
                    if ai_feedback.count('positive') > 0:
                        adjusted_weights['ai_intelligence'] = min(adjusted_weights['ai_intelligence'] * 1.2, 0.4)
                    
                    # If no specific feedback, increase all weights slightly
                    if len(company_feedback) == 0 and len(persona_feedback) == 0 and len(ai_feedback) == 0:
                        adjusted_weights['company_fit'] = min(adjusted_weights['company_fit'] * 1.1, 0.6)
                        adjusted_weights['persona_fit'] = min(adjusted_weights['persona_fit'] * 1.1, 0.6)
                        adjusted_weights['ai_intelligence'] = min(adjusted_weights['ai_intelligence'] * 1.1, 0.4)
                else:
                    # More rejected than approved - decrease weights proportionally
                    print(f"   More rejected than approved - decreasing weights")
                    # Decrease all weights slightly, but more for components that had negative feedback
                    if company_feedback.count('negative') > 0:
                        adjusted_weights['company_fit'] = max(adjusted_weights['company_fit'] * 0.8, 0.2)
                    if persona_feedback.count('negative') > 0:
                        adjusted_weights['persona_fit'] = max(adjusted_weights['persona_fit'] * 0.8, 0.2)
                    if ai_feedback.count('negative') > 0:
                        adjusted_weights['ai_intelligence'] = max(adjusted_weights['ai_intelligence'] * 0.8, 0.1)
                    
                    # If no specific feedback, decrease all weights slightly
                    if len(company_feedback) == 0 and len(persona_feedback) == 0 and len(ai_feedback) == 0:
                        adjusted_weights['company_fit'] = max(adjusted_weights['company_fit'] * 0.9, 0.2)
                        adjusted_weights['persona_fit'] = max(adjusted_weights['persona_fit'] * 0.9, 0.2)
                        adjusted_weights['ai_intelligence'] = max(adjusted_weights['ai_intelligence'] * 0.9, 0.1)
            else:
                print(f"   No feedback received - keeping current weights")
            
            # Normalize weights to ensure they sum to 1.0
            total_weight = sum(adjusted_weights.values())
            if total_weight > 0:
                for component in adjusted_weights:
                    adjusted_weights[component] = adjusted_weights[component] / total_weight
            
            print(f"🔄 Updating scoring weights:")
            print(f"   Current: {current_weights}")
            print(f"   Adjusted: {adjusted_weights}")
            
            # Update the scoring weights table
            weight_update_data = ScoringWeightUpdate(
                persona_fit_weight=str(int(adjusted_weights.get('persona_fit') * 100)),
                company_fit_weight=str(int(adjusted_weights.get('company_fit') * 100)),
                sales_data_weight=str(int(adjusted_weights.get('ai_intelligence') * 100))
            )
            update_scoring_weights(weight_update_data, db, current_user)
            
            print(f"✅ Scoring weights updated successfully")
        
        return {"message": f"Calibration session {complete_data.action}d successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete calibration session: {str(e)}")

@router.post("/session/{session_id}/rescore")
async def rescore_calibration_samples(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Re-score calibration samples with current scoring weights (virtual)"""
    try:
        # This is a virtual rescore - we don't store samples in database
        # The frontend should pass the original prospects data for rescoring
        return {"message": "Rescore completed successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rescore calibration samples: {str(e)}")

@router.get("/session/{session_id}", response_model=CalibrationSampleResponse)
async def get_calibration_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get calibration session (virtual - no database storage)"""
    try:
        # Return a virtual session - in practice, the frontend should maintain the session state
        virtual_session = {
            'id': session_id,
            'user_id': str(current_user.id),
            'status': 'active',
            'sample_size': 10,
            'feedback_count': 0,
            'approved_count': 0,
            'rejected_count': 0,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        return CalibrationSampleResponse(
            session=CalibrationSessionRead(**virtual_session),
            samples=[],
            total_samples=0,
            feedback_count=0,
            approved_count=0,
            rejected_count=0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get calibration session: {str(e)}")