"""
SEC Filing MCP Server (Refactored)
Retrieval-only vector database for SEC filings
NO HARDCODING - Dynamic field discovery
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
import hashlib
from agents.mcp import MCPServer
from agents.mcp.server import MCPTool, CallToolResult
from core.config import get_config
from core.database import get_postgres_client

# Import modular components
from .sec import RateLimiter, FilingFetcher, EmbeddingService, SECDatabaseOps
from .sec.session_cache import SessionCache

logger = logging.getLogger(__name__)
config = get_config()


class SECFilingServer(MCPServer):
    """SEC Filing server for retrieval-only vector database operations"""
    
    def __init__(self):
        super().__init__()
        self.cache = {}  # Legacy cache (deprecated)
        self.user_agent = config.sec_edgar_user_agent
        self._session_context = {}  # Store session/user context for fallback
        # Required by openai-agents SDK 0.2.0+ streaming tool adapter
        self.use_structured_content = False

        # Initialize modular components
        self.rate_limiter = RateLimiter(config.sec_rate_limit)
        self.filing_fetcher = FilingFetcher(self.user_agent)
        self.embedding_service = EmbeddingService(config)
        self.db_ops = SECDatabaseOps(config)
        
        # Initialize session cache if enabled
        if config.sec_session_cache_enabled:
            self.session_cache = SessionCache(
                ttl_minutes=config.sec_session_cache_ttl_min,
                max_entries=config.sec_session_cache_max_entries,
                max_mb=config.sec_session_cache_max_mb
            )
            logger.info(f"SEC session cache enabled with limits: TTL={config.sec_session_cache_ttl_min}min, "
                       f"max_entries={config.sec_session_cache_max_entries}, max_size={config.sec_session_cache_max_mb}MB")
            # Log initial cache stats
            self.session_cache.log_stats()
        else:
            self.session_cache = None
            logger.info("Session cache disabled for SEC filings")
        
        # Legacy compatibility
        self.embedding_provider = config.sec_embedding_provider
        self.embedding_model = config.sec_embedding_model
        self.embedding_dims = config.sec_embedding_dims
        self.pg_client = None
    
    @property
    def name(self) -> str:
        return "sec-filing"
    
    async def connect(self):
        """Initialize the server connection and validate configuration"""
        # Check if SEC vectors are enabled
        if not config.sec_vectors_enabled:
            logger.info(f"SEC vectors disabled via SEC_VECTORS_ENABLED flag")
            raise RuntimeError("SEC vector search is disabled. Set SEC_VECTORS_ENABLED=true to enable.")
        
        # Postgres availability guard
        if not config.enable_postgres:
            error_msg = "SEC filing vectors require PostgreSQL. Set ENABLE_POSTGRES=true and configure DATABASE_URL."
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Try to get PostgreSQL client
        self.pg_client = await get_postgres_client()
        
        # Additional guard to ensure pool is available
        if not self.pg_client or not hasattr(self.pg_client, 'pool') or not self.pg_client.pool:
            error_msg = "Failed to initialize PostgreSQL connection pool for SEC filing vectors"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Validate embedding type matches database
        await self.db_ops.validate_embedding_type()
        
        logger.info(f"{self.name} connected with PostgreSQL support (type: {config.sec_embedding_type})")
    
    def set_session_context(self, session_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Set session context for fallback when tools don't receive these parameters.
        Called by orchestrator before agent execution.
        """
        self._session_context = {
            'session_id': session_id,
            'user_id': user_id
        }
        logger.debug(f"Session context set: session={session_id[:8] if session_id else 'None'}...")
    
    async def cleanup(self):
        """Cleanup the server"""
        self.cache.clear()
        self._session_context.clear()
        logger.info(f"{self.name} cleaned up")
    
    async def get_prompt(self, name: str, arguments: Dict[str, Any] = {}) -> str:
        """Get a prompt by name. Not used by SECFilingServer."""
        return ""
    
    async def list_prompts(self) -> List[Dict[str, Any]]:
        """List available prompts. SECFilingServer doesn't use prompts."""
        return []
    
    async def index_filing(self, ticker: str, filing_type: str = "10-K", user_id: Optional[str] = None) -> Dict:
        """
        Ingestion path: fetch → chunk → embed → upsert
        Uses user context for RLS write policy
        If no user_id, runs stateless (no DB persistence)
        """
        # Log what user_id we received and what's in session context
        ctx = getattr(self, '_session_context', {})
        logger.info(f"[SEC index_filing] Called with user_id={user_id}, session_context={ctx}")
        
        # Use session context fallback if user_id not provided
        if not user_id and ctx:
            user_id = ctx.get('user_id')
            logger.info(f"[SEC index_filing] Using user_id from session context: {user_id}")
        
        try:
            # Rate limiting
            await self.rate_limiter.acquire()
            
            # Fetch filing with edgartools
            filing = await self.filing_fetcher.fetch_filing(ticker, filing_type)
            
            # Store the actual filing URL from edgartools
            filing_url = filing.url
            accession_number = filing.accession_number
            filing_date = filing.filing_date
            
            # Get filing HTML for better chunking
            try:
                filing_text = await asyncio.to_thread(filing.html)
                logger.debug("Retrieved filing as HTML for structured parsing")
            except Exception as e:
                logger.warning(f"Failed to get HTML, falling back to text: {e}")
                filing_text = await asyncio.to_thread(filing.text)
            
            # Chunk with embedding service
            chunks = self.embedding_service.chunk_filing(filing_text, chunk_size=config.sec_chunk_size, overlap=config.sec_chunk_overlap)
            
            # Cap chunks to prevent excessive costs
            if len(chunks) > config.sec_max_chunks_per_filing:
                logger.warning(
                    f"Filing has {len(chunks)} chunks, capping at {config.sec_max_chunks_per_filing} "
                    f"for {ticker} {filing_type}"
                )
                chunks = chunks[:config.sec_max_chunks_per_filing]
            
            # Generate embeddings
            embeddings = await self.embedding_service.generate_embeddings(chunks)
            
            # Store in database
            filing_meta = {
                'ticker': ticker,
                'filing_type': filing_type,
                'filing_date': filing_date,
                'accession_number': accession_number,
                'filing_url': filing_url
            }
            
            # Only persist to DB if BOTH config enables it AND we have a user_id
            inserted_count = 0
            db_error = None
            persisted = False
            
            if config.sec_persist_to_db and user_id:
                try:
                    inserted_count = await self.db_ops.upsert_chunks(chunks, embeddings, filing_meta, user_id)
                    persisted = True
                    logger.info(f"Indexed {inserted_count} chunks to DB for {ticker} {filing_type}")
                except Exception as db_e:
                    # Log DB error but don't fail - we still have chunks and embeddings for session cache
                    db_error = str(db_e)
                    if "row-level security" in db_error.lower() or "permission" in db_error.lower():
                        logger.warning(f"RLS error persisting {ticker} to DB (will use session cache only): {db_e}")
                    else:
                        logger.warning(f"DB error persisting {ticker} (will use session cache only): {db_e}")
            elif not config.sec_persist_to_db:
                logger.debug(f"SEC_PERSIST_TO_DB=false - using session cache only for {ticker} {filing_type}")
            else:
                logger.debug(f"No user_id - running stateless for {ticker} {filing_type}")
            
            return {
                'ticker': ticker,
                'filing_type': filing_type,
                'accession_number': accession_number,
                'filing_url': filing_url,
                'chunks_indexed': inserted_count,
                'chunks': chunks,  # Return for session cache
                'embeddings': embeddings,  # Return for session cache
                'persisted': persisted,
                'db_error': db_error  # Include any DB error for transparency
            }
            
        except Exception as e:
            logger.error(f"Error indexing filing for {ticker}: {e}")
            raise ValueError(f"Failed to index filing: {str(e)}")
    
    async def get_filing(self, company: str, filing_type: str = "latest", 
                        query: str = "", top_k: int = 10, 
                        stream: bool = None, user_id: Optional[str] = None,
                        session_id: Optional[str] = None) -> Dict:
        """
        Get and search SEC filing with live retrieval
        Fast path: Session cache -> search immediately  
        Medium path: Already indexed in DB -> search immediately
        Cold path: Fetch from SEC -> index -> search
        """
        # PostgreSQL availability guard
        if not config.enable_postgres and config.sec_persist_to_db:
            return {
                'error': 'SEC filing search requires PostgreSQL',
                'hint': 'Set ENABLE_POSTGRES=true and configure DATABASE_URL'
            }
        
        if not config.sec_live_enable:
            return {
                'error': 'Live retrieval disabled',
                'hint': 'Set SEC_LIVE_ENABLE=true to enable'
            }
        
        # Use config default if stream not specified
        if stream is None:
            stream = config.sec_live_stream
        
        # Validate and cap top_k
        if top_k > config.sec_top_k_max:
            logger.warning(f"Capping top_k from {top_k} to {config.sec_top_k_max}")
            top_k = config.sec_top_k_max

        # Fallback: pull session/user context from server if not provided (agent/MCP may omit)
        try:
            ctx = getattr(self, '_session_context', None)
            if session_id is None and ctx:
                session_id = ctx.get('session_id')
            if user_id is None and ctx:
                user_id = ctx.get('user_id')
        except Exception:
            # Non-fatal; proceed without session context
            pass
        
        try:
            # Rate limit for SEC requests
            await self.rate_limiter.acquire()
            
            # Step 1: Resolve filing metadata
            try:
                filing_meta = await self.filing_fetcher.resolve_filing_meta(company, filing_type)
                accession_number = filing_meta['accession_number']
            except Exception as e:
                logger.error(f"Failed to resolve filing metadata for {company}: {e}")
                return {
                    'query': query,
                    'company': company,
                    'filing_type': filing_type,
                    'error': f"Could not find {filing_type} filing for {company}: {str(e)}",
                    'results': [],
                    'count': 0
                }
            
            # Step 2: Check session cache first (fastest path)
            if self.session_cache:
                # Try session-specific cache first, then filing-specific cache
                cached_result = (self.session_cache.get(session_id, accession_number) if session_id 
                                else None) or self.session_cache.get(f"filing_{accession_number}", accession_number)
                if cached_result:
                    chunks, embeddings = cached_result
                    logger.info(f"Session cache HIT for {accession_number} in session {session_id[:8]}...")
                    
                    # Search within cached chunks
                    if query:
                        # Perform semantic search on cached embeddings
                        # This is fast since embeddings are already computed
                        from .sec.search_utils import search_in_memory
                        results = await search_in_memory(query, chunks, embeddings, top_k)
                    else:
                        # Return top chunks as preview
                        results = chunks[:top_k]
                    
                    return {
                        'query': query,
                        'filing_meta': filing_meta,
                        'results': results,
                        'count': len(results),
                        'data_source': 'session_cache',
                        'indexing_status': 'ready',
                        'cache_stats': self.session_cache.get_stats() if self.session_cache else None,
                        'persisted': False  # Session cache is temporary
                    }
            
            # Step 3: Check if already indexed in database (only if DB persistence is enabled AND we have user_id)
            if config.sec_persist_to_db and user_id:
                is_indexed = await self.db_ops.is_indexed(accession_number)
            else:
                is_indexed = False  # Skip DB check entirely when not persisting or no user_id
            
            if is_indexed and config.sec_persist_to_db and user_id:
                # Fast path: Search existing indexed filing
                logger.info(f"Filing {accession_number} already indexed, searching...")
                
                # Use search query if provided
                search_query = query if query else f"{filing_meta['company_name']} {filing_meta['filing_type']}"
                search_results = await self.search_filings(search_query, top_k, user_id)
                
                # Filter results to this filing
                filtered_results = [
                    r for r in search_results.get('results', [])
                    if r.get('accession_number') == accession_number
                ][:top_k]
                
                return {
                    'query': query,
                    'filing_meta': filing_meta,
                    'results': filtered_results,
                    'count': len(filtered_results),
                    'data_source': 'indexed',
                    'indexing_status': 'ready',
                    'last_indexed_at': filtered_results[0].get('last_updated') if filtered_results else None,
                    'persisted': True
                }
            
            # Step 3: Cold path - fetch and index
            logger.info(f"Filing {accession_number} not indexed, fetching from SEC...")
            
            # Fetch the filing
            filing = await self.filing_fetcher.fetch_filing(filing_meta['ticker'], filing_type)
            # Get HTML for better chunking, fallback to text
            try:
                filing_text = await asyncio.to_thread(filing.html)
                logger.debug("Retrieved filing as HTML for structured parsing")
            except Exception as e:
                logger.warning(f"Failed to get HTML, falling back to text: {e}")
                filing_text = await asyncio.to_thread(filing.text)
            
            # Parse sections for immediate preview if streaming
            if stream:
                sections = self.filing_fetcher.parse_sections(filing_text)
                preview_results = [
                    {
                        'section_name': s['section_name'],
                        'chunk_preview': s['preview'],
                        'accession_number': accession_number,
                        'filing_url': filing_meta['filing_url'],
                        'ticker': filing_meta['ticker']
                    }
                    for s in sections
                ]
                
                # Start background indexing
                asyncio.create_task(self._index_filing_background(
                    filing, filing_text, filing_meta, user_id, session_id
                ))
                
                return {
                    'query': query,
                    'filing_meta': filing_meta,
                    'results': preview_results,
                    'count': len(preview_results),
                    'data_source': 'live',
                    'indexing_status': 'in_progress',
                    'note': 'Showing previews while indexing. Semantic search will be available soon.'
                }
            
            # Non-streaming: Index and wait (with timeout)
            try:
                # Index with timeout
                index_result = await asyncio.wait_for(
                    self.index_filing(filing_meta['ticker'], filing_type, user_id),
                    timeout=config.sec_embed_timeout_s
                )
                
                # Get chunks and embeddings from the index result
                chunks = index_result.get('chunks', [])
                embeddings = index_result.get('embeddings', [])
                
                # Store in session cache if available
                if self.session_cache and session_id and chunks:
                    logger.info(f"Storing {len(chunks)} chunks to session cache for session {session_id[:8]}...")
                    stored = self.session_cache.put(
                        session_id,
                        filing_meta['accession_number'],
                        chunks,
                        embeddings
                    )
                    if stored:
                        logger.info(f"✅ Successfully cached filing in session")
                    else:
                        logger.warning(f"❌ Failed to store in session cache")
                
                # Search the indexed content using in-memory search
                # This works for dev users who don't have DB persistence
                search_query = query if query else f"{filing_meta['company_name']} {filing_meta['filing_type']}"
                
                if chunks and embeddings:
                    from .sec.search_utils import search_in_memory
                    results = await search_in_memory(search_query, chunks, embeddings, top_k)
                    # Enrich results with filing metadata
                    for result in results:
                        result['accession_number'] = accession_number
                        result['filing_url'] = filing_meta.get('filing_url')
                        result['ticker'] = filing_meta.get('ticker')
                else:
                    # Fallback to DB search if no chunks (shouldn't happen)
                    search_results = await self.search_filings(search_query, top_k, user_id)
                    results = [
                        r for r in search_results.get('results', [])
                        if r.get('accession_number') == accession_number
                    ][:top_k]
                
                return {
                    'query': query,
                    'filing_meta': filing_meta,
                    'results': results,
                    'count': len(results),
                    'data_source': 'live',
                    'indexing_status': 'ready',
                    'chunks_indexed': index_result.get('chunks_indexed', 0)
                }
                
            except asyncio.TimeoutError:
                # Timeout: Return previews and continue indexing in background
                logger.warning(f"Indexing timeout for {accession_number}, returning previews")
                
                sections = self.filing_fetcher.parse_sections(filing_text)
                preview_results = [
                    {
                        'section_name': s['section_name'],
                        'chunk_preview': s['preview'],
                        'accession_number': accession_number,
                        'filing_url': filing_meta['filing_url'],
                        'ticker': filing_meta['ticker']
                    }
                    for s in sections
                ]
                
                # Continue indexing in background
                asyncio.create_task(self._index_filing_background(
                    filing, filing_text, filing_meta, user_id, session_id
                ))
                
                return {
                    'query': query,
                    'filing_meta': filing_meta,
                    'results': preview_results,
                    'count': len(preview_results),
                    'data_source': 'live',
                    'indexing_status': 'in_progress',
                    'note': 'Indexing taking longer than expected. Showing previews.'
                }
                
        except Exception as e:
            logger.error(f"Error in get_filing: {e}")
            return {
                'query': query,
                'company': company,
                'filing_type': filing_type,
                'error': str(e),
                'data_source': 'error',
                'indexing_status': 'failed'
            }
    
    async def _index_filing_background(self, filing, filing_text: str, 
                                      filing_meta: Dict, user_id: Optional[str] = None,
                                      session_id: Optional[str] = None):
        """Background task to index filing with session cache support"""
        try:
            # Acquire persist slot (max 5 concurrent)
            if self.session_cache and hasattr(self.session_cache, 'acquire_persist_slot'):
                async with await self.session_cache.acquire_persist_slot():
                    await self._do_index_filing(filing, filing_text, filing_meta, user_id, session_id)
            else:
                await self._do_index_filing(filing, filing_text, filing_meta, user_id, session_id)
        except Exception as e:
            logger.error(f"Background indexing failed for {filing_meta['accession_number']}: {e}", exc_info=True)
    
    async def _do_index_filing(self, filing, filing_text: str, 
                              filing_meta: Dict, user_id: Optional[str] = None,
                              session_id: Optional[str] = None):
        """Actually perform the filing indexing"""
        try:
            logger.info(f"Background indexing started for {filing_meta['accession_number']} with session_id={session_id[:8] if session_id else 'None'}")
            
            # Chunk the filing
            chunks = self.embedding_service.chunk_filing(filing_text, chunk_size=config.sec_chunk_size, overlap=config.sec_chunk_overlap)
            logger.debug(f"Created {len(chunks)} chunks")
            
            # Cap chunks
            if len(chunks) > config.sec_max_chunks_per_filing:
                chunks = chunks[:config.sec_max_chunks_per_filing]
                logger.debug(f"Capped to {len(chunks)} chunks")
            
            # Generate embeddings
            embeddings = await self.embedding_service.generate_embeddings(chunks)
            logger.debug(f"Generated {len(embeddings)} embeddings")
            
            # Store in session cache first for immediate availability
            # Use filing accession as fallback for global caching of public documents
            cache_key = session_id or f"filing_{filing_meta['accession_number']}"
            logger.debug(f"Cache check: session_cache={self.session_cache is not None}, cache_key={cache_key}")
            if self.session_cache:
                logger.info(f"Attempting to cache entry: cache_key={cache_key[:12]}..., accession={filing_meta['accession_number']}, chunks={len(chunks)}")
                try:
                    # Get lock for this cache key if async locks available
                    if hasattr(self.session_cache, 'get_lock'):
                        lock = await self.session_cache.get_lock(user_id, session_id, filing_meta['accession_number'])
                        async with lock:
                            stored = self.session_cache.put(
                                cache_key, 
                                filing_meta['accession_number'],
                                chunks,
                                embeddings
                            )
                    else:
                        stored = self.session_cache.put(
                            cache_key, 
                            filing_meta['accession_number'],
                            chunks,
                            embeddings
                        )
                    
                    logger.info(f"Cache put returned: {stored}")
                    if stored:
                        logger.info(f"✅ Successfully cached {len(chunks)} chunks for {filing_meta['accession_number']}")
                        stats = self.session_cache.get_stats()
                        logger.info(f"Cache stats after put: {stats}")
                    else:
                        logger.warning(f"❌ Cache put failed for {filing_meta['accession_number']}")
                except Exception as cache_e:
                    logger.error(f"Cache put exception: {cache_e}", exc_info=True)
            else:
                logger.warning(f"Skipping cache: session_cache={self.session_cache is not None}, session_id={session_id}")
            
            # Store in database (only if persistence is enabled AND we have user_id)
            if config.sec_persist_to_db and user_id:
                inserted_count = await self.db_ops.upsert_chunks(chunks, embeddings, filing_meta, user_id)
                logger.info(f"Background indexing complete: {inserted_count} chunks in DB for {filing_meta['accession_number']}")
            elif not user_id:
                logger.info(f"Background indexing complete: Session cache only (no user_id for DB persistence)")
            else:
                logger.info(f"Background indexing complete: Session cache only (DB persistence disabled)")
            
        except Exception as e:
            # Don't retry on RLS/permission errors
            if "row-level security" in str(e).lower() or "permission" in str(e).lower():
                logger.error(f"RLS/Permission error in background indexing for {filing_meta['accession_number']}: {e}")
            else:
                logger.error(f"Background indexing failed for {filing_meta['accession_number']}: {e}", exc_info=True)
    
    async def search_filings(self, query: str, top_k: int = 10, 
                            user_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict:
        """
        Hybrid search with session cache merging.
        
        Search priority:
        1. Session cache (in-memory, fastest)
        2. Database (if SEC_PERSIST_TO_DB=true)
        
        Args:
            query: Search query text
            top_k: Number of results to return
            user_id: User ID for RLS context (optional)
            session_id: Session ID for cache lookup (optional)
            
        Returns:
            Dict with query, results, count, and data_source
        """
        # Fallback to session context if not provided
        ctx = getattr(self, '_session_context', None)
        if session_id is None and ctx:
            session_id = ctx.get('session_id')
        if user_id is None and ctx:
            user_id = ctx.get('user_id')
        
        all_results = []
        data_sources = []
        
        try:
            # Step 1: Search session cache first (fastest path)
            if self.session_cache and session_id:
                logger.debug(f"Searching session cache for session {session_id[:8]}...")
                
                # Get all cached entries for this session
                cache_stats = self.session_cache.get_stats()
                if cache_stats.get('total_entries', 0) > 0:
                    # Search through all cached filings in this session
                    from .sec.search_utils import search_in_memory
                    
                    # Iterate through cached entries for this session
                    if session_id in self.session_cache._cache:
                        for accession_number, entry in self.session_cache._cache[session_id].items():
                            if not entry.is_expired(self.session_cache._ttl_seconds):
                                chunks = entry.chunks
                                embeddings = entry.embeddings
                                
                                if chunks and embeddings:
                                    try:
                                        cache_results = await search_in_memory(query, chunks, embeddings, top_k)
                                        # Add accession number to results
                                        for result in cache_results:
                                            result['accession_number'] = accession_number
                                            result['data_source'] = 'session_cache'
                                        all_results.extend(cache_results)
                                    except Exception as cache_e:
                                        logger.warning(f"Error searching cache for {accession_number}: {cache_e}")
                    
                    if all_results:
                        data_sources.append('session_cache')
                        logger.info(f"Session cache search returned {len(all_results)} results")
            
            # Step 2: Search database if persistence is enabled and we don't have enough results
            if config.sec_persist_to_db and (len(all_results) < top_k or not all_results):
                try:
                    from core.database.sec_vector_search import SECVectorSearch
                    
                    vector_search = SECVectorSearch(self.embedding_model, self.embedding_dims)
                    db_results = await vector_search.hybrid_search(query, top_k, user_id)
                    
                    if db_results:
                        # Mark as from database
                        for result in db_results:
                            result['data_source'] = 'database'
                        all_results.extend(db_results)
                        data_sources.append('database')
                        logger.info(f"Database search returned {len(db_results)} results")
                        
                except Exception as db_e:
                    logger.warning(f"Database search failed (SEC_PERSIST_TO_DB may be disabled): {db_e}")
            
            # Step 3: Deduplicate and sort by score
            seen_ids = set()
            unique_results = []
            for result in all_results:
                # Use accession_number + chunk_index as unique key
                result_key = f"{result.get('accession_number', '')}_{result.get('chunk_index', 0)}"
                if result_key not in seen_ids:
                    seen_ids.add(result_key)
                    unique_results.append(result)
            
            # Sort by score (rerank_score or final_score or similarity_score)
            unique_results.sort(
                key=lambda x: x.get('rerank_score', x.get('final_score', x.get('similarity_score', 0))),
                reverse=True
            )
            
            # Take top_k
            results = unique_results[:top_k]
            
            # Include resolution metadata for consistency
            for result in results:
                result['metadata'] = {
                    'accession_number': result.get('accession_number'),
                    'section_name': result.get('section_name'),
                    'filing_url': result.get('filing_url'),
                    'similarity_score': result.get('rerank_score', result.get('final_score', result.get('similarity_score', 0))),
                    'ticker': result.get('ticker'),
                    'data_source': result.get('data_source', 'unknown')
                }
            
            # Provide helpful hint if no results
            hint = None
            if not results:
                if not self.session_cache or not session_id:
                    hint = "No session cache available. Try using get_filing first to index a specific filing."
                elif not config.sec_persist_to_db:
                    hint = "Database persistence is disabled (SEC_PERSIST_TO_DB=false). Results come from session cache only. Use get_filing to index filings first."
                else:
                    hint = "No matching filings found. Try indexing filings with get_filing or index_filing first."
            
            return {
                'query': query,
                'results': results,
                'count': len(results),
                'data_sources': data_sources if data_sources else ['none'],
                'hint': hint,
                'cache_stats': self.session_cache.get_stats() if self.session_cache else None
            }
            
        except Exception as e:
            logger.error(f"Error searching filings: {e}", exc_info=True)
            return {
                'query': query,
                'results': [],
                'count': 0,
                'error': str(e),
                'hint': 'Search failed. Ensure filings are indexed first using get_filing or index_filing.'
            }
    
    # MCP Protocol Methods
    async def list_tools(self, run_context, agent) -> List[MCPTool]:
        """MCP method: List available tools"""
        tools = self.get_tools()
        mcp_tools = []
        for tool in tools:
            mcp_tools.append(MCPTool(
                name=tool["function"]["name"],
                description=tool["function"]["description"],
                inputSchema=tool["function"]["parameters"]
            ))
        return mcp_tools
    
    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> CallToolResult:
        """MCP method: Execute a tool call with session context fallback"""
        if arguments is None:
            arguments = {}
        
        # Use fallback context if session_id or user_id not provided
        session_id = arguments.get("session_id") or self._session_context.get("session_id")
        user_id = arguments.get("user_id") or self._session_context.get("user_id")
        
        try:
            result = None
            if tool_name == "index_filing":
                result = await self.index_filing(
                    arguments["ticker"],
                    arguments.get("filing_type", "10-K"),
                    user_id
                )
            elif tool_name == "search_filings":
                result = await self.search_filings(
                    arguments["query"],
                    arguments.get("top_k", 10),
                    user_id,
                    session_id
                )
            elif tool_name == "get_filing":
                result = await self.get_filing(
                    arguments["company"],
                    arguments.get("filing_type", "latest"),
                    arguments.get("query", ""),
                    arguments.get("top_k", 10),
                    arguments.get("stream"),
                    user_id,
                    session_id
                )
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
            
            return CallToolResult(
                content=[{"type": "text", "text": json.dumps(result, default=str)}],
                is_error=False
            )
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name} - {e}")
            return CallToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                is_error=True
            )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return tool definitions for OpenAI function calling"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "index_filing",
                    "description": "Indexes SEC filing into vector database for semantic search. Provide ticker (AAPL) and filing_type (10-K, 10-Q, 8-K). Fetches filing from SEC EDGAR, chunks text, generates embeddings, stores in PostgreSQL. Returns chunks_indexed count and filing metadata.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticker": {
                                "type": "string",
                                "description": "Stock ticker symbol (e.g., AAPL, MSFT)"
                            },
                            "filing_type": {
                                "type": "string",
                                "description": "SEC filing type (e.g., 10-K, 10-Q, 8-K)",
                                "default": "10-K"
                            },
                            "user_id": {
                                "type": "string",
                                "description": "User ID for RLS context (optional)"
                            }
                        },
                        "required": ["ticker"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_filings",
                    "description": "Searches indexed SEC filings using hybrid semantic + keyword search. Provide query (e.g., 'revenue recognition policy', 'supply chain risks'). Returns top_k relevant chunks with similarity scores, accession numbers, filing URLs. Searches across all user's indexed filings.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (e.g., 'Apple supply chain risks')"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "Number of results to return",
                                "default": 10
                            },
                            "user_id": {
                                "type": "string",
                                "description": "User ID for filtering (optional)"
                            },
                            "session_id": {
                                "type": "string",
                                "description": "Session ID for merging cached results (optional)"
                            }
                        },
                        "required": ["query"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_filing",
                    "description": "Fetches and searches SEC filing with live retrieval and auto-indexing. Provide company (ticker/CIK/name) and optional filing_type (10-K, 10-Q, 8-K, or 'latest'). Three paths: session cache (fastest), already indexed (fast), cold fetch (auto-indexes). Use stream=true for immediate previews while indexing. Returns relevant chunks with query results.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "company": {
                                "type": "string",
                                "description": "Company ticker, CIK, or name (e.g., AAPL, 0000320193, Apple Inc.)"
                            },
                            "filing_type": {
                                "type": "string",
                                "description": "SEC filing type (e.g., 10-K, 10-Q, 8-K) or 'latest' for most recent",
                                "default": "latest"
                            },
                            "query": {
                                "type": "string",
                                "description": "Search query to find specific information in the filing",
                                "default": ""
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "Number of results to return",
                                "default": 10
                            },
                            "stream": {
                                "type": "boolean",
                                "description": "Return immediate previews while indexing continues",
                                "default": True
                            },
                            "user_id": {
                                "type": "string",
                                "description": "User ID for RLS context (optional)"
                            },
                            "session_id": {
                                "type": "string",
                                "description": "Session ID for caching follow-up queries (optional)"
                            }
                        },
                        "required": ["company"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            }
        ]
