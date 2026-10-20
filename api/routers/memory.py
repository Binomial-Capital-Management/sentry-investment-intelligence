"""
Memory Notebook API - CRUD for per-thread memory notes

Handles memory note operations with RLS enforcement.
See docs/memory-notebook-feature-spec.md for full specification.
"""

import logging
from fastapi import APIRouter, HTTPException, Request, status
from typing import Optional
from uuid import UUID

from api.models_dir.memory_models import (
    MemoryNoteCreate,
    MemoryNoteUpdate,
    MemoryNoteResponse,
    MemoryNotebookResponse,
    ContextTokenStats,
    MessageExcerptCreate,
    FileReferenceCreate,
    PortfolioReferenceCreate,
    ChartReferenceCreate,
)
from core.services.memory_service import get_memory_service
from core.services.file_memory_service import get_file_memory_service
from pydantic import BaseModel
from typing import Literal

logger = logging.getLogger(__name__)


class FilePinRequest(BaseModel):
    """Request body for pinning a file to memory with content extraction."""

    file_id: str
    extraction_mode: Optional[str] = None  # 'text' or 'vision' - overrides auto-detection for PDFs
    index: bool = True  # Whether to chunk and index large content for semantic retrieval


class CloudFilePinRequest(BaseModel):
    """Request body for pinning a cloud file (Google Drive/OneDrive) to memory."""

    source: Literal["google_drive", "onedrive"]
    cloud_file_id: str
    extraction_mode: Optional[str] = None  # 'text' or 'vision' - overrides auto-detection for PDFs
    index: bool = True  # Whether to chunk and index large content for semantic retrieval


class SECFilingPinRequest(BaseModel):
    """Request body for pinning an SEC filing to memory with chunking/indexing."""
    
    link: str  # SEC EDGAR URL
    title: str  # e.g., "AAPL 10-K - 2024-01-15"
    form_type: Optional[str] = None  # 10-K, 10-Q, 8-K, 13F-HR, etc.
    filing_date: Optional[str] = None
    cik: Optional[str] = None
    accession_number: Optional[str] = None
    ticker: Optional[str] = None
    index: bool = True  # Whether to chunk and index for semantic retrieval


class ThirteenFPinRequest(BaseModel):
    """Request body for pinning a 13F filing to memory using structured holdings data."""
    
    title: str  # e.g., "Citadel Advisors 13F-HR Q4 2024"
    institution_name: str
    cik: str
    year: int
    quarter: int
    total_value: float
    holdings_count: int
    holdings: list  # List of holdings with symbol, securityName, shares, value, weight
    sec_link: Optional[str] = None
    index: bool = True


class TranscriptPinRequest(BaseModel):
    """Request body for pinning an earnings transcript to memory."""
    
    ticker: str
    year: int
    quarter: int
    title: Optional[str] = None  # Auto-generated if not provided
    index: bool = True


router = APIRouter(prefix="/api/memory", tags=["memory"])


def validate_session_id(session_id: str) -> str:
    """
    Validate and normalize session_id.
    Accepts both UUID format and legacy web_ format for backwards compatibility.
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    # Accept legacy web_ prefixed IDs (backwards compatibility)
    if session_id.startswith("web_"):
        return session_id

    # Try to parse as UUID
    try:
        UUID(session_id)
        return session_id
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid session_id format: {session_id}")


def get_user_id(request: Request) -> str:
    """Extract user_id from request state."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id


def get_org_id(request: Request) -> Optional[str]:
    """Extract org_id from request state."""
    return getattr(request.state, "org_id", None) or None


# =============================================================================
# Core CRUD Endpoints
# =============================================================================


@router.get("/{session_id}", response_model=MemoryNotebookResponse)
async def get_session_notes(session_id: str, request: Request, section: Optional[str] = None):
    """
    Get all memory notes for a chat session.

    Query params:
    - section: Optional filter by section (entities, decisions, preferences, context, general)
    """
    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    service = get_memory_service()

    result = await service.get_session_notes(
        user_id=user_id, session_id=session_id, section=section
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))

    return MemoryNotebookResponse(
        session_id=result["session_id"],
        notes=[MemoryNoteResponse(**note) for note in result["notes"]],
        total_count=result["total_count"],
        sections=result["sections"],
    )


