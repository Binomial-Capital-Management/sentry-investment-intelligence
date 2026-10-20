"""
Upload endpoint for file attachments.
Follows NO HARDCODING principle - dynamically handles any file type.
Implements proper RLS for user separation.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse
from typing import List, Dict, Any, Optional
import uuid
import os
import aiofiles
import hashlib
import mimetypes
from datetime import datetime
import logging
import json

from core.config import get_config
from core.database.postgres_client import get_postgres_rls_client

config = get_config()
router = APIRouter(prefix="/api/uploads", tags=["uploads"])
logger = logging.getLogger(__name__)


def get_org_id_from_request(request: Request) -> str:
    """Extract org_id from request state, defaulting to empty string for personal workspace."""
    return getattr(request.state, 'org_id', None) or ''

# Dynamic upload directory configuration
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/uploads")
MAX_FILE_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "41943040"))  # 40MB default
MAX_UPLOAD_FILES = int(os.getenv("MAX_UPLOAD_FILES", "5"))

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Helper to format file size for user-friendly messages
def format_file_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


async def store_file_bytes(
    user_id: str,
    filename: str,
    content: bytes,
    *,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    org_id: str = '',
) -> Dict[str, Any]:
    """
    Persist raw file bytes to the upload store and return metadata.
    Shared by standard uploads and Google Drive imports.
    Properly scoped to the current organization workspace.
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if len(content) > MAX_FILE_SIZE:
        file_size_formatted = format_file_size(len(content))
        max_size_formatted = format_file_size(MAX_FILE_SIZE)
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({file_size_formatted}). Maximum file size is {max_size_formatted}."
        )

    file_id = str(uuid.uuid4())
    file_extension = os.path.splitext(filename)[1] if filename else ""
    stored_key = f"users/{user_id}/files/{file_id}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, stored_key.replace('/', '_'))
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Persist bytes locally
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    # Also persist to S3 in production
    try:
        from core.config import get_config
        cfg = get_config()
        if cfg.artifact_storage_backend == "s3" and cfg.artifact_s3_bucket:
            import boto3
            import asyncio
            s3 = boto3.client("s3", region_name=cfg.artifact_s3_region)
            s3_key = f"uploads/{stored_key.replace('/', '_')}"
            await asyncio.to_thread(
                s3.put_object, Bucket=cfg.artifact_s3_bucket, Key=s3_key, Body=content
            )
            logger.info(f"Uploaded file to S3: {s3_key}")
    except Exception as e:
        logger.warning(f"Failed to upload to S3 (local copy exists): {e}")

    # Infer content type when missing
    detected_type = content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    # Prepare metadata for DB
    file_hash = hashlib.sha256(content).hexdigest()
    metadata_dict = metadata.copy() if metadata else {}
    metadata_dict.setdefault("hash", file_hash)

    created_at_iso: str
    db_file_id: str

    if config.enable_postgres:
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
            # Constraint: EITHER user_id OR org_id must be set, not both
            # If in org workspace, set org_id and leave user_id NULL
            # If personal workspace, set user_id and leave org_id NULL
            effective_user_id = None if org_id else user_id
            effective_org_id = org_id if org_id else None
            record = await conn.fetchrow(
                """
                INSERT INTO files (user_id, org_id, original_name, stored_key, content_type, size_bytes, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                RETURNING id, created_at
                """,
                effective_user_id,
                effective_org_id,
                filename or "unnamed",
                stored_key,
                detected_type,
                len(content),
                json.dumps(metadata_dict),
            )
            db_file_id = str(record['id'])
            created_at_iso = record['created_at'].isoformat()
    else:
        db_file_id = file_id
        created_at_iso = datetime.utcnow().isoformat()

    return {
        "id": db_file_id,
        "original_name": filename or "unnamed",
        "content_type": detected_type,
        "size": len(content),
        "created_at": created_at_iso,
        "stored_key": stored_key,
    }

@router.post("/files")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...)
) -> Dict[str, Any]:
    """
    Upload multiple files and return their metadata.
    Files are stored with user separation via RLS.
    """
    # Get user ID from middleware (same pattern as working portfolios endpoint)
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Use clerk_user_id directly as internal_user_id (same as portfolios)
    org_id = get_org_id_from_request(request)
    uploaded_files: List[Dict[str, Any]] = []
    
    files_to_process = files[:MAX_UPLOAD_FILES]
    if len(files) > MAX_UPLOAD_FILES:
        logger.info("Limiting upload to %s files per request", MAX_UPLOAD_FILES)

    for file in files_to_process:
        try:
            # Check file size and persist with org_id
            contents = await file.read()
            stored = await store_file_bytes(
                clerk_user_id,
                file.filename or "unnamed",
                contents,
                content_type=file.content_type,
                org_id=org_id,
            )
            # Remove internal key from response
            stored.pop("stored_key", None)
            uploaded_files.append(stored)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            # Generic error to prevent information leakage
            raise HTTPException(
                status_code=500,
                detail="Failed to upload file"
            )
    
    return {
        "status": "success",
        "files": uploaded_files,
        "count": len(uploaded_files)
    }

