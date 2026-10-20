"""
Technical indicator calculations for pre-enrichment of streaming data.
Following CODING_RULES.md: No hardcoding, dynamic calculations only.
"""
import logging
from typing import Dict, Any, List, Optional
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    """
    Calculate technical indicators for streaming stock data.
    Maintains rolling windows of historical data per symbol.
    """
    
    def __init__(self, window_size: int = 100):
        """
        Initialize the indicator calculator.
        
        Args:
            window_size: Maximum historical data points to keep per symbol
        """
        self.window_size = window_size
        self.symbol_data: Dict[str, deque] = {}  # Historical data per symbol
        
    def enrich_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add technical indicators to a market data message.
        
        Args:
            message: Raw market data message
            
        Returns:
            Enriched message with indicators added
        """
        try:
            symbol = message.get('symbol')
            if not symbol:
                return message
                
            # Get or create historical data queue for this symbol
            if symbol not in self.symbol_data:
                self.symbol_data[symbol] = deque(maxlen=self.window_size)
            
            # Add current price to history
            price = float(message.get('price', 0))
            if price > 0:
                self.symbol_data[symbol].append(price)
            
            # Get historical prices as array
            prices = list(self.symbol_data[symbol])
            if len(prices) < 2:
                return message  # Not enough data for indicators
            
            # Calculate indicators and add to message
            enriched = message.copy()
            
            # Simple Moving Averages
            if len(prices) >= 20:
                enriched['sma20'] = np.mean(prices[-20:])
            if len(prices) >= 50:
                enriched['sma50'] = np.mean(prices[-50:])
            
            # Price change
            enriched['change'] = price - prices[-2] if len(prices) >= 2 else 0
            enriched['change_pct'] = ((price - prices[-2]) / prices[-2] * 100) if len(prices) >= 2 and prices[-2] > 0 else 0
            
            # Volatility (standard deviation)
            if len(prices) >= 20:
                enriched['volatility'] = np.std(prices[-20:])
            
            # RSI (Relative Strength Index)
            if len(prices) >= 14:
                rsi = self._calculate_rsi(prices, 14)
                if rsi is not None:
                    enriched['rsi'] = rsi
            
            # Bollinger Bands
            if len(prices) >= 20:
                bb = self._calculate_bollinger_bands(prices, 20, 2)
                if bb:
                    enriched['bb_upper'] = bb['upper']
                    enriched['bb_middle'] = bb['middle']
                    enriched['bb_lower'] = bb['lower']
            
            # Volume analysis (if volume provided)
            volume = message.get('volume')
            if volume and 'avg_volume' in message:
                avg_volume = message.get('avg_volume')
                if avg_volume and avg_volume > 0:
                    enriched['volume_ratio'] = volume / avg_volume
                    enriched['unusual_volume'] = volume > (avg_volume * 1.5)
            
            return enriched
            
        except Exception as e:
            logger.error(f"Error enriching message: {e}")
            return message
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """
        Calculate RSI (Relative Strength Index).
        
        Args:
            prices: Historical price data
            period: RSI period (default 14)
            
        Returns:
            RSI value or None if not enough data
        """
        try:
            if len(prices) < period + 1:
                return None
                
            deltas = np.diff(prices[-period-1:])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            
            if avg_loss == 0:
                return 100 if avg_gain > 0 else 50
                
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return round(rsi, 2)
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return None
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20, 
                                   std_dev: int = 2) -> Optional[Dict[str, float]]:
        """
        Calculate Bollinger Bands.
        
        Args:
            prices: Historical price data
            period: Moving average period
            std_dev: Number of standard deviations
            
        Returns:
            Dictionary with upper, middle, lower bands or None
        """
        try:
            if len(prices) < period:
                return None
                
            recent_prices = prices[-period:]
            middle = np.mean(recent_prices)
            std = np.std(recent_prices)
            
            return {
                'upper': round(middle + (std * std_dev), 2),
                'middle': round(middle, 2),
                'lower': round(middle - (std * std_dev), 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return None
    
    def get_symbol_stats(self, symbol: str) -> Dict[str, Any]:
        """
        Get statistics for a specific symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with symbol statistics
        """
        if symbol not in self.symbol_data:
            return {'symbol': symbol, 'data_points': 0}
            
        prices = list(self.symbol_data[symbol])
        
        return {
            'symbol': symbol,
            'data_points': len(prices),
            'min_price': min(prices) if prices else 0,
            'max_price': max(prices) if prices else 0,
            'avg_price': np.mean(prices) if prices else 0,
            'std_dev': np.std(prices) if len(prices) > 1 else 0
        }
    
    def clear_symbol_data(self, symbol: str):
        """Clear historical data for a specific symbol."""
        if symbol in self.symbol_data:
            del self.symbol_data[symbol]
    
    def clear_all_data(self):
        """Clear all historical data."""
        self.symbol_data.clear()