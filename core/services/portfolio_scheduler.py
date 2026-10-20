"""
Portfolio Value Scheduler
Automated daily price refresh and value tracking at 5 PM ET on weekdays.
Works on both local development and AWS ECS deployment.
"""

import asyncio
import logging
from datetime import datetime, time
from typing import List, Dict, Any, Optional
import json
import pytz
import aiohttp
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.database.postgres_client import get_postgres_rls_client

logger = logging.getLogger(__name__)


class PortfolioScheduler:
    """Manages automated portfolio price refreshes and value snapshots."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(
            timezone=pytz.timezone('America/New_York'),
            job_defaults={
                "misfire_grace_time": 3600,  # allow up to 1 hour late
                "coalesce": True,  # collapse missed runs into a single execution
            },
        )
        self.is_running = False
        self._lock = asyncio.Lock()  # Prevents shutdown-before-start race

    async def refresh_all_portfolios(self):
        """
        Refresh prices for all portfolios and save snapshots.
        Called automatically at 5 PM ET on weekdays.
        Respects RLS by processing each user's portfolios separately.
        """
        try:
            logger.info("Starting scheduled portfolio refresh at 5 PM ET")
            pg = await get_postgres_rls_client()

            # Get all user_ids from users table (users table has no RLS)
            # Then query portfolios for each user using proper RLS context
            async with pg.pool.acquire() as conn:
                users = await conn.fetch("SELECT id FROM users WHERE id IS NOT NULL")
            
            user_ids = [u['id'] for u in users]
            logger.info(f"Found {len(user_ids)} users to check for portfolios")
            
            # Use the same method that works for the API - pg.get_user_portfolios
            # Store portfolios grouped by user since get_user_portfolios doesn't return user_id
            from collections import defaultdict
            portfolios_by_user = defaultdict(list)
            portfolios = []
            for user_id in user_ids:
                user_portfolios = await pg.get_user_portfolios(user_id, org_id=None)
                for p in user_portfolios:
                    p['user_id'] = user_id  # Add user_id since get_user_portfolios doesn't return it
                    portfolios.append(p)
                    portfolios_by_user[user_id].append(p)

            logger.info(f"Found {len(portfolios)} portfolios to refresh")

            # Collect all unique tickers
            all_tickers = set()
            for portfolio in portfolios:
                tickers = portfolio.get('tickers') or []
                for t in tickers:
                    if t:
                        all_tickers.add(t)
                holdings = portfolio.get('holdings')
                if holdings:
                    if isinstance(holdings, str):
                        holdings = json.loads(holdings)
                    if isinstance(holdings, list):
                        for h in holdings:
                            if isinstance(h, dict) and h.get('ticker'):
                                all_tickers.add(h['ticker'])

            # Fetch all prices in one batch
            logger.info(f"Fetching prices for {len(all_tickers)} unique tickers")
            prices_dict = await self._fetch_bulk_prices(list(all_tickers))
            current_timestamp = datetime.now(pytz.UTC)

            # portfolios_by_user already populated during fetch
            logger.info(f"Grouped {len(portfolios)} portfolios into {len(portfolios_by_user)} users")

            # Process users concurrently (10 at a time) with bulk operations
            success_count = 0
            error_count = 0
            user_concurrency = 10
            user_semaphore = asyncio.Semaphore(user_concurrency)

            async def _process_user_portfolios(user_id: str, user_portfolios: List[Dict[str, Any]]):
                async with user_semaphore:
                    try:
                        # Prepare bulk updates and snapshots for this user
                        portfolio_updates = []
                        history_snapshots = []

                        for portfolio in user_portfolios:
                            update_data, snapshot_data = self._prepare_portfolio_update(
                                portfolio=portfolio,
                                prices=prices_dict,
                                timestamp=current_timestamp
                            )
                            if update_data:
                                portfolio_updates.append(update_data)
                            if snapshot_data:
                                history_snapshots.append(snapshot_data)

                        # Bulk update portfolios for this user
                        if portfolio_updates:
                            await pg.bulk_update_portfolios(user_id, portfolio_updates)

                        # Bulk insert history snapshots for this user
                        if history_snapshots:
                            await pg.bulk_insert_portfolio_history(user_id, history_snapshots)

                        return len(portfolio_updates), 0

                    except Exception as e:
                        logger.error(f"Failed to update portfolios for user {user_id}: {e}", exc_info=True)
                        return 0, len(user_portfolios)

            # Create tasks for all users
            tasks = [
                _process_user_portfolios(user_id, user_portfolios)
                for user_id, user_portfolios in portfolios_by_user.items()
            ]

            # Process all users concurrently with semaphore control
            results = await asyncio.gather(*tasks)

            # Aggregate results
            for success, errors in results:
                success_count += success
                error_count += errors

            logger.info(
                f"Portfolio refresh completed: {success_count} successful, "
                f"{error_count} errors"
            )

        except Exception as e:
            logger.error(f"Error in scheduled portfolio refresh: {e}", exc_info=True)

    async def _fetch_bulk_prices(self, tickers: List[str]) -> Dict[str, float]:
        """Fetch prices for multiple tickers efficiently using FMP API."""
        fmp_api_key = os.getenv('FMP_API_KEY')
        if not fmp_api_key:
            logger.error("FMP_API_KEY not configured")
            return {}

        async def fetch_single_price(session: aiohttp.ClientSession, ticker: str) -> tuple[str, float]:
            """Fetch price for a single ticker using FMP /stable/quote"""
            url = f"https://financialmodelingprep.com/stable/quote?symbol={ticker}&apikey={fmp_api_key}"
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:  # 4x for FMP API
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            price = data[0].get('price', 0.0)
                            return (ticker, float(price) if price else 0.0)
                    return (ticker, 0.0)
            except Exception as e:
                logger.error(f"Error fetching price for {ticker}: {e}")
                return (ticker, 0.0)

        try:
            prices = {}
            async with aiohttp.ClientSession() as session:
                tasks = [fetch_single_price(session, ticker) for ticker in tickers]
                results = await asyncio.gather(*tasks)
                for ticker, price in results:
                    prices[ticker] = price
            return prices
        except Exception as e:
            logger.error(f"Error fetching bulk prices: {e}")
            return {}

    def _prepare_portfolio_update(
        self,
        portfolio: Dict[str, Any],
        prices: Dict[str, float],
        timestamp: datetime
    ) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Prepare portfolio update and history snapshot data."""
        portfolio_id = portfolio['id']
        tickers = portfolio.get('tickers') or []
        weights = portfolio.get('weights') or []
        holdings = portfolio.get('holdings')
        
        if isinstance(holdings, (str, bytes)):
            holdings = json.loads(holdings if isinstance(holdings, str) else holdings.decode("utf-8"))
        
        timestamp_str = timestamp.isoformat()
        
        # If we have detailed holdings, use them
        if holdings and isinstance(holdings, list) and len(holdings) > 0:
            updated_holdings = []
            for holding in holdings:
                if not isinstance(holding, dict) or 'ticker' not in holding:
                    continue
                ticker = holding['ticker']
                current_price = prices.get(ticker, 0.0)
                updated_holding = {**holding}
                updated_holding['currentPrice'] = current_price
                updated_holding['priceUpdatedAt'] = timestamp_str
                updated_holdings.append(updated_holding)
            
            if not updated_holdings:
                return None, None
            
            def _qty(pos):
                lots = pos.get('lots')
                if isinstance(lots, list) and lots:
                    return sum(float(lot.get('quantity', 0) or 0) for lot in lots)
                return float(pos.get('quantity', 0) or 0)
            
            total_value = sum(_qty(h) * float(h.get('currentPrice') or 0) for h in updated_holdings)
            new_weights = [(_qty(h) * float(h.get('currentPrice') or 0)) / total_value if total_value > 0 else 0 for h in updated_holdings]
            portfolio_prices = {h['ticker']: prices.get(h['ticker'], 0.0) for h in updated_holdings}
        
        # Otherwise use tickers/weights
        elif tickers:
            updated_holdings = []
            portfolio_prices = {}
            for i, ticker in enumerate(tickers):
                current_price = prices.get(ticker, 0.0)
                w = weights[i] if i < len(weights) else (1.0 / len(tickers))
                updated_holdings.append({'ticker': ticker, 'currentPrice': current_price, 'priceUpdatedAt': timestamp_str, 'weight': w})
                portfolio_prices[ticker] = current_price
            total_value = sum((weights[i] if i < len(weights) else (1.0/len(tickers))) * prices.get(t, 0) for i, t in enumerate(tickers)) * 100
            new_weights = weights if weights else [1.0/len(tickers)] * len(tickers)
        else:
            return None, None
        
        update_data = {'portfolio_id': portfolio_id, 'holdings': updated_holdings, 'value': total_value, 'weights': new_weights}
        snapshot_data = {'portfolio_id': portfolio_id, 'snapshot_date': timestamp, 'total_value': total_value, 'holdings_snapshot': updated_holdings, 'prices_snapshot': portfolio_prices}
        return update_data, snapshot_data

    async def _update_portfolio_with_prices(
        self,
        pg,
        portfolio: Dict[str, Any],
        prices: Dict[str, float],
        timestamp: str
    ):
        """Update a single portfolio with new prices and create value snapshot."""
        portfolio_id = portfolio['id']
        user_id = portfolio['user_id']
        holdings = portfolio['holdings']
        if isinstance(holdings, (str, bytes)):
            holdings = json.loads(holdings if isinstance(holdings, str) else holdings.decode("utf-8"))

        if not holdings:
            return

        # Update holdings with current prices
        updated_holdings = []
        timestamp_str = timestamp.isoformat()
        for holding in holdings:
            ticker = holding['ticker']
            current_price = prices.get(ticker, 0.0)

            updated_holding = {**holding}
            updated_holding['currentPrice'] = current_price
            updated_holding['priceUpdatedAt'] = timestamp_str

            updated_holdings.append(updated_holding)

        def _quantity_from_holding(position: Dict[str, Any]) -> float:
            """Support both new (lots) and legacy (quantity) formats."""
            lots = position.get('lots')
            if isinstance(lots, list) and lots:
                return sum(float(lot.get('quantity', 0) or 0) for lot in lots)
            return float(position.get('quantity', 0) or 0)

        # Calculate total value with legacy compatibility
        total_value = 0.0
        for holding in updated_holdings:
            total_quantity = _quantity_from_holding(holding)
            current_price = float(holding.get('currentPrice') or 0.0)
            total_value += total_quantity * current_price

        # Calculate weights
        weights = []
        for holding in updated_holdings:
            total_quantity = _quantity_from_holding(holding)
            current_price = float(holding.get('currentPrice') or 0.0)
            position_value = total_quantity * current_price
            weight = position_value / total_value if total_value > 0 else 0.0
            weights.append(weight)

        # Update portfolio in database (with RLS context)
        async with pg.acquire_with_user_context(user_id) as conn:
            await conn.execute("""
                UPDATE portfolios
                SET
                    holdings = $1::jsonb,
                    value = $2,
                    weights = $3,
                    updated_at = NOW()
                WHERE id = $4
            """, json.dumps(updated_holdings), total_value, weights, portfolio_id)

            # Create value history snapshot
            # Allow multiple snapshots per day, update if exact timestamp exists
            await conn.execute("""
                INSERT INTO portfolio_value_history (
                    portfolio_id,
                    user_id,
                    snapshot_date,
                    total_value,
                    holdings_snapshot,
                    prices_snapshot
                )
                VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                ON CONFLICT (portfolio_id, snapshot_date)
                DO UPDATE SET
                    total_value = EXCLUDED.total_value,
                    holdings_snapshot = EXCLUDED.holdings_snapshot,
                    prices_snapshot = EXCLUDED.prices_snapshot
            """, portfolio_id, user_id, timestamp, total_value,
                json.dumps(updated_holdings), json.dumps(prices))

        logger.info(
            f"Updated portfolio {portfolio_id} ({portfolio['name']}): "
            f"${total_value:,.2f}"
        )

    async def start(self):
        """Start the scheduler with 5 PM ET weekday job."""
        async with self._lock:
            if self.is_running:
                logger.warning("Scheduler already running")
                return

            # Schedule for 5 PM ET, Monday-Friday
            self.scheduler.add_job(
                self.refresh_all_portfolios,
                trigger=CronTrigger(
                    day_of_week='mon-fri',  # Weekdays only
                    hour=17,                 # 5 PM
                    minute=0,
                    timezone='America/New_York'
                ),
                id='portfolio_refresh_5pm_et',
                name='Daily Portfolio Price Refresh',
                replace_existing=True,
                misfire_grace_time=3600,  # Catch up if start delayed (1 hour window)
            )

            self.scheduler.start()
            self.is_running = True
            logger.info("Portfolio scheduler started: 5 PM ET weekdays")

    async def stop(self):
        """Stop the scheduler."""
        async with self._lock:
            if self.is_running:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("Portfolio scheduler stopped")

    async def run_manual_refresh(self):
        """
        Manually trigger a refresh (for testing or on-demand updates).
        This bypasses the schedule and runs immediately.
        """
        logger.info("Manual portfolio refresh triggered")
        await self.refresh_all_portfolios()


# Global scheduler instance
portfolio_scheduler = PortfolioScheduler()


async def start_scheduler():
    """Initialize and start the portfolio scheduler."""
    try:
        await portfolio_scheduler.start()
        logger.info("Portfolio value scheduler initialized")
    except Exception as e:
        logger.error(f"Failed to start portfolio scheduler: {e}", exc_info=True)


async def stop_scheduler():
    """Stop the portfolio scheduler gracefully."""
    try:
        await portfolio_scheduler.stop()
        logger.info("Portfolio value scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping portfolio scheduler: {e}", exc_info=True)
