"""
File Tools for AI Agents

Purpose: Safely read user-uploaded files (RLS-enforced) and return a compact, sanitized preview
the agent can use for analysis. Follows CODING_RULES.md: NO HARDCODING, async-first, KISS.
"""

from typing import Optional, Dict, Any, List
import os
import io
import csv
import math
import logging

try:
    from agents import function_tool
except ImportError:  # Fallback when Agents SDK not present (tests/local tools)
    def function_tool(func):
        return func

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        f = float(value)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


async def _load_file_record(file_id: str, user_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Load file metadata via RLS when DB enabled; fallback to local when DB disabled.
    Returns: {id, original_name, stored_key, content_type, size}
    """
    from core.config import get_config
    config = get_config()

    # Prefer database when enabled
    if config.enable_postgres and user_id:
        try:
            from core.database.postgres_client import get_postgres_rls_client
            import uuid
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_user_context(user_id) as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, original_name, stored_key, content_type, size_bytes
                    FROM files
                    WHERE id = $1
                    """,
                    uuid.UUID(file_id),
                )
                if not row:
                    return None
                # asyncpg.Record supports both mapping and index access
                ctype = row["content_type"] if "content_type" in row else None
                return {
                    "id": str(row["id"]),
                    "original_name": row["original_name"],
                    "stored_key": row["stored_key"],
                    "content_type": (ctype.lower() if isinstance(ctype, str) else None),
                    "size": row["size_bytes"],
                }
        except Exception as e:
            logger.debug(f"DB lookup failed for file {file_id}: {e}")

    # Fallback: local sanitized path pattern (no DB)
    upload_dir = os.getenv("UPLOAD_DIR", "/tmp/uploads")
    if not user_id:
        return None
    pattern = os.path.join(upload_dir, f"users_{user_id}_files_{file_id}*")
    import glob
    matches = glob.glob(pattern)
    if not matches:
        return None
    path = matches[0]
    try:
        st = os.stat(path)
        return {
            "id": file_id,
            "original_name": os.path.basename(path),
            "stored_key": os.path.basename(path),
            "content_type": None,
            "size": st.st_size,
        }
    except Exception:
        return None


async def _read_bytes(file_record: Dict[str, Any]) -> Optional[bytes]:
    """Read file bytes from storage using stored_key convention."""
    upload_dir = os.getenv("UPLOAD_DIR", "/tmp/uploads")
    stored_key = file_record.get("stored_key")
    if not stored_key:
        return None
    safe_name = stored_key.replace("/", "_")
    file_path = os.path.join(upload_dir, safe_name)
    try:
        import aiofiles
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()
    except Exception as e:
        logger.debug(f"Failed to read file bytes: {e}")
        return None


def _detect_type(file_record: Dict[str, Any], filename: str) -> str:
    ctype = (file_record.get("content_type") or "").lower()
    if ctype:
        return ctype
    import mimetypes
    guess, _ = mimetypes.guess_type(filename)
    return (guess or "application/octet-stream").lower()


def _truncate_text(s: str, limit: int) -> (str, bool):
    if len(s) <= limit:
        return s, False
    return s[:limit], True


