import os
import uuid
from fastapi import UploadFile, HTTPException
from PIL import Image
import io
from datetime import datetime

UPLOAD_DIR = "uploads/headshots"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024

def ensure_upload_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)

def validate_image_file(file: UploadFile) -> bool:
    if not file.filename:
        return False
    
    file_ext = os.path.splitext(file.filename.lower())[1]
    if file_ext not in ALLOWED_EXTENSIONS:
        return False
    
    if file.size and file.size > MAX_FILE_SIZE:
        return False
    
    return True

async def save_headshot_image(file: UploadFile) -> tuple[str, str]:
    if not validate_image_file(file):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}. Max size: 5MB"
        )
    
    ensure_upload_dir()
    
    file_ext = os.path.splitext(file.filename.lower())[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        
        max_size = (500, 500)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        image.save(file_path, 'JPEG', quality=85, optimize=True)
        
        url = f"/uploads/headshots/{unique_filename}"
        
        return unique_filename, url
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process image: {str(e)}")

def delete_headshot_image(filename: str) -> bool:
    if not filename:
        return False
    
    file_path = os.path.join(UPLOAD_DIR, filename)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception:
        pass
    return False 