@router.post(
    "/{session_id}", response_model=MemoryNoteResponse, status_code=status.HTTP_201_CREATED
)
async def create_note(session_id: str, payload: MemoryNoteCreate, request: Request):
    """
    Create a new memory note for a chat session.

    The note will be injected into the context window and survive compaction.
    """
    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    org_id = get_org_id(request)
    service = get_memory_service()

    result = await service.create_note(
        user_id=user_id,
        session_id=session_id,
        content=payload.content,
        section=payload.section,
        priority=payload.priority,
        source=payload.source,
        source_message_id=payload.source_message_id,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        reference_metadata=payload.reference_metadata,
        org_id=org_id,
    )

    if result.get("status") == "error":
        message = result.get("message", "")
        if "not found" in message.lower() or "session" in message.lower():
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=500, detail=message)

    return MemoryNoteResponse(**result["note"])


@router.patch("/{session_id}/notes/{note_id}", response_model=MemoryNoteResponse)
async def update_note(session_id: str, note_id: str, payload: MemoryNoteUpdate, request: Request):
    """
    Update an existing memory note.

    Only provided fields will be updated (partial update).
    """
    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    service = get_memory_service()

    result = await service.update_note(
        user_id=user_id,
        session_id=session_id,
        note_id=note_id,
        content=payload.content,
        section=payload.section,
        priority=payload.priority,
        summary=payload.summary,
        reference_metadata=payload.reference_metadata,
    )

    if result.get("status") == "error":
        if "not found" in result.get("message", "").lower():
            raise HTTPException(status_code=404, detail="Note not found")
        raise HTTPException(status_code=500, detail=result.get("message"))

    return MemoryNoteResponse(**result["note"])


@router.delete("/{session_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(session_id: str, note_id: str, request: Request):
    """Delete a memory note."""
    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    service = get_memory_service()

    result = await service.delete_note(user_id=user_id, session_id=session_id, note_id=note_id)

    if result.get("status") == "error":
        if "not found" in result.get("message", "").lower():
            raise HTTPException(status_code=404, detail="Note not found")
        raise HTTPException(status_code=500, detail=result.get("message"))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_session_memory(session_id: str, request: Request, section: Optional[str] = None):
    """
    Clear all memory notes for a session.

    Query params:
    - section: Optional - only clear notes in this section
    """
    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    service = get_memory_service()

    result = await service.clear_session_memory(
        user_id=user_id, session_id=session_id, section=section
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))


# =============================================================================
# Token Stats Endpoint
# =============================================================================


@router.get("/{session_id}/stats", response_model=ContextTokenStats)
async def get_context_stats(session_id: str, request: Request, model: Optional[str] = None):
    """
    Get token usage breakdown for context window visibility.

    Returns memory notebook size, remaining capacity, and pressure level.

    Query params:
    - model: Optional model identifier (defaults to gpt-5)
    """
    from core.database.postgres_client import get_postgres_rls_client
    from core.config import get_config

    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    service = get_memory_service()
    config = get_config()

    # Load actual messages from database
    messages = []
    if config.enable_postgres:
        try:
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_user_context(user_id) as conn:
                rows = await conn.fetch(
                    """
                    SELECT content FROM chat_messages
                    WHERE session_id = $1
                    ORDER BY created_at ASC
                """,
                    session_id,
                )
                messages = [{"content": row["content"]} for row in rows]
        except Exception as e:
            logger.warning(f"Failed to load messages for token stats: {e}")

    state = {"messages": messages}

    result = await service.get_context_token_stats(
        user_id=user_id, session_id=session_id, selected_model=model or "gpt-5", state=state
    )

    return ContextTokenStats(**result)


# =============================================================================
# Rich Reference Endpoints (Phase 2)
# =============================================================================


