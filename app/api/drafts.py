from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from app.schemas.draft import DraftCreate, DraftUpdate, DraftResponse

from app.database import get_db
from app.models.draft import Draft
from app.services.storage import storage_service

router = APIRouter()

@router.get("/", response_model=List[DraftResponse])
def list_drafts(db: Session = Depends(get_db)):
    """Get all drafts"""
    drafts = db.query(Draft).order_by(Draft.updated_at.desc()).all()
    return drafts

@router.post("/", response_model=DraftResponse)
def create_draft(draft: DraftCreate, db: Session = Depends(get_db)):
    """Create new draft"""
    new_draft = Draft(
        to=draft.to,
        subject=draft.subject,
        body=draft.body,
        attachments = []
    )
    db.add(new_draft)
    db.commit()
    db.refresh(new_draft)
    return new_draft

@router.get("/{draft_id}", response_model=DraftResponse)
def get_draft(draft_id: int, db: Session = Depends(get_db)):
    """Get a specific draft"""
    draft = db.query(Draft).filter(Draft.id == draft_id).filter().first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft

@router.put("/{draft_id}", response_model=DraftResponse)
def update_draft(
    draft_id: int,
    draft_update: DraftUpdate,
    db: Session = Depends(get_db)
):
    """Update a draft (auto-save)"""
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft.to = draft_update.to #type: ignore
    draft.body = draft_update.body #type: ignore
    draft.subject = draft_update.subject #type: ignore
    db.commit()
    db.refresh(draft)
    return draft

@router.post("/{draft_id}/attachments")
async def upload_attachment(
    draft_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a temporary draft attachment"""
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    file_info = await storage_service.save_draft_attachment(draft_id=draft_id, file=file)

    attachments = draft.attachments or [] 
    attachments.append(file_info)
    draft.attachments = attachments #type: ignore

    db.commit()
    db.refresh(draft)

    return file_info

@router.delete("/{draft_id}/attachments/{filename}")
def remove_draft_attachment(
    draft_id: int,
    filename: str,
    db: Session = Depends(get_db)
):
    """Remove attachment from draft"""
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    attachments = [a for a in (draft.attachments or []) if a["filename"] != filename]#type: ignore
    draft.attachments = attachments #type: ignore
    
    db.commit()

    return {
        "message": "Attachments removed"
    }

@router.delete("/{draft_id}")
def delete_draft(draft_id: int, db: Session = Depends(get_db)):
    """Delete a draft"""
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    storage_service.delete_draft_files(draft_id)
    
    db.delete(draft)
    db.commit()
    return {"message": "Draft deleted"}