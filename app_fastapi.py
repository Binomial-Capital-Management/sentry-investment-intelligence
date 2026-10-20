"""Thin FastAPI app that wires lifespan, CORS, and routers.

All heavy endpoint logic lives under the `api/` package.

# FORCE_RELOAD_MARKER_V1 - This comment triggers Uvicorn to reload
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any

from core.exceptions import CanvasBaseException
import traceback
import asyncio
from contextlib import asynccontextmanager
import logging

import io
from datetime import datetime
import os

# Initialize Sentry before other imports
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from core.config import get_config
from api.orchestrator import get_v6_orchestrator
from api.db import init_conversation_store
from api.routers.v6 import router as v6_router
from api.routers.auth import router as auth_router
from api.routers.sse_tickets import router as sse_tickets_router
from api.routers.organizations import router as organizations_router
from api.routers.portfolios import router as portfolios_router
from api.routers.portfolio_history import router as portfolio_history_router
from api.routers.portfolio_risk import router as portfolio_risk_router
from api.routers.chats import router as chats_router
from api.routers.brokers import router as brokers_router
from api.routers.uploads import router as uploads_router
from api.routers.exports import router as exports_router
from api.routers.websocket import router as websocket_router
from api.routers.workflows import router as workflows_router
from api.routers.workflow_assistant import router as workflow_assistant_router
from api.routers.workflow_capabilities import router as workflow_capabilities_router
from api.routers.tasks import router as tasks_router
from api.routers.task_assistant import router as task_assistant_router
from api.routers.slack_integration import router as slack_integration_router
from api.routers.teams_integration import router as teams_integration_router
from api.routers.email_lists import router as email_lists_router
from api.routers.contact import router as contact_router
from api.routers.bug_reports import router as bug_reports_router
from api.routers.ticker_search import router as ticker_search_router
from api.routers.institution_search import router as institution_search_router
from api.routers.filings import router as filings_router
from api.routers.user_lists import router as user_lists_router
from api.routers.google_drive import router as google_drive_router
from api.routers.onedrive import router as onedrive_router
from api.routers.insights import router as insights_router
from api.routers.market_data import router as market_data_router
from api.routers.screener import router as screener_router
from api.routers.user_settings import router as user_settings_router
from api.routers.gamma_themes import router as gamma_themes_router
from api.routers.postmortems import router as postmortems_router
from api.routers.marketplace import router as marketplace_router
from api.routers.canvas import router as canvas_router
from api.routers.memory import router as memory_router
from api.routers.studio import router as studio_router
from api.routers.excel_agent import router as excel_agent_router
from core.auth import get_clerk_auth
# Legacy middleware - still used for now, will be replaced with split middleware
from api.middleware.auth_context import RLSContextMiddleware
# New split middleware (available for future migration)
# from core.auth.middleware import AuthMiddleware, RLSMiddleware, OrganizationMiddleware

_log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

# Configure logging with both console and file output
_log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
_log_file = os.path.join(os.path.dirname(__file__), 'logs', 'backend.log')

# Ensure logs directory exists
os.makedirs(os.path.dirname(_log_file), exist_ok=True)

# Set up root logger
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format=_log_format,
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler(_log_file, mode='a', encoding='utf-8'),  # File output
    ]
)

# Quiet noisy third-party loggers
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("openai.agents").setLevel(logging.INFO)  # Keep agent lifecycle events
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("watchfiles").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.info(f"Backend logging to file: {_log_file}")

config = get_config()

SCHEDULER_METADATA = {
    "portfolio": "Portfolio value refresh (weekdays 5 PM ET)",
    "insight": "Insight generation (daily 6 AM ET)",
    "fgi": "Fear & Greed Index ingest (weekdays 8 AM & 2 PM ET)",
    "tasks": "User task scheduler (dynamic APScheduler jobs)",
    "ibkr": "IBKR position refresh (12 PM & 5:30 PM ET)",
}


def _initial_scheduler_status():
    """Provide a baseline scheduler status map for health reporting."""
    now = datetime.now().isoformat()
    return {
        name: {
            "running": False,
            "details": details,
            "error": "not started",
            "updated_at": now,
        }
        for name, details in SCHEDULER_METADATA.items()
    }

# Initialize Sentry if DSN is provided
SENTRY_DSN = os.getenv("SENTRY_DSN")  # Must be set via environment variable, not hardcoded
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            FastApiIntegration(
                transaction_style="endpoint",
                failed_request_status_codes=[400, 403, 404, 405, 409, 410, 422, 429, 500, 501, 502, 503, 504],
            ),
            LoggingIntegration(
                level=logging.INFO,  # Capture info and above as breadcrumbs
                event_level=logging.ERROR  # Send errors as events
            ),
        ],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),  # 10% in production
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),  # 10% profiling
        environment=os.getenv("ENVIRONMENT", "development"),
        release=os.getenv("RELEASE_VERSION", "v6.1.0"),
        send_default_pii=False,  # Don't send PII data
        attach_stacktrace=True,
        before_send=lambda event, hint: filter_sensitive_data(event),
    )
    logger.info(f"Sentry initialized for environment: {os.getenv('ENVIRONMENT', 'development')}")
else:
    logger.info("Sentry DSN not provided, error tracking disabled")

def filter_sensitive_data(event):
    """Filter out sensitive data from Sentry events"""
    # Remove sensitive headers
    if "request" in event and "headers" in event["request"]:
        sensitive_headers = ["authorization", "cookie", "x-api-key", "x-clerk-session"]
        for header in sensitive_headers:
            if header in event["request"]["headers"]:
                event["request"]["headers"][header] = "[FILTERED]"
    
    # Remove sensitive data from extra context
    if "extra" in event:
        sensitive_keys = ["password", "token", "secret", "api_key", "clerk_user_id"]
        for key in sensitive_keys:
            if key in event["extra"]:
                event["extra"][key] = "[FILTERED]"
    
    return event


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request timeouts.
    Prevents hung requests from blocking workers indefinitely.
    
    Default: 1800 seconds (30 minutes) - allows for heavy AI/risk calculations and long tasks
    Long-running endpoints (chat, tasks, exports, workflows) are excluded entirely.
    """
    
    def __init__(self, app, timeout_seconds: int = 1800):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds
    
    async def dispatch(self, request: Request, call_next):
        # Skip timeout for long-running endpoints:
        # - /ws/ : WebSocket connections
        # - /v6/chat : AI chat (can take 15-20+ minutes for deep analysis)
        # - /api/tasks : Task execution (can take 15-20+ minutes)
        # - /api/workflows : Workflow execution
        # - /v6/export, /api/exports : PDF/PPTX generation
        # - /api/brokers/ibkr/sync : IBKR sync can be slow
        skip_paths = [
            "/ws/",
            "/v6/chat",
            "/api/tasks",
            "/api/workflows", 
            "/v6/export",
            "/api/exports",
            "/api/brokers/ibkr/sync",
        ]
        if any(request.url.path.startswith(p) for p in skip_paths):
            return await call_next(request)
        
        try:
            return await asyncio.wait_for(
                call_next(request), 
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.error(f"Request timeout ({self.timeout_seconds}s) on {request.method} {request.url.path}")
            return JSONResponse(
                status_code=504,
                content={
                    "error": True,
                    "detail": f"Request timed out after {self.timeout_seconds} seconds",
                    "path": str(request.url.path),
                }
            )


async def verify_database_role_security():
    """Verify the database role has proper security settings (not superuser, not bypassrls)"""
    import asyncpg
    import time
    
    if not config.enable_postgres:
        return
    
    start_time = time.time()
    try:
        # Connect to verify role permissions
        conn = await asyncpg.connect(config.database_url)
        try:
            # Check current role and its privileges
            role_info = await conn.fetchrow("""
                SELECT current_user as role_name,
                       rolsuper,
                       rolbypassrls
                FROM pg_roles
                WHERE rolname = current_user
            """)
            
            if not role_info:
                raise RuntimeError("Could not fetch database role information")
            
            role_name = role_info['role_name']
            is_superuser = role_info['rolsuper']
            bypasses_rls = role_info['rolbypassrls']
            
            # Fail if dangerous privileges detected
            if is_superuser:
                raise RuntimeError(
                    f"SECURITY ERROR: Database role '{role_name}' is a SUPERUSER. "
                    f"This bypasses all Row-Level Security! "
                    f"Please use a non-superuser role (e.g., {config.db_app_role})."
                )
            
            if bypasses_rls:
                raise RuntimeError(
                    f"SECURITY ERROR: Database role '{role_name}' has BYPASSRLS privilege. "
                    f"This bypasses Row-Level Security! "
                    f"Please use a role without BYPASSRLS."
                )
            
            # Check row_security setting
            try:
                val = await conn.fetchval("SELECT current_setting('row_security')")
                is_on = str(val).lower() == 'on'
                logger.info(f"Database row_security setting: {val} (enabled: {is_on})")
            except Exception as e:
                logger.warning(f"Could not check row_security setting: {e}")
            
            # Check FORCE RLS on tenant tables (dynamically discovered)
            tenant_tables = await conn.fetch("""
                SELECT DISTINCT t.tablename
                FROM pg_tables t
                JOIN pg_class c ON c.relname = t.tablename
                WHERE t.schemaname = 'public'
                AND t.tablename IN (
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                    AND (tablename LIKE '%portfolio%' 
                         OR tablename LIKE '%chat%' 
                         OR tablename LIKE '%workflow%'
                         OR tablename = 'risk_analyses')
                    AND tablename != 'users'  -- Exclude users table (managed by Clerk)
                )
            """)
            
            # Check relforcerowsecurity for each tenant table
            force_rls_results = []
            for table in tenant_tables:
                force_rls = await conn.fetchval("""
                    SELECT c.relforcerowsecurity
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relname = $1 AND n.nspname = 'public'
                """, table['tablename'])
                force_rls_results.append((table['tablename'], force_rls))
                if not force_rls:
                    logger.warning(f"⚠️ Table '{table['tablename']}' does not have FORCE RLS enabled")
            
            # Log summary
            tables_with_force = sum(1 for _, forced in force_rls_results if forced)
            elapsed = time.time() - start_time
            logger.info(
                f"✅ Role '{role_name}' security verified in {elapsed:.2f}s - "
                f"superuser={is_superuser}, bypassrls={bypasses_rls}, "
                f"force_rls={tables_with_force}/{len(force_rls_results)} tables"
            )
            
        finally:
            await conn.close()
            
    except RuntimeError:
        # Security violations (superuser, bypassrls) — must be fatal
        raise
    except Exception as e:
        error_msg = str(e) if e else "Unknown error"
        logger.warning(f"Database role verification failed (non-fatal): {error_msg}")
        logger.warning(f"DATABASE_URL configured: {bool(config.database_url)}")
        logger.warning(f"Exception type: {type(e).__name__}")
        logger.warning("Continuing startup — RLS verification will be skipped")


async def run_database_migrations():
    """Run database migrations using Alembic.
    
    This replaces the custom SQL migration runner with Alembic,
    which properly handles complex SQL including $$ dollar-quoted blocks.
    """
    import asyncpg
    from pathlib import Path
    from datetime import datetime
    
    # Set up file logging for migrations
    migration_log_path = Path(__file__).parent / "logs" / "migrations.log"
    migration_log_path.parent.mkdir(exist_ok=True)
    
    file_handler = logging.FileHandler(migration_log_path, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    logger.info(f"=== Migration Run Started: {datetime.now().isoformat()} ===")
    logger.info("Running Alembic migrations...")

    try:
        # Run Alembic migrations (synchronous, uses psycopg2)
        from alembic.config import Config
        from alembic import command
        
        alembic_cfg = Config(str(Path(__file__).parent / "alembic.ini"))
        
        # Run upgrade to head
        logger.info("Upgrading database to head revision...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations completed successfully")
        
        # Verify critical tables exist using asyncpg
        logger.info("Verifying critical tables...")
        conn = await asyncpg.connect(config.database_url)
        try:
            tables_to_check = ['users', 'portfolios', 'chat_sessions', 'chat_messages']
            missing_tables = []

            for table in tables_to_check:
                exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = $1
                    )
                """, table)

                if not exists:
                    missing_tables.append(table)

            if missing_tables:
                logger.error(f"Critical tables missing after migrations: {missing_tables}")
                logger.info(f"=== Migration Run Finished (FAILED) ===")
                logger.info(f"Full migration log saved to: {migration_log_path}")
                logger.removeHandler(file_handler)
                file_handler.close()
                return False
            else:
                logger.info("All critical database tables exist")
                logger.info(f"=== Migration Run Finished (SUCCESS) ===")
                logger.info(f"Full migration log saved to: {migration_log_path}")
                logger.removeHandler(file_handler)
                file_handler.close()
                return True
        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        logger.info(f"=== Migration Run Finished (ERROR) ===")
        logger.info(f"Full migration log saved to: {migration_log_path}")
        logger.removeHandler(file_handler)
        file_handler.close()
        return False


async def run_rls_canary_test():
    """Run a canary test to verify RLS is working (for staging/dev environments)"""
    import asyncpg
    import uuid
    from datetime import datetime

    logger.info("Running RLS canary test...")

    try:
        # Connect as app role
        conn = await asyncpg.connect(config.database_url)
        try:
            test_user_a = f"canary_user_a_{uuid.uuid4().hex[:8]}"
            test_user_b = f"canary_user_b_{uuid.uuid4().hex[:8]}"
            test_portfolio_id = None
            
            try:
                # Create test portfolio as user A
                await conn.execute("SET LOCAL app.current_user_id = $1", test_user_a)
                test_portfolio_id = await conn.fetchval(
                    """
                    INSERT INTO portfolios (user_id, name, tickers, weights, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $5)
                    RETURNING id
                    """,
                    test_user_a, "RLS_CANARY_TEST", ["TEST"], [1.0], datetime.utcnow()
                )
                
                # Try to read as user B (should fail/return nothing)
                await conn.execute("SET LOCAL app.current_user_id = $1", test_user_b)
                leaked_data = await conn.fetch(
                    "SELECT * FROM portfolios WHERE id = $1",
                    test_portfolio_id
                )
                
                if leaked_data:
                    raise RuntimeError(
                        f"RLS BREACH DETECTED: User B could see User A's portfolio! "
                        f"Found {len(leaked_data)} rows. RLS is not working correctly."
                    )
                
                # Test UPDATE as user B (should affect 0 rows)
                update_result = await conn.execute(
                    "UPDATE portfolios SET name = 'HACKED' WHERE id = $1",
                    test_portfolio_id
                )
                if update_result != "UPDATE 0":
                    raise RuntimeError(f"RLS BREACH: User B could update User A's portfolio!")
                
                # Test DELETE as user B (should affect 0 rows)
                delete_result = await conn.execute(
                    "DELETE FROM portfolios WHERE id = $1",
                    test_portfolio_id
                )
                if delete_result != "DELETE 0":
                    raise RuntimeError(f"RLS BREACH: User B could delete User A's portfolio!")
                
                # Verify user A can still see it
                await conn.execute("SET LOCAL app.current_user_id = $1", test_user_a)
                owned_data = await conn.fetch(
                    "SELECT * FROM portfolios WHERE id = $1",
                    test_portfolio_id
                )
                
                if not owned_data:
                    raise RuntimeError("RLS ERROR: User A cannot see their own portfolio!")
                
                logger.info("✅ RLS canary test PASSED: User isolation verified (SELECT/UPDATE/DELETE)")
                
            finally:
                # Clean up test data
                if test_portfolio_id:
                    await conn.execute("SET LOCAL app.current_user_id = $1", test_user_a)
                    await conn.execute("DELETE FROM portfolios WHERE id = $1", test_portfolio_id)
                    
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"RLS canary test failed: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_status = getattr(app.state, "scheduler_status", None)
    if scheduler_status is None:
        app.state.scheduler_status = _initial_scheduler_status()
        scheduler_status = app.state.scheduler_status

    def record_scheduler(name: str, running: bool, *, error: str | None = None):
        details = scheduler_status.get(name, {}).get("details") or SCHEDULER_METADATA.get(name)
        scheduler_status[name] = {
            "running": bool(running),
            "details": details,
            "error": error,
            "updated_at": datetime.now().isoformat(),
        }

    kafka_producer = None
    screener_hub = None
    portfolio_started = False
    portfolio_stop = None
    insight_scheduler = None
    insight_started = False
    task_scheduler_started = False
    task_stop_fn = None
    position_scheduler = None
    ibkr_started = False
    cleanup_done = False

    async def shutdown_resources():
        nonlocal cleanup_done
        if cleanup_done:
            return
        cleanup_done = True

        if portfolio_started and portfolio_stop:
            try:
                await portfolio_stop()
            except Exception as exc:
                logger.error("Error stopping portfolio scheduler: %s", exc)
            record_scheduler("portfolio", False)

        if insight_started and insight_scheduler:
            try:
                await insight_scheduler.stop()
                logger.info("Insight scheduler stopped")
            except Exception as exc:
                logger.error("Error stopping insight scheduler: %s", exc)
            record_scheduler("insight", False)

        if task_scheduler_started and task_stop_fn:
            try:
                await task_stop_fn()
            except Exception as exc:
                logger.error("Error stopping task scheduler: %s", exc)
            record_scheduler("tasks", False)

        if ibkr_started and position_scheduler:
            try:
                await position_scheduler.shutdown()
                logger.info("IBKR position refresh scheduler stopped")
            except Exception as exc:
                logger.error("Error stopping IBKR scheduler: %s", exc)
            record_scheduler("ibkr", False)

        try:
            orch = get_v6_orchestrator()
            await orch.close()
        except Exception as exc:
            logger.warning("Shutdown cleanup error (orchestrator): %s", exc)

        if screener_hub:
            try:
                await screener_hub.stop()
                logger.info("ScreenerHub stopped")
            except Exception as exc:
                logger.warning("Failed to stop ScreenerHub: %s", exc)
            finally:
                if hasattr(app.state, "screener_hub"):
                    delattr(app.state, "screener_hub")

        if kafka_producer:
            try:
                await kafka_producer.stop()
            except Exception as exc:
                logger.warning("Failed to stop Kafka producer: %s", exc)

    try:
        # Ensure EFS directories exist and are writable for SQLite databases
        config = get_config()

        # AWS Bedrock authentication uses ECS task role (no hardcoded keys)
        if not os.getenv("AWS_REGION"):
            os.environ["AWS_REGION"] = "us-east-1"
        logger.info("✅ AWS credentials via ECS task role (Bedrock, S3, Lambda)")

        import litellm
        litellm.modify_params = True
        litellm.drop_params = True
        litellm.set_verbose = False
        logger.info("✅ LiteLLM modify_params + drop_params enabled for cross-provider compatibility")

        efs_dirs = [
            os.path.dirname(config.langgraph_db_path),
            os.path.dirname(config.openai_sessions_db_path),
            os.path.dirname(config.conversation_db_path),
        ]

        for efs_dir in efs_dirs:
            if not efs_dir:
                continue
            os.makedirs(efs_dir, mode=0o755, exist_ok=True)
            test_file = os.path.join(efs_dir, ".write_test")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                # Clean up test file (ignore if already removed)
                try:
                    os.remove(test_file)
                except FileNotFoundError:
                    pass
                logger.info("✅ EFS directory ready: %s", efs_dir)
            except Exception as exc:
                logger.error("❌ EFS directory not writable: %s - %s", efs_dir, exc)
                raise RuntimeError(f"EFS mount not writable at {efs_dir}: {exc}") from exc

        if config.enable_postgres:
            # Skip migrations on startup unless explicitly enabled (run manually with: alembic upgrade head)
            if os.getenv("RUN_MIGRATIONS_ON_STARTUP", "false").lower() == "true":
                logger.info("Running database migrations...")
                migration_success = await run_database_migrations()
                if not migration_success:
                    logger.error("Database migration failed - continuing with degraded functionality")
            else:
                logger.info("Skipping migrations on startup (set RUN_MIGRATIONS_ON_STARTUP=true to enable)")

            if config.skip_rls_checks:
                if os.getenv("FLASK_ENV", "development") != "development":
                    raise RuntimeError("SECURITY ERROR: SKIP_RLS_CHECKS cannot be used outside development!")
                logger.warning("⚠️ RLS CHECKS BYPASSED - DEV MODE ONLY")
            else:
                await verify_database_role_security()

            if os.getenv("RUN_RLS_CANARY_TEST", "false").lower() == "true":
                await run_rls_canary_test()

        orch = get_v6_orchestrator()
        await orch.ensure_compiled()
        await orch.connect_mcp_servers()
        await init_conversation_store()
        logger.info("V6 orchestrator ready; conversation store initialized; MCP servers connected")

        import asyncio
        from core.streaming import KafkaConfig, MarketDataProducer
        from core.streaming.screener_hub import ScreenerHub

        kafka_config = KafkaConfig()
        if kafka_config.is_enabled():
            producer_candidate = MarketDataProducer(kafka_config)
            if await producer_candidate.start():
                kafka_producer = producer_candidate
                logger.info("Kafka producer started, enabling streaming with delays")
                asyncio.create_task(producer_candidate.stream_screener_universe())
            else:
                logger.warning("Kafka producer failed to start")

            hub_candidate = ScreenerHub(kafka_config)
            if await hub_candidate.start():
                screener_hub = hub_candidate
                app.state.screener_hub = screener_hub
                logger.info("ScreenerHub started with single Kafka consumer")
            else:
                logger.warning("ScreenerHub failed to start")

        from core.services.portfolio_scheduler import portfolio_scheduler, start_scheduler, stop_scheduler

        portfolio_stop = stop_scheduler
        try:
            await start_scheduler()
            if portfolio_scheduler.is_running:
                portfolio_started = True
                record_scheduler("portfolio", True)
            else:
                record_scheduler("portfolio", False, error="Portfolio scheduler did not report running")
        except Exception as exc:
            logger.error("Failed to start portfolio scheduler: %s", exc, exc_info=True)
            record_scheduler("portfolio", False, error=str(exc))

        from core.services.insight_scheduler import get_insight_scheduler

        try:
            insight_scheduler = await get_insight_scheduler(concurrency=100)
            await insight_scheduler.start()
            insight_started = insight_scheduler.is_running
            if insight_started:
                logger.info("Insight scheduler started (6 AM ET daily)")
                record_scheduler("insight", True)
            else:
                record_scheduler("insight", False, error="Insight scheduler did not report running")
        except Exception as exc:
            logger.error("Failed to start insight scheduler: %s", exc, exc_info=True)
            record_scheduler("insight", False, error=str(exc))

        # FGI scheduler now runs as AWS Lambda (fear-greed-index) triggered by EventBridge
        # Scheduled at 8 AM and 2 PM ET on weekdays
        record_scheduler("fgi", False, error="Migrated to AWS Lambda")

        tasks_enabled = os.getenv("TASK_SCHEDULER_ENABLED", "true").lower() == "true"
        if tasks_enabled:
            from core.services.task_scheduler import start_task_scheduler, stop_task_scheduler, task_scheduler

            task_stop_fn = stop_task_scheduler
            try:
                await start_task_scheduler()
                task_scheduler_started = task_scheduler.is_running
                record_scheduler("tasks", task_scheduler_started, error=None if task_scheduler_started else "Task scheduler did not report running")
            except Exception as exc:
                logger.error("Failed to start task scheduler: %s", exc, exc_info=True)
                record_scheduler("tasks", False, error=str(exc))
        else:
            record_scheduler("tasks", False, error="TASK_SCHEDULER_ENABLED=false")

        from core.scheduler.position_refresh import get_position_refresh_scheduler

        position_scheduler = get_position_refresh_scheduler()
        if position_scheduler.enabled:
            try:
                await position_scheduler.start()
                ibkr_started = position_scheduler.is_running
                record_scheduler("ibkr", ibkr_started, error=None if ibkr_started else "IBKR scheduler did not report running")
            except Exception as exc:
                logger.error("Failed to start IBKR scheduler: %s", exc, exc_info=True)
                record_scheduler("ibkr", False, error=str(exc))
        else:
            record_scheduler("ibkr", False, error="IBKR position refresh disabled")

    except Exception as exc:
        logger.error("Startup initialization failed: %s", exc, exc_info=True)
        await shutdown_resources()
        raise

    try:
        yield
    finally:
        await shutdown_resources()

app = FastAPI(
    lifespan=lifespan,
    title=config.fastapi_title,
    description=config.fastapi_description,
    version=config.fastapi_version,
)
app.state.scheduler_status = _initial_scheduler_status()


# =============================================================================
# GLOBAL EXCEPTION HANDLERS - Prevent crashes on any error
# =============================================================================

@app.exception_handler(CanvasBaseException)
async def canvas_exception_handler(request: Request, exc: CanvasBaseException):
    """
    Handle all Canvas custom exceptions (UnauthorizedError, ProcessNotFoundError, etc.)
    
    Returns structured JSON response with error code and message.
    """
    # Log at appropriate level based on status code
    if exc.status_code >= 500:
        logger.error(
            f"[{exc.error_code}] {exc.message}",
            extra={
                "status_code": exc.status_code,
                "path": str(request.url.path),
                "method": request.method,
                "details": exc.details,
                "user_id": getattr(request.state, 'user_id', None),
            },
        )
        # Report to Sentry for 5xx errors
        if SENTRY_DSN:
            try:
                sentry_sdk.capture_exception(exc)
            except Exception:
                pass
    elif exc.status_code >= 400:
        logger.warning(
            f"[{exc.error_code}] {exc.message}",
            extra={
                "status_code": exc.status_code,
                "path": str(request.url.path),
                "details": exc.details,
            }
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions gracefully without crashing"""
    logger.warning(f"HTTP {exc.status_code} on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "detail": str(exc.detail),
            "status_code": exc.status_code,
            "path": str(request.url.path),
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors gracefully"""
    logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "detail": "Validation error",
            "errors": exc.errors(),
            "path": str(request.url.path),
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler to prevent crashes.
    
    This ensures that ANY unhandled exception returns a proper error response
    instead of crashing the worker.
    """
    # Log the full traceback for debugging
    error_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{id(exc)}"
    
    logger.error(
        f"Unhandled exception [{error_id}] on {request.method} {request.url.path}: "
        f"{type(exc).__name__}: {str(exc)}"
    )
    logger.error(f"Full traceback [{error_id}]:\n{traceback.format_exc()}")
    
    # Report to Sentry if configured
    if SENTRY_DSN:
        try:
            sentry_sdk.capture_exception(exc)
        except Exception:
            pass  # Don't crash on Sentry errors
    
    # Return a safe error response
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "detail": "Internal server error. The issue has been logged.",
            "error_id": error_id,
            "path": str(request.url.path),
            # Don't expose internal error details in production
            "message": str(exc) if os.getenv("ENVIRONMENT") != "production" else "An unexpected error occurred",
        }
    )

