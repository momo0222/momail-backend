from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import get_db
from app.models.action import Action
from app.models.email import Email
from app.schemas.action import ActionResponse, ActionCreate, ActionApprove, GenerateReplyRequest, GenerateReplyResponse
from app.services.gmail_client import GmailClient

router = APIRouter()
gmail_client = GmailClient()

@router.get("/pending", response_model=List[ActionResponse])
def get_pending_actions(db: Session = Depends(get_db)):
    """Get all pending actions awaiting user approval"""
    actions = (
        db.query(Action)
        .filter(Action.status == "pending")
        .order_by(Action.created_at.asc())
        .all()
    )
    return actions

@router.get("/{action_id}", response_model=ActionResponse)
def get_action(action_id: int, db: Session = Depends(get_db)):
    """Get a specific action by ID"""
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action

@router.post("/", response_model=ActionResponse)
def create_action(action: ActionCreate, db: Session = Depends(get_db)):
    """Create a new action"""
    db_action = Action(**action.model_dump())
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    return db_action

@router.post("/{action_id}/approve", response_model=ActionResponse)
def approve_action(
    action_id: int, 
    approval: ActionApprove, 
    db: Session = Depends(get_db)
):
    """
    Approve or reject a pending action

    If approved and edited_reply provided, uses that instead of suggested_reply
    """
    action = db.query(Action).filter(Action.id == action_id).first()

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
     # Prevent re-executing already completed actions
    if action.status in ["executed", "approved"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Action already {action.status}. Cannot execute again."
        )
    
    # Prevent re-rejecting
    if action.status == "rejected":#type: ignore
        raise HTTPException(
            status_code=400,
            detail="Action already rejected. Cannot change status."
        )
    
    # Only pending actions can be approved
    if action.status != "pending":#type: ignore
        raise HTTPException(
            status_code=400,
            detail=f"Action has status '{action.status}'. Only pending actions can be approved."
        )
    
    if not approval.approved:
        action.status = "rejected"  # type: ignore
        db.commit()
        db.refresh(action)
        return action
    
    if approval.approved:
        action.status = "approved"#type: ignore
        if approval.edited_reply:
            action.actual_reply = approval.edited_reply#type: ignore
        email = db.query(Email).filter(Email.id == action.email_id).first()
    
        subject = email.subject or "" #type: ignore
        # Remove all "Re: " prefixes (case insensitive)
        import re
        subject = re.sub(r'^(re:\s*)+', '', subject, 0, re.IGNORECASE).strip() #type:ignore


        # Add single "Re:" prefix
        reply_subject = f"Re: {subject}"
        if action.action_type == "reply": # type: ignore
            sent_message = gmail_client.send_email( 
                to=email.from_address,  #type: ignore
                subject=f"Re: {email.subject}", #type: ignore
                body=action.suggested_reply, #type: ignore
                thread_id=email.thread_id #type: ignore
            )
            action.actual_reply = action.suggested_reply # type: ignore
            sent_email_id = sent_message.get('id') if sent_message else None
        
            if sent_email_id:
                # ✅ Persist sent email into DB with Gmail ID
                sent_email = Email(
                    id=sent_email_id,  # ← Add this!
                    thread_id=email.thread_id,#type: ignore
                    from_address=email.to_address,#type: ignore
                    to_address=email.from_address,#type: ignore
                    subject=f"Re: {email.subject}",#type: ignore
                    body=approval.edited_reply or action.suggested_reply,
                    snippet=(approval.edited_reply or action.suggested_reply)[:200],
                    classification="sent",
                    processed=True,
                )
            db.add(sent_email)
           
        elif action.action_type == "archive": # type: ignore
            # Archive the email in Gmail
            gmail_client.service.users().messages().modify(
                userId='me',
                id=email.id,  # type: ignore
                body={'removeLabelIds': ['INBOX']}
            ).execute()

           
        email.processed = True # type: ignore
          
        # TODO: Actually execute the action (send email, etc.)
        # For now, just mark as executed
        action.status = "executed"#type: ignore
        action.processed_at = datetime.now() #type: ignore
    else:
        action.status = "rejected" #type: ignore
    db.commit()
    db.refresh(action)
    return action

@router.delete("/{action_id}")
def delete_action(action_id: int, db: Session = Depends(get_db)):
    """Delete an action by ID"""
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    db.delete(action)
    db.commit()
    return {"detail": "Action deleted"}

@router.get("/stats/summary")
def get_stats(db: Session = Depends(get_db)):
    """Get action statistics"""
    total = db.query(Action).count()
    pending = db.query(Action).filter(Action.status == "pending").count()
    approved = db.query(Action).filter(Action.status == "approved").count()
    executed = db.query(Action).filter(Action.status == "executed").count()
    rejected = db.query(Action).filter(Action.status == "rejected").count()
    
    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "executed": executed,
        "rejected": rejected
    }

@router.post("/admin/fix-senders")
def fix_senders(db: Session = Depends(get_db)):
    from email.utils import parseaddr

    emails = db.query(Email).all()
    updated = 0

    for e in emails:
        _, addr = parseaddr(e.from_address or "") #type: ignore
        if addr and e.from_address != addr:#type: ignore
            e.from_address = addr.lower().strip()#type: ignore
            updated += 1

    db.commit()
    return {"updated": updated}

@router.post("/generate-reply", response_model=GenerateReplyResponse)
def generate_request(
    request: GenerateReplyRequest,
    db: Session = Depends(get_db)
):
    """
    Generate an AI reply for an email on demand

    Tone options: professional, casual, friendly, brief
    """

    email = db.query(Email).filter(Email.id == request.email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    parsed_email = {
        "from": email.from_address,
        "to": email.to_address,
        "subject": email.subject,
        "body": email.body or email.snippet,
        "tone": request.tone
    }

    if request.custom_instructions:
        parsed_email["instructions"] = request.custom_instructions

    suggested_reply = gmail_client.generate_smart_reply(parsed_email=parsed_email)

    return GenerateReplyResponse(
        suggested_reply=suggested_reply,
        email_id=email.id #type: ignore
    )