@router.post(
    "/{session_id}/excerpt", response_model=MemoryNoteResponse, status_code=status.HTTP_201_CREATED
)
async def pin_message_excerpt(session_id: str, payload: MessageExcerptCreate, request: Request):
    """
    Pin a highlighted message excerpt to memory.

    Used when user selects text in a message and clicks "Pin to Memory".
    """
    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    org_id = get_org_id(request)
    service = get_memory_service()

    # Get the message content to extract the excerpt
    # In full implementation, this would fetch the message and extract the text
    # For now, we'll store the offsets in metadata

    result = await service.create_note(
        user_id=user_id,
        session_id=session_id,
        content=f"[Excerpt from message - offsets {payload.start_offset}:{payload.end_offset}]",
        section=payload.section,
        priority=payload.priority,
        source="user",
        source_message_id=payload.message_id,
        reference_type="message_excerpt",
        reference_metadata={"start_offset": payload.start_offset, "end_offset": payload.end_offset},
        org_id=org_id,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))

    return MemoryNoteResponse(**result["note"])


@router.post(
    "/{session_id}/file", response_model=MemoryNoteResponse, status_code=status.HTTP_201_CREATED
)
async def attach_file_reference(session_id: str, payload: FileReferenceCreate, request: Request):
    """
    Attach a file reference to memory.

    Stores what to remember about a file that was uploaded/discussed.
    """
    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    org_id = get_org_id(request)
    service = get_memory_service()

    result = await service.create_note(
        user_id=user_id,
        session_id=session_id,
        content=payload.note,
        section=payload.section,
        priority=payload.priority,
        source="user",
        reference_type="file",
        reference_id=payload.file_id,
        reference_metadata={},
        org_id=org_id,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))

    return MemoryNoteResponse(**result["note"])


@router.post(
    "/{session_id}/pin-file", response_model=MemoryNoteResponse, status_code=status.HTTP_201_CREATED
)
async def pin_file_to_memory(session_id: str, payload: FilePinRequest, request: Request):
    """
    Pin an uploaded file to memory with full content extraction.

    For PDFs:
    - Auto-detects page count to choose extraction method
    - Long PDFs (4+ pages) use PyMuPDF text extraction (full document)
    - Short PDFs (1-3 pages) use GPT-5 Vision (higher quality)
    - Override with extraction_mode='text' or 'vision'

    For images: Uses GPT-5 Vision
    For documents (Word, Excel, CSV): Uses text extraction libraries

    Indexing (index=true, default):
    - Large content (>1000 tokens) is chunked and embedded for semantic retrieval
    - At query time, only relevant chunks are injected into context
    - Set index=false to skip chunking and store as single note (will be summarized if large)
    """
    from core.services.memory_chunk_service import get_memory_chunk_service

    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    org_id = get_org_id(request)

    file_service = get_file_memory_service()

    # Extract and create memory note
    result = await file_service.encode_file_for_memory(
        file_id=payload.file_id,
        user_id=user_id,
        session_id=session_id,
        org_id=org_id,
        extraction_mode=payload.extraction_mode,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))

    note = result.get("note", {})

    # Get the FULL extracted content for indexing (not the summarized note content!)
    full_content = result.get("full_content_for_indexing", "")
    original_tokens = result.get("original_token_count", 0)

    # Optionally index the content for semantic retrieval
    if payload.index and note.get("id") and full_content:
        chunk_service = get_memory_chunk_service()

        logger.info(f"Indexing FULL content ({original_tokens} tokens), not the note summary")

        index_result = await chunk_service.index_note(
            memory_note_id=str(note["id"]),
            content=full_content,  # Use FULL extracted content, not summarized note
            session_id=session_id,
            user_id=user_id,
        )

        # Add indexing info to response metadata
        if index_result.get("status") == "success":
            chunk_count = index_result.get("chunk_count")
            total_tokens = index_result.get("total_tokens")
            logger.info(f"Indexed file content: {chunk_count} chunks, {total_tokens} tokens")
            # Update note metadata to indicate it's indexed
            if "reference_metadata" not in note or note["reference_metadata"] is None:
                note["reference_metadata"] = {}
            note["reference_metadata"]["indexed"] = True
            note["reference_metadata"]["chunk_count"] = index_result.get("chunk_count")
            note["reference_metadata"]["indexed_tokens"] = index_result.get("total_tokens")
        elif index_result.get("status") == "skipped":
            logger.info(f"Indexing skipped: {index_result.get('message')}")

    return MemoryNoteResponse(**note)


