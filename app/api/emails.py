from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, and_
from typing import List, Optional

from app.database import get_db
from app.models.email import Email
from app.models.draft import Draft
from app.schemas.email import EmailResponse, EmailCreate, SendReplyRequest, ComposeEmailRequest, AttachmentInfo
from app.services.gmail_provider import get_gmail_client
from app.services.storage import storage_service
import re


router = APIRouter()
def get_client():
    return get_gmail_client()

@router.get("/", response_model=List[EmailResponse])
def list_emails(
    skip: int = 0, 
    limit: int = 100, 
    classification: Optional[str] = None,
    processed: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    List emails with optional filters

    - **skip**: Number of records to skip for pagination
    - **limit**: Maximum number of records to return
    - **classification**: Filter by email classification(urgent, spam, routine, personal)
    - **processed**: Filter by whether the email has been processed
    """
    query = db.query(Email)

    if classification:
        query = query.filter(Email.classification == classification)
    
    if processed is not None:
        query = query.filter(Email.processed == processed)

    query = query.order_by(Email.created_at.desc())
    emails = query.offset(skip).limit(limit).all()

    return emails

@router.get("/threads")
def list_threads(
    classification: Optional[str] = None,
    processed: Optional[bool] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List emails grouped by thread
    Returns one email per thread with thread count
    """

    # Subquery to get the latest email per thread
    latest_email_subq = (
        db.query(
            Email.thread_id,
            func.max(Email.created_at).label('latest_created_at')
        )
        .group_by(Email.thread_id)
        .subquery()
    )
    
    # Get full email details for latest in each thread
    query = (
        db.query(Email)
        .join(
            latest_email_subq,
            and_(
                Email.thread_id == latest_email_subq.c.thread_id,
                Email.created_at == latest_email_subq.c.latest_created_at
            )
        )
    )
    # Apply filters
    if classification:
        query = query.filter(Email.classification == classification)
    
    if processed is not None:
        query = query.filter(Email.processed == processed)
    
    # Get threads ordered by most recent
    threads = query.order_by(Email.created_at.desc()).limit(limit).all()
    
    # Build response with thread counts
    result = []
    for email in threads:
        # Count emails in this thread
        thread_count = db.query(Email).filter(Email.thread_id == email.thread_id).count()
        
        # Check if thread has any unread
        has_unread = db.query(Email).filter(
            Email.thread_id == email.thread_id,
            Email.processed == False
        ).count() > 0
        
        result.append({
            "id": email.id,
            "thread_id": email.thread_id,
            "from_address": email.from_address,
            "to_address": email.to_address,
            "subject": email.subject,
            "snippet": email.snippet,
            "body": email.body,
            "classification": email.classification,
            "processed": email.processed,
            "created_at": email.created_at.isoformat(),
            "thread_count": thread_count,
            "has_unread": has_unread
        })
    return result

@router.get("/threads/{thread_id}")
def get_thread_emails(thread_id: str, db: Session = Depends(get_db), gmail_client=Depends(get_client)):
    """
    Get all emails in a specific thread, ordered chronologically
    """
    emails = (
        db.query(Email)
        .filter(Email.thread_id == thread_id)
        .order_by(Email.created_at.asc())
        .all()
    )

    if not emails:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    for email in emails:
        print(f"Email: {email}")
        email.processed = True #type:ignore
    db.commit()
    try:
        gmail_client.mark_as_read(emails[-1].id)
    except Exception:
        pass

    return [
        {
            "id": email.id,
            "thread_id": email.thread_id,
            "from_address": email.from_address,
            "to_address": email.to_address,
            "subject": email.subject,
            "snippet": email.snippet,
            "body": email.body,
            "classification": email.classification,
            "processed": email.processed,
            "created_at": email.created_at.isoformat(),
        }
        for email in emails
    ]

@router.get("/search/threads", response_model=List[EmailResponse])
def search_threads(
    query: str="",
    sender: Optional[str]=None,
    classification: Optional[str]=None,
    processed: Optional[bool]=None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Search emails with threads with multiple filters

    - **query** Search in subject and body
    - **sender** Filter by sender email
    - **classification** Filter by classification
    - **processed** Filter by processing status
    """

    q = db.query(Email)

    if query:
        filter_clause = or_(
            Email.subject.ilike(f'%{query}%'),
            Email.body.ilike(f'%{query}%')
        )
        q = q.filter(filter_clause)

    if sender:
        q = q.filter(Email.from_address.ilike(f"%{sender}%"))
    
    if classification:
        q = q.filter(Email.classification == classification)
    
    if processed is not None:
        q = q.filter(Email.processed == processed)


    # Subquery to get the latest email per thread
    latest_per_thread_subq = (
        
        q.with_entities(
        Email.thread_id,
        func.max(Email.created_at).label('latest_created_at')
        )
        .group_by(Email.thread_id)
        .subquery()
    )
    threads_q = (
        db.query(Email)
        .join(
            latest_per_thread_subq,
            and_(
                Email.thread_id == latest_per_thread_subq.c.thread_id,
                Email.created_at == latest_per_thread_subq.c.latest_created_at,
            ),
        )
        .order_by(Email.created_at.desc())
        .limit(limit)
    )
    threads = threads_q.all()
    # Get full email details for latest in each thread
     # Build response with thread counts
    result = []
    for email in threads:
        # Count emails in this thread
        thread_count = db.query(Email).filter(Email.thread_id == email.thread_id).count()
        
        # Check if thread has any unread
        has_unread = db.query(Email).filter(
            Email.thread_id == email.thread_id,
            Email.processed == False
        ).count() > 0
        
        result.append({
            "id": email.id,
            "thread_id": email.thread_id,
            "from_address": email.from_address,
            "to_address": email.to_address,
            "subject": email.subject,
            "snippet": email.snippet,
            "body": email.body,
            "classification": email.classification,
            "processed": email.processed,
            "created_at": email.created_at.isoformat(),
            "thread_count": thread_count,
            "has_unread": has_unread
        })
    return result
    

@router.get("/search", response_model=List[EmailResponse])
def search_emails(
    query: str="",
    sender: Optional[str]=None,
    classification: Optional[str]=None,
    processed: Optional[bool]=None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Search emails with multiple filters

    - **query** Search in subject and body
    - **sender** Filter by sender email
    - **classification** Filter by classification
    - **processed** Filter by processing status
    """

    q = db.query(Email)

    if query:
        filter_clause = or_(
            Email.subject.ilike(f'%{query}%'),
            Email.body.ilike(f'%{query}%')
        )
        q = q.filter(filter_clause)

    if sender:
        q = q.filter(Email.from_address.ilike(f"%{sender}%"))
    
    if classification:
        q = q.filter(Email.classification == classification)
    
    if processed is not None:
        q = q.filter(Email.processed == processed)
    
    # Order by newest first
    emails = q.order_by(Email.created_at.desc()).limit(limit).all()
    return emails

@router.get("/{email_id}", response_model=EmailResponse)
def get_email(email_id: str, db: Session = Depends(get_db)):
    """Get a specific email by ID"""
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return email

@router.post("/", response_model=EmailResponse)
def create_email(email: EmailCreate, db: Session = Depends(get_db)):
    """Create a new email record"""
    db_email = Email(**email.model_dump())
    db.add(db_email)
    db.commit()
    db.refresh(db_email)
    return db_email

@router.get("/unprocessed/count")
def count_unprocessed(db: Session = Depends(get_db)):
    """Count unprocessed emails"""
    count = db.query(Email).filter(Email.processed == False).count()
    return {"count": count}

@router.post("/send-new")
def send_new(
    request: ComposeEmailRequest,
    db: Session = Depends(get_db),
    gmail_client=Depends(get_client)
):
    
    attachment_data = [
        (att.filepath, att.original_filename)
        for att in request.attachments
    ]
    sent_message = gmail_client.send_email_with_attachments(
        to=request.to_address,
        subject=request.subject,
        body=request.body,
        attachment_data=attachment_data,
    )

    if request.draft_id:
        storage_service.delete_draft_files(draft_id=request.draft_id)

        draft = db.query(Draft).filter(Draft.id == request.draft_id).first()
        if draft:
            db.delete(draft)
            db.commit()
    # Save sent email to database
    sent_email_id = sent_message.get('id') if sent_message else None

    if sent_email_id:
        from_address = gmail_client.from_address
        
        sent_email = Email(
            id=sent_email_id,
            thread_id=sent_message.get('threadId'),
            from_address=from_address,
            to_address=request.to_address,
            subject=request.subject,
            body=request.body,
            snippet=request.body[:200],
            classification="sent",
            processed=True,
        )
        db.add(sent_email)
        db.commit()
    return {"message": "Email sent successfully", "email_id": sent_email_id}

@router.post("/send-reply")
def send_reply(
    request: SendReplyRequest,
    db: Session = Depends(get_db),
    gmail_client=Depends(get_client)
):
    """Send a reply to an email"""
    email = db.query(Email).filter(Email.id == request.email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    subject = email.subject or ""
    # Remove all "Re: " prefixes (case insensitive)
    subject = re.sub(r'^(re:\s*)+', '', subject, flags=re.IGNORECASE).strip() #type:ignore
    # Add single "Re:" prefix
    reply_subject = f"Re: {subject}"
    # Send the email
    sent_message = gmail_client.send_email(
        to=email.from_address,#type: ignore
        subject=f"Re: {reply_subject}",
        body=request.reply_text,
        thread_id=email.thread_id #type: ignore
    )

    # Save sent email to database
    sent_email_id = sent_message.get('id') if sent_message else None
    if sent_email_id:
        sent_email = Email(
            id=sent_email_id,
            thread_id=email.thread_id,
            from_address=email.to_address,
            to_address=email.from_address,
            subject=f"Re: {email.subject}",
            body=request.reply_text,
            snippet=request.reply_text[:200],
            classification="sent",
            processed=True,
        )
        db.add(sent_email)
    email.processed = True #type: ignore
    db.commit()

    return {"message": "reply sent successfully", "email_id": sent_email_id}
