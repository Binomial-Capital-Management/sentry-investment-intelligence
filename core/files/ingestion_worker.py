"""
Files ingestion worker: extracts text from uploaded files, chunks, embeds, and stores vectors
in files_chunks with RLS (separate from SEC).
"""

import asyncio
import logging
import os
from typing import Optional, List, Dict, Any
import asyncpg

from core.config import get_config

logger = logging.getLogger(__name__)


async def _next_job(conn) -> Optional[Dict[str, Any]]:
    row = await conn.fetchrow(
        """
        SELECT id, user_id, file_id
        FROM files_ingest_jobs
        WHERE status = 'queued'
        ORDER BY created_at ASC
        LIMIT 1
        """
    )
    return dict(row) if row else None


async def _set_job_status(pg_client, job_id: str, status: str, error: Optional[str] = None):
    """Update job status with retry logic for transient failures."""
    max_retries = 3
    retry_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            # Use raw pool connection for status updates (no RLS needed)
            # Set a shorter timeout and don't use transactions
            async with pg_client.pool.acquire(timeout=5) as conn:
                try:
                    await conn.execute(
                        """
                        UPDATE files_ingest_jobs
                        SET status = $2, error = $3, updated_at = NOW()
                        WHERE id = $1
                        """,
                        job_id,
                        status,
                        error,
                        timeout=5  # Command timeout
                    )
                    logger.info(f"Updated job {job_id} status to {status}")
                    return  # Success
                except asyncio.TimeoutError as e:
                    # This catches command timeout
                    raise e  # Re-raise to be caught by outer try
        except (asyncio.TimeoutError, asyncpg.exceptions.QueryCanceledError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"Timeout updating job {job_id} status to {status}, retry {attempt + 1}/{max_retries} in {retry_delay}s")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Failed to update job {job_id} status to {status} after {max_retries} retries: {type(e).__name__}")
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status to {status}: {e}")
            break  # Don't retry on non-timeout errors


async def _load_file_bytes(conn, user_id: str, file_id: str) -> Optional[bytes]:
    # Look up stored_key under RLS
    row = await conn.fetchrow(
        """
        SELECT stored_key
        FROM files
        WHERE id = $1
        """,
        file_id,
    )
    if not row:
        return None
    stored_key = row["stored_key"]
    if not stored_key:
        return None
    upload_dir = os.getenv("UPLOAD_DIR", "/tmp/uploads")
    safe = stored_key.replace("/", "_")
    path = os.path.join(upload_dir, safe)
    try:
        import aiofiles
        async with aiofiles.open(path, "rb") as f:
            return await f.read()
    except Exception as e:
        logger.error(f"Failed to read file bytes: {e}")
        return None


def _is_binary_file(content_type: str) -> bool:
    """Check if file type should skip embedding based on content type"""
    if not content_type:
        return False
    skip_types = ['image/', 'video/', 'audio/', 'application/zip', 'application/octet-stream']
    return any(t in content_type.lower() for t in skip_types)