@router.post(
    "/{session_id}/pin-cloud-file",
    response_model=MemoryNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def pin_cloud_file_to_memory(session_id: str, payload: CloudFilePinRequest, request: Request):
    """
    Pin a cloud file (Google Drive or OneDrive) to memory with full content extraction.

    This endpoint:
    1. Imports the file from the cloud provider
    2. Extracts content using appropriate method (Vision for images/short PDFs, text for documents)
    3. Creates a memory note with the extracted content
    4. Optionally indexes the content for semantic retrieval

    For PDFs:
    - Auto-detects page count to choose extraction method
    - Long PDFs (4+ pages) use PyMuPDF text extraction
    - Short PDFs (1-3 pages) use GPT-5 Vision
    - Override with extraction_mode='text' or 'vision'

    For images: Uses GPT-5 Vision
    For documents (Word, Excel, CSV): Uses text extraction libraries
    """
    from core.services.memory_chunk_service import get_memory_chunk_service
    from api.routers.uploads import store_file_bytes

    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    org_id = get_org_id(request)

    # Step 1: Import file from cloud provider
    if payload.source == "google_drive":
        from core.services.integration_service import (
            get_drive_credential,
            build_authorized_credentials,
        )
        from core.integrations.google_drive import get_metadata, download_file, export_document
        import mimetypes

        credential = await get_drive_credential(user_id, org_id=org_id or "")
        if not credential:
            raise HTTPException(
                status_code=404,
                detail="No Google Drive account linked. Please connect Google Drive first.",
            )

        google_credentials = await build_authorized_credentials(credential)

        try:
            metadata = await get_metadata(google_credentials, payload.cloud_file_id)
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail=f"Failed to fetch Google Drive file metadata: {exc}"
            )

        drive_mime = metadata.get("mimeType") or ""
        filename = metadata.get("name") or "Google Drive File"

        # Handle Google Workspace native formats - must be exported
        GOOGLE_EXPORT_MIME_MAP = {
            "application/vnd.google-apps.document": {
                "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "extension": ".docx",
            },
            "application/vnd.google-apps.spreadsheet": {
                "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "extension": ".xlsx",
            },
            "application/vnd.google-apps.presentation": {
                "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "extension": ".pptx",
            },
        }

        if drive_mime.startswith("application/vnd.google-apps."):
            export_target = GOOGLE_EXPORT_MIME_MAP.get(drive_mime)
            if not export_target:
                # Default to PDF for other Google formats
                export_target = {"mime": "application/pdf", "extension": ".pdf"}

            try:
                content_bytes, _ = await export_document(
                    google_credentials,
                    payload.cloud_file_id,
                    export_target["mime"],
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=400, detail=f"Failed to export Google Drive file: {exc}"
                )

            content_type = export_target["mime"]
            if not filename.lower().endswith(export_target["extension"]):
                filename = f"{filename}{export_target['extension']}"
        else:
            try:
                content_bytes, _ = await download_file(google_credentials, payload.cloud_file_id)
            except Exception as exc:
                raise HTTPException(
                    status_code=400, detail=f"Failed to download Google Drive file: {exc}"
                )
            content_type = (
                drive_mime or mimetypes.guess_type(filename)[0] or "application/octet-stream"
            )

        # Store the file
        stored = await store_file_bytes(
            user_id,
            filename,
            content_bytes,
            content_type=content_type,
            metadata={
                "source": "google_drive",
                "drive_file_id": payload.cloud_file_id,
            },
        )
        file_id = stored["id"]

    elif payload.source == "onedrive":
        from core.services.integration_service import (
            get_onedrive_credential,
            build_onedrive_access_token,
        )
        from core.integrations import onedrive as onedrive_api
        import mimetypes

        credential = await get_onedrive_credential(user_id, org_id=org_id or "")
        if not credential:
            raise HTTPException(
                status_code=404, detail="No OneDrive account linked. Please connect OneDrive first."
            )

        access_token = await build_onedrive_access_token(credential)

        try:
            content_bytes, metadata = await onedrive_api.download_file(
                access_token, payload.cloud_file_id
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to download OneDrive file: {exc}")

        filename = metadata.get("name") or "OneDrive file"
        mime_type = (
            (metadata.get("file") or {}).get("mimeType")
            or mimetypes.guess_type(filename)[0]
            or "application/octet-stream"
        )

        # Store the file
        stored = await store_file_bytes(
            user_id,
            filename,
            content_bytes,
            content_type=mime_type,
            metadata={
                "source": "onedrive",
                "onedrive_item_id": payload.cloud_file_id,
            },
        )
        file_id = stored["id"]

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported cloud source: {payload.source}")

    # Step 2: Extract content and create memory note
    file_service = get_file_memory_service()

    result = await file_service.encode_file_for_memory(
        file_id=file_id,
        user_id=user_id,
        session_id=session_id,
        org_id=org_id,
        extraction_mode=payload.extraction_mode,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))

    note = result.get("note", {})

    # Get the FULL extracted content for indexing
    full_content = result.get("full_content_for_indexing", "")
    original_tokens = result.get("original_token_count", 0)

    # Step 3: Optionally index the content for semantic retrieval
    if payload.index and note.get("id") and full_content:
        chunk_service = get_memory_chunk_service()

        logger.info(f"Indexing cloud file content ({original_tokens} tokens) from {payload.source}")

        index_result = await chunk_service.index_note(
            memory_note_id=str(note["id"]),
            content=full_content,
            session_id=session_id,
            user_id=user_id,
        )

        if index_result.get("status") == "success":
            logger.info(
                f"Indexed cloud file: {index_result.get('chunk_count')} chunks, "
                f"{index_result.get('total_tokens')} tokens"
            )
            if "reference_metadata" not in note or note["reference_metadata"] is None:
                note["reference_metadata"] = {}
            note["reference_metadata"]["indexed"] = True
            note["reference_metadata"]["chunk_count"] = index_result.get("chunk_count")
            note["reference_metadata"]["indexed_tokens"] = index_result.get("total_tokens")
            note["reference_metadata"]["cloud_source"] = payload.source
        elif index_result.get("status") == "skipped":
            logger.info(f"Indexing skipped: {index_result.get('message')}")

    return MemoryNoteResponse(**note)