cors_kwargs: Dict[str, Any] = {
    "allow_origins": config.cors_allow_origins,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if config.cors_allow_origin_regex:
    cors_kwargs["allow_origin_regex"] = config.cors_allow_origin_regex
app.add_middleware(CORSMiddleware, **cors_kwargs)

# Add RLS middleware for PostgreSQL user isolation
app.add_middleware(RLSContextMiddleware)

# Add logging context middleware for request tracing
# This captures user_id/org_id from RLSContextMiddleware and propagates to all loggers
from api.middleware.logging_middleware import LoggingContextMiddleware
app.add_middleware(LoggingContextMiddleware)

# Add request timeout middleware (30 minutes default, prevents hung requests)
# Long-running endpoints (chat, tasks, workflows, exports) are excluded entirely
# Note: Middleware executes in reverse order, so this runs FIRST (outermost)
app.add_middleware(RequestTimeoutMiddleware, timeout_seconds=1800)

# Mount routers (primary API lives under /v6)
app.include_router(v6_router)
app.include_router(auth_router)
app.include_router(sse_tickets_router)
app.include_router(organizations_router)
app.include_router(portfolios_router)
app.include_router(portfolio_history_router)
app.include_router(portfolio_risk_router)
app.include_router(chats_router)
app.include_router(brokers_router)
app.include_router(uploads_router)
app.include_router(exports_router)
app.include_router(websocket_router)
app.include_router(workflows_router)
app.include_router(workflow_assistant_router)
app.include_router(workflow_capabilities_router)
app.include_router(tasks_router)
app.include_router(task_assistant_router)
app.include_router(slack_integration_router)
app.include_router(teams_integration_router)
app.include_router(email_lists_router)
app.include_router(contact_router)
app.include_router(bug_reports_router)
app.include_router(ticker_search_router)
app.include_router(institution_search_router)
app.include_router(filings_router)
app.include_router(user_lists_router)
app.include_router(google_drive_router)
app.include_router(onedrive_router)
app.include_router(insights_router)
app.include_router(market_data_router)
app.include_router(screener_router)
app.include_router(user_settings_router)
app.include_router(gamma_themes_router)
app.include_router(postmortems_router)
app.include_router(marketplace_router)
app.include_router(canvas_router)
app.include_router(memory_router)
app.include_router(studio_router)
app.include_router(excel_agent_router)

@app.get("/")
async def root():
    return {
        "name": "Binomial Risk Analyst V6 API",
        "status": "operational",
        "version": config.fastapi_version,
        "endpoints": {
            "/v6/chat": "POST - Process chat messages with V6 orchestrator",
            "/health": "GET - Health check endpoint",
            "/metrics": "GET - Performance metrics",
        },
    }

@app.get("/health")
async def health_check():
    """Simple health check - if app responds, it's healthy.
    Orchestrator availability is checked separately via /health/schedulers.
    """
    return {"status": "healthy"}


@app.get("/health/schedulers")
async def scheduler_health():
    status = getattr(app.state, "scheduler_status", None)
    if not status:
        status = _initial_scheduler_status()
        app.state.scheduler_status = status
    overall = "healthy" if all(entry.get("running") for entry in status.values()) else "degraded"
    return {
        "status": overall,
        "schedulers": status,
    }


@app.get("/v6/health")
async def v6_health_check():
    return await health_check()

@app.get("/metrics")
async def get_metrics():
    try:
        orch = get_v6_orchestrator()
        return orch.get_performance_metrics() if hasattr(orch, 'get_performance_metrics') else {"message": "Metrics not available"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/sentry-debug")
async def trigger_error():
    """Debug endpoint to test Sentry integration"""
    # Only enable in development
    if os.getenv("ENVIRONMENT", "development") == "production":
        return {"message": "Debug endpoint disabled in production"}
    
    sentry_sdk.capture_message("Test message from FastAPI", level="info")
    # This will trigger an error that Sentry will capture
    division_by_zero = 1 / 0

# Export endpoints are handled by the exports router at /v6/export/*
# The exports router is mounted above and handles /v6/export/pdf and other export endpoints

if __name__ == "__main__":
    import uvicorn
    logger.info(
        "Starting FastAPI server on %s:%s (workers=%s)",
        config.fastapi_host,
        config.fastapi_port,
        config.fastapi_workers,
    )
    # Suppress noisy watchfiles polling logs (VS Code git status triggers .git changes every 10s)
    # Must be set here (supervisor process), not in lifespan (worker subprocess)
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)

    uvicorn.run(
        "app_fastapi:app",
        host=config.fastapi_host,
        port=config.fastapi_port,
        reload=config.fastapi_reload,
        reload_excludes=[".git"] if config.fastapi_reload else None,
        log_level=str(config.log_level).lower(),
        workers=config.fastapi_workers,
        timeout_keep_alive=600,
    )
