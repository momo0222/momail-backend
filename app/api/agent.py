from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.agent import AgentStats
from app.schemas.chat import ChatRequest, ChatResponse
from app.models import Email, Action
from app.services.agent_service import agent
from sqlalchemy import or_
import re

from datetime import datetime, timedelta

from app.services.gmail_client import GmailClient
from typing import List

router = APIRouter()
gmail_client = GmailClient()

@router.get("/stats", response_model=AgentStats)
def get_status(db: Session=Depends(get_db)):
    """Get agent status"""
    running = agent.running
    total_emails = db.query(Email).count()
    processed_emails = db.query(Email).filter(Email.processed).count()
    pending_actions = db.query(Action).filter(Action.status == "pending").count()

    return AgentStats(
        running=running,
        total_emails=total_emails,
        processed_emails=processed_emails,
        pending_actions=pending_actions
    )

@router.post("/chat", response_model=ChatResponse)
def chat_with_agent(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Chat with the agent to search/manage emails using natural language
    
    Examples:
    - "Find emails from John"
    - "Show me urgent emails"
    - "What emails came in today?"
    - "Archive all emails from spam@marketing.com"
    """
    message = request.message.lower()
    
    # Parse the user's intent using OpenAI
    search_params = parse_search_intent(message)
    print("SEARCH PARAMS:", search_params)
    
    # Execute the search
    emails = search_emails_with_params(db, search_params)
    
    # Generate a natural response
    reply = generate_reply(message, emails, search_params)
    
    return ChatResponse(
        reply=reply,
        emails=[email_to_dict(e) for e in emails[:10]],  # Return max 10
    )

def parse_search_intent(message: str) -> dict:
    """
    Use OpenAI to extract search parameters from natural language
    """
    from openai import OpenAI
    import json
    
    client = OpenAI()
    
    prompt = f"""
You are an email search assistant. Parse this user request into search parameters.

User request: "{message}"

Extract:
- sender: email address or name mentioned
- classification: urgent, routine, spam, personal
- time_range: today, yesterday, last_week, last_month
- query: any keywords to search in subject/body
- action: search, archive, delete, mark_read (if user wants to do something)

Return ONLY valid JSON with these fields (use null if not mentioned):
{{"sender": null, "classification": null, "time_range": null, "query": null, "action": "search"}}
"""
    
    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )
    
     # ✅ Extract text from the response
    text = response.output_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"```$", "", text.strip())
        text = text.strip()


    # ✅ Parse JSON safely
    try:
        parsed = json.loads(text)
        return parsed
    except json.JSONDecodeError:
        print("⚠️ Failed to parse JSON from LLM:")
        print(text)

        # Fallback: return safe defaults
        return {
            "sender": None,
            "classification": None,
            "time_range": None,
            "query": None,
            "action": "search",
        }

def search_emails_with_params(db: Session, params: dict) -> List[Email]:
    """
    Search emails based on parsed parameters
    """
    query = db.query(Email)
    
    # Filter by sender
    if params.get('sender'):
        query = query.filter(Email.from_address.ilike(f"%{params['sender']}%"))
    
    # Filter by classification
    if params.get('classification'):
        query = query.filter(Email.classification == params['classification'])
    
    # Filter by time range
    if params.get('time_range'):
        now = datetime.now()
        if params['time_range'] == 'today':
            start = now.replace(hour=0, minute=0, second=0)
            query = query.filter(Email.created_at >= start)
        elif params['time_range'] == 'yesterday':
            start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0)
            end = now.replace(hour=0, minute=0, second=0)
            query = query.filter(Email.created_at >= start, Email.created_at < end)
        elif params['time_range'] == 'last_week':
            start = now - timedelta(days=7)
            query = query.filter(Email.created_at >= start)
        elif params['time_range'] == 'last_month':
            start = now - timedelta(days=30)
            query = query.filter(Email.created_at >= start)
    
    # Search by keywords
    if params.get('query'):
        query = query.filter(or_(
            Email.subject.ilike(f"%{params['query']}%"),
            Email.body.ilike(f"%{params['query']}%")
        ))
    
    return query.order_by(Email.created_at.desc()).limit(50).all()

def generate_reply(message: str, emails: List[Email], params: dict) -> str:
    """
    Generate a natural language response
    """
    count = len(emails)
    
    if count == 0:
        return f"I couldn't find any emails matching '{message}'. Try a different search?"
    
    # Build context about what was found
    filters_used = []
    if params.get('sender'):
        filters_used.append(f"from {params['sender']}")
    if params.get('classification'):
        filters_used.append(f"classified as {params['classification']}")
    if params.get('time_range'):
        filters_used.append(f"from {params['time_range']}")
    
    filters_text = " ".join(filters_used) if filters_used else "matching your search"
    
    return f"I found {count} email{'s' if count != 1 else ''} {filters_text}. Showing the most recent ones below."

def email_to_dict(email: Email) -> dict:
    """Convert Email model to dict for response"""
    return {
        "id": email.id,
        "from_address": email.from_address,
        "subject": email.subject,
        "snippet": email.snippet,
        "classification": email.classification,
        "created_at": email.created_at.isoformat(),
        "processed": email.processed
    }






