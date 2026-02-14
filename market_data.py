"""
JARVIS Market Data Fetcher
Fetches real-time cryptocurrency price data from exchanges
Supports multiple timeframes and symbols
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import asyncio
from threading import Thread
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """
    Fetches and manages market data for JARVIS
    Supports real-time updates via WebSocket or REST API
    """
    
    def __init__(self, exchange_name: str = 'binance'):
        """
        Initialize market data fetcher
        
        Args:
            exchange_name: Exchange to use ('binance', 'bybit', 'coinbase', etc.)
        """
        self.exchange_name = exchange_name
        self.exchange = getattr(ccxt, exchange_name)({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}  # Use futures for more data
        })
        
        self.cache = {}  # Cache for OHLCV data
        self.last_update = {}  # Track last update time
        
        logger.info(f"✅ Market Data Fetcher initialized for {exchange_name}")
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """
        Fetch OHLCV (candlestick) data
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d', etc.)
            limit: Number of candles to fetch
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Check cache
            cache_key = f"{symbol}_{timeframe}"
            current_time = time.time()
            
            # Use cache if data is less than 1 minute old
            if cache_key in self.cache and cache_key in self.last_update:
                if current_time - self.last_update[cache_key] < 60:
                    logger.debug(f"Using cached data for {symbol} {timeframe}")
                    return self.cache[cache_key].copy()
            
            # Fetch from exchange
            logger.info(f"📊 Fetching {symbol} {timeframe} data...")
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Update cache
            self.cache[cache_key] = df.copy()
            self.last_update[cache_key] = current_time
            
            logger.info(f"✅ Fetched {len(df)} candles for {symbol} {timeframe}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error fetching {symbol} {timeframe}: {str(e)}")
            # Return cached data if available
            if cache_key in self.cache:
                logger.warning("Returning cached data due to fetch error")
                return self.cache[cache_key].copy()
            raise
    
    def fetch_ticker(self, symbol: str) -> Dict:
        """
        Fetch current ticker (latest price)
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            
        Returns:
            Dict with ticker info including last price, bid, ask, volume
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'high': ticker['high'],
                'low': ticker['low'],
                'volume': ticker['baseVolume'],
                'timestamp': datetime.fromtimestamp(ticker['timestamp'] / 1000)
            }
        except Exception as e:
            logger.error(f"❌ Error fetching ticker for {symbol}: {str(e)}")
            raise
    
    def get_current_price(self, symbol: str) -> float:
        """
        Get current price quickly
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            
        Returns:
            Current price as float
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"❌ Error getting price for {symbol}: {str(e)}")
            raise
    
    def fetch_multiple_timeframes(self, symbol: str, timeframes: List[str], 
                                   limit: int = 500) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple timeframes at once
        
        Args:
            symbol: Trading pair
            timeframes: List of timeframes to fetch
            limit: Number of candles per timeframe
            
        Returns:
            Dict mapping timeframe to DataFrame
        """
        result = {}
        
        for tf in timeframes:
            try:
                result[tf] = self.fetch_ohlcv(symbol, tf, limit)
                time.sleep(0.1)  # Rate limiting
            except Exception as e:
                logger.error(f"❌ Error fetching {tf}: {str(e)}")
        
        return result
    
    def get_higher_timeframe_data(self, symbol: str, current_tf: str, 
                                   trading_style: str) -> pd.DataFrame:
        """
        Get higher timeframe data based on trading style
        Mimics your PineScript HTF logic
        
        Args:
            symbol: Trading pair
            current_tf: Current timeframe
            trading_style: 'Swing Trading', 'Day Trading', or 'Scalping/Intraday'
            
        Returns:
            DataFrame with HTF data
        """
        # Determine HTF based on current timeframe
        tf_map = {
            '1m': {'Swing Trading': '1d', 'Day Trading': '1h', 'Scalping/Intraday': '15m'},
            '5m': {'Swing Trading': '1d', 'Day Trading': '1h', 'Scalping/Intraday': '15m'},
            '15m': {'Swing Trading': '1d', 'Day Trading': '1h', 'Scalping/Intraday': '4h'},
            '30m': {'Swing Trading': '1d', 'Day Trading': '4h', 'Scalping/Intraday': '4h'},
            '1h': {'Swing Trading': '1d', 'Day Trading': '4h', 'Scalping/Intraday': '4h'},
            '4h': {'Swing Trading': '1d', 'Day Trading': '1d', 'Scalping/Intraday': '4h'},
            '1d': {'Swing Trading': '1w', 'Day Trading': '1d', 'Scalping/Intraday': '4h'},
        }
        
        htf = tf_map.get(current_tf, {}).get(trading_style, '1d')
        
        logger.info(f"📈 HTF for {current_tf} ({trading_style}): {htf}")
        return self.fetch_ohlcv(symbol, htf)
    
    def start_realtime_monitoring(self, symbol: str, timeframe: str, 
                                   callback, interval: int = 60):
        """
        Start real-time price monitoring
        Calls callback function with updated data every interval seconds
        
        Args:
            symbol: Trading pair to monitor
            timeframe: Timeframe to monitor
            callback: Function to call with updated data
            interval: Update interval in seconds
        """
        def monitor():
            logger.info(f"🔄 Starting real-time monitoring for {symbol} {timeframe}")
            
            while True:
                try:
                    # Fetch latest data
                    df = self.fetch_ohlcv(symbol, timeframe, limit=500)
                    current_price = self.get_current_price(symbol)
                    
                    # Call callback with updated data
                    callback(df, current_price)
                    
                    # Wait for next update
                    time.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"❌ Error in real-time monitoring: {str(e)}")
                    time.sleep(10)  # Wait before retrying
        
        # Start monitoring in background thread
        monitor_thread = Thread(target=monitor, daemon=True)
        monitor_thread.start()
        
        logger.info(f"✅ Real-time monitoring started for {symbol} {timeframe}")
        return monitor_thread


# Standalone market data server
class MarketDataServer:
    """
    Market data server that continuously fetches and broadcasts price updates
    """
    
    def __init__(self, config: Dict):
        self.fetcher = MarketDataFetcher(config.get('exchange', 'binance'))
        self.symbols = config.get('symbols', ['BTC/USDT'])
        self.timeframes = config.get('timeframes', ['4h'])
        self.update_interval = config.get('update_interval', 60)
        self.callbacks = []
        self.running = False
    
    def register_callback(self, callback):
        """Register a callback to receive market updates"""
        self.callbacks.append(callback)
    
    def start(self):
        """Start the market data server"""
        self.running = True
        
        def run_server():
            logger.info("🚀 Market Data Server started")
            
            while self.running:
                for symbol in self.symbols:
                    for timeframe in self.timeframes:
                        try:
                            # Fetch latest data
                            df = self.fetcher.fetch_ohlcv(symbol, timeframe, limit=500)
                            current_price = self.fetcher.get_current_price(symbol)
                            
                            # Notify all callbacks
                            for callback in self.callbacks:
                                try:
                                    callback(symbol, timeframe, df, current_price)
                                except Exception as e:
                                    logger.error(f"Callback error: {str(e)}")
                            
                        except Exception as e:
                            logger.error(f"Error updating {symbol} {timeframe}: {str(e)}")
                
                time.sleep(self.update_interval)
        
        # Start in background thread
        server_thread = Thread(target=run_server, daemon=True)
        server_thread.start()
        return server_thread
    
    def stop(self):
        """Stop the market data server"""
        self.running = False
        logger.info("🛑 Market Data Server stopped")


# Test the fetcher
if __name__ == "__main__":
    # Test basic fetching
    fetcher = MarketDataFetcher('binance')
    
    # Fetch BTC data
    df = fetcher.fetch_ohlcv('BTC/USDT', '4h', limit=100)
    print(f"✅ Fetched {len(df)} candles")
    print(df.tail())
    
    # Get current price
    price = fetcher.get_current_price('BTC/USDT')
    print(f"✅ Current BTC price: ${price:,.2f}")
    
    # Fetch multiple timeframes
    data = fetcher.fetch_multiple_timeframes('BTC/USDT', ['1h', '4h', '1d'])
    print(f"✅ Fetched {len(data)} timeframes")
