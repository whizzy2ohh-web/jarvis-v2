// JARVIS AI Trading Terminal - Main JavaScript

// Configuration
const API_URL = 'https://your-backend-url.railway.app/api'; // Will be updated after deployment
const UPDATE_INTERVAL = 10000; // Update every 10 seconds

// State
let currentSymbol = 'BTC/USDT';
let currentTimeframe = '4h';
let signalCheckInterval = null;

// Available assets
const assets = [
    { symbol: 'BTC/USDT', name: 'Bitcoin', ticker: 'BTC', favorite: true },
    { symbol: 'ETH/USDT', name: 'Ethereum', ticker: 'ETH', favorite: true },
    { symbol: 'SOL/USDT', name: 'Solana', ticker: 'SOL', favorite: true },
    { symbol: 'BNB/USDT', name: 'Binance Coin', ticker: 'BNB', favorite: true },
    { symbol: 'XRP/USDT', name: 'Ripple', ticker: 'XRP', favorite: false },
    { symbol: 'ADA/USDT', name: 'Cardano', ticker: 'ADA', favorite: false },
    { symbol: 'DOGE/USDT', name: 'Dogecoin', ticker: 'DOGE', favorite: false },
    { symbol: 'DOT/USDT', name: 'Polkadot', ticker: 'DOT', favorite: false }
];

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    console.log('🚀 Initializing JARVIS Terminal...');
    
    // Render assets
    renderAssets();
    
    // Start monitoring
    startSignalMonitoring();
    
    // Setup search
    setupSearch();
    
    // Setup music toggle
    setupMusic();
    
    console.log('✅ JARVIS Terminal Ready');
}

// Render asset grid
function renderAssets() {
    const grid = document.getElementById('asset-grid');
    grid.innerHTML = '';
    
    assets.forEach(asset => {
        const card = document.createElement('div');
        card.className = 'asset-card';
        if (asset.symbol === currentSymbol) {
            card.classList.add('selected');
        }
        
        card.innerHTML = `
            <div class="asset-header">
                <div class="asset-symbol">${asset.ticker}</div>
                <div class="asset-favorite">${asset.favorite ? '⭐' : '☆'}</div>
            </div>
            <div class="asset-name">${asset.symbol}</div>
        `;
        
        card.onclick = () => selectAsset(asset.symbol);
        
        grid.appendChild(card);
    });
}

// Select asset
function selectAsset(symbol) {
    currentSymbol = symbol;
    renderAssets();
    updateCurrentAssetDisplay();
    fetchLatestSignal();
}

