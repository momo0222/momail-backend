from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database import get_db
from app.models.user_file import UserFile
from app.services.storage import storage_service
from datetime import datetime

router = APIRouter()

class UserFileResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    filepath: str
    size: int
    file_type: str
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("/", response_model=List[UserFileResponse])
def list_user_files(db: Session=Depends(get_db)):
    """List all persistent user files"""
    user_id = 1 #TODO: get from auth
    files = db.query(UserFile).filter(UserFile.user_id == user_id).all()
    return files

@router.post("/", response_model=UserFileResponse)
async def upload_user_file(
    file: UploadFile = File(...),
    file_type: str = "document",
    db: Session = Depends(get_db)
):
    """Upload a persistent user file (resume, template, etc.)"""
    user_id = 1 #TODO: get from auth

    # save file to storage
    file_info = await storage_service.save_user_file(user_id=user_id, file=file)

    user_file = UserFile(
        user_id = user_id,
        filename = file_info["filename"],
        original_filename = file_info["original_filename"],
        filepath = file_info["filepath"],
        size = file_info["size"],
        file_type = file_type
    )

    db.add(user_file)
    db.commit()
    db.refresh(user_file)

    return user_file

@router.delete("/{file_id}")
def delete_user_file(file_id: int, db: Session = Depends(get_db)):
    """Delete a persistent user file"""
    user_id = 1 #TODO: get from auth
    
    user_file = db.query(UserFile).filter(
        UserFile.id == file_id,
        UserFile.user_id == user_id
    ).first()

    if not user_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    #Delete from storage
    storage_service.delete_file(user_file.filepath) #type: ignore

    #delete from db
    db.delete(user_file)
    db.commit()

    return {"message": "File deleted"}

@router.get("/{file_id}/content")
def get_file_content(file_id: int, db: Session = Depends(get_db)):
    """Get file content"""
    user_id = 1 #TODO: get from auth

    user_file = db.query(UserFile).filter(
        UserFile.id == file_id,
        UserFile.user_id == user_id
    ).first()

    if not user_file:
        raise HTTPException(status_code=404, detail="File not found")

    file_content = storage_service.get_file_content(filepath=user_file.filepath)#type: ignore
    if not file_content:
        raise HTTPException(status_code=500, detail="Failed to read file")

    try:
        text_content = file_content.decode("utf-8")
    except:
        text_content = f"[Binary filen: {user_file.filename}]"

    return {
        "filename": user_file.original_filename,
        "content": text_content,
        "size": user_file.size
    }