@router.get("/files/{file_id}")
async def get_file_metadata(
    file_id: str,
    request: Request
) -> Dict[str, Any]:
    """
    Get metadata for an uploaded file.
    User can only access their own files via RLS.
    """
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Use clerk_user_id directly as internal_user_id (same as portfolios)
    internal_user_id = clerk_user_id
    org_id = get_org_id_from_request(request)

    if config.enable_postgres:
        try:
            pg = await get_postgres_rls_client()

            async with pg.acquire_with_org_context(internal_user_id, org_id if org_id else None) as conn:
                file_record = await conn.fetchrow(
                    "SELECT * FROM files WHERE id = $1 AND org_id = $2",
                    uuid.UUID(file_id), org_id
                )
                
                if not file_record:
                    # Generic error to prevent enumeration
                    raise HTTPException(status_code=404, detail="File not found")
                
                return {
                    "id": str(file_record['id']),
                    "original_name": file_record['original_name'],
                    "content_type": file_record['content_type'],
                    "size": file_record['size_bytes'],
                    "created_at": file_record['created_at'].isoformat(),
                    "metadata": file_record.get('metadata', {})
                }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get file metadata: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve file")
    
    # Fallback to local storage check (use Clerk ID for file paths)
    user_file_pattern = os.path.join(UPLOAD_DIR, f"users_{clerk_user_id}_files_{file_id}*")
    import glob
    matches = glob.glob(user_file_pattern)
    
    if not matches:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = matches[0]
    file_stats = os.stat(file_path)
    
    return {
        "id": file_id,
        "size": file_stats.st_size,
        "created_at": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
        "exists": True
    }


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: str,
    request: Request,
):
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    stored_key = None
    filename = None
    content_type = None
    org_id = get_org_id_from_request(request)

    if config.enable_postgres:
        pg = await get_postgres_rls_client()
        try:
            async with pg.acquire_with_org_context(clerk_user_id, org_id if org_id else None) as conn:
                row = await conn.fetchrow(
                    "SELECT stored_key, original_name, content_type FROM files WHERE id = $1 AND org_id = $2",
                    uuid.UUID(file_id), org_id
                )
                if not row:
                    raise HTTPException(status_code=404, detail="File not found")
                stored_key = row["stored_key"]
                filename = row["original_name"]
                content_type = row["content_type"]
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Failed to fetch file metadata: {exc}")
            raise HTTPException(status_code=500, detail="Failed to fetch file")

    path_candidate = None
    if stored_key:
        path_candidate = os.path.join(UPLOAD_DIR, stored_key.replace('/', '_'))
    else:
        pattern = os.path.join(UPLOAD_DIR, f"users_{clerk_user_id}_files_{file_id}*")
        import glob
        matches = glob.glob(pattern)
        if matches:
            path_candidate = matches[0]

    if not path_candidate or not os.path.exists(path_candidate):
        raise HTTPException(status_code=404, detail="File not found")

    headers = {}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return FileResponse(path_candidate, media_type=content_type or "application/octet-stream", headers=headers)

@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    request: Request
) -> Dict[str, str]:
    """
    Delete an uploaded file.
    User can only delete their own files via RLS.
    """
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Use clerk_user_id directly as internal_user_id (same as portfolios)
    internal_user_id = clerk_user_id
    org_id = get_org_id_from_request(request)

    if config.enable_postgres:
        try:
            pg = await get_postgres_rls_client()

            async with pg.acquire_with_org_context(internal_user_id, org_id if org_id else None) as conn:
                # First get the file to find its stored_key with org_id check
                file_record = await conn.fetchrow(
                    "SELECT stored_key FROM files WHERE id = $1 AND org_id = $2",
                    uuid.UUID(file_id), org_id
                )
                
                if not file_record:
                    raise HTTPException(status_code=404, detail="File not found")
                
                # Delete from database (will cascade to message_files)
                await conn.execute(
                    "DELETE FROM files WHERE id = $1 AND org_id = $2",
                    uuid.UUID(file_id), org_id
                )
                
                # Delete physical file
                file_path = os.path.join(UPLOAD_DIR, file_record['stored_key'].replace('/', '_'))
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                return {"status": "deleted", "file_id": file_id}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete file")
    
    # Fallback to local storage (use Clerk ID for file paths)
    user_file_pattern = os.path.join(UPLOAD_DIR, f"users_{clerk_user_id}_files_{file_id}*")
    import glob
    matches = glob.glob(user_file_pattern)
    
    if not matches:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        os.remove(matches[0])
        return {"status": "deleted", "file_id": file_id}
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file")

@router.get("/files")
async def list_user_files(
    request: Request,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """
    List all files for the current user.
    RLS ensures only user's own files are visible.
    """
    clerk_user_id = getattr(request.state, 'user_id', None)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Use clerk_user_id directly as internal_user_id (same as portfolios)
    internal_user_id = clerk_user_id
    org_id = get_org_id_from_request(request)
    
    if config.enable_postgres:
        try:
            pg = await get_postgres_rls_client()

            async with pg.acquire_with_org_context(internal_user_id, org_id if org_id else None) as conn:
                # Count total files with org_id filter
                count_result = await conn.fetchrow(
                    "SELECT COUNT(*) as total FROM files WHERE org_id = $1",
                    org_id
                )
                total = count_result['total']
                
                # Get paginated files with org_id filter
                files = await conn.fetch(
                    """
                    SELECT id, original_name, content_type, size_bytes, created_at, metadata
                    FROM files
                    WHERE org_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    org_id,
                    limit,
                    offset
                )
                
                return {
                    "files": [
                        {
                            "id": str(f['id']),
                            "original_name": f['original_name'],
                            "content_type": f['content_type'],
                            "size": f['size_bytes'],
                            "created_at": f['created_at'].isoformat(),
                            "metadata": f.get('metadata', {})
                        }
                        for f in files
                    ],
                    "total": total,
                    "limit": limit,
                    "offset": offset
                }
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve files")
    
    # Fallback - return empty list if no database
    return {
        "files": [],
        "total": 0,
        "limit": limit,
        "offset": offset
    }