// Select timeframe
function selectTimeframe(tf) {
    currentTimeframe = tf;
    
    // Update UI
    document.querySelectorAll('.timeframe-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tf="${tf}"]`).classList.add('active');
    
    updateCurrentAssetDisplay();
    fetchLatestSignal();
}

// Update current asset display
function updateCurrentAssetDisplay() {
    const ticker = currentSymbol.split('/')[0];
    document.getElementById('selected-symbol').textContent = ticker;
    document.getElementById('selected-tf').textContent = currentTimeframe.toUpperCase();
}

// Fetch latest signal from backend
async function fetchLatestSignal() {
    try {
        // Show loading state
        const signalDisplay = document.getElementById('signal-display');
        signalDisplay.innerHTML = `
            <div class="signal-icon">⏳</div>
            <div class="signal-message">Checking for signals...</div>
        `;
        
        // Format symbol for API (remove /)
        const symbolFormatted = currentSymbol.replace('/', '');
        
        // Fetch from backend
        const response = await fetch(`${API_URL}/signals/latest?symbol=${symbolFormatted}&timeframe=${currentTimeframe}`);
        
        if (!response.ok) {
            throw new Error('API request failed');
        }
        
        const data = await response.json();
        
        if (data.signal) {
            displaySignal(data.signal);
        } else {
            displayNoSignal();
        }
        
        // Update price and analysis
        if (data.analysis) {
            updateAnalysis(data.analysis);
        }
        
    } catch (error) {
        console.error('Error fetching signal:', error);
        displayOfflineMode();
    }
}

// Display active signal
function displaySignal(signal) {
    const signalDisplay = document.getElementById('signal-display');
    const signalDetails = document.getElementById('signal-details');
    
    // Hide the "waiting" message
    signalDisplay.classList.add('hidden');
    
    // Show signal details
    signalDetails.classList.remove('hidden');
    if (signal.type === 'SHORT') {
        signalDetails.classList.add('short');
    }
    
    const timeAgo = getTimeAgo(signal.timestamp);
    
    signalDetails.innerHTML = `
        <div class="signal-header-box">
            <div class="signal-type ${signal.type.toLowerCase()}">${signal.type} ${currentSymbol.split('/')[0]}</div>
            <div class="signal-time">${timeAgo}</div>
        </div>
        
        <div class="signal-levels">
            <div class="signal-level entry">
                <div class="signal-level-label">📍 ENTRY</div>
                <div class="signal-level-value">$${signal.entry.toLocaleString()}</div>
            </div>
            <div class="signal-level tp">
                <div class="signal-level-label">🎯 TAKE PROFIT</div>
                <div class="signal-level-value">$${signal.takeProfit.toLocaleString()}</div>
            </div>
            <div class="signal-level tp">
                <div class="signal-level-label">🎯 PARTIAL TP</div>
                <div class="signal-level-value">$${signal.partialTP.toLocaleString()}</div>
            </div>
            <div class="signal-level sl">
                <div class="signal-level-label">🛡 STOP LOSS</div>
                <div class="signal-level-value">$${signal.stopLoss.toLocaleString()}</div>
            </div>
        </div>
        
        <div style="margin-top: 20px; text-align: center; color: var(--cyan); font-size: 14px;">
            ⚖️ Risk/Reward: 1:${signal.riskReward}
        </div>
    `;
    
    // Update signal status
    document.getElementById('signal-value').textContent = signal.type;
    document.getElementById('signal-value').className = `analysis-value signal ${signal.type.toLowerCase()}`;
}

// Display no signal state
function displayNoSignal() {
    const signalDisplay = document.getElementById('signal-display');
    const signalDetails = document.getElementById('signal-details');
    
    signalDisplay.classList.remove('hidden');
    signalDetails.classList.add('hidden');
    
    signalDisplay.innerHTML = `
        <div class="signal-icon">🔍</div>
        <div class="signal-message">No entry signal yet. Monitoring for setups...</div>
    `;
    
    document.getElementById('signal-value').textContent = 'WAITING';
    document.getElementById('signal-value').className = 'analysis-value signal';
}

// Display offline mode
function displayOfflineMode() {
    const signalDisplay = document.getElementById('signal-display');
    
    signalDisplay.innerHTML = `
        <div class="signal-icon">🔌</div>
        <div class="signal-message">Backend offline. Using demo mode...</div>
    `;
    
    // Use demo data
    setTimeout(() => {
        displayDemoSignal();
    }, 2000);
}

// Display demo signal (for testing without backend)
function displayDemoSignal() {
    const demoSignal = {
        type: 'LONG',
        entry: 69000,
        takeProfit: 70500,
        partialTP: 69750,
        stopLoss: 68500,
        riskReward: 3.0,
        timestamp: new Date().toISOString()
    };
    
    displaySignal(demoSignal);
    
    // Update analysis with demo data
    updateAnalysis({
        trend: 'BULLISH',
        rsi: 55.3,
        price: 69051.40
    });
}

// Update analysis display
function updateAnalysis(analysis) {
    if (analysis.trend) {
        const trendEl = document.getElementById('trend-value');
        trendEl.textContent = analysis.trend;
        trendEl.className = `analysis-value trend ${analysis.trend.toLowerCase()}`;
    }
    
    if (analysis.rsi) {
        document.getElementById('rsi-value').textContent = analysis.rsi.toFixed(2);
    }
    
    if (analysis.price) {
        document.getElementById('asset-price').textContent = `$${analysis.price.toLocaleString()}`;
    }
}

// Start signal monitoring
function startSignalMonitoring() {
    // Initial fetch
    fetchLatestSignal();
    
    // Set up interval
    signalCheckInterval = setInterval(() => {
        fetchLatestSignal();
    }, UPDATE_INTERVAL);
    
    console.log('✅ Signal monitoring started');
}

// Stop signal monitoring
function stopSignalMonitoring() {
    if (signalCheckInterval) {
        clearInterval(signalCheckInterval);
        signalCheckInterval = null;
    }
}

// Get time ago string
function getTimeAgo(timestamp) {
    const now = new Date();
    const then = new Date(timestamp);
    const diff = Math.floor((now - then) / 1000); // seconds
    
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    return `${Math.floor(diff / 86400)} days ago`;
}

// Tab switching
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');
    
    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Load tab-specific data
    if (tabName === 'history') {
        loadTradeHistory();
    }
}

