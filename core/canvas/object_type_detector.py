"""
Object Type Detector - Detects object type from symbol.

Uses FMP company-profile to determine if a symbol is:
- equity (stock)
- etf
- crypto
- forex
- commodity
"""

import os
import re
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from functools import lru_cache

import aiohttp

logger = logging.getLogger(__name__)

# Common forex pairs
FOREX_CURRENCIES = {
    "EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD", 
    "SEK", "NOK", "DKK", "HKD", "SGD", "MXN", "ZAR", "TRY"
}

# Common crypto suffixes
CRYPTO_SUFFIXES = {"USD", "USDT", "BTC", "ETH", "EUR", "GBP"}

# Commodity futures patterns
COMMODITY_PATTERNS = [
    r"^[A-Z]{1,2}=F$",  # GC=F, SI=F, CL=F
    r"^[A-Z]{2,3}[FGHJKMNQUVXZ]\d{2}$",  # CLF24, GCZ24
]


@dataclass
class ObjectTypeResult:
    """Result of object type detection."""
    object_type: str
    symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None
    is_actively_trading: bool = True
    raw_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_type": self.object_type,
            "symbol": self.symbol,
            "name": self.name,
            "exchange": self.exchange,
            "currency": self.currency,
            "is_actively_trading": self.is_actively_trading,
        }


