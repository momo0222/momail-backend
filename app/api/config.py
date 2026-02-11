from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentConfig
from app.schemas.config import AgentConfigResponse, AgentConfigUpdate, AddEmails


router = APIRouter()

def get_or_create_config(db: Session) -> AgentConfig:
    """Get config or create config if it doesn't exist"""
    config = db.query(AgentConfig).filter(AgentConfig.id == 1).first()
    if not config:
        config = AgentConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config

@router.get("/", response_model=AgentConfigResponse)
def get_config(db: Session = Depends(get_db)):
    """Get the agent configuration"""
    config = get_or_create_config(db)

    response = AgentConfigResponse(
        id=config.id, # type: ignore
        auto_reply_whitelist=config.auto_reply_whitelist,# type: ignore
        auto_reply_blacklist=config.auto_reply_blacklist,# type: ignore
        check_interval=config.check_interval,# type: ignore
        dry_run_mode=config.dry_run_mode,# type: ignore
        enable_auto_reply=config.enable_auto_reply,# type: ignore
        enable_spam_filter=config.enable_spam_filter,# type: ignore
        enable_learning=config.enable_learning,# type: ignore
        whitelist_parsed=config.get_whitelist(),
        blacklist_parsed=config.get_blacklist(),
    )
    return response

@router.patch("/")
def update_config(
    config_update: AgentConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update agent configuration"""
    config = get_or_create_config(db)

    update_data = config_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)
    
    db.commit()
    db.refresh(config)

    return {
        "message": "Configuration updated successfully.",
        "whitelist": config.get_whitelist(),
        "blacklist": config.get_blacklist()
        }

@router.post("/whitelist/add")
def add_to_whitelist(data: AddEmails, db: Session = Depends(get_db)):
    """Add an email/domain to the auto-reply whitelist"""
    config = get_or_create_config(db)

    whitelist = config.get_whitelist()
    added = []
    
    for email in data.emails:
        email_clean = email.strip().lower()
        if email_clean not in whitelist:
            whitelist.append(email_clean)
            added.append(email_clean)

    config.auto_reply_whitelist = ",".join(whitelist) # type: ignore
    db.commit()
    db.refresh(config)
    return {
        "message": f"Added {len(added)} email(s) to whitelist",
        "added": added,
        "whitelist": whitelist
    }

@router.post("/blacklist/add")
def add_to_blacklist(data: AddEmails, db: Session = Depends(get_db)):
    """Add an email/domain to the auto-reply blacklist"""
    config = get_or_create_config(db)

    blacklist = config.get_blacklist()
    added = []
    
    for email in data.emails:
        email_clean = email.strip().lower()
        if email_clean not in blacklist:
            blacklist.append(email_clean)
            added.append(email_clean)

    config.auto_reply_blacklist = ",".join(blacklist) # type: ignore
    db.commit()
    db.refresh(config)
    return {
        "message": f"Added {len(added)} email(s) to blacklist",
        "added": added,
        "blacklist": blacklist
    }

@router.delete("/whitelist/{email}")
def remove_from_whitelist(email: str, db: Session = Depends(get_db)):
    """Remove email/domain from whitelist"""
    config = get_or_create_config(db)

    whitelist = config.get_whitelist()
    email = email.strip().lower()
    if email in whitelist:
        whitelist.remove(email)
        config.auto_reply_whitelist = ",".join(whitelist) # type: ignore
        db.commit()
        db.refresh(config)
    return {"message": f"{email} removed from whitelist.", "whitelist": whitelist}

@router.delete("/blacklist/{email}")
def remove_from_blacklist(email: str, db: Session = Depends(get_db)):
    """Remove email/domain from blacklist"""
    config = get_or_create_config(db)

    blacklist = config.get_blacklist()
    email = email.strip().lower()
    if email in blacklist:
        blacklist.remove(email)
        config.auto_reply_blacklist = ",".join(blacklist) # type: ignore
        db.commit()
        db.refresh(config)
    return {"message": f"{email} removed from blacklist.", "blacklist": blacklist}