// Toggle settings
function toggleSettings() {
    const panel = document.getElementById('settings-panel');
    panel.classList.toggle('hidden');
    panel.classList.toggle('active');
}

// Filter assets
function filterAssets(filter) {
    // Update active filter tab
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Filter logic here (for now just show all)
    renderAssets();
}

// Search setup
function setupSearch() {
    const searchInput = document.getElementById('asset-search');
    
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        
        // Filter assets
        const filteredAssets = assets.filter(asset => 
            asset.symbol.toLowerCase().includes(query) ||
            asset.name.toLowerCase().includes(query) ||
            asset.ticker.toLowerCase().includes(query)
        );
        
        // Re-render with filtered assets
        const grid = document.getElementById('asset-grid');
        grid.innerHTML = '';
        
        filteredAssets.forEach(asset => {
            const card = document.createElement('div');
            card.className = 'asset-card';
            if (asset.symbol === currentSymbol) {
                card.classList.add('selected');
            }
            
            card.innerHTML = `
                <div class="asset-header">
                    <div class="asset-symbol">${asset.ticker}</div>
                    <div class="asset-favorite">${asset.favorite ? '⭐' : '☆'}</div>
                </div>
                <div class="asset-name">${asset.symbol}</div>
            `;
            
            card.onclick = () => selectAsset(asset.symbol);
            
            grid.appendChild(card);
        });
        
        // Update count
        document.querySelector('.asset-count').textContent = `${filteredAssets.length} pairs available`;
    });
}

// Setup music
function setupMusic() {
    const toggle = document.getElementById('music-toggle');
    const audio = document.getElementById('background-music');
    
    toggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            audio.play().catch(err => console.log('Music play failed:', err));
        } else {
            audio.pause();
        }
    });
}

// Load trade history
async function loadTradeHistory() {
    const historyList = document.getElementById('history-list');
    
    try {
        const response = await fetch(`${API_URL}/history?limit=20`);
        
        if (!response.ok) {
            throw new Error('Failed to load history');
        }
        
        const data = await response.json();
        
        if (data.history && data.history.length > 0) {
            renderHistory(data.history);
        } else {
            historyList.innerHTML = `
                <div class="coming-soon">
                    <h2>📊 No Trade History Yet</h2>
                    <p>Trades will appear here once signals are executed</p>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Error loading history:', error);
        renderDemoHistory();
    }
}

// Render history
function renderHistory(history) {
    const historyList = document.getElementById('history-list');
    
    historyList.innerHTML = history.map(trade => `
        <div class="history-item ${trade.result.toLowerCase()}">
            <div class="history-header">
                <div class="history-symbol">${trade.direction} ${trade.symbol}</div>
                <div class="history-result ${trade.result.toLowerCase()}">
                    ${trade.pnlPercent > 0 ? '+' : ''}${trade.pnlPercent.toFixed(2)}%
                </div>
            </div>
            <div class="history-details">
                <div>
                    <div class="history-detail-label">Entry</div>
                    <div>$${trade.entry.toLocaleString()}</div>
                </div>
                <div>
                    <div class="history-detail-label">Exit</div>
                    <div>$${trade.exit.toLocaleString()}</div>
                </div>
                <div>
                    <div class="history-detail-label">Result</div>
                    <div>${trade.result}</div>
                </div>
                <div>
                    <div class="history-detail-label">Exit Time</div>
                    <div>${getTimeAgo(trade.exitTime)}</div>
                </div>
            </div>
        </div>
    `).join('');
}

// Render demo history (for testing)
function renderDemoHistory() {
    const demoHistory = [
        {
            direction: 'LONG',
            symbol: 'BTCUSDT',
            entry: 68000,
            exit: 69500,
            result: 'WIN',
            pnlPercent: 2.21,
            exitTime: new Date(Date.now() - 86400000).toISOString()
        },
        {
            direction: 'SHORT',
            symbol: 'ETHUSDT',
            entry: 3600,
            exit: 3550,
            result: 'WIN',
            pnlPercent: 1.39,
            exitTime: new Date(Date.now() - 172800000).toISOString()
        }
    ];
    
    renderHistory(demoHistory);
}

// Expose functions globally
window.switchTab = switchTab;
window.toggleSettings = toggleSettings;
window.filterAssets = filterAssets;
window.selectTimeframe = selectTimeframe;

console.log('✅ JARVIS Terminal script loaded');
