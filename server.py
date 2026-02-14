"""
JARVIS Web Terminal - Backend API Server
Runs 24/7 on cloud platform (Railway/Render)
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time
from datetime import datetime
import logging
import os

from jarvis_engine import JarvisEngine
from market_data import MarketDataFetcher
from jarvis_db import JarvisDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Initialize components
db = JarvisDatabase('jarvis_web.db')
data_fetcher = MarketDataFetcher('binance')

# JARVIS engine configuration
ENGINE_CONFIG = {
    'trading_style': 'Day Trading',
    'use_htf_confirmation': True,
    'swing_length': 5,
    'bos_threshold': 0.1,
    'fvg_min_size': 0.15,
    'ob_lookback': 5,
    'stop_loss_atr': 1.5,
    'take_profit_rr': 3.0,
    'partial_tp_rr': 1.5,
    'use_partial_tp': True,
    'trend_ma_period': 50,
    'rsi_period': 14
}

engine = JarvisEngine(ENGINE_CONFIG)

# Monitored assets
ASSETS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
TIMEFRAMES = ['4h', '1h', '15m']

# Global state
latest_signals = {}  # {symbol_timeframe: signal_data}
latest_analysis = {}  # {symbol_timeframe: analysis_data}
monitoring_active = False


def monitor_markets():
    """
    Background thread that monitors markets 24/7
    """
    global latest_signals, latest_analysis, monitoring_active
    
    logger.info("🚀 Starting market monitoring...")
    monitoring_active = True
    
    while monitoring_active:
        try:
            for symbol in ASSETS:
                for timeframe in TIMEFRAMES:
                    try:
                        # Fetch market data
                        df = data_fetcher.fetch_ohlcv(symbol, timeframe, limit=500)
                        
                        # Get HTF data
                        htf_tf = engine.determine_htf_timeframe(timeframe)
                        htf_df = data_fetcher.fetch_ohlcv(symbol, htf_tf, limit=200)
                        
                        # Run analysis
                        analysis = engine.analyze_market(df, htf_df)
                        
                        # Store analysis
                        key = f"{symbol}_{timeframe}"
                        latest_analysis[key] = {
                            'symbol': symbol,
                            'timeframe': timeframe,
                            'trend': analysis.get('market_trend'),
                            'rsi': analysis.get('rsi'),
                            'price': analysis.get('current_price'),
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        # Check for signal
                        if analysis.get('signal'):
                            logger.info(f"🎯 NEW {analysis['signal']} SIGNAL: {symbol} {timeframe}")
                            
                            # Format symbol for database
                            symbol_formatted = symbol.replace('/', '')
                            
                            # Prepare signal data
                            signal_data = {
                                'symbol': symbol_formatted,
                                'timeframe': timeframe,
                                'signal': analysis['signal'],
                                'timestamp': analysis['timestamp'],
                                'entry_price': analysis['entry_price'],
                                'stop_loss': analysis['stop_loss'],
                                'take_profit': analysis['take_profit'],
                                'partial_tp': analysis['partial_tp'],
                                'atr': analysis['atr'],
                                'rsi': analysis['rsi'],
                                'market_trend': analysis['market_trend'],
                                'htf_trend': analysis['htf_trend'],
                                'risk_reward': analysis['risk_reward'],
                                'structure': analysis.get('structure', {}),
                                'zones': analysis.get('zones', {})
                            }
                            
                            # Save to database
                            signal_id = db.save_signal(signal_data)
                            
                            # Store in memory
                            latest_signals[key] = {
                                'id': signal_id,
                                'type': analysis['signal'],
                                'entry': analysis['entry_price'],
                                'stopLoss': analysis['stop_loss'],
                                'takeProfit': analysis['take_profit'],
                                'partialTP': analysis['partial_tp'],
                                'riskReward': analysis['risk_reward'],
                                'timestamp': analysis['timestamp'].isoformat() if hasattr(analysis['timestamp'], 'isoformat') else str(analysis['timestamp'])
                            }
                            
                            logger.info(f"✅ Signal saved: ID {signal_id}")
                        
                        # Small delay between symbols
                        time.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"Error analyzing {symbol} {timeframe}: {str(e)}")
            
            # Wait before next cycle (60 seconds)
            logger.info(f"✅ Monitoring cycle complete. Sleeping for 60s...")
            time.sleep(60)
            
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
            time.sleep(10)
    
    logger.info("🛑 Market monitoring stopped")


# API Routes

@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'service': 'JARVIS Web Terminal API',
        'version': '2.0',
        'monitoring': monitoring_active
    })


@app.route('/api/signals/latest', methods=['GET'])
def get_latest_signal():
    """Get latest signal for symbol/timeframe"""
    symbol = request.args.get('symbol', 'BTCUSDT')
    timeframe = request.args.get('timeframe', '4h')
    
    # Add slash for internal format
    symbol_with_slash = symbol[:3] + '/' + symbol[3:]
    key = f"{symbol_with_slash}_{timeframe}"
    
    signal = latest_signals.get(key)
    analysis = latest_analysis.get(key, {})
    
    return jsonify({
        'success': True,
        'signal': signal,
        'analysis': analysis
    })


@app.route('/api/signals/all', methods=['GET'])
def get_all_signals():
    """Get all recent signals from database"""
    limit = request.args.get('limit', 50, type=int)
    signals = db.get_all_signals(limit=limit)
    
    formatted_signals = []
    for signal in signals:
        formatted_signals.append({
            'id': signal['id'],
            'symbol': signal['symbol'],
            'timeframe': signal['timeframe'],
            'type': signal['signal_type'],
            'entry': signal['entry_price'],
            'stopLoss': signal['stop_loss'],
            'takeProfit': signal['take_profit'],
            'partialTP': signal['partial_tp'],
            'riskReward': signal['risk_reward'],
            'timestamp': signal['timestamp']
        })
    
    return jsonify({
        'success': True,
        'count': len(formatted_signals),
        'signals': formatted_signals
    })


@app.route('/api/history', methods=['GET'])
def get_history():
    """Get trade history"""
    limit = request.args.get('limit', 100, type=int)
    symbol = request.args.get('symbol', None)
    
    history = db.get_trade_history(limit=limit, symbol=symbol)
    
    formatted_history = []
    for trade in history:
        formatted_history.append({
            'id': trade['id'],
            'symbol': trade['symbol'],
            'timeframe': trade['timeframe'],
            'direction': trade['direction'],
            'entry': trade['entry_price'],
            'exit': trade['exit_price'],
            'entryTime': trade['entry_time'],
            'exitTime': trade['exit_time'],
            'pnl': trade['pnl'],
            'pnlPercent': trade['pnl_percent'],
            'result': trade['result'],
            'exitReason': trade['exit_reason']
        })
    
    return jsonify({
        'success': True,
        'count': len(formatted_history),
        'history': formatted_history
    })


@app.route('/api/performance', methods=['GET'])
def get_performance():
    """Get performance statistics"""
    symbol = request.args.get('symbol', 'BTCUSDT')
    timeframe = request.args.get('timeframe', '4h')
    
    stats = db.get_performance_stats(symbol, timeframe)
    
    if stats:
        formatted_stats = {
            'symbol': stats['symbol'],
            'timeframe': stats['timeframe'],
            'totalTrades': stats['total_trades'],
            'winningTrades': stats['winning_trades'],
            'losingTrades': stats['losing_trades'],
            'winRate': stats['win_rate'],
            'totalPnL': stats['total_pnl'],
            'totalPnLPercent': stats['total_pnl_percent'],
            'largestWin': stats['largest_win'],
            'largestLoss': stats['largest_loss']
        }
    else:
        formatted_stats = {
            'symbol': symbol,
            'timeframe': timeframe,
            'totalTrades': 0,
            'winningTrades': 0,
            'losingTrades': 0,
            'winRate': 0,
            'totalPnL': 0,
            'totalPnLPercent': 0,
            'largestWin': 0,
            'largestLoss': 0
        }
    
    return jsonify({
        'success': True,
        'stats': formatted_stats
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    return jsonify({
        'success': True,
        'status': {
            'monitoring': monitoring_active,
            'activeSymbols': len(ASSETS),
            'activeTimeframes': len(TIMEFRAMES),
            'cachedSignals': len(latest_signals),
            'timestamp': datetime.now().isoformat()
        }
    })


# Start monitoring thread
def start_monitoring():
    """Start the background monitoring thread"""
    monitor_thread = threading.Thread(target=monitor_markets, daemon=True)
    monitor_thread.start()
    logger.info("✅ Monitoring thread started")


# Run server
if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🤖 JARVIS Web Terminal API Server")
    logger.info("=" * 60)
    
    # Start monitoring
    start_monitoring()
    
    # Start Flask server
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
