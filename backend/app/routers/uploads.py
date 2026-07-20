from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.config import settings
from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter()

# backend/uploads — served read-only via the /uploads static mount in main.py.
UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"

ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.post("/uploads", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile,
    _current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    extension = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PNG, JPEG, WebP, or GIF images are allowed",
        )
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image is larger than 5 MB",
        )
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    # Random server-side name: never trust the client filename.
    name = f"{secrets.token_hex(16)}{extension}"
    (UPLOADS_DIR / name).write_bytes(data)
    return {"url": f"{settings.api_base_url.rstrip('/')}/uploads/{name}"}
