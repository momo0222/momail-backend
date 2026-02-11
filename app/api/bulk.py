from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models import Email, Action
from app.services.gmail_provider import get_gmail_client
from app.schemas.bulk import (
    MarkReadRequest,
    BulkDeleteRequest,
    BulkDeleteSenderRequest,
    ArchiveSenderRequest,
    ExecutePendingRequest
)

router = APIRouter()

gmail_client = get_gmail_client()

@router.post("/emails/mark-read")
def mark_emails_as_read(
    request: MarkReadRequest,
    db: Session = Depends(get_db)
):
    """
    Mark multiple emails as read.

    Request Body:
    {
        "email_ids": ["email1", "email2]
        "execute_in_gmail": true
    }
    """
    if request.execute_in_gmail:
        # Actually mark as read in Gmail
        marked = 0
        failed = []

        for email_id in request.email_ids:
            try:
                gmail_client.mark_as_read(email_id)
                marked += 1
            except Exception as e:
                failed.append({"email_id": email_id, "error": str(e)})
        
        # Update DB
        db.query(Email).filter(Email.id.in_(request.email_ids)).update(
            {"processed": True},
            synchronize_session=False
        )

        db.commit()
        return {
            "message": f"Marked {marked} emails as read in Gmail",
            "marked": marked,
            "failed": len(failed),
            "failures": failed
        }
    else:
        # Update DB only 
        updated = db.query(Email).filter(Email.id.in_(request.email_ids)).update(
            {"processed": True},
            synchronize_session=False
        )

        db.commit()
        return {"message": f"Marked {updated} emails as processed in database only"}

@router.post("/emails/bulk-delete")
def bulk_delete_emails(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db)
):
    """
    Delete multiple emails

    Request Body:
    {
        "emails_ids": ["email1", "email2"],
        "delete_from_gmail": false
    }
    """
    if request.delete_from_gmail:
        deleted = 0
        failed = []

        for email_id in request.email_ids:
            try:
                gmail_client.service.users().messages().trash(
                    userId='me',
                    id=email_id
                ).execute()
                deleted += 1
            except Exception as e:
                failed.append({"email_id": email_id, "error": str(e)})

        # Remove from DB
        db.query(Action).filter(Action.email_id.in_(request.email_ids)).delete(synchronize_session=False)
        db.query(Email).filter(Email.id.in_(request.email_ids)).delete(synchronize_session=False)
        db.commit()

        return {
            "message": f"Deleted {deleted} emails from Gmail and database",
            "deleted": deleted,
            "failed": len(failed),
            "failures": failed
        }
    else:
        # Delete from DB only
        db.query(Action).filter(Action.email_id.in_(request.email_ids)).delete(synchronize_session=False)
        deleted = db.query(Email).filter(Email.id.in_(request.email_ids)).delete(synchronize_session=False)
        db.commit()
        return {"message": f"Deleted {deleted} emails from database only"}

@router.post("/emails/bulk-archive-sender")
def bulk_archive_sender(
    request: ArchiveSenderRequest,
    db: Session = Depends(get_db)
):
    """
    Archive all emails from a specific sender.

    Request Body:
        {
            "sender": "person@gmail.com",
            "execute_in_gmail": false
        }
    """
    emails = db.query(Email).filter(Email.from_address == request.sender).all()

    if not emails:
        return {
            "message": f"No emails found from sender {request.sender}",
            "archived": 0
        }

    if request.execute_in_gmail:
        # Execute in Gmail
        archived = 0
        failed = []
        
        for email in emails:
            try:
                gmail_client.archive(email.id)#type: ignore
                archived += 1
                # mark as processed in DB
                email.processed = True #type: ignore
                
                action = Action(
                    email_id=email.id,
                    action_type="archive",
                    status="executed",
                    reason=f"Bulk archived sender {request.sender}"
                )
                db.add(action)

            except Exception as e:
                failed.append({"email_id": email.id, "error": str(e)})

        db.commit()

        return {
            "message": f"Archived {archived} emails from {request.sender} in Gmail",
            "archived": archived,
            "failed": len(failed),
            "failures": failed
        }
    
    else:
        # Update DB only
        for email in emails:
            email.processed = True #type: ignore

            action = Action(
                email_id=email.id,
                action_type="archive",
                status="pending",
                reason=f"Bulk archived sender {request.sender}"
            )
            db.add(action)

        db.commit()

        return {
            "message": f"Archived {len(emails)} emails from {request.sender} in database only",
            "archived": len(emails)
        }

