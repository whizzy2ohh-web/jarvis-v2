"""
JARVIS AI Trading Engine
Converts TradingView PineScript logic to Python for real-time signal generation
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JarvisEngine:
    """
    JARVIS AI Trading Engine - Smart Money Concepts Strategy
    Implements all logic from your TradingView PineScript
    """
    
    def __init__(self, config: Dict):
        # Trading Style & HTF Confirmation
        self.trading_style = config.get('trading_style', 'Day Trading')
        self.use_htf_confirmation = config.get('use_htf_confirmation', True)
        
        # Structure Settings
        self.swing_length = config.get('swing_length', 5)
        self.bos_threshold = config.get('bos_threshold', 0.1)
        
        # Fair Value Gap
        self.fvg_min_size = config.get('fvg_min_size', 0.15)
        self.show_fvg = config.get('show_fvg', True)
        
        # Order Block
        self.ob_lookback = config.get('ob_lookback', 5)
        self.show_ob = config.get('show_ob', True)
        
        # Risk Management
        self.stop_loss_atr = config.get('stop_loss_atr', 1.5)
        self.take_profit_rr = config.get('take_profit_rr', 3.0)
        self.partial_tp_rr = config.get('partial_tp_rr', 1.5)
        self.use_partial_tp = config.get('use_partial_tp', True)
        self.partial_tp_percent = config.get('partial_tp_percent', 50)
        
        # Trade Filters
        self.min_atr = config.get('min_atr', 0.0)
        self.use_time_filter = config.get('use_time_filter', False)
        self.session_start = config.get('session_start', 0)
        self.session_end = config.get('session_end', 23)
        
        # Trend Analysis
        self.trend_ma_period = config.get('trend_ma_period', 50)
        self.rsi_period = config.get('rsi_period', 14)
        
        # State tracking
        self.last_swing_high = None
        self.last_swing_low = None
        self.bull_fvg_top = None
        self.bull_fvg_bottom = None
        self.bear_fvg_top = None
        self.bear_fvg_bottom = None
        self.bull_ob_top = None
        self.bull_ob_bottom = None
        self.bear_ob_top = None
        self.bear_ob_bottom = None
        
        logger.info(f"JARVIS Engine initialized with style: {self.trading_style}")
    
    def determine_htf_timeframe(self, current_timeframe: str) -> str:
        """Determine higher timeframe based on current timeframe and trading style"""
        
        # Convert timeframe to minutes
        tf_minutes = self._timeframe_to_minutes(current_timeframe)
        
        if self.trading_style == "Swing Trading":
            if tf_minutes <= 240:  # 4H or lower
                return "1D"
            elif tf_minutes <= 1440:  # Daily
                return "1W"
            else:
                return "1W"
                
        elif self.trading_style == "Day Trading":
            if tf_minutes <= 15:  # 15-min or lower
                return "1h"
            elif tf_minutes <= 60:  # 1-Hour
                return "4h"
            elif tf_minutes <= 240:  # 4-Hour
                return "1D"
            else:
                return "1D"
                
        else:  # Scalping/Intraday
            if tf_minutes <= 5:  # 5-min or lower
                return "15m"
            elif tf_minutes <= 15:  # 15-min
                return "4h"
            else:
                return "4h"
    
    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes"""
        timeframe = timeframe.lower()
        if 'm' in timeframe:
            return int(timeframe.replace('m', ''))
        elif 'h' in timeframe:
            return int(timeframe.replace('h', '')) * 60
        elif 'd' in timeframe:
            return int(timeframe.replace('d', '')) * 1440
        elif 'w' in timeframe:
            return int(timeframe.replace('w', '')) * 10080
        return 240  # Default to 4H
    
    def calculate_pivot_high(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate pivot highs (swing highs)"""
        pivot_high = pd.Series(index=df.index, dtype=float)
        
        for i in range(period, len(df) - period):
            is_pivot = True
            center_high = df['high'].iloc[i]
            
            # Check left side
            for j in range(1, period + 1):
                if df['high'].iloc[i - j] >= center_high:
                    is_pivot = False
                    break
            
            # Check right side
            if is_pivot:
                for j in range(1, period + 1):
                    if df['high'].iloc[i + j] >= center_high:
                        is_pivot = False
                        break
            
            if is_pivot:
                pivot_high.iloc[i] = center_high
        
        return pivot_high
    
    def calculate_pivot_low(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate pivot lows (swing lows)"""
        pivot_low = pd.Series(index=df.index, dtype=float)
        
        for i in range(period, len(df) - period):
            is_pivot = True
            center_low = df['low'].iloc[i]
            
            # Check left side
            for j in range(1, period + 1):
                if df['low'].iloc[i - j] <= center_low:
                    is_pivot = False
                    break
            
            # Check right side
            if is_pivot:
                for j in range(1, period + 1):
                    if df['low'].iloc[i + j] <= center_low:
                        is_pivot = False
                        break
            
            if is_pivot:
                pivot_low.iloc[i] = center_low
        
        return pivot_low
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def detect_fvg(self, df: pd.DataFrame, index: int) -> Tuple[bool, bool, float, float]:
        """Detect Fair Value Gaps (bullish and bearish)"""
        if index < 2:
            return False, False, 0, 0
        
        current_low = df['low'].iloc[index]
        current_high = df['high'].iloc[index]
        high_2_bars_ago = df['high'].iloc[index - 2]
        low_2_bars_ago = df['low'].iloc[index - 2]
        
        # Bullish FVG: Gap between high[2] and current low
        bullish_fvg = current_low > high_2_bars_ago
        bullish_fvg_size = 0
        if bullish_fvg:
            bullish_fvg_size = ((current_low - high_2_bars_ago) / high_2_bars_ago) * 100
        
        valid_bullish_fvg = bullish_fvg and bullish_fvg_size >= self.fvg_min_size
        
        # Bearish FVG: Gap between low[2] and current high
        bearish_fvg = current_high < low_2_bars_ago
        bearish_fvg_size = 0
        if bearish_fvg:
            bearish_fvg_size = ((low_2_bars_ago - current_high) / low_2_bars_ago) * 100
        
        valid_bearish_fvg = bearish_fvg and bearish_fvg_size >= self.fvg_min_size
        
        return valid_bullish_fvg, valid_bearish_fvg, bullish_fvg_size, bearish_fvg_size
    
    def detect_order_block(self, df: pd.DataFrame, index: int) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """Detect Order Blocks (bullish and bearish)"""
        if index < self.ob_lookback:
            return None, None, None, None
        
        current_close = df['close'].iloc[index]
        current_open = df['open'].iloc[index]
        
        bull_ob_top = None
        bull_ob_bottom = None
        bear_ob_top = None
        bear_ob_bottom = None
        
        # Bullish OB: Last bearish candle before bullish move
        for i in range(1, self.ob_lookback + 1):
            past_close = df['close'].iloc[index - i]
            past_open = df['open'].iloc[index - i]
            past_high = df['high'].iloc[index - i]
            past_low = df['low'].iloc[index - i]
            
            if (past_close < past_open and  # Bearish candle
                current_close > past_close and  # Current close above past close
                current_close > current_open):  # Current is bullish
                bull_ob_top = past_high
                bull_ob_bottom = past_low
                break
        
        # Bearish OB: Last bullish candle before bearish move
        for i in range(1, self.ob_lookback + 1):
            past_close = df['close'].iloc[index - i]
            past_open = df['open'].iloc[index - i]
            past_high = df['high'].iloc[index - i]
            past_low = df['low'].iloc[index - i]
            
            if (past_close > past_open and  # Bullish candle
                current_close < past_close and  # Current close below past close
                current_close < current_open):  # Current is bearish
                bear_ob_top = past_high
                bear_ob_bottom = past_low
                break
        
        return bull_ob_top, bull_ob_bottom, bear_ob_top, bear_ob_bottom
    
    def analyze_market(self, df: pd.DataFrame, htf_df: Optional[pd.DataFrame] = None) -> Dict:
        """
        Main analysis function - processes market data and generates signals
        This is the core function that replicates your TradingView indicator
        """
        
        if len(df) < 100:
            logger.warning("Not enough data for analysis")
            return {'signal': None, 'reason': 'Insufficient data'}
        
        # Get latest index
        index = len(df) - 1
        
        # Calculate indicators
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['atr'] = self.calculate_atr(df, 14)
        df['rsi'] = self.calculate_rsi(df, self.rsi_period)
        df['trend_ma'] = df['close'].rolling(window=self.trend_ma_period).mean()
        
        # Calculate pivot points
        swing_highs = self.calculate_pivot_high(df, self.swing_length)
        swing_lows = self.calculate_pivot_low(df, self.swing_length)
        
        # Update last swing high/low
        for i in range(len(swing_highs) - 1, -1, -1):
            if pd.notna(swing_highs.iloc[i]):
                self.last_swing_high = swing_highs.iloc[i]
                break
        
        for i in range(len(swing_lows) - 1, -1, -1):
            if pd.notna(swing_lows.iloc[i]):
                self.last_swing_low = swing_lows.iloc[i]
                break
        
        # Current price data
        current_close = df['close'].iloc[index]
        current_high = df['high'].iloc[index]
        current_low = df['low'].iloc[index]
        current_atr = df['atr'].iloc[index]
        current_rsi = df['rsi'].iloc[index]
        current_trend_ma = df['trend_ma'].iloc[index]
        
        # HTF Trend Analysis
        htf_bullish = True
        htf_bearish = False
        if htf_df is not None and len(htf_df) > 0:
            htf_close = htf_df['close'].iloc[-1]
            htf_ma = htf_df['close'].rolling(window=50).mean().iloc[-1]
            htf_bullish = htf_close > htf_ma
            htf_bearish = htf_close < htf_ma
        
        # Break of Structure (BOS)
        bullish_bos = False
        bearish_bos = False
        if self.last_swing_high is not None:
            bullish_bos = current_close > self.last_swing_high * (1 + self.bos_threshold / 100)
        if self.last_swing_low is not None:
            bearish_bos = current_close < self.last_swing_low * (1 - self.bos_threshold / 100)
        
        # Change of Character (CHoCH)
        bullish_choch = False
        bearish_choch = False
        if self.last_swing_high is not None:
            bullish_choch = current_close > self.last_swing_high
        if self.last_swing_low is not None:
            bearish_choch = current_close < self.last_swing_low
        
        # Detect FVG
        valid_bull_fvg, valid_bear_fvg, bull_fvg_size, bear_fvg_size = self.detect_fvg(df, index)
        
        if valid_bull_fvg:
            self.bull_fvg_top = current_low
            self.bull_fvg_bottom = df['high'].iloc[index - 2]
        
        if valid_bear_fvg:
            self.bear_fvg_top = df['low'].iloc[index - 2]
            self.bear_fvg_bottom = current_high
        
        # Check if FVG filled/invalidated
        if self.bull_fvg_bottom is not None and current_low <= self.bull_fvg_bottom:
            self.bull_fvg_top = None
            self.bull_fvg_bottom = None
        
        if self.bear_fvg_top is not None and current_high >= self.bear_fvg_top:
            self.bear_fvg_top = None
            self.bear_fvg_bottom = None
        
        # Detect Order Blocks
        bull_ob_t, bull_ob_b, bear_ob_t, bear_ob_b = self.detect_order_block(df, index)
        
        if bull_ob_t is not None:
            self.bull_ob_top = bull_ob_t
            self.bull_ob_bottom = bull_ob_b
        if bear_ob_t is not None:
            self.bear_ob_top = bear_ob_t
            self.bear_ob_bottom = bear_ob_b
        
        # Check if OB invalidated
        if self.bull_ob_bottom is not None and current_close < self.bull_ob_bottom:
            self.bull_ob_top = None
            self.bull_ob_bottom = None
        
        if self.bear_ob_top is not None and current_close > self.bear_ob_top:
            self.bear_ob_top = None
            self.bear_ob_bottom = None
        
        # ATR Filter
        atr_filter = self.min_atr == 0 or current_atr >= self.min_atr
        
        # Time Filter
        in_session = True
        if self.use_time_filter:
            current_hour = datetime.now().hour
            in_session = self.session_start <= current_hour <= self.session_end
        
        # Market Trend Analysis
        market_trend = "NEUTRAL"
        price_above_ma = current_close > current_trend_ma
        price_below_ma = current_close < current_trend_ma
        
        if price_above_ma and current_rsi > 50:
            if current_rsi > 60:
                market_trend = "STRONG BULLISH"
            else:
                market_trend = "BULLISH"
        elif price_below_ma and current_rsi < 50:
            if current_rsi < 40:
                market_trend = "STRONG BEARISH"
            else:
                market_trend = "BEARISH"
        
        # LONG ENTRY CONDITIONS
        long_structure = bullish_bos or bullish_choch
        long_in_fvg = (self.bull_fvg_top is not None and 
                       current_low <= self.bull_fvg_top and 
                       current_high >= self.bull_fvg_bottom)
        long_in_ob = (self.bull_ob_top is not None and 
                      current_low <= self.bull_ob_top and 
                      current_high >= self.bull_ob_bottom)
        long_pullback = long_in_fvg or long_in_ob
        
        htf_aligned_long = htf_bullish if self.use_htf_confirmation else True
        
        long_condition = (long_structure and long_pullback and 
                         atr_filter and in_session and htf_aligned_long)
        
        # SHORT ENTRY CONDITIONS
        short_structure = bearish_bos or bearish_choch
        short_in_fvg = (self.bear_fvg_top is not None and 
                        current_high >= self.bear_fvg_bottom and 
                        current_low <= self.bear_fvg_top)
        short_in_ob = (self.bear_ob_top is not None and 
                       current_high >= self.bear_ob_bottom and 
                       current_low <= self.bear_ob_top)
        short_pullback = short_in_fvg or short_in_ob
        
        htf_aligned_short = htf_bearish if self.use_htf_confirmation else True
        
        short_condition = (short_structure and short_pullback and 
                          atr_filter and in_session and htf_aligned_short)
        
        # Calculate entry levels
        signal = None
        entry_price = None
        stop_loss = None
        take_profit = None
        partial_tp = None
        
        if long_condition:
            signal = "LONG"
            entry_price = current_close
            stop_loss = entry_price - (current_atr * self.stop_loss_atr)
            risk_amount = entry_price - stop_loss
            take_profit = entry_price + (risk_amount * self.take_profit_rr)
            partial_tp = entry_price + (risk_amount * self.partial_tp_rr)
            
        elif short_condition:
            signal = "SHORT"
            entry_price = current_close
            stop_loss = entry_price + (current_atr * self.stop_loss_atr)
            risk_amount = stop_loss - entry_price
            take_profit = entry_price - (risk_amount * self.take_profit_rr)
            partial_tp = entry_price - (risk_amount * self.partial_tp_rr)
        
        # Compile analysis results
        analysis = {
            'timestamp': df.index[index],
            'signal': signal,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'partial_tp': partial_tp,
            'current_price': current_close,
            'atr': current_atr,
            'rsi': current_rsi,
            'market_trend': market_trend,
            'htf_trend': 'BULLISH' if htf_bullish else 'BEARISH' if htf_bearish else 'NEUTRAL',
            'structure': {
                'bullish_bos': bullish_bos,
                'bearish_bos': bearish_bos,
                'bullish_choch': bullish_choch,
                'bearish_choch': bearish_choch,
                'last_swing_high': self.last_swing_high,
                'last_swing_low': self.last_swing_low
            },
            'zones': {
                'bull_fvg': {'top': self.bull_fvg_top, 'bottom': self.bull_fvg_bottom},
                'bear_fvg': {'top': self.bear_fvg_top, 'bottom': self.bear_fvg_bottom},
                'bull_ob': {'top': self.bull_ob_top, 'bottom': self.bull_ob_bottom},
                'bear_ob': {'top': self.bear_ob_top, 'bottom': self.bear_ob_bottom}
            },
            'risk_reward': self.take_profit_rr if signal else None
        }
        
        if signal:
            logger.info(f"🎯 {signal} SIGNAL DETECTED at {entry_price}")
            logger.info(f"   SL: {stop_loss:.2f} | TP: {take_profit:.2f} | RR: 1:{self.take_profit_rr}")
        
        return analysis


# Example usage
if __name__ == "__main__":
    # Test configuration
    config = {
        'trading_style': 'Day Trading',
        'use_htf_confirmation': True,
        'swing_length': 5,
        'bos_threshold': 0.1,
        'fvg_min_size': 0.15,
        'take_profit_rr': 3.0
    }
    
    engine = JarvisEngine(config)
    print("✅ JARVIS Engine initialized successfully!")