def _extract_text_from_file(content: bytes, content_type: str, filename: str) -> str:
    """
    Extract text using Aug 2025 best practices:
    - Content-based detection over extensions
    - Proper library usage per file type
    - Token limit safety
    """
    import io
    
    # Skip binary/media files (but not office documents)
    # Note: .docx files often come as application/octet-stream, so check filename first
    if not (filename.lower().endswith(('.docx', '.doc', '.xlsx', '.xls', '.pdf', '.txt', '.csv', '.json'))):
        if _is_binary_file(content_type):
            logger.info(f"Skipping binary file: {content_type}")
            return ""
    
    # Check if it's a ZIP-based Office document (docx/xlsx) by magic bytes
    if len(content) > 4 and content[:2] == b'PK':
        # This is a ZIP file, likely Office document
        if filename.lower().endswith(('.docx', '.doc')) or 'word' in filename.lower():
            # Force treat as Word document
            content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif filename.lower().endswith(('.xlsx', '.xls')) or 'excel' in filename.lower():
            # Force treat as Excel document
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    # PDF extraction (using PyPDF2 - already installed)
    if filename.lower().endswith('.pdf') or 'pdf' in (content_type or '').lower():
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            text = ''
            # Limit to 100 pages to prevent overflow
            for i, page in enumerate(reader.pages):
                if i >= 100:
                    logger.info(f"PDF has more than 100 pages, truncating")
                    break
                text += page.extract_text() + '\n'
            if text.strip():
                return text
        except Exception as e:
            logger.warning(f"PDF extraction failed, trying fallback: {e}")
    
    # Word document extraction (python-docx already installed)
    if filename.lower().endswith(('.docx', '.doc')) or 'word' in (content_type or '').lower():
        try:
            from docx import Document
            doc = Document(io.BytesIO(content))
            # Extract paragraphs (limit to 1000)
            paragraphs = []
            for i, p in enumerate(doc.paragraphs):
                if i >= 1000:
                    logger.info(f"Word doc has more than 1000 paragraphs, truncating")
                    break
                paragraphs.append(p.text)
            
            # Extract tables (limit to 50)
            tables_text = []
            for i, table in enumerate(doc.tables):
                if i >= 50:
                    logger.info(f"Word doc has more than 50 tables, truncating")
                    break
                for row in table.rows:
                    tables_text.append('\t'.join([cell.text for cell in row.cells]))
            
            text = '\n'.join(paragraphs + tables_text)
            if text.strip():
                return text
        except Exception as e:
            logger.warning(f"Word extraction failed, trying fallback: {e}")
    
    # Excel extraction (openpyxl already installed)
    if filename.lower().endswith(('.xlsx', '.xls')) or 'excel' in (content_type or '').lower() or 'spreadsheet' in (content_type or '').lower():
        try:
            import pandas as pd
            # Read all sheets but limit rows
            excel_file = pd.ExcelFile(io.BytesIO(content))
            texts = []
            for i, sheet_name in enumerate(excel_file.sheet_names):
                if i >= 10:
                    logger.info(f"Excel has more than 10 sheets, truncating")
                    break
                df = pd.read_excel(excel_file, sheet_name=sheet_name, nrows=1000)
                texts.append(f"Sheet: {sheet_name}\n{df.to_string()}")
            text = '\n\n'.join(texts)
            if text.strip():
                return text
        except Exception as e:
            logger.warning(f"Excel extraction failed, trying fallback: {e}")
    
    # CSV handling
    if filename.lower().endswith('.csv') or 'csv' in (content_type or '').lower():
        try:
            import pandas as pd
            df = pd.read_csv(io.BytesIO(content), nrows=1000)
            return df.to_string()
        except Exception as e:
            logger.warning(f"CSV extraction failed, trying fallback: {e}")
    
    # JSON handling  
    if filename.lower().endswith('.json') or 'json' in (content_type or '').lower():
        try:
            import json
            data = json.loads(content.decode('utf-8'))
            # Convert to string and limit size
            text = json.dumps(data, indent=2)
            if len(text) > 100000:
                text = text[:100000] + "\n... [truncated]"
            return text
        except Exception as e:
            logger.warning(f"JSON extraction failed, trying fallback: {e}")
    
    # Default text extraction
    try:
        text = content.decode('utf-8', errors='replace')
        # Basic validation - if >50% non-printable in first 1000 chars, likely binary
        sample = text[:1000] if len(text) > 1000 else text
        printable_ratio = sum(1 for c in sample if c.isprintable()) / len(sample) if sample else 0
        if printable_ratio < 0.5:
            logger.warning(f"File appears to be binary (printable ratio: {printable_ratio:.2f})")
            return ""
        return text
    except Exception:
        try:
            return content.decode('latin-1', errors='replace')
        except Exception:
            logger.warning("Failed all text extraction methods")
            return ""


def _chunk_text(text: str, size: int, overlap: int) -> List[str]:
    chunks: List[str] = []
    if size <= 0:
        return chunks
    step = max(1, size - overlap)
    i = 0
    n = len(text)
    while i < n:
        chunks.append(text[i : i + size])
        i += step
        if len(chunks) >= 20000:  # hard safety cap
            break
    return chunks


async def _embed_texts(texts: List[str]) -> List[List[float]]:
    cfg = get_config()
    provider = cfg.file_embedding_provider
    model = cfg.file_embedding_model
    dims = cfg.file_embedding_dims
    try:
        if provider == "voyage":
            import voyageai
            client = voyageai.AsyncClient(api_key=cfg.voyage_api_key)
            resp = await client.embed(texts=texts, model=model, input_type="document", output_dimension=dims, output_dtype="float")
            return resp.embeddings
        else:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=cfg.openai_api_key)
            resp = await client.embeddings.create(model=model, input=texts)
            return [d.embedding for d in resp.data]
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        raise


async def _store_chunks(conn, user_id: str, file_id: str, chunks: List[str], embeddings: List[List[float]]):
    cfg = get_config()
    # Delete existing chunks for this file first to avoid duplicates
    await conn.execute(
        "DELETE FROM files_chunks WHERE file_id = $1",
        file_id
    )
    logger.info(f"Deleted existing chunks for file {file_id}")
    
    # Insert new chunks
    for idx, (text, vec) in enumerate(zip(chunks, embeddings)):
        vec_text = f"[{','.join(map(str, vec))}]"
        await conn.execute(
            f"""
            INSERT INTO files_chunks (user_id, file_id, chunk_id, content, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5::{cfg.file_vector_cast}, $6)
            """,
            user_id, file_id, idx, text, vec_text, '{}',
        )