@router.post("/actions/execute-pending")
def execute_pending_actions(
    request: ExecutePendingRequest,
    db: Session = Depends(get_db)
):
    """
    Execute pending actions in bulk.

    Request Body:
    {
        "action_type": "reply"  # optional, if provided only execute this type
    }
    """
    query = db.query(Action).filter(Action.status == "approved")
    if request.action_type:
        query = query.filter(Action.action_type == request.action_type)
    
    actions = query.all()

    if not actions:
        return {"message": "No pending actions to execute", "executed": 0}

    executed = 0
    failed = []

    for action in actions:
        try:
            # Here we would have logic to execute the action, e.g., send reply, archive email, etc.

            email = db.query(Email).filter(Email.id == action.email_id).first()

            if action.action_type == "reply": # type: ignore
                gmail_client.send_email( 
                    to=email.from_address,  #type: ignore
                    subject=f"Re: {email.subject}", #type: ignore
                    body=action.suggested_reply, #type: ignore
                    thread_id=email.thread_id #type: ignore
                )
                action.actual_reply = action.suggested_reply # type: ignore
            elif action.action_type == "archive": # type: ignore
                # Archive the email in Gmail
                gmail_client.service.users().messages().modify(
                    userId='me',
                    id=email.id,  # type: ignore
                    body={'removeLabelIds': ['INBOX']}
                ).execute()

            action.status = "executed" # type: ignore
            email.processed = True # type: ignore
            executed += 1

        except Exception as e:
            failed.append({
                "action_id": action.id,
                "email_id": action.email_id,
                "error": str(e)
            })
            action.status = "failed" # type: ignore

    db.commit()

    return {
        "message": f"Executed {executed} pending actions",
        "executed": executed,
        "failed": len(failed),
        "failures": failed
    }

@router.get("/stats/by-sender")
def get_stats_by_sender(db: Session = Depends(get_db)):
    """
    Get email statistics grouped by sender.
    """
    from sqlalchemy import func

    results = (
        db.query(
            Email.from_address,
            func.count(Email.id).label("count"),
            Email.classification
        ).group_by(Email.from_address, Email.classification)
        .order_by(func.count(Email.id).desc())
        .limit(20)
        .all()
    )

    return [
        {
            "sender": r[0],
            "count": r[1],
            "classification": r[2]
        }
        for r in results
    ]

@router.post("/emails/bulk-delete-sender")
def bulk_delete_sender(
    request: BulkDeleteSenderRequest,
    db: Session = Depends(get_db)
):
    """
    Bulk delete all emails from a specific sender.

    Request Body:
        {
            "sender": "spam@marketing.com",
            "delete_from_gmail": false
        }
     """
    emails = db.query(Email).filter(Email.from_address==request.sender).all()

    if not emails:
        return {"message": "No emails found from this sender", "count": 0}
    
    email_ids = [e.id for e in emails]

    if request.delete_from_gmail:
        deleted = 0
        failed = []

        for email_id in email_ids:
            try:
                gmail_client.service.users().messages().trash(
                    userId='me',
                    id=email_id
                ).execute()
                deleted += 1
            except Exception as e:
                failed.append({"email_id": email_id, "error": str(e)})
        
        # Delete from database
        db.query(Action).filter(Action.email_id.in_(email_ids)).delete(synchronize_session=False)
        db_deleted = db.query(Email).filter(Email.id.in_(email_ids)).delete(synchronize_session=False)
        db.commit()
    
        return {
            "message": f"Deleted {deleted} emails from {request.sender} in Gmail",
            "sender": request.sender,
            "deleted_gmail": deleted,
            "deleted_db": db_deleted,
            "failed": len(failed),
            "failures": failed
        }
    else:
        # Just delete from database
        db.query(Action).filter(Action.email_id.in_(email_ids)).delete(synchronize_session=False)
        deleted = db.query(Email).filter(Email.id.in_(email_ids)).delete(synchronize_session=False)
        db.commit()
        
        return {
            "message": f"Deleted {deleted} emails from {request.sender} in database only",
            "sender": request.sender,
            "deleted": deleted,
            "note": "Emails still exist in Gmail. Set delete_from_gmail=true to move to trash."
        }