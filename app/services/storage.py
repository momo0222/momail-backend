import os
import uuid
import shutil
from typing import Optional, List
from pathlib import Path
from fastapi import UploadFile

class StorageService:
    """
    File storage abstraction layer
    - local system for dev
    """

    def __init__(self, base_path: str="uploads"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)

        #create subdirectories
        self.user_files_path = self.base_path / "user-files"
        self.draft_attachments_path = self.base_path / "drafts"

        self.user_files_path.mkdir(exist_ok=True)
        self.draft_attachments_path.mkdir(exist_ok=True)

    def get_user_files_path(self, user_id: int) -> Path:
        """Get user's personal files directory"""
        user_dir = self.user_files_path / str(user_id)
        user_dir.mkdir(exist_ok=True)
        return user_dir
    
    def get_draft_dir(self, draft_id: int) -> Path:
        """Get user's personal files directory"""
        draft_dir = self.draft_attachments_path / str(draft_id)
        draft_dir.mkdir(exist_ok=True)
        return draft_dir
    
    async def save_user_file(
        self,
        user_id: int,
        file: UploadFile,
        custom_filename: Optional[str] = None
    ) -> dict:
        """
        Save a persistent user file(resume, template, etc)
        """
        user_dir = self.get_user_files_path(user_id=user_id)

        if custom_filename:
            filename = custom_filename
        else:
            file_ext = Path(file.filename).suffix if file.filename else ""
            filename = f"{uuid.uuid4()}{file_ext}"
        
        filepath = user_dir / filename

        # Save content
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        return {
            "filename": filename,
            "original_filename": file.filename,
            "filepath": str(filepath),
            "size": len(content),
            "type": "user_file"
        }
    
    async def save_draft_attachment(
        self,
        draft_id: int,
        file: UploadFile
    ) -> dict:
        """Save a temporary draft attachment"""
        draft_dir = self.get_draft_dir(draft_id=draft_id)

        filename = file.filename if file.filename else ""
        filepath = draft_dir / filename

        counter = 1
        while filepath.exists():
            stem = Path(file.filename if file.filename else "").stem
            ext = Path(file.filename if file.filename else "").suffix
            filename = f"{stem}_{counter}{ext}"
            filepath = draft_dir / filename
            counter += 1

        # Save file
        content = await file.read()
        with open(filepath, 'wb') as f:
            f.write(content)
        
        return {
            "filename": filename,
            "original_filename": file.filename,
            "filepath": str(filepath),
            "size": len(content),
            "type": "draft_attachment"
        }
    
    def list_user_files(self, user_id: int) -> List[dict]:
        """List all user's persistent files"""
        user_dir = self.get_user_files_path(user_id=user_id)
        files = []

        for filepath in user_dir.iterdir():
            if filepath.is_file():
                files.append({
                    "filename": filepath.name,
                    "filepath": str(filepath),
                    "size": filepath.stat().st_size,
                    "type": "user_file"
                })

        return files

    def delete_file(self, filepath: str) -> bool:
        """Delete a specific file"""
        try:
            path = Path(filepath)
            if path.exists():
                path.unlink()
                return True
        except Exception as e:
            print(f"Error deleting file: {e}")
        return False
    
    def delete_draft_files(self, draft_id: int) -> bool:
        """Delete all files for a draft"""
        try:
            draft_dir = self.get_draft_dir(draft_id=draft_id)
            if draft_dir.exists():
                shutil.rmtree(draft_dir)
                return True
        except Exception as e:
            print(f"Error deleting draft files: {e}")
        return False

    def delete_user_file(self, user_id: int, filename: str) -> bool:
        """Delete a specific user file"""
        user_dir = self.get_user_files_path(user_id=user_id)
        filepath = user_dir / filename
        return self.delete_file(str(filepath))

    def get_file_content(self, filepath: str) -> Optional[bytes]:
        """Read file content"""
        try:
            with open(filepath, 'rb') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file: {e}")
            return None
    
    def read_file_for_email(self, filepath: str) -> Optional[tuple[str, bytes]]:
        """
        Read file for email attachment
        Returns: (filename, content) or None if error
        """
        try:
            path = Path(filepath)
            if not path.exists():
                print(f"File not found: {filepath}")
                return None
            
            filename = path.name
            with open(path, 'rb') as f:
                content = f.read()
            
            return (filename, content)
        except Exception as e:
            print(f"Error reading file for email: {e}")
            return None

storage_service = StorageService()