async def _delete_chunks_for_file(conn, user_id: str, file_id: str) -> None:
    try:
        await conn.execute(
            "DELETE FROM files_chunks WHERE file_id = $1",
            file_id,
        )
    except Exception as e:
        logger.warning(f"Failed to delete chunks for file {file_id}: {e}")


async def _has_required_tables(conn) -> bool:
    try:
        rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = ANY($1)
            """,
            ['files_ingest_jobs', 'files_chunks'],
        )
        found = {r['table_name'] for r in rows}
        return 'files_ingest_jobs' in found and 'files_chunks' in found
    except Exception as e:
        logger.debug(f"Failed to check required tables: {e}")
        return False


async def start_ingestion_worker():
    cfg = get_config()
    if not cfg.enable_postgres or not cfg.file_vectors_enabled:
        logger.info("Files ingestion worker disabled")
        return

    from core.database.postgres_client import get_postgres_rls_client
    pg = await get_postgres_rls_client()

    logger.info("Files ingestion worker running")
    # Ensure required tables exist; otherwise disable worker gracefully
    try:
        async with pg.acquire_with_user_context(None) as conn:
            ok = await _has_required_tables(conn)
            if not ok:
                logger.warning("Files ingestion worker disabled: required tables missing (run migrations 003/004)")
                return
    except Exception as e:
        logger.warning(f"Files ingestion worker disabled: unable to verify tables: {e}")
        return
    while True:
        try:
            # Fetch next job with short-lived connection
            async with pg.acquire_with_user_context(None) as conn:
                job = await _next_job(conn)
            
            if not job:
                await asyncio.sleep(1.0)
                continue
            
            # Set status to running (no connection needed, function handles it)
            await _set_job_status(pg, job["id"], "running")
            
            # user_id is already TEXT in database
            user_id = job["user_id"]
            file_id = job["file_id"]
            
            # Read file bytes and metadata under user RLS
            async with pg.acquire_with_user_context(user_id) as uconn:
                content = await _load_file_bytes(uconn, user_id, file_id)
                # Fetch file metadata for proper extraction
                file_info = await uconn.fetchrow(
                    "SELECT content_type, original_name FROM files WHERE id = $1",
                    file_id
                )
            
            if not content:
                await _set_job_status(pg, job["id"], "error", "file read failed")
                continue
            
            # Extract text based on file type
            content_type = file_info['content_type'] if file_info else None
            filename = file_info['original_name'] if file_info else ''
            text = _extract_text_from_file(content, content_type, filename)
            
            # Handle binary files gracefully
            if not text:
                if _is_binary_file(content_type):
                    # Binary files are expected to have no text - mark as done
                    await _set_job_status(pg, job["id"], "done", "binary file - skipped embedding")
                    logger.info(f"Skipped binary file {file_id} ({content_type})")
                else:
                    # Non-binary files with no text are an error
                    await _set_job_status(pg, job["id"], "error", "no extractable text")
                continue
            
            # Add safety check to prevent token overflow
            MAX_TEXT_LENGTH = 100000  # ~25k tokens for safety
            if len(text) > MAX_TEXT_LENGTH:
                logger.warning(f"Truncating text from {len(text)} to {MAX_TEXT_LENGTH} chars for file {file_id}")
                text = text[:MAX_TEXT_LENGTH]
            
            # Chunk
            chunks = _chunk_text(text, cfg.file_chunk_size, cfg.file_chunk_overlap)
            if not chunks:
                await _set_job_status(pg, job["id"], "error", "no chunks")
                continue
            
            # Embed - this is the long operation, no DB connection held
            embeddings = await _embed_texts(chunks)
            
            # Store under user RLS with fresh connections
            try:
                async with pg.acquire_with_user_context(user_id) as uconn2:
                    await _store_chunks(uconn2, user_id, file_id, chunks, embeddings)
                    logger.info(f"Stored {len(chunks)} chunks for file {file_id}")
                
                # Update status to done (no connection needed, function handles it)
                await _set_job_status(pg, job["id"], "done")
            except Exception as e:
                logger.error(f"Failed to store chunks for file {file_id}: {e}")
                await _set_job_status(pg, job["id"], "error", str(e)[:500])
                continue
        except asyncio.CancelledError:
            logger.info("Files ingestion worker stopped")
            break
        except Exception as e:
            logger.error(f"Ingestion worker error: {e}")
            await asyncio.sleep(1.0)