class ObjectTypeDetector:
    """
    Detects object type from a symbol.
    
    Uses pattern matching for obvious cases (forex, commodity futures)
    and FMP API for stocks/ETFs/crypto.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        self.base_url = "https://financialmodelingprep.com/api/v3"
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, ObjectTypeResult] = {}
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def cleanup(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _detect_forex(self, symbol: str) -> Optional[ObjectTypeResult]:
        """Check if symbol is a forex pair."""
        # Format: EURUSD, EUR/USD, EURUSD=X
        clean = symbol.replace("/", "").replace("=X", "").upper()
        
        if len(clean) == 6:
            base = clean[:3]
            quote = clean[3:]
            if base in FOREX_CURRENCIES and quote in FOREX_CURRENCIES:
                return ObjectTypeResult(
                    object_type="forex",
                    symbol=symbol,
                    name=f"{base}/{quote}",
                    exchange="FOREX",
                    currency=quote,
                )
        return None
    
    def _detect_commodity_futures(self, symbol: str) -> Optional[ObjectTypeResult]:
        """Check if symbol is a commodity futures contract."""
        for pattern in COMMODITY_PATTERNS:
            if re.match(pattern, symbol.upper()):
                return ObjectTypeResult(
                    object_type="commodity",
                    symbol=symbol,
                    name=symbol,
                    exchange="FUTURES",
                    currency="USD",
                )
        return None
    
    def _detect_crypto_pattern(self, symbol: str) -> Optional[ObjectTypeResult]:
        """Check if symbol matches crypto pattern."""
        upper = symbol.upper()
        
        # Check for common crypto patterns: BTCUSD, BTC-USD, BTC/USD
        clean = upper.replace("-", "").replace("/", "")
        
        for suffix in CRYPTO_SUFFIXES:
            if clean.endswith(suffix) and len(clean) > len(suffix):
                base = clean[:-len(suffix)]
                if len(base) >= 2 and len(base) <= 5:
                    return ObjectTypeResult(
                        object_type="crypto",
                        symbol=symbol,
                        name=f"{base}/{suffix}",
                        exchange="CRYPTO",
                        currency=suffix,
                    )
        return None
    
    async def _fetch_profile(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch company profile from FMP."""
        if not self.api_key:
            logger.warning("No FMP API key available for profile lookup")
            return None
        
        session = await self._get_session()
        url = f"{self.base_url}/profile/{symbol}?apikey={self.api_key}"
        
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning(f"FMP profile request failed: {resp.status}")
                    return None
                
                data = await resp.json()
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                return None
        except Exception as e:
            logger.error(f"Error fetching profile for {symbol}: {e}")
            return None
    
    def _determine_type_from_profile(
        self, 
        symbol: str, 
        profile: Dict[str, Any]
    ) -> ObjectTypeResult:
        """Determine object type from FMP profile data."""
        
        is_etf = profile.get("isEtf", False)
        exchange = profile.get("exchangeShortName", "") or profile.get("exchange", "")
        company_name = profile.get("companyName", symbol)
        currency = profile.get("currency", "USD")
        is_active = profile.get("isActivelyTrading", True)
        
        # Check for ETF
        if is_etf:
            return ObjectTypeResult(
                object_type="etf",
                symbol=symbol,
                name=company_name,
                exchange=exchange,
                currency=currency,
                is_actively_trading=is_active,
                raw_data=profile,
            )
        
        # Check for crypto exchange
        exchange_upper = exchange.upper()
        if "CRYPTO" in exchange_upper or exchange_upper in ["BINANCE", "COINBASE", "KRAKEN"]:
            return ObjectTypeResult(
                object_type="crypto",
                symbol=symbol,
                name=company_name,
                exchange=exchange,
                currency=currency,
                is_actively_trading=is_active,
                raw_data=profile,
            )
        
        # Check for commodity
        sector = profile.get("sector", "").upper()
        if "COMMODITY" in sector or "FUTURES" in exchange_upper:
            return ObjectTypeResult(
                object_type="commodity",
                symbol=symbol,
                name=company_name,
                exchange=exchange,
                currency=currency,
                is_actively_trading=is_active,
                raw_data=profile,
            )
        
        # Default to equity
        return ObjectTypeResult(
            object_type="equity",
            symbol=symbol,
            name=company_name,
            exchange=exchange,
            currency=currency,
            is_actively_trading=is_active,
            raw_data=profile,
        )
    
    async def detect(self, symbol: str) -> ObjectTypeResult:
        """
        Detect the object type for a given symbol.
        
        Args:
            symbol: The ticker symbol to detect
            
        Returns:
            ObjectTypeResult with detected type and metadata
        """
        symbol = symbol.upper().strip()
        
        # Check cache first
        if symbol in self._cache:
            return self._cache[symbol]
        
        # Special case: market-wide data (no specific symbol)
        if symbol in ("_MARKET_", "MARKET", "_MARKET", ""):
            result = ObjectTypeResult(
                object_type="market",
                symbol=symbol,
                name="Market Wide Data",
                is_actively_trading=True,
            )
            self._cache[symbol] = result
            return result
        
        # Try pattern-based detection first (no API call needed)
        
        # Check forex
        forex_result = self._detect_forex(symbol)
        if forex_result:
            self._cache[symbol] = forex_result
            return forex_result
        
        # Check commodity futures
        commodity_result = self._detect_commodity_futures(symbol)
        if commodity_result:
            self._cache[symbol] = commodity_result
            return commodity_result
        
        # Check crypto pattern
        crypto_result = self._detect_crypto_pattern(symbol)
        if crypto_result:
            self._cache[symbol] = crypto_result
            return crypto_result
        
        # Fall back to FMP API lookup
        profile = await self._fetch_profile(symbol)
        
        if profile:
            result = self._determine_type_from_profile(symbol, profile)
        else:
            # Default to equity if we can't determine
            result = ObjectTypeResult(
                object_type="equity",
                symbol=symbol,
                name=symbol,
            )
        
        self._cache[symbol] = result
        return result
    
    def clear_cache(self):
        """Clear the detection cache."""
        self._cache.clear()


# Singleton instance for convenience
_detector: Optional[ObjectTypeDetector] = None


def get_detector() -> ObjectTypeDetector:
    """Get or create the singleton detector instance."""
    global _detector
    if _detector is None:
        _detector = ObjectTypeDetector()
    return _detector


async def detect_object_type(symbol: str) -> ObjectTypeResult:
    """Convenience function to detect object type."""
    detector = get_detector()
    return await detector.detect(symbol)







