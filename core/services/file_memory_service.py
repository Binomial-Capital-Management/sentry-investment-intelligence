"""
File Memory Service Layer

Encodes uploaded files for memory notebook storage using GPT-5 Vision for PDFs/images
and text extraction for documents.

See docs/memory-notebook-feature-spec.md for full specification.
"""

import os
import logging
import tempfile
import asyncio
from typing import Dict, Any, Optional, Set
from uuid import UUID

logger = logging.getLogger(__name__)


class FileMemoryService:
    """Service layer for encoding files and adding them to memory notebook."""
    
    IMAGE_EXTENSIONS: Set[str] = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
    
    VISION_PROMPT = """Analyze this image comprehensively for reference:

1. DESCRIPTION: Provide a detailed description of what the image shows (objects, people, scenes, colors, composition)
2. TEXT: If any text is visible, transcribe it verbatim
3. TABLES/DATA: If tables or structured data are present, format as markdown
4. CHARTS/GRAPHS: If charts are present, describe type, axes, trends, and key data points
5. NUMBERS: Extract any numerical values with context
6. KEY DETAILS: Note any logos, brands, dates, locations, or other identifying information

Be thorough and descriptive - this will be used as reference material for future analysis."""
    
    def __init__(self):
        """Initialize service with config values."""
        from core.config import get_config
        cfg = get_config()
        
        # Load extraction settings from config
        self.max_tokens = getattr(cfg, 'file_memory_max_tokens', 5000)
        self.vision_page_limit = getattr(cfg, 'file_memory_vision_page_limit', 5)
        self.pdf_text_threshold = getattr(cfg, 'file_memory_pdf_text_threshold', 3)
        self.pdf_min_chars_per_page = getattr(cfg, 'file_memory_pdf_min_chars_per_page', 100)
    
    def _safe_token_count(self, text: str) -> int:
        """Approximate token count with fallback."""
        if not text:
            return 0
        try:
            import tiktoken
            from core.config import get_config
            cfg = get_config()
            encoding_name = getattr(cfg, 'sec_tokenizer_encoding', 'cl100k_base')
            enc = tiktoken.get_encoding(encoding_name)
            return len(enc.encode(text))
        except Exception:
            return max(1, len(text) // 4)
    
    def _detect_pdf_extraction_mode(self, pdf_bytes: bytes) -> str:
        """
        Decide extraction mode based on page count.
        
        Long PDFs (> PDF_TEXT_THRESHOLD pages) use text extraction because
        Vision only processes up to VISION_PAGE_LIMIT pages.
        
        Args:
            pdf_bytes: PDF file content as bytes
            
        Returns:
            'text' for PyMuPDF text extraction, 'vision' for GPT-5 Vision
        """
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_count = len(doc)
            doc.close()
            
            logger.info(f"PDF has {page_count} pages, threshold is {self.pdf_text_threshold}")
            
            if page_count > self.pdf_text_threshold:
                return 'text'
            else:
                return 'vision'
                
        except Exception as e:
            logger.warning(f"Failed to detect PDF page count: {e}, defaulting to vision")
            return 'vision'
    
    def _extract_pdf_text(self, pdf_bytes: bytes) -> tuple[str, bool]:
        """
        Extract full text from PDF using PyMuPDF.
        
        Args:
            pdf_bytes: PDF file content as bytes
            
        Returns:
            Tuple of (extracted_text, is_text_sparse)
            is_text_sparse is True if average chars per page < PDF_MIN_CHARS_PER_PAGE
        """
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_parts = []
            total_chars = 0
            page_count = len(doc)
            
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(f"=== Page {page_num + 1} ===\n{page_text}")
                    total_chars += len(page_text)
            
            doc.close()
            
            # Check if text extraction yielded meaningful content
            avg_chars_per_page = total_chars / max(1, page_count)
            is_sparse = avg_chars_per_page < self.pdf_min_chars_per_page
            
            if is_sparse:
                logger.info(f"PDF text extraction sparse: {avg_chars_per_page:.0f} chars/page avg")
            else:
                logger.info(f"PDF text extraction successful: {total_chars} total chars, {page_count} pages")
            
            return "\n\n".join(text_parts), is_sparse
            
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return "", True
    
    async def _load_file_record(
        self, 
        file_id: str, 
        user_id: str,
        org_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Load file record from database.
        
        Args:
            file_id: File UUID
            user_id: User ID for RLS context
            org_id: Organization ID for workspace context
            
        Returns:
            File record dict or None
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        
        config = get_config()
        if not config.enable_postgres:
            logger.warning("PostgreSQL not enabled, cannot load file record")
            return None
        
        try:
            pg = await get_postgres_rls_client()
            
            async with pg.acquire_with_org_context(user_id, org_id if org_id else None) as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, user_id, org_id, original_name, stored_key, content_type, size_bytes
                    FROM files 
                    WHERE id = $1
                    """,
                    UUID(file_id)
                )
                
                if not row:
                    return None
                
                return {
                    "id": str(row["id"]),
                    "user_id": row["user_id"],
                    "org_id": row["org_id"],
                    "original_name": row["original_name"],
                    "stored_key": row["stored_key"],
                    "content_type": row["content_type"],
                    "size_bytes": row["size_bytes"]
                }
                
        except Exception as e:
            logger.error(f"Failed to load file record {file_id}: {e}")
            return None
    
    async def _read_file_bytes(self, file_record: Dict[str, Any]) -> Optional[bytes]:
        """
        Read file bytes from storage. Tries local first, falls back to S3.
        
        Args:
            file_record: File record from database
            
        Returns:
            File content as bytes or None
        """
        stored_key = file_record.get("stored_key")
        if not stored_key:
            return None
        
        upload_dir = os.getenv("UPLOAD_DIR", "/tmp/uploads")
        safe_key = stored_key.replace("/", "_")
        file_path = os.path.join(upload_dir, safe_key)
        
        # Try local first
        try:
            import aiofiles
            async with aiofiles.open(file_path, "rb") as f:
                return await f.read()
        except FileNotFoundError:
            pass  # Fall through to S3
        except Exception as e:
            logger.error(f"Failed to read file bytes locally: {e}")
        
        # Try S3 fallback
        try:
            from core.config import get_config
            cfg = get_config()
            if cfg.artifact_storage_backend == "s3" and cfg.artifact_s3_bucket:
                import boto3
                import asyncio
                s3 = boto3.client("s3", region_name=cfg.artifact_s3_region)
                s3_key = f"uploads/{safe_key}"
                response = await asyncio.to_thread(
                    s3.get_object, Bucket=cfg.artifact_s3_bucket, Key=s3_key
                )
                content = await asyncio.to_thread(response["Body"].read)
                logger.info(f"Read file from S3: {s3_key}")
                return content
        except Exception as e:
            logger.error(f"File not found in S3 either: {e}")
        
        logger.error(f"File not found on disk or S3: {file_path}")
        return None
    
    async def _save_temp_file(self, content: bytes, extension: str) -> str:
        """
        Save bytes to temporary file for vision processing.
        
        Args:
            content: File bytes
            extension: File extension including dot
            
        Returns:
            Path to temporary file
        """
        fd, temp_path = tempfile.mkstemp(suffix=extension)
        try:
            import aiofiles
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(content)
            return temp_path
        finally:
            os.close(fd)
    
    async def _summarize_content(self, content: str, detailed: bool = False) -> str:
        """
        Summarize content that exceeds token budget using LLM.
        
        Args:
            content: Full content text
            detailed: If True, create a more detailed summary (~800-1000 tokens)
                      If False, create a brief summary (~200 tokens)
            
        Returns:
            Summarized content
        """
        try:
            from openai import AsyncOpenAI
            
            from core.config import get_config
            cfg = get_config()
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                # Fallback: truncate
                logger.warning("No OpenAI API key for summarization, truncating")
                return content[:self.max_tokens * 4]
            
            client = AsyncOpenAI(api_key=api_key)
            summarization_model = getattr(cfg, 'summarization_model', 'gpt-4o-mini')
            
            if detailed:
                # Detailed summary for UI display when indexing is enabled
                system_prompt = """You are a document summarizer for financial professionals. Create a DETAILED summary that includes:

1. **Document Overview**: Type, parties involved, dates, total pages/length
2. **Key Numbers**: All monetary amounts, percentages, ratios, quantities
3. **Important Dates**: Deadlines, effective dates, milestones
4. **Named Entities**: Companies, people, locations, products mentioned
5. **Section Breakdown**: Brief description of each major section/article
6. **Critical Terms**: Key definitions, conditions, clauses that matter
7. **Action Items**: Obligations, requirements, next steps

Be thorough - this summary helps users quickly understand the document's contents.
Output should be 800-1000 tokens, well-structured with markdown formatting."""
                max_tokens = 1200
            else:
                # Brief summary for non-indexed notes
                system_prompt = "You are a document summarizer. Create a comprehensive summary that preserves all key information, numbers, dates, and named entities. Output should be under 4000 tokens."
                max_tokens = 4000
            
            response = await client.chat.completions.create(
                model=summarization_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Summarize this document:\n\n{content[:50000]}"
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            
            return response.choices[0].message.content or content[:self.max_tokens * 4]
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            # Fallback: truncate
            return content[:self.max_tokens * 4]
    
    async def _extract_pdf_content(
        self,
        file_bytes: bytes,
        extraction_mode: Optional[str]
    ) -> Dict[str, Any]:
        """
        Extract content from PDF using text or vision.
        
        Args:
            file_bytes: PDF file content
            extraction_mode: Optional override ('text' or 'vision')
            
        Returns:
            Dict with 'content', 'method', or 'error'
        """
        # Determine extraction mode
        if extraction_mode in ('text', 'vision'):
            pdf_mode = extraction_mode
            logger.info(f"PDF extraction mode forced to: {pdf_mode}")
        else:
            pdf_mode = self._detect_pdf_extraction_mode(file_bytes)
            logger.info(f"PDF extraction mode auto-detected: {pdf_mode}")
        
        extraction_method = pdf_mode
        extracted_content = ""
        
        if pdf_mode == 'text':
            extraction_method = "text"
            extracted_content, is_sparse = self._extract_pdf_text(file_bytes)
            
            if is_sparse and extracted_content.strip():
                logger.info("Text extraction sparse, falling back to vision for first pages")
                extraction_method = "text_sparse"
            elif is_sparse:
                logger.info("No text extracted, using vision instead")
                pdf_mode = 'vision'
        
        if pdf_mode == 'vision':
            extraction_method = "vision"
            temp_path = await self._save_temp_file(file_bytes, ".pdf")
            try:
                from core.agents.vision_tools import analyze_pdf_with_gpt5
                
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: analyze_pdf_with_gpt5(temp_path, self.vision_page_limit)
                )
                
                if result.get("success") and result.get("results"):
                    pages = result["results"]
                    extracted_content = "\n\n".join(
                        f"=== Page {p['page']} ===\n{p.get('analysis', '')}"
                        for p in pages if p.get("analysis")
                    )
                elif result.get("error"):
                    return {"error": f"Vision analysis failed: {result['error']}"}
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        return {"content": extracted_content, "method": extraction_method}
    
    async def _extract_image_content(
        self,
        file_bytes: bytes,
        ext: str
    ) -> Dict[str, Any]:
        """
        Extract content from image using GPT-5 Vision.
        
        Args:
            file_bytes: Image file content
            ext: File extension
            
        Returns:
            Dict with 'content', 'method', or 'error'
        """
        temp_path = await self._save_temp_file(file_bytes, ext or ".jpg")
        try:
            from core.agents.vision_tools import analyze_image_with_gpt5
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: analyze_image_with_gpt5(temp_path, self.VISION_PROMPT)
            )
            
            if result.get("success") and result.get("analysis"):
                return {"content": result["analysis"], "method": "vision"}
            elif result.get("error"):
                return {"error": f"Vision analysis failed: {result['error']}"}
            else:
                return {"content": "", "method": "vision"}
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    async def _apply_token_budget(
        self,
        extracted_content: str,
        will_be_indexed: bool
    ) -> tuple[str, bool, int]:
        """
        Apply token budget, summarizing if needed.
        
        Args:
            extracted_content: Full extracted text
            will_be_indexed: Whether content will be chunked
            
        Returns:
            Tuple of (note_content, was_summarized, note_token_count)
        """
        original_token_count = self._safe_token_count(extracted_content)
        note_content = extracted_content
        was_summarized = False
        
        if original_token_count > self.max_tokens:
            if will_be_indexed:
                logger.info(f"Content exceeds budget ({original_token_count} > {self.max_tokens}), creating detailed summary")
                note_content = await self._summarize_content(extracted_content, detailed=True)
            else:
                logger.info(f"Content exceeds budget ({original_token_count} > {self.max_tokens}), summarizing")
                note_content = await self._summarize_content(extracted_content, detailed=False)
            was_summarized = True
        
        note_token_count = self._safe_token_count(note_content)
        return note_content, was_summarized, note_token_count
    
    async def _create_file_memory_note(
        self,
        file_record: Dict[str, Any],
        note_content: str,
        extraction_method: str,
        original_token_count: int,
        note_token_count: int,
        was_summarized: bool,
        will_be_indexed: bool,
        user_id: str,
        session_id: str,
        file_id: str,
        org_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Create the memory note record.
        
        Returns:
            Created note or error dict
        """
        from core.services.memory_service import get_memory_service
        
        content_type = file_record.get("content_type", "")
        formatted_content = f"**File: {file_record.get('original_name', 'Unknown')}**\n\n{note_content}"
        
        return await get_memory_service().create_note(
            user_id=user_id,
            session_id=session_id,
            content=formatted_content,
            section="context",
            priority=7,
            source="tool",
            reference_type="file",
            reference_id=file_id,
            reference_metadata={
                "filename": file_record.get("original_name"),
                "content_type": content_type,
                "extraction_method": extraction_method,
                "note_token_count": note_token_count,
                "original_token_count": original_token_count,
                "was_summarized": was_summarized,
                "will_be_indexed": will_be_indexed,
                "original_size_bytes": file_record.get("size_bytes")
            },
            org_id=org_id
        )
    
    async def encode_file_for_memory(
        self,
        file_id: str,
        user_id: str,
        session_id: str,
        org_id: Optional[str] = None,
        extraction_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Encode a file and create a memory note for it.
        
        Routes to appropriate extractor based on file type:
        - PDFs: Text extraction or GPT-5 Vision based on page count
        - Images: GPT-5 Vision
        - Documents: Text extraction libraries
        
        Args:
            file_id: UUID of the uploaded file
            user_id: User ID for RLS context
            session_id: Chat session UUID
            org_id: Optional organization ID
            extraction_mode: Optional override ('text' or 'vision')
            
        Returns:
            Created memory note or error dict
        """
        # 1. Load and validate file
        file_record = await self._load_file_record(file_id, user_id, org_id)
        if not file_record:
            return {"status": "error", "message": "File not found or access denied"}
        
        file_bytes = await self._read_file_bytes(file_record)
        if not file_bytes:
            return {"status": "error", "message": "Failed to read file from storage"}
        
        # 2. Extract content based on file type
        filename = file_record.get("original_name", "").lower()
        content_type = file_record.get("content_type", "")
        ext = os.path.splitext(filename)[1].lower() if filename else ""
        
        if filename.endswith('.pdf') or 'pdf' in content_type.lower():
            result = await self._extract_pdf_content(file_bytes, extraction_mode)
        elif ext in self.IMAGE_EXTENSIONS or content_type.startswith('image/'):
            result = await self._extract_image_content(file_bytes, ext)
        else:
            from core.files.ingestion_worker import _extract_text_from_file
            result = {"content": _extract_text_from_file(file_bytes, content_type, filename), "method": "text"}
        
        if result.get("error"):
            return {"status": "error", "message": result["error"]}
        
        extracted_content = result["content"]
        extraction_method = result["method"]
        
        # 3. Validate extraction
        if not extracted_content or not extracted_content.strip():
            return {"status": "error", "message": "No content could be extracted from file"}
        
        # 4. Apply token budget
        from core.config import get_config
        cfg = get_config()
        original_token_count = self._safe_token_count(extracted_content)
        chunk_threshold = getattr(cfg, 'memory_chunk_threshold', 1000)
        will_be_indexed = original_token_count > chunk_threshold
        
        note_content, was_summarized, note_token_count = await self._apply_token_budget(
            extracted_content, will_be_indexed
        )
        
        # 5. Create memory note
        note_result = await self._create_file_memory_note(
            file_record, note_content, extraction_method,
            original_token_count, note_token_count, was_summarized, will_be_indexed,
            user_id, session_id, file_id, org_id
        )
        
        # 6. Include full content for indexing
        if note_result.get("status") == "success":
            note_result["full_content_for_indexing"] = extracted_content
            note_result["original_token_count"] = original_token_count
        
        return note_result


# Singleton instance
_file_memory_service: Optional[FileMemoryService] = None


def get_file_memory_service() -> FileMemoryService:
    """Get or create the file memory service singleton."""
    global _file_memory_service
    if _file_memory_service is None:
        _file_memory_service = FileMemoryService()
    return _file_memory_service