@router.post(
    "/{session_id}/pin-sec-filing",
    response_model=MemoryNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def pin_sec_filing_to_memory(session_id: str, payload: SECFilingPinRequest, request: Request):
    """
    Pin an SEC filing to memory with full content extraction and indexing.
    
    Fetches the SEC filing content, creates a memory note with metadata,
    then chunks and embeds the full content for semantic retrieval.
    
    This is the proper way to add SEC filings to context - they're too long
    for direct injection, so we chunk and retrieve relevant sections at query time.
    """
    from core.services.memory_chunk_service import get_memory_chunk_service
    from core.filings.sec_edgar import SECEdgarClient
    from bs4 import BeautifulSoup
    import re
    
    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    org_id = get_org_id(request)
    
    # Step 1: Fetch SEC filing content
    sec_client = SECEdgarClient()
    
    try:
        # Resolve the filing URL if it's an index page
        filing_url = payload.link
        base_url = None
        
        if '-index.htm' in filing_url.lower() or not filing_url.lower().endswith(('.htm', '.html')):
            # It's an index page, find the primary document
            base_url = "/".join(filing_url.rstrip('/').split("/")[:-1]) if filing_url.lower().endswith('.htm') else filing_url.rstrip('/')
            doc_filename = await sec_client.find_primary_document(base_url)
            if doc_filename:
                filing_url = f"{base_url}/{doc_filename}"
        
        # Fetch the filing content
        html_content = await sec_client.fetch_filing(filing_url)
        
        if not html_content:
            raise HTTPException(status_code=502, detail="Failed to fetch SEC filing content")
        
    except Exception as e:
        logger.error(f"SEC filing fetch error: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch SEC filing: {str(e)}")
    
    # Step 2: Extract text from HTML
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'head', 'meta', 'link']):
            element.decompose()
        
        # Get text and clean it up
        text_content = soup.get_text(separator='\n')
        
        # Clean up whitespace
        lines = [line.strip() for line in text_content.split('\n')]
        text_content = '\n'.join(line for line in lines if line)
        
        # Remove excessive newlines
        text_content = re.sub(r'\n{3,}', '\n\n', text_content)
        
    except Exception as e:
        logger.error(f"HTML parsing error: {e}")
        # Fallback: use raw HTML with tags stripped
        text_content = re.sub(r'<[^>]+>', ' ', html_content)
        text_content = re.sub(r'\s+', ' ', text_content).strip()
    
    # Count tokens
    try:
        import tiktoken
        enc = tiktoken.get_encoding('cl100k_base')
        token_count = len(enc.encode(text_content))
    except Exception:
        token_count = len(text_content) // 4
    
    logger.info(f"SEC filing extracted: {token_count} tokens from {payload.title}")
    
    # Step 3: Create memory note with filing metadata
    service = get_memory_service()
    
    # Create a summary for the note content (first ~500 chars + metadata)
    summary_text = text_content[:500] + "..." if len(text_content) > 500 else text_content
    note_content = f"""**SEC Filing: {payload.title}**

Form: {payload.form_type or 'Unknown'}
Filed: {payload.filing_date or 'Unknown'}
Ticker: {payload.ticker or 'N/A'}
CIK: {payload.cik or 'N/A'}

{summary_text}

[Full content indexed for semantic search - {token_count:,} tokens]
"""
    
    result = await service.create_note(
        user_id=user_id,
        session_id=session_id,
        content=note_content,
        section="context",
        priority=7,  # High priority for SEC filings
        source="tool",
        reference_type="sec_filing",
        reference_metadata={
            "title": payload.title,
            "form_type": payload.form_type,
            "filing_date": payload.filing_date,
            "cik": payload.cik,
            "accession_number": payload.accession_number,
            "ticker": payload.ticker,
            "url": payload.link,
            "token_count": token_count,
        },
        org_id=org_id,
    )
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    
    note = result.get("note", {})
    
    # Step 4: Index the full filing content for semantic retrieval
    if payload.index and note.get("id") and text_content:
        chunk_service = get_memory_chunk_service()
        
        logger.info(f"Indexing SEC filing: {token_count} tokens")
        
        index_result = await chunk_service.index_note(
            memory_note_id=str(note["id"]),
            content=text_content,  # Full extracted text
            session_id=session_id,
            user_id=user_id,
        )
        
        if index_result.get("status") == "success":
            chunk_count = index_result.get("chunk_count")
            indexed_tokens = index_result.get("total_tokens")
            logger.info(f"Indexed SEC filing: {chunk_count} chunks, {indexed_tokens} tokens")
            
            if "reference_metadata" not in note or note["reference_metadata"] is None:
                note["reference_metadata"] = {}
            note["reference_metadata"]["indexed"] = True
            note["reference_metadata"]["chunk_count"] = chunk_count
            note["reference_metadata"]["indexed_tokens"] = indexed_tokens
        elif index_result.get("status") == "skipped":
            logger.info(f"Indexing skipped: {index_result.get('message')}")
        else:
            logger.warning(f"Indexing failed: {index_result.get('message')}")
    
    return MemoryNoteResponse(**note)