def _extract_text(content: bytes, ctype: str, filename: str, char_cap: int) -> Dict[str, Any]:
    # Images - use GPT-5 vision
    if any(ext in filename.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']) or ctype.startswith("image/"):
        try:
            from .vision_tools import analyze_image_with_gpt5
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as f:
                f.write(content)
                temp_path = f.name

            result = analyze_image_with_gpt5(temp_path)
            os.remove(temp_path)

            if result.get("success"):
                text = result.get("analysis", "Image processed but no content extracted")
                preview, truncated = _truncate_text(text, char_cap)
                return {"kind": "text", "preview": preview, "truncated": truncated}
        except:
            return {"kind": "unsupported", "preview": "Image analysis unavailable", "truncated": False}

    # Word documents
    if filename.lower().endswith(".docx"):
        try:
            from .document_extractors import extract_word_document
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as f:
                f.write(content)
                temp_path = f.name

            result = extract_word_document(temp_path)
            os.remove(temp_path)

            if result.get("success"):
                text = result.get("text", "")
                preview, truncated = _truncate_text(text, char_cap)
                return {"kind": "text", "preview": preview, "truncated": truncated}
        except:
            return {"kind": "unsupported", "preview": "Word document extraction unavailable", "truncated": False}

    # Direct text types
    if ctype.startswith("text/") or any(ctype.endswith(x) for x in ("json", "xml")):
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            text = content.decode("latin-1", errors="replace")
        preview, truncated = _truncate_text(text, char_cap)
        return {"kind": "text", "preview": preview, "truncated": truncated}

    # PDF - try GPT-5 vision first, then fallback
    if "pdf" in ctype or filename.lower().endswith(".pdf"):
        # Try GPT-5 vision approach
        try:
            from .vision_tools import analyze_pdf_with_gpt5
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as f:
                f.write(content)
                temp_path = f.name

            result = analyze_pdf_with_gpt5(temp_path, page_limit=3)
            os.remove(temp_path)

            if result.get("success"):
                analyses = [r.get("analysis", "") for r in result.get("results", [])]
                text = "\n\n".join(analyses)
                preview, truncated = _truncate_text(text, char_cap)
                return {"kind": "text", "preview": preview, "truncated": truncated}
        except:
            pass  # Fallback to pypdf

        # Fallback to pypdf
        try:
            import pypdf  # type: ignore
            reader = pypdf.PdfReader(io.BytesIO(content))
            parts: List[str] = []
            for page in reader.pages[:10]:  # cap pages
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    continue
            text = "\n".join(parts)
            preview, truncated = _truncate_text(text, char_cap)
            return {"kind": "text", "preview": preview, "truncated": truncated}
        except Exception:
            return {"kind": "unsupported", "preview": "PDF text extraction unavailable", "truncated": False}

    return {"kind": "unsupported", "preview": "Unsupported file type", "truncated": False}


def _extract_table(content: bytes, ctype: str, filename: str, row_cap: int) -> Optional[Dict[str, Any]]:
    # CSV
    if "csv" in ctype or filename.lower().endswith(".csv"):
        try:
            text = content.decode("utf-8", errors="replace")
            reader = csv.reader(io.StringIO(text))
            rows = []
            for i, row in enumerate(reader):
                if i >= row_cap:
                    break
                rows.append(row)
            return {"kind": "table", "rows": rows, "truncated": True}
        except Exception:
            return {"kind": "unsupported", "preview": "Failed to parse CSV", "truncated": False}

    # XLSX - Enhanced with document_extractors
    if filename.lower().endswith(".xlsx") or "spreadsheetml" in ctype:
        try:
            # Try enhanced extraction first
            from .document_extractors import extract_excel_enhanced
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as f:
                f.write(content)
                temp_path = f.name

            result = extract_excel_enhanced(temp_path)
            os.remove(temp_path)

            if result.get("success"):
                sheets = result.get("sheets", {})
                if sheets:
                    # Get first sheet's data
                    first_sheet = list(sheets.values())[0]
                    rows = first_sheet.get("data", [])[:row_cap]
                    return {"kind": "table", "rows": rows, "truncated": len(rows) >= row_cap}
        except:
            pass  # Fallback to basic openpyxl

        # Fallback to basic extraction
        try:
            import openpyxl  # type: ignore
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
            ws = wb.active
            rows: List[List[Any]] = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= row_cap:
                    break
                rows.append(["" if v is None else v for v in row])
            return {"kind": "table", "rows": rows, "truncated": True}
        except Exception:
            return {"kind": "unsupported", "preview": "Failed to parse XLSX", "truncated": False}

    return None


def extract_file_preview_from_bytes(
    content: bytes,
    filename: str,
    content_type: str,
    mode: str = "auto",
    max_chars: Optional[int] = None,
    max_rows: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Produce a preview/extract from arbitrary file bytes using the same logic as read_file_content_raw.
    """
    max_chars = max_chars or int(os.getenv("FILE_EXTRACT_MAX_CHARS", "40000"))
    max_rows = max_rows or int(os.getenv("FILE_EXTRACT_MAX_ROWS", "2000"))

    if mode == "table":
        table = _extract_table(content, content_type, filename, max_rows)
        extract = table if table else _extract_text(content, content_type, filename, max_chars)
    elif mode == "text":
        extract = _extract_text(content, content_type, filename, max_chars)
    else:
        table = _extract_table(content, content_type, filename, max_rows)
        extract = table if table else _extract_text(content, content_type, filename, max_chars)

    return extract or {"kind": "unsupported", "preview": "Unsupported file type", "truncated": False}


# Keep the raw async function for direct use
async def read_file_content_raw(file_id: str, user_id: Optional[str] = None, mode: Optional[str] = "auto") -> Dict[str, Any]:
    """
    Read a user-uploaded file (RLS) and return a compact preview for analysis.

    Args:
        file_id: The file ID to read
        user_id: User ID for RLS. If None, falls back to DEV_INTERNAL_USER_ID in dev mode.
        mode: "auto" (default), "text", or "table"

    Returns:
        Dict with status and file content/extract
    """
    # Env-driven caps per CODING_RULES
    max_bytes = int(os.getenv("FILE_MAX_BYTES", "10000000"))  # 10 MB
    max_chars = int(os.getenv("FILE_EXTRACT_MAX_CHARS", "40000"))
    max_rows = int(os.getenv("FILE_EXTRACT_MAX_ROWS", "2000"))

    # Fallback for dev mode if user_id not provided
    if not user_id:
        from core.config import get_config
        config = get_config()
        if not config.enable_auth:
            # Use the same user_id as the middleware uses
            user_id = os.getenv('DEV_INTERNAL_USER_ID', "dev-local-user")
            logger.info(f"[FILE TOOLS] Using DEV_INTERNAL_USER_ID: {user_id}")

    if not user_id:
        logger.error(f"[FILE TOOLS] No user_id provided for file_id: {file_id}")
        return {"status": "error", "message": "No user context available"}

    record = await _load_file_record(file_id, user_id)
    if not record:
        return {"status": "error", "message": "File not found"}

    if record.get("size", 0) and record["size"] > max_bytes:
        return {"status": "error", "message": "File too large to analyze"}

    content = await _read_bytes(record)
    if content is None:
        return {"status": "error", "message": "Failed to read file"}

    filename = record.get("original_name") or record.get("stored_key") or "file"
    ctype = _detect_type(record, filename)

    if mode == "table":
        table = _extract_table(content, ctype, filename, max_rows)
        extract = table if table else _extract_text(content, ctype, filename, max_chars)
    elif mode == "text":
        extract = _extract_text(content, ctype, filename, max_chars)
    else:
        table = _extract_table(content, ctype, filename, max_rows)
        extract = table if table else _extract_text(content, ctype, filename, max_chars)

    return {
        "status": "success",
        "file": {
            "id": record["id"],
            "name": filename,
            "content_type": ctype,
            "size": record.get("size"),
        },
        "extract": extract,
    }


# Wrap with function_tool decorator for SDK usage
read_file_content = function_tool(read_file_content_raw)
