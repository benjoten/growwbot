# Day Trader Terminal & Groww Suite 🚀

A modern algorithmic day-trading web application and portfolio manager combining:
1. **DayTrader Autonomous Bi-Directional Intraday Trading System** (`/system`): Multi-asset automated intraday engine for Indian Equities, Index Options (`NIFTY`, `BANKNIFTY`, `FINNIFTY`, `SENSEX` weekly CE/PE with exact strike selection, delta, and Greeks), and Crypto Perpetuals (`BTC`, `ETH`, `SOL` 24x7) with embedded **TradingView Lightweight Charts** (interactive auto-drawings for Entry Box, T1, T2, Stop-Loss, and R:R synced directly to tickets).
2. **US Stocks & ETFs Day-Trading Suite** (`/us`): Built on the 11 skills from [Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill), with embedded **TradingView Advanced Charting**, automated mathematical position sizing, **Alpaca Paper Trading**, historical **Backtesting** with equity curves, and **Monte Carlo Time Machine** forward projections.
3. **AI-Powered Indian Stock Market Screener** (`/screener`): 9:00 AM IST pre-market scanner across 38 liquid NSE/BSE stocks with automated Telegram and Email alerts.
4. **Delta Exchange Crypto Derivatives** (`/crypto`): 100x leverage perpetual futures with dynamic entry, T1, T2, SL, and live sizing.
5. **Indian Market Groww Integration** (`/groww`): Direct connection with Groww broker via official `growwapi` and automated TOTP authentication.

---

## 🌟 Autonomous Bi-Directional System (`/system`)

- **Universe Coverage**:
  - **Indian Index Options**: Weekly ATM/OTM Delta ~0.50 / ~0.35 options for `NIFTY` (step 50, lot 25), `BANKNIFTY` (step 100, lot 15), `FINNIFTY` (step 50, lot 25), and `SENSEX` (step 100, lot 10).
  - **NSE/BSE Equities**: Top liquid momentum stocks (`RELIANCE`, `HDFCBANK`, `ICICIBANK`, `SBIN`, `TCS`, `INFY`, `WIPRO`, `BAJFINANCE`, `LT`, etc.).
  - **Crypto Perpetuals**: 24x7 monitoring of `BTCUSDT`, `ETHUSDT`, `SOLUSDT` with Funding Rate bias, Open Interest (OI) delta, and Order-Book imbalance.
- **Bi-Directional Setups**: Emits both **LONG** (`BUY CALL`, `LONG PERP`, `BUY (LONG)`) and **SHORT** (`BUY PUT`, `SHORT PERP`, `SELL (SHORT)`) trade tickets.
- **TradingView Interactive Chart Sync**:
  - Selecting any trade call instantly loads the real candlestick data (1m, 5m, 15m, 1h, 1D).
  - Automatically draws on chart: **Shaded Entry Zone Box**, **Target 1 & Target 2 horizontal dashed lines**, and **Stop-Loss horizontal dashed line**.
- **Institutional Trade Ticket Details**:
  - Direction, Exact Strike & Delta, Entry Price (with slippage buffer), T1 (1.5R), T2 (2.5R), Stop-Loss (1.0R).
  - Position sizing in Lots / Contracts / Shares with exact max risk cap and expected profits.
  - Walk-Forward Backtest Expectancy (2+ years historical calibration: Win Rate %, Profit Factor, Max Drawdown, Sharpe Ratio).
  - Upside & Downside scenario narratives and 15:15 IST max hold time rule.
  - 1-Click Paper Execution order placement.

---

## 🌟 Key Features

### 1. Embedded TradingView Advanced Chart & Skill Overlays
- Real-time candlestick charting for all US Equities & ETFs (e.g. `TSLA`, `NVDA`, `AAPL`, `SPY`, `QQQ`, `AMD`, `MSFT`, `AMZN`, `SOXL`).
- **Interactive Price Level Ladder & Overlays**: Clearly marked visual badges and lines for:
  - 🟢 **Take Profit (Exit)**: Dynamic target level based on risk-reward rules (`1R`, `1.5R`, `2R`, `3R`).
  - 🔵 **Entry Trigger**: Breakout level computed from selected setup patterns.
  - 🔴 **Stop-Loss**: Mathematical stop derived from `or-mid` (Opening Range Midpoint), `or-low`, `atr:1.5`, or percentage.
  - 🟡 **15-Minute Opening Range**: High and low benchmarks.