@router.post(
    "/{session_id}/pin-13f-filing",
    response_model=MemoryNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def pin_13f_filing_to_memory(session_id: str, payload: ThirteenFPinRequest, request: Request):
    """
    Pin a 13F filing to memory using structured holdings data.
    
    Unlike regular SEC filings, 13F files are XML-based and don't parse well with HTML extraction.
    This endpoint uses the pre-fetched holdings data from FMP to create indexable text content.
    """
    from core.services.memory_chunk_service import get_memory_chunk_service
    
    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    org_id = get_org_id(request)
    
    # Build text content from holdings data
    holdings_text = []
    holdings_text.append(f"# 13F-HR Filing: {payload.institution_name}")
    holdings_text.append(f"Quarter: Q{payload.quarter} {payload.year}")
    holdings_text.append(f"CIK: {payload.cik}")
    holdings_text.append(f"Total Portfolio Value: ${payload.total_value:,.0f}")
    holdings_text.append(f"Number of Holdings: {payload.holdings_count}")
    holdings_text.append("")
    holdings_text.append("## Holdings")
    holdings_text.append("")
    
    # Add top holdings with details (use 'or' to handle None values)
    for i, h in enumerate(payload.holdings[:100], 1):  # Limit to top 100
        symbol = h.get('symbol') or 'N/A'
        name = h.get('securityName') or ''
        shares = h.get('shares') or 0
        value = h.get('value') or 0
        weight = h.get('weight') or 0
        holdings_text.append(f"{i}. **{symbol}** - {name}")
        holdings_text.append(f"   Shares: {shares:,} | Value: ${value:,.0f} | Weight: {weight*100:.2f}%")
        holdings_text.append("")
    
    text_content = "\n".join(holdings_text)
    
    # Count tokens
    try:
        import tiktoken
        enc = tiktoken.get_encoding('cl100k_base')
        token_count = len(enc.encode(text_content))
    except Exception:
        token_count = len(text_content) // 4
    
    logger.info(f"13F filing content created: {token_count} tokens for {payload.institution_name}")
    
    # Create memory note
    service = get_memory_service()
    
    # Summary for note content (use 'or' to handle None values)
    top_holdings_preview = ", ".join([h.get('symbol') or '?' for h in payload.holdings[:5]])
    note_content = f"""**13F-HR Filing: {payload.institution_name}**

Q{payload.quarter} {payload.year} | CIK: {payload.cik}
Total Value: ${payload.total_value/1e9:.2f}B | {payload.holdings_count} holdings

Top holdings: {top_holdings_preview}...

[Full holdings indexed for semantic search - {token_count:,} tokens]
"""
    
    result = await service.create_note(
        user_id=user_id,
        session_id=session_id,
        content=note_content,
        section="context",
        priority=7,
        source="tool",
        reference_type="sec_filing",
        reference_metadata={
            "title": payload.title,
            "form_type": "13F-HR",
            "institution_name": payload.institution_name,
            "cik": payload.cik,
            "year": payload.year,
            "quarter": payload.quarter,
            "total_value": payload.total_value,
            "holdings_count": payload.holdings_count,
            "url": payload.sec_link,
            "token_count": token_count,
        },
        org_id=org_id,
    )
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    
    note = result.get("note", {})
    
    # Index the holdings content
    if payload.index and note.get("id") and text_content:
        chunk_service = get_memory_chunk_service()
        
        logger.info(f"Indexing 13F filing: {token_count} tokens")
        
        index_result = await chunk_service.index_note(
            memory_note_id=str(note["id"]),
            content=text_content,
            session_id=session_id,
            user_id=user_id,
        )
        
        if index_result.get("status") == "success":
            chunk_count = index_result.get("chunk_count")
            indexed_tokens = index_result.get("total_tokens")
            logger.info(f"Indexed 13F filing: {chunk_count} chunks, {indexed_tokens} tokens")
            
            if "reference_metadata" not in note or note["reference_metadata"] is None:
                note["reference_metadata"] = {}
            note["reference_metadata"]["indexed"] = True
            note["reference_metadata"]["chunk_count"] = chunk_count
            note["reference_metadata"]["indexed_tokens"] = indexed_tokens
    
    return MemoryNoteResponse(**note)


@router.post(
    "/{session_id}/pin-transcript",
    response_model=MemoryNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def pin_transcript_to_memory(session_id: str, payload: TranscriptPinRequest, request: Request):
    """
    Pin an earnings call transcript to memory with chunking/indexing.
    
    Fetches the transcript content from FMP API and indexes it for semantic retrieval.
    """
    from core.services.memory_chunk_service import get_memory_chunk_service
    import aiohttp
    import os
    
    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    org_id = get_org_id(request)
    
    FMP_API_KEY = os.environ.get("FMP_API_KEY")
    if not FMP_API_KEY:
        raise HTTPException(status_code=500, detail="FMP_API_KEY not configured")
    
    # Fetch transcript from FMP
    url = f"https://financialmodelingprep.com/api/v3/earning_call_transcript/{payload.ticker}"
    params = {
        "year": payload.year,
        "quarter": payload.quarter,
        "apikey": FMP_API_KEY,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=30) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"FMP transcript API error: {response.status} - {error_text}")
                    raise HTTPException(status_code=response.status, detail=f"FMP API error: {error_text[:200]}")
                data = await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"FMP connection error: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to FMP API")
    
    if not data or not isinstance(data, list) or len(data) == 0:
        raise HTTPException(status_code=404, detail=f"No transcript found for {payload.ticker} Q{payload.quarter} {payload.year}")
    
    transcript_data = data[0]
    transcript_content = transcript_data.get("content", "")
    transcript_date = transcript_data.get("date", "")
    
    if not transcript_content:
        raise HTTPException(status_code=404, detail="Transcript content is empty")
    
    # Count tokens
    try:
        import tiktoken
        enc = tiktoken.get_encoding('cl100k_base')
        token_count = len(enc.encode(transcript_content))
    except Exception:
        token_count = len(transcript_content) // 4
    
    title = payload.title or f"{payload.ticker} Q{payload.quarter} {payload.year} Earnings Call"
    logger.info(f"Transcript fetched: {token_count} tokens for {title}")
    
    # Create memory note
    service = get_memory_service()
    
    # Summary for note content
    summary_text = transcript_content[:500] + "..." if len(transcript_content) > 500 else transcript_content
    note_content = f"""**Earnings Call: {title}**

Ticker: {payload.ticker}
Date: {transcript_date}
Quarter: Q{payload.quarter} {payload.year}

{summary_text}

[Full transcript indexed for semantic search - {token_count:,} tokens]
"""
    
    result = await service.create_note(
        user_id=user_id,
        session_id=session_id,
        content=note_content,
        section="context",
        priority=7,
        source="tool",
        reference_type="transcript",
        reference_metadata={
            "title": title,
            "ticker": payload.ticker,
            "year": payload.year,
            "quarter": payload.quarter,
            "date": transcript_date,
            "token_count": token_count,
        },
        org_id=org_id,
    )
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    
    note = result.get("note", {})
    
    # Index the transcript content
    if payload.index and note.get("id") and transcript_content:
        chunk_service = get_memory_chunk_service()
        
        logger.info(f"Indexing transcript: {token_count} tokens")
        
        index_result = await chunk_service.index_note(
            memory_note_id=str(note["id"]),
            content=transcript_content,
            session_id=session_id,
            user_id=user_id,
        )
        
        if index_result.get("status") == "success":
            chunk_count = index_result.get("chunk_count")
            indexed_tokens = index_result.get("total_tokens")
            logger.info(f"Indexed transcript: {chunk_count} chunks, {indexed_tokens} tokens")
            
            if "reference_metadata" not in note or note["reference_metadata"] is None:
                note["reference_metadata"] = {}
            note["reference_metadata"]["indexed"] = True
            note["reference_metadata"]["chunk_count"] = chunk_count
            note["reference_metadata"]["indexed_tokens"] = indexed_tokens
    
    return MemoryNoteResponse(**note)


