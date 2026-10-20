"""
Centralized configuration management for the Binomial Risk Analyst.
Handles environment variables, validation, and default values.
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging
from pathlib import Path
from .constants import (
    DEFAULT_PORTFOLIO_VALUE, DEFAULT_MC_SIMULATIONS, DEFAULT_RISK_FREE_RATE,
    DEFAULT_MAX_VAR_95, DEFAULT_MAX_CONCENTRATION, DEFAULT_MIN_SHARPE_RATIO,
    TRADING_DAYS_PER_YEAR, DEFAULT_MONTE_CARLO_HORIZON,
    MIN_MC_SIMULATIONS
)

logger = logging.getLogger(__name__)

# Load environment variables once at module level
# Allow specifying an explicit env file path via ENV_FILE/ENV_PATH (env-driven; no hardcoding)
_explicit_env_file = os.getenv('ENV_FILE') or os.getenv('ENV_PATH')
if _explicit_env_file:
    try:
        loaded = load_dotenv(_explicit_env_file, override=False)
        if loaded:
            logger.info(f"Loaded environment from ENV_FILE: {_explicit_env_file}")
        else:
            logger.warning(f"ENV_FILE specified but not found/readable: {_explicit_env_file}")
    except Exception as e:
        logger.warning(f"Failed to load ENV_FILE '{_explicit_env_file}': {e}")

# Also load default .env if present (does not override existing env vars)
load_dotenv()


class Config:
    """Centralized configuration management."""
    
    def __init__(self):
        self._config_cache = {}
        self._load_config()
    
    def reload(self):
        """Reload configuration from environment variables."""
        # Reload .env files
        from dotenv import load_dotenv
        # Reload explicit ENV_FILE first if provided
        explicit_env_file = os.getenv('ENV_FILE') or os.getenv('ENV_PATH')
        if explicit_env_file:
            try:
                load_dotenv(explicit_env_file, override=True)
                logger.info(f"Reloaded environment from ENV_FILE: {explicit_env_file}")
            except Exception as e:
                logger.warning(f"Failed to reload ENV_FILE '{explicit_env_file}': {e}")
        # Then reload default .env if present
        load_dotenv(override=True)
        # Reload all config values
        self._load_config()
        logger.info("Configuration reloaded from environment")
    
    def _load_config(self) -> None:
        """Load and validate all configuration values."""
        # API Keys
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.perplexity_api_key = os.getenv('PERPLEXITY_API_KEY', os.getenv('OPENAI_API_KEY'))  # Can fallback to OpenAI key
        self.fred_api_key = os.getenv('FRED_API_KEY')
        self.fmp_api_key = os.getenv('FMP_API_KEY')
        self.voyage_api_key = os.getenv('VOYAGE_API_KEY', '')  # Voyage AI for financial embeddings
        self.RAPIDAPI_FGI_KEY = os.getenv('RAPIDAPI_FGI_KEY')  # RapidAPI Fear & Greed Index
        
        # AI Provider configuration
        self.ai_provider = os.getenv('AI_PROVIDER', 'perplexity')  # 'perplexity' or 'openai'
        self.openai_model = os.getenv('OPENAI_MODEL', 'gpt-4-turbo')  # or 'gpt-4o' for speed
        self.perplexity_model = os.getenv('PERPLEXITY_MODEL', 'sonar-pro')  # Default Perplexity model
        self.agent_model = os.getenv('AGENT_MODEL', 'gpt-5.1')  # Default agent model (configurable, not hardcoded)
        
        # Portfolio settings
        self.portfolio_value = float(os.getenv('PORTFOLIO_VALUE', DEFAULT_PORTFOLIO_VALUE))
        self.risk_free_rate = self._get_current_risk_free_rate()
        
        # Risk limits
        self.max_var_95 = float(os.getenv('MAX_VAR_95', DEFAULT_MAX_VAR_95))
        self.max_concentration = float(os.getenv('MAX_CONCENTRATION', DEFAULT_MAX_CONCENTRATION))
        self.min_sharpe_ratio = float(os.getenv('MIN_SHARPE_RATIO', DEFAULT_MIN_SHARPE_RATIO))
        
        # Simulation parameters
        self.mc_simulations = int(os.getenv('MC_SIMULATIONS', DEFAULT_MC_SIMULATIONS))
        self.mc_time_horizon = int(os.getenv('MC_TIME_HORIZON', DEFAULT_MONTE_CARLO_HORIZON))
        self.trading_days = int(os.getenv('TRADING_DAYS', TRADING_DAYS_PER_YEAR))
        
        # Data settings
        self.lookback_years = int(os.getenv('LOOKBACK_YEARS', 3))
        self.data_frequency = os.getenv('DATA_FREQUENCY', 'daily')
        
        # Logging
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')

        # Deployment environment & safety rails
        self.environment = os.getenv('ENVIRONMENT', 'development').lower()
        self.enable_cost_tracking = os.getenv('ENABLE_COST_TRACKING', 'true').lower() == 'true'
        require_redis_default = 'true' if self.environment in ('production', 'staging') else 'false'
        self.require_redis_for_streaming = os.getenv(
            'REQUIRE_REDIS_FOR_STREAMING', require_redis_default
        ).lower() == 'true'
        
        # API settings
        self.api_timeout = float(os.getenv('API_TIMEOUT', '30.0'))

        # Async utilities configuration
        self.async_concurrency_limit = int(os.getenv('ASYNC_CONCURRENCY_LIMIT', '10'))

        # File handling / attachment limits
        self.max_file_attachments = int(os.getenv('MAX_FILE_ATTACHMENTS', '10'))

        # Streaming checkpoints / Redis configuration
        self.redis_url = os.getenv('REDIS_URL')
        self.stream_checkpoint_ttl_seconds = int(os.getenv('STREAM_CHECKPOINT_TTL_SECONDS', '300'))
        self.stream_checkpoint_limit = int(os.getenv('STREAM_CHECKPOINT_LIMIT', '200'))

        # Streaming run-state / pub-sub configuration
        runstate_url = os.getenv('RUNSTATE_REDIS_URL')
        self.runstate_redis_url = runstate_url if runstate_url else self.redis_url
        self.runstate_ttl_seconds = int(os.getenv('RUNSTATE_TTL_SECONDS', '3600'))

        # --- FastAPI/Web settings (Config2 upgrade) ---
        # FastAPI metadata
        self.fastapi_title = os.getenv('FASTAPI_TITLE', 'Binomial Risk Analyst V6 API')
        self.fastapi_description = os.getenv('FASTAPI_DESCRIPTION', 'Async-first API for V6 OpenAI Agents SDK implementation')
        self.fastapi_version = os.getenv('FASTAPI_VERSION', '6.0.0')

        # Server runtime
        self.fastapi_host = os.getenv('FASTAPI_HOST', '0.0.0.0')
        self.fastapi_port = int(os.getenv('FASTAPI_PORT', '8002'))
        self.fastapi_reload = os.getenv('FASTAPI_RELOAD', 'false').lower() == 'true'
        self.fastapi_workers = int(os.getenv('FASTAPI_WORKERS', '1'))

        # CORS configuration
        self.cors_allow_origin_regex = os.getenv('CORS_ALLOW_ORIGIN_REGEX')
        self.cors_allow_origins = self._parse_csv_list(
            'CORS_ALLOW_ORIGINS',
            [
                'http://localhost:3000',
                'http://localhost:3001',
                'https://d205uglxtpwr4k.cloudfront.net',
                'https://binomialsentry.ai',
                'https://www.binomialsentry.ai',
            ],
        )

        # Streaming configuration
        self.stream_heartbeat_seconds = int(os.getenv('STREAM_HEARTBEAT_SEC', '10'))
        self.stream_typing_delay_seconds = float(os.getenv('STREAM_TYPING_DELAY_SEC', '0.015'))
        # Enable true token streaming via LangGraph astream_events (flag-gated)
        self.enable_true_token_streaming = os.getenv('ENABLE_TRUE_TOKEN_STREAMING', 'false').lower() == 'true'
        # Enable structured event forwarding alongside token streaming
        self.enable_stream_events = os.getenv('ENABLE_STREAM_EVENTS', 'true').lower() == 'true'
        # Cross-provider compaction (provider switch continuity)
        self.cross_provider_compaction_enabled = os.getenv('CROSS_PROVIDER_COMPACTION_ENABLED', 'true').lower() == 'true'
        self.cross_provider_compaction_scan_tokens = int(os.getenv('CROSS_PROVIDER_COMPACTION_SCAN_TOKENS', '200000'))
        self.cross_provider_compaction_inject_tokens = int(os.getenv('CROSS_PROVIDER_COMPACTION_INJECT_TOKENS', '30000'))
        self.cross_provider_compaction_sse_enabled = os.getenv('CROSS_PROVIDER_COMPACTION_SSE_ENABLED', 'true').lower() == 'true'
        self.cross_provider_compaction_summary_model = os.getenv('CROSS_PROVIDER_COMPACTION_SUMMARY_MODEL', '').strip()
        self.cross_provider_compaction_summary_timeout_sec = float(os.getenv('CROSS_PROVIDER_COMPACTION_SUMMARY_TIMEOUT_SEC', '8.0'))
        self.cross_provider_compaction_summary_max_output_tokens = int(os.getenv('CROSS_PROVIDER_COMPACTION_SUMMARY_MAX_OUTPUT_TOKENS', '2048'))
        # SQLite session compaction (Agents SDK persisted history safety)
        # When enabled, older SQLiteSession items are summarized via the same LLM/settings as cross-provider compaction,
        # then reinjected as a single summary item.
        self.sqlite_session_compaction_summary_enabled = os.getenv('SQLITE_SESSION_COMPACTION_SUMMARY_ENABLED', 'false').lower() == 'true'
        self.deep_analysis_max_hops = int(os.getenv('DEEP_ANALYSIS_MAX_HOPS', '6'))

        # Orchestrator configuration
        # Format: module.path:ClassName
        self.orchestrator_class = os.getenv(
            'ORCHESTRATOR_CLASS',
            'core.ai.langgraph_orchestrator:LangGraphOrchestrator',
        )
        # Session configuration
        self.session_id_prefix = os.getenv('SESSION_ID_PREFIX', 'fastapi_')
        # Header used by clients to pass session id
        self.session_id_header = os.getenv('SESSION_ID_HEADER', 'X-Session-Id')

        # Export configuration
        self.export_filename_prefix = os.getenv('EXPORT_FILENAME_PREFIX', 'SENTRY_ANALYSIS')

        # Artifact storage configuration
        self.artifact_local_root = Path(os.getenv('ARTIFACT_LOCAL_ROOT', '/tmp'))
        self.artifact_storage_backend = os.getenv('ARTIFACT_STORAGE_BACKEND', 'local').lower()
        self.artifact_s3_bucket = os.getenv('ARTIFACT_S3_BUCKET')
        self.artifact_s3_prefix = os.getenv('ARTIFACT_S3_PREFIX', 'artifacts')
        self.artifact_s3_region = (
            os.getenv('ARTIFACT_S3_REGION')
            or os.getenv('AWS_REGION')
            or os.getenv('AWS_DEFAULT_REGION')
        )
        
        # Chart configuration
        # Limit inline points to keep tool call tokens bounded
        self.charts_max_inline_points = int(os.getenv('CHARTS_MAX_INLINE_POINTS', '500'))
        self.charts_max_render_points = int(os.getenv('CHARTS_MAX_RENDER_POINTS', '2000'))

        # Intent classification tokens (heuristic fallback)
        self.classify_simple_tokens = self._parse_csv_tokens(
            'CLASSIFY_SIMPLE_TOKENS',
            {
                'hi', 'hello', 'hey', 'good morning', 'good evening', 'what can you do'
            },
        )
        self.classify_search_tokens = self._parse_csv_tokens(
            'CLASSIFY_SEARCH_TOKENS',
            {'price', 'news', 'latest', 'today', 'headline', 'update'},
        )
        self.classify_calc_tokens = self._parse_csv_tokens(
            'CLASSIFY_CALC_TOKENS',
            {
                'calculate', 'calc', 'var', 'cvar', 'monte carlo', 'optimize', 'efficient frontier', 'hedge'
            },
        )
        
        # LangGraph persistence settings
        self.langgraph_checkpointer_enabled = os.getenv('LANGGRAPH_CHECKPOINTER_ENABLED', 'true').lower() == 'true'
        self.langgraph_db_path = os.getenv('LANGGRAPH_DB_PATH', 'data/state/langgraph_state.db')
        self.openai_sessions_db_path = os.getenv('OPENAI_SESSIONS_DB_PATH', 'data/sessions/binomial_sessions.db')
        self.max_graph_recursion = int(os.getenv('MAX_GRAPH_RECURSION', '60'))

        # Conversation message store (server-side ground truth)
        self.conversation_db_path = os.getenv('CONVERSATION_DB_PATH', 'data/conversations/conversation_messages.db')

        # Context window management (token-aware)
        # Maximum context the model supports (tokens). Use provider docs or env override.
        self.model_context_max_tokens = int(os.getenv('MODEL_CONTEXT_MAX_TOKENS', '128000'))
        # Ratio of total context reserved for prior history (rest for system/tools/output)
        self.context_budget_ratio = float(os.getenv('CONTEXT_BUDGET_RATIO', '0.5'))
        # Minimum number of recent turns to include regardless of budget
        self.min_history_turns = int(os.getenv('MIN_HISTORY_TURNS', '4'))
        # Enable enhanced context packer
        self.enable_context_packer = os.getenv('ENABLE_CONTEXT_PACKER', 'true').lower() == 'true'
        # Section budgets (ratios must sum to <= 1.0)
        self.context_system_ratio = float(os.getenv('CONTEXT_SYSTEM_RATIO', '0.2'))
        self.context_pinned_ratio = float(os.getenv('CONTEXT_PINNED_RATIO', '0.1'))
        self.context_current_ratio = float(os.getenv('CONTEXT_CURRENT_RATIO', '0.2'))
        self.context_recent_ratio = float(os.getenv('CONTEXT_RECENT_RATIO', '0.45'))
        self.context_scratch_ratio = float(os.getenv('CONTEXT_SCRATCH_RATIO', '0.05'))
        # Max messages to keep before summarization/packing
        self.context_max_history_messages = int(os.getenv('CONTEXT_MAX_HISTORY_MESSAGES', '50'))
        # Pinned memory formatting limits
        self.context_pinned_max_lines = int(os.getenv('CONTEXT_PINNED_MAX_LINES', '12'))
        # Rolling summary max token budget (within pinned ratio)
        self.context_summary_max_tokens = int(os.getenv('CONTEXT_SUMMARY_MAX_TOKENS', '1500'))
        
        # Authentication configuration (Clerk)
        self.enable_auth = os.getenv('ENABLE_AUTH', 'false').lower() == 'true'
        self.clerk_secret_key = os.getenv('CLERK_SECRET_KEY', '')
        self.clerk_webhook_secret = os.getenv('CLERK_WEBHOOK_SECRET', '')

        # Google Drive integration configuration
        self.google_drive_enabled = os.getenv('GOOGLE_DRIVE_ENABLED', 'false').lower() == 'true'
        self.google_drive_client_id = os.getenv('GOOGLE_DRIVE_CLIENT_ID', '')
        self.google_drive_client_secret = os.getenv('GOOGLE_DRIVE_CLIENT_SECRET', '')
        self.google_drive_redirect_uri = os.getenv('GOOGLE_DRIVE_REDIRECT_URI', '')
        self.google_drive_encryption_key = os.getenv('GOOGLE_DRIVE_ENCRYPTION_KEY', '')
        self.google_drive_service_account_json = os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON', '')
        self.google_drive_scopes = self._parse_csv_list(
            'GOOGLE_DRIVE_SCOPES',
            [
                'https://www.googleapis.com/auth/drive.readonly',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile',
                'openid',
            ],
        )
        self.google_drive_cache_ttl = int(os.getenv('GOOGLE_DRIVE_CACHE_TTL_SEC', '300'))
        
        # OneDrive integration configuration
        self.onedrive_enabled = os.getenv('ONEDRIVE_ENABLED', 'false').lower() == 'true'
        self.onedrive_client_id = os.getenv('ONEDRIVE_CLIENT_ID', '')
        self.onedrive_client_secret = os.getenv('ONEDRIVE_CLIENT_SECRET', '')
        self.onedrive_redirect_uri = os.getenv('ONEDRIVE_REDIRECT_URI', '')
        self.onedrive_encryption_key = os.getenv('ONEDRIVE_ENCRYPTION_KEY', '')
        self.onedrive_tenant_id = os.getenv('ONEDRIVE_TENANT_ID', 'common')
        self.onedrive_scopes = self._parse_csv_list(
            'ONEDRIVE_SCOPES',
            [
                'offline_access',
                'openid',
                'profile',
                'Files.Read',
                'Files.Read.All',
                'User.Read',
                'Sites.Read.All',
                'Sites.Search.All',
                'AllSites.Read',
                'AllSites.Write',
                'MyFiles.Read',
                'MyFiles.Write',
            ],
        )
        self.onedrive_cache_ttl = int(os.getenv('ONEDRIVE_CACHE_TTL_SEC', '300'))

        # Slack integration configuration
        self.slack_enabled = os.getenv('SLACK_ENABLED', 'false').lower() == 'true'
        self.slack_app_id = os.getenv('SLACK_APP_ID', '')
        self.slack_client_id = os.getenv('SLACK_CLIENT_ID', '')
        self.slack_client_secret = os.getenv('SLACK_CLIENT_SECRET', '')
        self.slack_signing_secret = os.getenv('SLACK_SIGNING_SECRET', '')
        self.slack_verification_token = os.getenv('SLACK_VERIFICATION_TOKEN', '')
        self.slack_redirect_uri = os.getenv('SLACK_REDIRECT_URI', '')
        self.slack_scopes = os.getenv(
            'SLACK_SCOPES',
            'channels:read,groups:read,im:read,mpim:read,chat:write,files:read,files:write',
        )
        self.slack_encryption_key = os.getenv('SLACK_ENCRYPTION_KEY', '')
        self.slack_state_ttl_seconds = int(os.getenv('SLACK_STATE_TTL_SECONDS', '900'))

        if self.slack_enabled:
            missing = []
            if not self.slack_client_id:
                missing.append('SLACK_CLIENT_ID')
            if not self.slack_client_secret:
                missing.append('SLACK_CLIENT_SECRET')
            if not self.slack_signing_secret:
                missing.append('SLACK_SIGNING_SECRET')
            if not self.slack_redirect_uri:
                missing.append('SLACK_REDIRECT_URI')
            if not self.slack_encryption_key:
                missing.append('SLACK_ENCRYPTION_KEY')
            if missing:
                raise ValueError(f"Slack integration enabled but missing: {', '.join(missing)}")
            try:
                from cryptography.fernet import Fernet
                Fernet(self.slack_encryption_key)
            except Exception as exc:
                raise ValueError("SLACK_ENCRYPTION_KEY must be a valid Fernet key") from exc

        # Teams integration configuration
        self.teams_enabled = os.getenv('TEAMS_ENABLED', 'false').lower() == 'true'
        self.teams_client_id = os.getenv('TEAMS_CLIENT_ID', '')
        self.teams_client_secret = os.getenv('TEAMS_CLIENT_SECRET', '')
        self.teams_tenant_id = os.getenv('TEAMS_TENANT_ID', 'common')
        self.teams_redirect_uri = os.getenv('TEAMS_REDIRECT_URI', '')
        self.teams_scopes = os.getenv(
            'TEAMS_SCOPES',
            'offline_access Group.Read.All Channel.ReadBasic.All ChannelMessage.Send Files.ReadWrite.All Sites.ReadWrite.All',
        )
        self.teams_encryption_key = os.getenv('TEAMS_ENCRYPTION_KEY', '')
        self.teams_state_ttl_seconds = int(os.getenv('TEAMS_STATE_TTL_SECONDS', '900'))

        if self.teams_enabled:
            missing = []
            if not self.teams_client_id:
                missing.append('TEAMS_CLIENT_ID')
            if not self.teams_client_secret:
                missing.append('TEAMS_CLIENT_SECRET')
            if not self.teams_redirect_uri:
                missing.append('TEAMS_REDIRECT_URI')
            if not self.teams_encryption_key:
                missing.append('TEAMS_ENCRYPTION_KEY')
            if missing:
                raise ValueError(f"Teams integration enabled but missing: {', '.join(missing)}")
            try:
                from cryptography.fernet import Fernet
                Fernet(self.teams_encryption_key)
            except Exception as exc:
                raise ValueError("TEAMS_ENCRYPTION_KEY must be a valid Fernet key") from exc

        # SES email configuration (must be defined before validation)
        self.ses_region = os.getenv('SES_REGION', 'us-east-1')
        self.ses_smtp_server = os.getenv('SES_SMTP_SERVER')
        self.ses_smtp_user = os.getenv('SES_SMTP_USER')
        self.ses_smtp_password = os.getenv('SES_SMTP_PASSWORD')
        self.ses_smtp_port = int(os.getenv('SES_SMTP_PORT', '587'))
        self.contact_to = os.getenv('CONTACT_TO', 'contact@bcmassets.com')
        self.contact_from = os.getenv('CONTACT_FROM', 'contact@bcmassets.com')
        self.bug_report_to = os.getenv('BUG_REPORT_EMAIL', 'support@bcmassets.com')

        # Email delivery configuration
        self.tasks_email_enabled = os.getenv('TASKS_EMAIL_ENABLED', 'false').lower() == 'true'
        self.tasks_email_from = os.getenv('TASKS_EMAIL_FROM', '')
        self.tasks_email_override_to = os.getenv('TASKS_EMAIL_OVERRIDE_TO', '')

        if self.tasks_email_enabled:
            missing = []
            if not self.tasks_email_from:
                missing.append('TASKS_EMAIL_FROM')
            if not self.ses_smtp_server:
                missing.append('SES_SMTP_SERVER')
            if not self.ses_smtp_user:
                missing.append('SES_SMTP_USER')
            if not self.ses_smtp_password:
                missing.append('SES_SMTP_PASSWORD')
            if missing:
                raise ValueError(f"Email delivery enabled but missing: {', '.join(missing)}")
        
        # PostgreSQL configuration
        self.enable_postgres = os.getenv('ENABLE_POSTGRES', 'false').lower() == 'true'
        
        # Support separate DB_APP_PASSWORD for better security
        from urllib.parse import urlparse, urlunparse
        
        db_app_password = os.getenv('DB_APP_PASSWORD', '')
        database_url = os.getenv('DATABASE_URL', '')
        
        # If DB_APP_PASSWORD is provided, properly parse and set it in the URL
        if db_app_password and database_url:
            parsed = urlparse(database_url)
            # Split netloc to get user and host parts
            if '@' in parsed.netloc:
                user_pass, host_port = parsed.netloc.rsplit('@', 1)
                # Extract username (before : or entire string if no : present)
                username = user_pass.split(':')[0] if ':' in user_pass else user_pass
                # Rebuild netloc with new password
                new_netloc = f"{username}:{db_app_password}@{host_port}"
                # Rebuild URL with new netloc
                self.database_url = urlunparse(parsed._replace(netloc=new_netloc))
            else:
                # No @ means no auth in URL, just use as-is
                self.database_url = database_url
        else:
            self.database_url = database_url
        
        # Configurable database role name
        self.db_app_role = os.getenv('DB_APP_ROLE', 'binomial_app')
        
        # Dev-only flag to skip RLS checks (with safeguard)
        self.skip_rls_checks = os.getenv('SKIP_RLS_CHECKS', 'false').lower() == 'true'
        if self.skip_rls_checks and os.getenv('FLASK_ENV', 'development') != 'development':
            raise ValueError(
                "SECURITY ERROR: SKIP_RLS_CHECKS cannot be enabled outside development environment. "
                "This would bypass critical security checks in production!"
            )
            
        self.postgres_migration_phase = int(os.getenv('POSTGRES_MIGRATION_PHASE', '1'))
        
        # FMP (Financial Modeling Prep) configuration
        self.use_fmp_market = os.getenv('USE_FMP_MARKET', 'false').lower() == 'true'
        self.use_fmp_docs = os.getenv('USE_FMP_DOCS', 'false').lower() == 'true'
        
        # Workflow Engine configuration
        self.workflows_engine_enabled = os.getenv('WORKFLOWS_ENGINE_ENABLED', 'true').lower() == 'true'  # Feature flag - enabled by default
        self.workflows_shadow_mode = os.getenv('WORKFLOWS_SHADOW_MODE', 'false').lower() == 'true'  # Run without surfacing results (disabled for PR3C)
        self.workflows_max_concurrent_runs_per_user = int(os.getenv('WORKFLOWS_MAX_CONCURRENT_RUNS_PER_USER', '1'))  # Limit concurrent runs per user
        self.workflows_dataset_timeout = float(os.getenv('WORKFLOWS_DATASET_TIMEOUT', '30.0'))  # Dataset operation timeout
        self.workflows_agent_timeout = float(os.getenv('WORKFLOWS_AGENT_TIMEOUT', '120.0'))  # Agent operation timeout
        self.workflows_output_timeout = float(os.getenv('WORKFLOWS_OUTPUT_TIMEOUT', '15.0'))  # Output operation timeout
        self.workflows_rate_limit_per_minute = int(os.getenv('WORKFLOWS_RATE_LIMIT_PER_MINUTE', '10'))  # Rate limit per user
        
        # SEC Filing configuration
        self.sec_vectors_enabled = os.getenv('SEC_VECTORS_ENABLED', 'false').lower() == 'true'  # Feature flag
        self.sec_edgar_user_agent = os.getenv('SEC_EDGAR_USER_AGENT', 'BinomialRiskAnalyst/1.0 (admin@example.com)')
        
        # Embedding provider configuration
        self.sec_embedding_provider = os.getenv('SEC_EMBEDDING_PROVIDER', 'voyage')  # 'voyage' or 'openai'
        self.sec_embedding_type = os.getenv('SEC_EMBEDDING_TYPE', 'vector')  # 'halfvec' or 'vector'
        
        # Dynamic configuration based on embedding provider
        if self.sec_embedding_provider == 'voyage':
            # Use Voyage-3-large with 1024 dims (better for finance, 3x smaller)
            self.sec_embedding_model = os.getenv('SEC_EMBEDDING_MODEL', 'voyage-3-large')
            self.sec_embedding_dims = int(os.getenv('SEC_EMBEDDING_DIMS', '1024'))
            self.sec_vector_cast = 'vector'
            self.sec_vector_ops = 'vector_cosine_ops'
        elif self.sec_embedding_type == 'halfvec':
            # Legacy: halfvec with OpenAI text-embedding-3-large (3072 dims)
            self.sec_embedding_model = os.getenv('SEC_EMBEDDING_MODEL', 'text-embedding-3-large')
            self.sec_embedding_dims = int(os.getenv('SEC_EMBEDDING_DIMS', '3072'))
            self.sec_vector_cast = 'halfvec'
            self.sec_vector_ops = 'halfvec_cosine_ops'
        else:
            # Legacy: vector with OpenAI text-embedding-3-small (1536 dims)
            self.sec_embedding_model = os.getenv('SEC_EMBEDDING_MODEL', 'text-embedding-3-small')
            self.sec_embedding_dims = int(os.getenv('SEC_EMBEDDING_DIMS', '1536'))
            self.sec_vector_cast = 'vector'
            self.sec_vector_ops = 'vector_cosine_ops'
        
        self.sec_rate_limit = float(os.getenv('SEC_RATE_LIMIT', '3.0'))  # requests per second
        self.sec_enable_caching = os.getenv('SEC_ENABLE_CACHING', 'true').lower() == 'true'
        self.sec_cache_ttl = int(os.getenv('SEC_CACHE_TTL', '300'))  # 5 minutes
        self.sec_max_chunks_per_filing = int(os.getenv('SEC_MAX_CHUNKS_PER_FILING', '400'))  # Increased for better coverage
        self.sec_embedding_batch_size = int(os.getenv('SEC_EMBEDDING_BATCH_SIZE', '30'))  # Conservative start for token-aware batching
        self.sec_chunk_size = int(os.getenv('SEC_CHUNK_SIZE', '2000'))  # Token size per chunk (increased to fit merged blocks)
        self.sec_chunk_overlap = float(os.getenv('SEC_CHUNK_OVERLAP', '0.10'))  # Overlap ratio (was hardcoded 0.20)
        self.sec_max_tokens_per_batch = int(os.getenv('SEC_MAX_TOKENS_PER_BATCH', '120000'))  # Voyage-3-large limit is 120k tokens
        self.sec_top_k_max = int(os.getenv('SEC_TOP_K_MAX', '50'))  # Maximum results to return
        
        # Workflow WebSocket configuration (enabled for PR3C)
        self.workflows_ws_enabled = os.getenv('WORKFLOWS_WS_ENABLED', 'true').lower() == 'true'
        self.workflows_ws_ping_sec = int(os.getenv('WORKFLOWS_WS_PING_SEC', '20'))  # Keepalive ping interval
        self.workflows_ws_max_idle_sec = int(os.getenv('WORKFLOWS_WS_MAX_IDLE_SEC', '120'))  # Max idle before close
        
        # Tokenizer configuration (GPT-5 P1 fix)
        self.sec_tokenizer_encoding = os.getenv('SEC_TOKENIZER_ENCODING', 'cl100k_base')
        
        # Chunking configuration (GPT-5 P1 fix)
        self.sec_chunk_cap = int(os.getenv('SEC_CHUNK_CAP', '6000'))  # Max tokens per chunk
        
        # Hybrid search weights (GPT-5 P1 fix - move magic numbers to config)
        self.sec_semantic_weight = float(os.getenv('SEC_SEMANTIC_WEIGHT', '0.6'))
        self.sec_keyword_weight = float(os.getenv('SEC_KEYWORD_WEIGHT', '0.4'))
        self.sec_min_score = float(os.getenv('SEC_MIN_SCORE', '0.3'))
        
        # Rate limiting and timeouts (GPT-5 P2 fix)
        self.sec_embed_timeout_s = float(os.getenv('SEC_EMBED_TIMEOUT_S', '240.0'))  # Increased to 4 minutes
        self.sec_operation_timeout = int(os.getenv('SEC_OPERATION_TIMEOUT', '300'))  # 5 minutes for SEC operations (includes embedding)
        self.sec_embed_max_retries = int(os.getenv('SEC_EMBED_MAX_RETRIES', '3'))
        self.sec_embed_base_delay = float(os.getenv('SEC_EMBED_BASE_DELAY', '1.0'))
        
        # FMP fallback configuration
        self.fmp_max_attempts = int(os.getenv('FMP_MAX_ATTEMPTS', '3'))
        
        
        # Live retrieval configuration
        self.sec_live_enable = os.getenv('SEC_LIVE_ENABLE', 'true').lower() == 'true'
        self.sec_live_stream = os.getenv('SEC_LIVE_STREAM', 'true').lower() == 'true'
        
        # Session cache configuration
        self.sec_session_cache_enabled = os.getenv('SEC_SESSION_CACHE_ENABLED', 'true').lower() == 'true'
        self.sec_session_cache_ttl_min = int(os.getenv('SEC_SESSION_CACHE_TTL_MIN', '30'))  # 30 min default
        self.sec_session_cache_max_entries = int(os.getenv('SEC_SESSION_CACHE_MAX_ENTRIES', '100'))
        self.sec_session_cache_max_mb = int(os.getenv('SEC_SESSION_CACHE_MAX_MB', '500'))  # 500MB max
        
        # Database persistence control - disabled by default (ephemeral embeddings)
        # SEC filings are public, session cache handles follow-ups, no need to persist
        self.sec_persist_to_db = os.getenv('SEC_PERSIST_TO_DB', 'false').lower() == 'true'
        self.sec_warm_cache_from_db = os.getenv('SEC_WARM_CACHE_FROM_DB', 'false').lower() == 'true'
        
        # Validate SEC embedding model/dims consistency
        if self.sec_embedding_provider == 'voyage':
            if self.sec_embedding_model == 'voyage-3-large' and self.sec_embedding_dims not in [256, 512, 1024, 2048]:
                raise ValueError(f"voyage-3-large supports 256, 512, 1024, or 2048 dimensions, got {self.sec_embedding_dims}")
        elif self.sec_embedding_provider == 'openai':
            if self.sec_embedding_model == 'text-embedding-3-large' and self.sec_embedding_dims != 3072:
                raise ValueError(f"text-embedding-3-large requires 3072 dimensions, got {self.sec_embedding_dims}")
            elif self.sec_embedding_model == 'text-embedding-3-small' and self.sec_embedding_dims != 1536:
                raise ValueError(f"text-embedding-3-small requires 1536 dimensions, got {self.sec_embedding_dims}")
        
        # Routing optimization flags (NEW)
        self.doc_end_on_complete = os.getenv('DOC_END_ON_COMPLETE', 'true').lower() == 'true'
        self.doc_route_sticky = os.getenv('DOC_ROUTE_STICKY', 'true').lower() == 'true'

        # Insight generation configuration
        self.insight_max_concurrency = int(os.getenv('INSIGHT_MAX_CONCURRENCY', '10'))
        
        # =============================================================================
        # File Embedding Configuration (for files_chunks table)
        # Defaults to same settings as SEC embeddings for consistency
        # =============================================================================
        self.file_vectors_enabled = os.getenv('FILE_VECTORS_ENABLED', 'true').lower() == 'true'
        self.file_embedding_provider = os.getenv('FILE_EMBEDDING_PROVIDER', self.sec_embedding_provider)
        self.file_embedding_model = os.getenv('FILE_EMBEDDING_MODEL', self.sec_embedding_model)
        self.file_embedding_dims = int(os.getenv('FILE_EMBEDDING_DIMS', str(self.sec_embedding_dims)))
        self.file_vector_cast = os.getenv('FILE_VECTOR_CAST', self.sec_vector_cast)
        self.file_chunk_size = int(os.getenv('FILE_CHUNK_SIZE', '500'))  # chars per chunk
        self.file_chunk_overlap = int(os.getenv('FILE_CHUNK_OVERLAP', '50'))  # overlap chars
        self.file_top_k = int(os.getenv('FILE_TOP_K', '5'))  # default chunks to retrieve
        
        # =============================================================================
        # Memory Notebook Chunking Configuration
        # For semantic retrieval of large memory notes
        # =============================================================================
        self.memory_chunk_enabled = os.getenv('MEMORY_CHUNK_ENABLED', 'true').lower() == 'true'
        self.memory_chunk_size = int(os.getenv('MEMORY_CHUNK_SIZE', '500'))  # tokens per chunk
        self.memory_chunk_overlap = int(os.getenv('MEMORY_CHUNK_OVERLAP', '50'))  # overlap tokens
        self.memory_chunk_threshold = int(os.getenv('MEMORY_CHUNK_THRESHOLD', '1000'))  # min tokens to trigger chunking
        self.memory_chunk_top_k = int(os.getenv('MEMORY_CHUNK_TOP_K', '5'))  # chunks to retrieve per query
        self.memory_chunk_max_count = int(os.getenv('MEMORY_CHUNK_MAX_COUNT', '1000'))  # safety cap on chunks per note
        # Use same embedding config as files for consistency
        self.memory_embedding_provider = os.getenv('MEMORY_EMBEDDING_PROVIDER', self.file_embedding_provider)
        self.memory_embedding_model = os.getenv('MEMORY_EMBEDDING_MODEL', self.file_embedding_model)
        self.memory_embedding_dims = int(os.getenv('MEMORY_EMBEDDING_DIMS', str(self.file_embedding_dims)))
        self.memory_vector_cast = os.getenv('MEMORY_VECTOR_CAST', self.file_vector_cast)
        
        # =============================================================================
        # Workbook Indexing Configuration (Excel Agent)
        # Chunking and embedding for Excel workbook semantic search
        # =============================================================================
        self.workbook_embedding_model = os.getenv('WORKBOOK_EMBEDDING_MODEL', 'text-embedding-3-small')
        self.workbook_embedding_dims = int(os.getenv('WORKBOOK_EMBEDDING_DIMS', '1536'))
        self.workbook_vector_cast = os.getenv('WORKBOOK_VECTOR_CAST', 'vector')
        self.workbook_chunk_top_k = int(os.getenv('WORKBOOK_CHUNK_TOP_K', '10'))
        self.workbook_chunk_max_per_sheet = int(os.getenv('WORKBOOK_CHUNK_MAX_PER_SHEET', '200'))
        self.workbook_index_stale_days = int(os.getenv('WORKBOOK_INDEX_STALE_DAYS', '90'))

        # =============================================================================
        # Summarization Configuration
        # Model used for fast summarization tasks (file memory, etc.)
        # =============================================================================
        self.summarization_model = os.getenv('SUMMARIZATION_MODEL', 'gpt-4o-mini')
        
        # =============================================================================
        # File Memory Extraction Settings
        # Controls for FileMemoryService PDF/image processing
        # =============================================================================
        self.file_memory_max_tokens = int(os.getenv('FILE_MEMORY_MAX_TOKENS', '5000'))
        self.file_memory_vision_page_limit = int(os.getenv('FILE_MEMORY_VISION_PAGE_LIMIT', '5'))
        self.file_memory_pdf_text_threshold = int(os.getenv('FILE_MEMORY_PDF_TEXT_THRESHOLD', '3'))
        self.file_memory_pdf_min_chars_per_page = int(os.getenv('FILE_MEMORY_PDF_MIN_CHARS_PER_PAGE', '100'))

        # Validate critical settings
        self._validate_config()

    def _parse_csv_list(self, env_var_name: str, default_list: list) -> list:
        """Parse a comma-separated env var into a list of strings."""
        value = os.getenv(env_var_name)
        if value is None:
            return list(default_list)
        items = [item.strip() for item in value.split(',') if item.strip()]
        return items if items else list(default_list)

    def _parse_csv_tokens(self, env_var_name: str, default_tokens: set) -> set:
        """Parse a comma-separated env var into a lowercased set of tokens."""
        value = os.getenv(env_var_name)
        if value is None:
            return set(token.lower() for token in default_tokens)
        tokens = {token.strip().lower() for token in value.split(',') if token.strip()}
        return tokens if tokens else set(token.lower() for token in default_tokens)
    
    def _get_current_risk_free_rate(self) -> float:
        """Get current risk-free rate from FRED, FMP fallback, or use default."""
        # First check environment variable
        env_rate = os.getenv('RISK_FREE_RATE')
        if env_rate:
            return float(env_rate)

        # Try to fetch from FRED if API key available
        if self.fred_api_key:
            try:
                import socket
                from fredapi import Fred

                # Set timeout to prevent hanging
                original_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(5.0)

                try:
                    fred = Fred(api_key=self.fred_api_key)
                    # Get latest 3-month T-bill rate
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=7)
                    tb3ms = fred.get_series('TB3MS', start=start_date, end=end_date)
                    if not tb3ms.empty:
                        # Convert from percentage to decimal
                        latest_rate = tb3ms.iloc[-1] / 100
                        logger.info(f"Fetched current risk-free rate from FRED: {latest_rate:.4f}")
                        return latest_rate
                finally:
                    socket.setdefaulttimeout(original_timeout)
            except Exception as e:
                logger.warning(f"Failed to fetch risk-free rate from FRED: {e}")

        # Try FMP as fallback
        if self.fmp_api_key:
            try:
                import requests
                url = f"https://financialmodelingprep.com/stable/treasury-rates?apikey={self.fmp_api_key}"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        # Get 3-month rate from most recent data
                        latest = data[0]
                        if 'month3' in latest:
                            # FMP returns rate as percentage, convert to decimal
                            latest_rate = float(latest['month3']) / 100
                            logger.info(f"Fetched current risk-free rate from FMP: {latest_rate:.4f}")
                            return latest_rate
            except Exception as e:
                logger.warning(f"Failed to fetch risk-free rate from FMP: {e}")

        # Fall back to default
        logger.info(f"Using default risk-free rate: {DEFAULT_RISK_FREE_RATE}")
        return DEFAULT_RISK_FREE_RATE
    
    def _validate_config(self) -> None:
        """Validate configuration values."""
        if not self.openai_api_key and not self.perplexity_api_key:
            raise ValueError("Either OPENAI_API_KEY or PERPLEXITY_API_KEY is required")
        
        if self.portfolio_value <= 0:
            raise ValueError(f"Portfolio value must be positive, got {self.portfolio_value}")
        
        if not 0 < self.max_var_95 < 1:
            raise ValueError(f"MAX_VAR_95 must be between 0 and 1, got {self.max_var_95}")
        
        if not 0 < self.max_concentration <= 1:
            raise ValueError(f"MAX_CONCENTRATION must be between 0 and 1, got {self.max_concentration}")
        
        if self.mc_simulations < MIN_MC_SIMULATIONS:
            raise ValueError(f"MC_SIMULATIONS must be at least {MIN_MC_SIMULATIONS}, got {self.mc_simulations}")

        if self.google_drive_enabled:
            missing_fields = []
            if not self.google_drive_client_id:
                missing_fields.append('GOOGLE_DRIVE_CLIENT_ID')
            if not self.google_drive_client_secret:
                missing_fields.append('GOOGLE_DRIVE_CLIENT_SECRET')
            if not self.google_drive_redirect_uri:
                missing_fields.append('GOOGLE_DRIVE_REDIRECT_URI')
            if not self.google_drive_encryption_key:
                missing_fields.append('GOOGLE_DRIVE_ENCRYPTION_KEY')
            if not self.google_drive_scopes:
                missing_fields.append('GOOGLE_DRIVE_SCOPES')

            if missing_fields:
                raise ValueError(
                    f"Google Drive integration enabled but missing required settings: {', '.join(missing_fields)}"
                )

            # Validate encryption key format (Fernet requires URL-safe base64 32 bytes)
            try:
                from cryptography.fernet import Fernet
                Fernet(self.google_drive_encryption_key)
            except Exception as exc:  # pragma: no cover - configuration validation
                raise ValueError(
                    "GOOGLE_DRIVE_ENCRYPTION_KEY must be a valid Fernet key (URL-safe base64, 32 bytes)"
                ) from exc
        
        if self.onedrive_enabled:
            missing_fields = []
            if not self.onedrive_client_id:
                missing_fields.append('ONEDRIVE_CLIENT_ID')
            if not self.onedrive_client_secret:
                missing_fields.append('ONEDRIVE_CLIENT_SECRET')
            if not self.onedrive_redirect_uri:
                missing_fields.append('ONEDRIVE_REDIRECT_URI')
            if not self.onedrive_encryption_key:
                missing_fields.append('ONEDRIVE_ENCRYPTION_KEY')
            if not self.onedrive_scopes:
                missing_fields.append('ONEDRIVE_SCOPES')
            if missing_fields:
                raise ValueError(
                    f"OneDrive integration enabled but missing required settings: {', '.join(missing_fields)}"
                )
            try:
                from cryptography.fernet import Fernet
                Fernet(self.onedrive_encryption_key)
            except Exception as exc:
                raise ValueError(
                    "ONEDRIVE_ENCRYPTION_KEY must be a valid Fernet key (URL-safe base64, 32 bytes)"
                ) from exc
    
    def get_risk_limits(self) -> Dict[str, float]:
        """Get all risk limits as a dictionary."""
        return {
            'max_var_95': self.max_var_95,
            'max_concentration': self.max_concentration,
            'min_sharpe_ratio': self.min_sharpe_ratio
        }
    
    def get_simulation_params(self) -> Dict[str, Any]:
        """Get Monte Carlo simulation parameters."""
        return {
            'n_simulations': self.mc_simulations,
            'time_horizon': self.mc_time_horizon,
            'trading_days': self.trading_days
        }
    
    def get_portfolio_params(self) -> Dict[str, float]:
        """Get portfolio-related parameters."""
        return {
            'portfolio_value': self.portfolio_value,
            'risk_free_rate': self.risk_free_rate
        }
    
    def get_data_params(self) -> Dict[str, Any]:
        """Get data fetching parameters."""
        return {
            'lookback_years': self.lookback_years,
            'frequency': self.data_frequency
        }
    
    def update_config(self, **kwargs) -> None:
        """Update configuration values at runtime."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise ValueError(f"Unknown configuration key: {key}")
        
        # Re-validate after updates
        self._validate_config()
    
    def _is_placeholder_key(self, key_value: Optional[str]) -> bool:
        """Check if an API key looks like a placeholder."""
        if not key_value:
            return True
        
        placeholder_patterns = [
            'your_', 'YOUR_',
            '_here', '_HERE',
            'xxx', 'XXX',
            'placeholder', 'PLACEHOLDER',
            'example', 'EXAMPLE',
            'test', 'TEST',
            'demo', 'DEMO',
            'dummy', 'DUMMY',
            'fake', 'FAKE',
            'sample', 'SAMPLE'
        ]
        
        key_lower = key_value.lower()
        return any(pattern in key_lower for pattern in [p.lower() for p in placeholder_patterns])
    
    def check_api_keys_validity(self) -> Dict[str, str]:
        """Check API keys for placeholder values and return warnings."""
        warnings = {}
        
        if self._is_placeholder_key(self.openai_api_key):
            warnings['openai'] = "OpenAI API key appears to be a placeholder. Please set a valid key."
        
        if self._is_placeholder_key(self.perplexity_api_key):
            warnings['perplexity'] = "Perplexity API key appears to be a placeholder. Please set a valid key."
        
        if self._is_placeholder_key(self.fred_api_key):
            warnings['fred'] = "FRED API key appears to be a placeholder. Please set a valid key."
        
        if self._is_placeholder_key(self.fmp_api_key):
            warnings['fmp'] = "FMP API key appears to be a placeholder. Please set a valid key."
        
        # Log warnings
        for provider, warning in warnings.items():
            logger.warning(f"API Key Warning - {provider}: {warning}")
        
        return warnings


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config


def validate_api_keys() -> Dict[str, bool]:
    """Validate that required API keys are present."""
    return {
        'openai': bool(config.openai_api_key),
        'fred': bool(config.fred_api_key),
        'fmp': bool(config.fmp_api_key)
    }


def get_env_summary() -> Dict[str, Any]:
    """Get a summary of current environment configuration."""
    return {
        'portfolio_value': config.portfolio_value,
        'mc_simulations': config.mc_simulations,
        'risk_limits': config.get_risk_limits(),
        'api_keys_present': validate_api_keys()
    }
