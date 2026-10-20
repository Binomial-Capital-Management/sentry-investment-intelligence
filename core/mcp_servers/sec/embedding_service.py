"""
Embedding service for SEC filings
Handles text chunking and embedding generation with retries
"""

import asyncio
import re
import logging
import time
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI
import voyageai

logger = logging.getLogger(__name__)

# Import metrics if available
try:
    from core.monitoring.metrics import metrics_collector
except ImportError:
    metrics_collector = None


class EmbeddingService:
    """Generate embeddings for SEC filing chunks"""
    
    def __init__(self, config):
        """
        Initialize embedding service
        
        Args:
            config: Configuration object with embedding settings
        """
        self.config = config
        self.embedding_provider = config.sec_embedding_provider
        self.embedding_model = config.sec_embedding_model
        self.embedding_dims = config.sec_embedding_dims
        self.batch_size = config.sec_embedding_batch_size
        self.max_retries = config.sec_embed_max_retries
        self.base_delay = config.sec_embed_base_delay
        self.timeout = config.sec_embed_timeout_s
        
        # Circuit breaker for embedding service
        self.circuit_breaker_failures = 0
        self.circuit_breaker_threshold = 3  # Open after 3 consecutive failures
        self.circuit_breaker_timeout = 60  # Pause for 60 seconds when open
        self.circuit_breaker_open_until = 0  # Timestamp when breaker can close
        
        # Initialize clients based on provider
        if self.embedding_provider == 'voyage':
            self.voyage_client = voyageai.AsyncClient(api_key=config.voyage_api_key)
            self.openai_client = None
        else:
            self.openai_client = AsyncOpenAI(api_key=config.openai_api_key)
            self.voyage_client = None
    
    def chunk_filing(self, text: str, chunk_size: int = 1000, overlap: float = 0.2) -> List[Dict]:
        """
        Chunk filing HTML using block-based parsing with BeautifulSoup
        Dynamically discovers content blocks and merges micro blocks
        """
        chunks = []
        
        # Try to parse as HTML with BeautifulSoup
        try:
            from bs4 import BeautifulSoup
            import tiktoken
            
            # Get tokenizer for measuring chunk sizes
            if "text-embedding-3" in self.embedding_model:
                encoding = tiktoken.get_encoding("cl100k_base")
            elif "voyage" in self.embedding_model:
                encoding = tiktoken.get_encoding("cl100k_base")
            else:
                encoding = tiktoken.encoding_for_model(self.embedding_model)
                
        except ImportError as e:
            logger.warning(f"Required library not installed: {e}. Falling back to text-based chunking")
            return self._fallback_text_chunking(text, chunk_size, overlap)
        
        # Parse HTML with lxml parser for speed
        soup = BeautifulSoup(text, 'lxml')
        
        # Extract text blocks from semantic elements
        blocks = []
        block_elements = ['p', 'li', 'table', 'section', 'article', 'h1', 'h2', 'h3', 'h4']
        
        for element in soup.find_all(block_elements):
            if element.name == 'table':
                # Extract table content more cleanly
                rows = element.find_all('tr')
                table_lines = []
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    # Get non-empty cell text
                    cell_texts = [cell.get_text(strip=True) for cell in cells if cell.get_text(strip=True)]
                    if cell_texts:
                        table_lines.append(' | '.join(cell_texts))
                
                # Only keep tables with actual content (not just empty cells)
                if table_lines and len(table_lines) > 1:
                    block_text = '\n'.join(table_lines)
                else:
                    continue  # Skip empty/sparse tables
            else:
                block_text = element.get_text(strip=True)
            
            # Skip very short or empty blocks
            if not block_text or len(block_text) < 30:
                continue
                
            # Calculate token count for this block
            token_count = len(encoding.encode(block_text))
            
            blocks.append({
                'text': block_text,
                'tokens': token_count,
                'tag': element.name,
                'is_header': element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
            })
        
        # If no blocks found, fall back to text parsing
        if not blocks:
            logger.info("No HTML blocks found, using text-based chunking")
            return self._fallback_text_chunking(text, chunk_size, overlap)
        
        # Merge micro blocks (<40 tokens) with next block to avoid header-only chunks
        merged_blocks = []
        i = 0
        while i < len(blocks):
            current_block = blocks[i]
            
            # Merge small blocks more aggressively to reduce chunk count
            if current_block['tokens'] < 1500 and i < len(blocks) - 1:
                next_block = blocks[i + 1]
                merged_text = current_block['text'] + ' ' + next_block['text']
                merged_tokens = len(encoding.encode(merged_text))
                
                merged_blocks.append({
                    'text': merged_text,
                    'tokens': merged_tokens,
                    'tag': next_block['tag'],  # Use the main block's tag
                    'is_header': False  # Merged blocks are content
                })
                i += 2  # Skip both blocks
            else:
                merged_blocks.append(current_block)
                i += 1
        
        # Group blocks into chunks respecting token limits
        current_chunk = []
        current_tokens = 0
        
        for block in merged_blocks:
            # If adding this block exceeds chunk_size, save current chunk
            if current_tokens + block['tokens'] > chunk_size and current_chunk:
                chunk_text = ' '.join([b['text'] for b in current_chunk])
                
                # Calculate metadata for reranking
                metadata = self._calculate_chunk_metadata(chunk_text, current_chunk)
                
                chunks.append({
                    'text': chunk_text,
                    'section': self._detect_section(chunk_text),
                    'metadata': metadata
                })
                
                # Start new chunk with overlap
                if overlap > 0 and len(current_chunk) > 1:
                    # Keep last portion of current chunk for overlap
                    overlap_blocks = []
                    overlap_tokens = 0
                    for b in reversed(current_chunk):
                        overlap_tokens += b['tokens']
                        overlap_blocks.insert(0, b)
                        if overlap_tokens >= chunk_size * overlap:
                            break
                    current_chunk = overlap_blocks
                    current_tokens = overlap_tokens
                else:
                    current_chunk = []
                    current_tokens = 0
            
            # Add block to current chunk
            current_chunk.append(block)
            current_tokens += block['tokens']
        
        # Add final chunk if exists
        if current_chunk:
            chunk_text = ' '.join([b['text'] for b in current_chunk])
            metadata = self._calculate_chunk_metadata(chunk_text, current_chunk)
            
            chunks.append({
                'text': chunk_text,
                'section': self._detect_section(chunk_text),
                'metadata': metadata
            })
        
        logger.info(f"Created {len(chunks)} chunks from {len(blocks)} HTML blocks (merged from {len(merged_blocks)})")
        return chunks
    
    def _calculate_chunk_metadata(self, text: str, blocks: List[Dict]) -> Dict:
        """Calculate metadata for reranking chunks"""
        import re
        
        # Count numeric values and currency mentions
        numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', text)
        currency_mentions = len(re.findall(r'\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?', text, re.IGNORECASE))
        
        # Calculate numeric density (numbers per 100 chars)
        numeric_density = len(numbers) / max(len(text) / 100, 1)
        
        # Check if mostly headers (penalty for navigation/TOC)
        header_ratio = sum(1 for b in blocks if b.get('is_header', False)) / max(len(blocks), 1)
        
        return {
            'numeric_density': numeric_density,
            'currency_presence': currency_mentions > 0,
            'header_penalty': header_ratio > 0.5,
            'token_count': sum(b['tokens'] for b in blocks),
            'block_count': len(blocks),
            'has_tables': any(b['tag'] == 'table' for b in blocks)
        }
    
    def _detect_section(self, text: str) -> str:
        """Detect section from text content - simple heuristics"""
        text_lower = text.lower()
        
        # Simple pattern matching - let embeddings do the heavy lifting
        if 'item 1a' in text_lower or 'risk factor' in text_lower:
            return "RISK_FACTORS"
        if 'item 7' in text_lower or 'management' in text_lower and 'discussion' in text_lower:
            return "MD&A"
        if 'item 8' in text_lower or 'financial statement' in text_lower:
            return "FINANCIAL_STATEMENTS"
        if 'item 1' in text_lower and 'item 1a' not in text_lower:
            return "BUSINESS"
        
        # MD&A content
        if re.search(r"management'?s?\s*discussion|md&a|results\s*of\s*operations", text_lower):
            return "MD&A"
        
        return "BODY"
    
    def _fallback_text_chunking(self, text: str, chunk_size: int, overlap: float) -> List[Dict]:
        """Fallback to simple text-based chunking when HTML parsing fails"""
        chunks = []
        
        try:
            import tiktoken
            if "text-embedding-3" in self.embedding_model:
                encoding = tiktoken.get_encoding("cl100k_base")
            elif "voyage" in self.embedding_model:
                encoding = tiktoken.get_encoding("cl100k_base")
            else:
                encoding = tiktoken.encoding_for_model(self.embedding_model)
                
            tokens = encoding.encode(text)
            overlap_tokens = int(chunk_size * overlap)
            
            start_token = 0
            while start_token < len(tokens):
                end_token = min(start_token + chunk_size, len(tokens))
                chunk_tokens = tokens[start_token:end_token]
                chunk_text = encoding.decode(chunk_tokens)
                
                chunks.append({
                    'text': chunk_text,
                    'section': self._detect_section(chunk_text),
                    'metadata': {
                        'start_token': start_token,
                        'end_token': end_token,
                        'token_count': len(chunk_tokens)
                    }
                })
                
                start_token = end_token - overlap_tokens if end_token < len(tokens) else end_token
                
        except ImportError:
            # Ultimate fallback: character-based
            chars_per_chunk = chunk_size * 4
            overlap_chars = int(chars_per_chunk * overlap)
            
            start = 0
            while start < len(text):
                end = min(start + chars_per_chunk, len(text))
                chunk_text = text[start:end]
                
                chunks.append({
                    'text': chunk_text,
                    'section': self._detect_section(chunk_text),
                    'metadata': {
                        'start_char': start,
                        'end_char': end,
                        'chunk_size': end - start
                    }
                })
                start = end - overlap_chars if end < len(text) else end
        
        return chunks
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text (e.g., query).
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        # Use batch method with single item
        result = await self.generate_embeddings([{'text': text}])
        return result[0] if result else []
    
    async def generate_embeddings(self, chunks: List[Dict]) -> List[List[float]]:
        """Generate embeddings for chunks with token-aware batching, dimension validation, and retry logic"""
        import time
        from core.config import Config
        config = Config()
        
        # Check circuit breaker
        if self.circuit_breaker_open_until > time.time():
            time_left = int(self.circuit_breaker_open_until - time.time())
            logger.warning(f"Circuit breaker OPEN - embedding service paused for {time_left}s after repeated failures")
            raise ValueError(f"Embedding service circuit breaker open, retry in {time_left} seconds")
        
        embeddings = []
        
        # Token-aware batching - pack chunks by token count instead of fixed batch size
        MAX_TOKENS_PER_BATCH = config.sec_max_tokens_per_batch
        MAX_CHUNKS_PER_BATCH = 20  # Reduced to prevent exceeding Voyage 120K token limit per batch
        
        batches = []
        current_batch = []
        current_tokens = 0
        
        for chunk in chunks:
            # Get token count for this chunk (use stored value or calculate)
            chunk_tokens = chunk.get('tokens', chunk.get('token_count', int(len(chunk['text']) / 3.5)))  # Better estimate: 1 token ≈ 3.5 chars
            
            # Check if adding this chunk would exceed limits
            if (current_tokens + chunk_tokens > MAX_TOKENS_PER_BATCH or 
                len(current_batch) >= MAX_CHUNKS_PER_BATCH) and current_batch:
                # Save current batch and start new one
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            
            current_batch.append(chunk)
            current_tokens += chunk_tokens
        
        # Add final batch if not empty
        if current_batch:
            batches.append(current_batch)
        
        logger.info(f"Processing {len(chunks)} chunks in {len(batches)} token-aware batches")
        
        # Process batches concurrently with rate limiting
        # Voyage allows up to 10 concurrent requests per second
        MAX_CONCURRENT = 6  # Increased for better parallelism
        REQUESTS_PER_SECOND = 10  # Use Voyage's full 10 req/s limit
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        
        # Rate limiter - track request times
        request_times = []
        
        async def process_batch_with_rate_limit(batch_idx: int, batch: List[Dict]) -> List[List[float]]:
            """Process a single batch with rate limiting and concurrency control"""
            async with semaphore:
                # Rate limiting - ensure we don't exceed requests per second
                current_time = time.time()
                
                # Clean old request times (older than 1 second)
                nonlocal request_times
                request_times = [t for t in request_times if current_time - t < 1.0]
                
                # If we've hit the rate limit, wait
                if len(request_times) >= REQUESTS_PER_SECOND:
                    wait_time = 1.0 - (current_time - request_times[0])
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                        current_time = time.time()
                        request_times = [t for t in request_times if current_time - t < 1.0]
                
                # Record this request time
                request_times.append(current_time)
                
                # Process the batch
                return await self._process_single_batch(batch_idx, batch)
        
        # Process all batches concurrently
        tasks = []
        for batch_idx, batch in enumerate(batches):
            task = process_batch_with_rate_limit(batch_idx, batch)
            tasks.append(task)
        
        # Wait for all batches to complete
        batch_results = await asyncio.gather(*tasks)
        
        # Flatten results into single list
        for batch_embeddings in batch_results:
            embeddings.extend(batch_embeddings)
        
        logger.info(f"Generated {len(embeddings)} embeddings in {len(batches)} token-aware batches (concurrent processing)")
        return embeddings
    
    async def _process_single_batch(self, batch_idx: int, batch: List[Dict]) -> List[List[float]]:
        """Process a single batch of chunks into embeddings"""
        import time
        
        batch_texts = [chunk['text'] for chunk in batch]
        batch_tokens = sum(chunk.get('tokens', chunk.get('token_count', int(len(chunk['text']) / 3.5))) for chunk in batch)
        batch_embeddings = []
        
        # Retry logic with exponential backoff
        for retry in range(self.max_retries):
            request_start = time.time()
            try:
                if self.embedding_provider == 'voyage':
                    # Use Voyage API for embeddings with timeout
                    result = await asyncio.wait_for(
                        self.voyage_client.embed(
                            texts=batch_texts,
                            model=self.embedding_model,
                            input_type="document",  # SEC filings are documents
                            output_dimension=self.embedding_dims,  # Use configured dimension
                            output_dtype="float"  # Use float for best quality
                        ),
                        timeout=self.timeout
                    )
                    
                    # Extract embeddings from Voyage response
                    for embedding in result.embeddings:
                        # Validate dimensions
                        if len(embedding) != self.embedding_dims:
                            raise ValueError(
                                f"Embedding dimension mismatch: expected {self.embedding_dims}, "
                                f"got {len(embedding)} from {self.embedding_model}"
                            )
                        batch_embeddings.append(embedding)
                else:
                    # Fallback to OpenAI with timeout
                    response = await asyncio.wait_for(
                        self.openai_client.embeddings.create(
                            model=self.embedding_model,
                            input=batch_texts  # List of texts for batch processing
                        ),
                        timeout=self.timeout
                    )
                    
                    # Extract embeddings from OpenAI response
                    for data in response.data:
                        embedding = data.embedding
                        
                        # Validate dimensions
                        if len(embedding) != self.embedding_dims:
                            raise ValueError(
                                f"Embedding dimension mismatch: expected {self.embedding_dims}, "
                                f"got {len(embedding)} from {self.embedding_model}"
                            )
                        
                        batch_embeddings.append(embedding)
                
                logger.debug(f"Generated embeddings for batch {batch_idx + 1}, size: {len(batch)}, tokens: {batch_tokens}")
                
                # Record metrics
                if metrics_collector:
                    latency_ms = (time.time() - request_start) * 1000
                    metrics_collector.embeddings.record_request(
                        success=True, 
                        latency_ms=latency_ms,
                        batch_size=len(batch)
                    )
                
                # Reset circuit breaker on success
                self.circuit_breaker_failures = 0
                return batch_embeddings  # Success, return results
                
            except asyncio.TimeoutError:
                logger.warning(f"Timeout generating embeddings for batch {batch_idx + 1}, retry {retry + 1}/{self.max_retries}")
                if retry == self.max_retries - 1:
                    # Record metrics
                    if metrics_collector:
                        latency_ms = (time.time() - request_start) * 1000
                        metrics_collector.embeddings.record_request(
                            success=False,
                            latency_ms=latency_ms,
                            batch_size=len(batch),
                            error_type='timeout'
                        )
                    
                    # Trip circuit breaker after max retries
                    self.circuit_breaker_failures += 1
                    if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
                        self.circuit_breaker_open_until = time.time() + self.circuit_breaker_timeout
                        logger.error(f"Circuit breaker OPENED after {self.circuit_breaker_failures} failures - pausing for {self.circuit_breaker_timeout}s")
                        if metrics_collector:
                            metrics_collector.embeddings.circuit_breaker_opens += 1
                    raise ValueError(f"Timeout after {self.max_retries} retries")
                await asyncio.sleep(self.base_delay * (2 ** retry))  # Exponential backoff
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Check for 400 error - batch too large
                if '400' in error_str or 'max tokens per batch' in error_str or 'too large' in error_str:
                    logger.warning(f"Batch too large ({batch_tokens} tokens, {len(batch)} chunks), splitting and retrying")
                    if len(batch) > 1:
                        # Split batch in half and process recursively
                        mid = len(batch) // 2
                        first_half = batch[:mid]
                        second_half = batch[mid:]
                        
                        # Process first half
                        first_embeddings = await self.generate_embeddings(first_half)
                        batch_embeddings.extend(first_embeddings)
                        
                        # Process second half
                        second_embeddings = await self.generate_embeddings(second_half)
                        batch_embeddings.extend(second_embeddings)
                        
                        return batch_embeddings  # Exit retry loop, batch processed via split
                    else:
                        # Single chunk still too large - shouldn't happen with proper chunking
                        logger.error(f"Single chunk too large: {batch_tokens} tokens")
                        raise ValueError(f"Single chunk exceeds token limit: {batch_tokens} tokens")
                
                # Check for rate limit errors
                elif '429' in error_str or 'rate' in error_str or 'limit' in error_str:
                    logger.warning(f"Rate limit hit for batch {batch_idx + 1}, retry {retry + 1}/{self.max_retries}")
                    if retry == self.max_retries - 1:
                        # Record metrics
                        if metrics_collector:
                            latency_ms = (time.time() - request_start) * 1000
                            metrics_collector.embeddings.record_request(
                                success=False,
                                latency_ms=latency_ms,
                                batch_size=len(batch),
                                error_type='429'
                            )
                        
                        # Trip circuit breaker for rate limits
                        self.circuit_breaker_failures += 1
                        if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
                            self.circuit_breaker_open_until = time.time() + self.circuit_breaker_timeout
                            logger.error(f"Circuit breaker OPENED after {self.circuit_breaker_failures} rate limit failures - pausing for {self.circuit_breaker_timeout}s")
                            if metrics_collector:
                                metrics_collector.embeddings.circuit_breaker_opens += 1
                        logger.error(f"Rate limit exceeded after {self.max_retries} retries, circuit breaker may be open")
                        raise
                    await asyncio.sleep(self.base_delay * (2 ** retry) * 2)  # Longer wait for rate limits
                else:
                    logger.error(f"Error generating embeddings for batch: {e}")
                    raise
        
        # If we reach here, all retries failed
        raise ValueError(f"Failed to generate embeddings for batch {batch_idx} after {self.max_retries} retries")