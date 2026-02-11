from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.schemas.dashboard import DashboardStats, Totals, RecentActivity, TopSender
from app.models import Email, Action
from app.services.agent_service import agent
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session=Depends(get_db)):
    """Stats for dashboard"""
    total_emails = db.query(Email).count()
    processed_emails = db.query(Email).filter(Email.processed).count()
    pending_actions = db.query(Action).filter(Action.status == "pending").count()
    unprocessed = total_emails - processed_emails

    totals = Totals(
        emails=total_emails,
        processed=processed_emails,
        pending_actions=pending_actions,
        unprocessed=unprocessed
    )

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    last_7_days = db.query(Email).filter(Email.created_at >= seven_days_ago).count()

    recent_activity = RecentActivity(
        last_7_days=last_7_days
    )

    classification_rows = (
        db.query(
            Email.classification,
            func.count(Email.id)
        )
        .filter(Email.classification.isnot(None))
        .group_by(Email.classification)
        .all()
    )
    classification = {
        classification: count for classification, count in classification_rows
    }

    action_types_rows = (
        db.query(
            Action.action_type,
            func.count(Action.id)
        )
        .group_by(Action.action_type)
        .all()
    )
    action_types = {
        action_type: count for action_type, count in action_types_rows
    }

    top_sender_rows = (
        db.query(
            Email.from_address,
            func.count(Email.id).label("count")
        ).group_by(Email.from_address)
        .order_by(func.count(Email.id).desc())
        .limit(5)
        .all()
    )

    top_senders = [
        TopSender(
            email=email,
            count=count
        ) for email, count in top_sender_rows
    ]

    return DashboardStats(
        totals=totals,
        classification=classification,
        action_types=action_types,
        recent_activity=recent_activity,
        top_senders=top_senders
    )