@router.post(
    "/{session_id}/portfolio",
    response_model=MemoryNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def attach_portfolio_reference(
    session_id: str, payload: PortfolioReferenceCreate, request: Request
):
    """
    Attach a portfolio reference to memory.

    Stores what to remember about a portfolio being discussed.
    """
    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    org_id = get_org_id(request)
    service = get_memory_service()

    result = await service.create_note(
        user_id=user_id,
        session_id=session_id,
        content=payload.note,
        section=payload.section,
        priority=payload.priority,
        source="user",
        reference_type="portfolio",
        reference_id=payload.portfolio_id,
        reference_metadata={},
        org_id=org_id,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))

    return MemoryNoteResponse(**result["note"])


@router.post(
    "/{session_id}/chart", response_model=MemoryNoteResponse, status_code=status.HTTP_201_CREATED
)
async def attach_chart_reference(session_id: str, payload: ChartReferenceCreate, request: Request):
    """
    Attach a chart reference to memory.

    Stores what to remember about a chart generated in the conversation.
    """
    session_id = validate_session_id(session_id)
    user_id = get_user_id(request)
    org_id = get_org_id(request)
    service = get_memory_service()

    result = await service.create_note(
        user_id=user_id,
        session_id=session_id,
        content=payload.note,
        section=payload.section,
        priority=payload.priority,
        source="user",
        reference_type="chart",
        reference_metadata={
            "chart_config": payload.chart_config,
            "data_summary": payload.data_summary,
        },
        org_id=org_id,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))

    return MemoryNoteResponse(**result["note"])