### 2. All 11 Skills Fully Exposed & Selectable in UI
| Skill | Module | Function in Application |
|---|---|---|
| **`trader-scanner`** | [scan.py](file:///.agents/skills/trader-scanner/scan.py) | Market-wide scanner for 5 setups: ORB, 20-Day High Breakout, Bull Flag, 20D SMA Reclaim, Oversold RSI Bounce |
| **`trader-entry`** | [entry.py](file:///.agents/skills/trader-entry/entry.py) | Bar-by-bar entry timing on 5-minute closed bars and opening range formation |
| **`trader-exit`** | [exit.py](file:///.agents/skills/trader-exit/exit.py) | Stop loss planner (`or-mid`, `or-low`, `atr:1.5`, `pct:2%`) and Take-Profit planner (`1R`, `1.5R`, `2R`, `3R`), 15:55 ET flat-by rule |
| **`trader-timemachine`** | [timemachine.py](file:///.agents/skills/trader-timemachine/timemachine.py) | Monte Carlo simulation with 2,000–10,000 bootstrap session replays and historical pattern odds |
| **`trader-budget`** | [size.py](file:///.agents/skills/trader-budget/size.py) | Sizing algorithm allocating whole shares to exact dollar max loss, account budget, and cash buffer |
| **`trader-risk`** | [check.py](file:///.agents/skills/trader-risk/check.py) | Pre-trade gatekeeper verifying minimum R:R ratio, daily limits, and required stop loss |
| **`trader-broker`** | [ticket.py](file:///.agents/skills/trader-broker/ticket.py) | Alpaca paper trading execution and bracket order dispatch |
| **`trader-alerts`** | [alerts.py](file:///.agents/skills/trader-alerts/alerts.py) | Price and time triggers (opening bell, stop hit, target reached, 15:55 close) |
| **`trader-news`** | [news.py](file:///.agents/skills/trader-news/news.py) | Live breaking news and SEC 8-K disclosures tagged by Earnings, Analyst, Deals, Legal |
| **`trader-analyst`** | [facts.py](file:///.agents/skills/trader-analyst/facts.py) | SEC EDGAR XBRL company facts (TTM revenue, gross/operating/profit margins, EPS) |
| **`trader-pelosi`** | [ptr.py](file:///.agents/skills/trader-pelosi/ptr.py) | U.S. House of Representatives STOCK Act trade disclosures (PTRs) |

### 3. Alpaca Paper Trading & Virtual Broker Simulator
- **Live Alpaca Paper Trading API**: Connect your official paper trading credentials (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`) to place real orders directly into the live paper market.
- **Built-in Paper Broker Simulator**: Works immediately out of the box with $100,000 virtual capital, simulating bracket orders (entry, stop-loss, take-profit), tracking real-time P&L, position inventory, and order history.
- **1-Click Flatten**: Immediately close any open position by 15:55 ET to avoid overnight market exposure.

### 4. Historical Backtesting Engine & Equity Curve
- Evaluates chosen strategy on 60 days of 5-minute historical bars for any selected stock or ETF.
- Computes comprehensive quantitative metrics:
  - **Win Rate (%)**
  - **Total P&L (%) and Total Profit ($)**
  - **Average Trade Return (%)**
  - **Maximum Drawdown (%)** (peak-to-trough)
  - **Sharpe Ratio** (annualized)
  - **Profit Factor** (gross gains / gross losses)
  - Interactive **Cumulative Equity Curve** plotted with Chart.js.

### 5. Time Machine Monte Carlo Projection
- Simulates 2,000–10,000 bootstrap replays from historical 5-minute bar returns.
- Yields statistical probabilities:
  - Target Hit First (%)
  - Stop Hit First (%)
  - Neither / Still Open at Market Close (%)
  - 90% Confidence Interval Expected P&L Range
  - Fan Chart displaying multiple replay paths.
- Honest statistical verdict ("Leans toward target", "Close to coin flip", "Leans toward stop").
- Explicit regulatory disclaimer: *Projections are probabilistic estimates derived from historical data and do not constitute financial advice.*

---

## 📁 Project Architecture

```
Groww-Trading-Project/
├── .agents/skills/               # Installed Antigravity skills
│   ├── trader-scanner/
│   ├── trader-entry/
│   ├── trader-exit/
│   ├── trader-timemachine/
│   ├── trader-budget/
│   ├── trader-risk/
│   ├── trader-broker/
│   ├── trader-alerts/
│   ├── trader-news/
│   ├── trader-analyst/
│   └── trader-pelosi/
├── alpaca_service.py             # Alpaca Paper Trading REST API & Paper Simulator
├── backtest_engine.py            # Historical backtesting & metrics engine
├── skills_engine.py              # Strategy coordinator & Monte Carlo engine
├── groww_client.py               # Groww API & automated TOTP authentication
├── config.py                     # Environment & credentials loader
├── app.py                        # Unified Flask application & REST API
├── templates/
│   ├── us_trader.html            # US Day Trader Terminal with TradingView widget
│   └── index.html                # Groww Indian Broker Dashboard
├── run.bat                       # 1-click Windows launcher
└── requirements.txt              # Python dependencies
```

---

## ⚡ Quick Start

### 1. Launch the Application
Run via the Windows batch script:
```powershell
.\run.bat
```
Or start manually with the virtual environment:
```powershell
.\venv\Scripts\activate
python app.py
```

Open your browser at:
- **US Day Trading Terminal**: **[http://127.0.0.1:5000/](http://127.0.0.1:5000/)**
- **Groww Indian Broker Terminal**: **[http://127.0.0.1:5000/groww](http://127.0.0.1:5000/groww)**

---

## ⚙️ Alpaca API Configuration (Optional)
To connect your official Alpaca paper account:
1. Click the **"Paper Mode / Config"** button in the dashboard topbar.
2. Enter your `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` from your Alpaca dashboard.
3. Click **"Save & Connect"**. The system will save them securely to `.env` and immediately switch to live Alpaca Paper trading.
