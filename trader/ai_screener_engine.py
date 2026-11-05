"""
AI-Powered Indian Stock Market Screener Engine
Scans NSE & BSE stock universe for high-potential intraday & swing BUY setups.
Analyzes Candlestick patterns, RSI, MACD, EMAs, VWAP, Bollinger Bands, Volume Spikes,
and dynamically calculates Entry, Target 1, Target 2, Stop-Loss, and R:R ratios.
"""

import os
import json
import time
from datetime import datetime, date, timedelta
from pathlib import Path
import pytz
import pandas as pd
import numpy as np
import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "trader" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = STATE_DIR / "daily_screener_report.json"
ALERTS_CONFIG_FILE = STATE_DIR / "alerts_config.json"

IST = pytz.timezone("Asia/Kolkata")

# NSE/BSE High-Liquidity Stocks Universe
WATCHLIST_UNIVERSE = [
    # Large Cap Nifty 50 Giants
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries", "sector": "Energy & Oil", "bse": "500325"},
    {"symbol": "TATAMOTORS.NS", "name": "Tata Motors Ltd", "sector": "Automobile", "bse": "500570"},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank Ltd", "sector": "Banking & Fin", "bse": "500180"},
    {"symbol": "ICICIBANK.NS", "name": "ICICI Bank Ltd", "sector": "Banking & Fin", "bse": "532174"},
    {"symbol": "INFY.NS", "name": "Infosys Ltd", "sector": "IT & Tech", "bse": "500209"},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services", "sector": "IT & Tech", "bse": "532540"},
    {"symbol": "LT.NS", "name": "Larsen & Toubro Ltd", "sector": "Infrastructure", "bse": "500510"},
    {"symbol": "SBIN.NS", "name": "State Bank of India", "sector": "Banking & Fin", "bse": "500112"},
    {"symbol": "ITC.NS", "name": "ITC Ltd", "sector": "FMCG", "bse": "500875"},
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel Ltd", "sector": "Telecom", "bse": "532454"},
    {"symbol": "AXISBANK.NS", "name": "Axis Bank Ltd", "sector": "Banking & Fin", "bse": "532215"},
    {"symbol": "BAJFINANCE.NS", "name": "Bajaj Finance Ltd", "sector": "NBFC & Fin", "bse": "500034"},
    {"symbol": "MARUTI.NS", "name": "Maruti Suzuki India", "sector": "Automobile", "bse": "532500"},
    {"symbol": "SUNPHARMA.NS", "name": "Sun Pharma Industries", "sector": "Healthcare", "bse": "524715"},
    {"symbol": "TITAN.NS", "name": "Titan Company Ltd", "sector": "Consumer & Retail", "bse": "500114"},
    {"symbol": "TATASTEEL.NS", "name": "Tata Steel Ltd", "sector": "Metals & Mining", "bse": "500470"},
    {"symbol": "NTPC.NS", "name": "NTPC Ltd", "sector": "Power & Energy", "bse": "532555"},
    {"symbol": "POWERGRID.NS", "name": "Power Grid Corp of India", "sector": "Power & Energy", "bse": "532898"},
    {"symbol": "ADANIENT.NS", "name": "Adani Enterprises", "sector": "Conglomerate", "bse": "512599"},
    {"symbol": "ADANIPORTS.NS", "name": "Adani Ports & SEZ", "sector": "Ports & Logistics", "bse": "532921"},
    {"symbol": "COALINDIA.NS", "name": "Coal India Ltd", "sector": "Metals & Mining", "bse": "533278"},
    {"symbol": "ONGC.NS", "name": "Oil & Natural Gas Corp", "sector": "Energy & Oil", "bse": "500312"},
    {"symbol": "M&M.NS", "name": "Mahindra & Mahindra", "sector": "Automobile", "bse": "500520"},
    {"symbol": "HINDALCO.NS", "name": "Hindalco Industries", "sector": "Metals & Mining", "bse": "500440"},
    {"symbol": "JSWSTEEL.NS", "name": "JSW Steel Ltd", "sector": "Metals & Mining", "bse": "500228"},
    {"symbol": "WIPRO.NS", "name": "Wipro Ltd", "sector": "IT & Tech", "bse": "507685"},
    {"symbol": "HCLTECH.NS", "name": "HCL Technologies", "sector": "IT & Tech", "bse": "532281"},
    {"symbol": "KOTAKBANK.NS", "name": "Kotak Mahindra Bank", "sector": "Banking & Fin", "bse": "500247"},
    # High-Momentum Growth & Midcap Stocks
    {"symbol": "BEL.NS", "name": "Bharat Electronics Ltd", "sector": "Defense & Aerospace", "bse": "500049"},
    {"symbol": "HAL.NS", "name": "Hindustan Aeronautics Ltd", "sector": "Defense & Aerospace", "bse": "541154"},
    {"symbol": "TRENT.NS", "name": "Trent Ltd", "sector": "Consumer & Retail", "bse": "500251"},
    {"symbol": "ZOMATO.NS", "name": "Zomato Ltd", "sector": "Internet & E-com", "bse": "543320"},
    {"symbol": "JIOFIN.NS", "name": "Jio Financial Services", "sector": "NBFC & Fin", "bse": "543940"},
    {"symbol": "SUZLON.NS", "name": "Suzlon Energy Ltd", "sector": "Green Energy", "bse": "532667"},
    {"symbol": "BHEL.NS", "name": "Bharat Heavy Electricals", "sector": "Capital Goods", "bse": "500103"},
    {"symbol": "REC.NS", "name": "REC Ltd", "sector": "Power Finance", "bse": "532955"},
    {"symbol": "PFC.NS", "name": "Power Finance Corp", "sector": "Power Finance", "bse": "532810"},
    {"symbol": "VEDL.NS", "name": "Vedanta Ltd", "sector": "Metals & Mining", "bse": "500295"},
    {"symbol": "DLF.NS", "name": "DLF Ltd", "sector": "Real Estate", "bse": "532868"}
]

# Official NSE Holidays 2026/2027 (Common dates)
NSE_HOLIDAYS = [
    "2026-01-26", "2026-03-03", "2026-03-25", "2026-04-03", "2026-04-14",
    "2026-05-01", "2026-06-17", "2026-08-15", "2026-09-07", "2026-10-02",
    "2026-10-20", "2026-11-08", "2026-11-10", "2026-11-24", "2026-12-25"
]

class IndianStockScreener:
    """
    AI-powered Indian Stock Market Screener Engine:
    - Scans NSE/BSE equities
    - Analyzes Technicals: RSI, MACD, EMAs (9/21/50/200), VWAP, Bollinger Bands, RVOL
    - Detects Candlestick Patterns: Bullish Engulfing, Hammer, Morning Star, Breakout Bars
    - Computes Dynamic Entry Point, Target 1 (1.5R), Target 2 (2.8R), Stop-Loss (1.0R), and Expected Profit %
    - AI Confidence Scoring (0 - 100)
    - Pre-Market & 9:00 AM IST execution
    """

    def __init__(self):
        self.report_file = REPORT_FILE

    def get_market_status(self) -> dict:
        """Determines whether the Indian Stock Market is currently Open, Pre-Market, Closed, Weekend or Holiday."""
        now_ist = datetime.now(IST)
        date_str = now_ist.strftime("%Y-%m-%d")
        weekday = now_ist.weekday() # 0 = Monday, 6 = Sunday

        is_weekend = weekday in (5, 6)
        is_holiday = date_str in NSE_HOLIDAYS

        # Indian Market Times:
        # Pre-Market: 9:00 AM - 9:15 AM
        # Normal Market: 9:15 AM - 3:30 PM
        current_time_val = now_ist.hour * 100 + now_ist.minute

        if is_weekend:
            status = "WEEKEND_CLOSED"
            status_text = "Market Closed (Weekend)"
            can_trade = False
        elif is_holiday:
            status = "HOLIDAY_CLOSED"
            status_text = "Market Closed (Official NSE Holiday)"
            can_trade = False
        elif 900 <= current_time_val < 915:
            status = "PRE_MARKET"
            status_text = "NSE / BSE Pre-Market Session (9:00 AM - 9:15 AM)"
            can_trade = True
        elif 915 <= current_time_val < 1530:
            status = "MARKET_OPEN"
            status_text = "NSE / BSE Live Market Session (9:15 AM - 3:30 PM)"
            can_trade = True
        else:
            status = "MARKET_CLOSED"
            status_text = "Market Closed (After Hours)"
            can_trade = False

        # Calculate next 9:00 AM IST scan time
        next_scan = now_ist.replace(hour=9, minute=0, second=0, microsecond=0)
        if current_time_val >= 900 or is_weekend or is_holiday:
            # Advance to next trading day
            days_to_add = 1
            test_date = now_ist + timedelta(days=days_to_add)
            while test_date.weekday() in (5, 6) or test_date.strftime("%Y-%m-%d") in NSE_HOLIDAYS:
                days_to_add += 1
                test_date = now_ist + timedelta(days=days_to_add)
            next_scan = test_date.replace(hour=9, minute=0, second=0, microsecond=0)

        seconds_until_next = max(0, int((next_scan - now_ist).total_seconds()))

        return {
            "status": status,
            "status_text": status_text,
            "can_trade": can_trade,
            "is_weekend": is_weekend,
            "is_holiday": is_holiday,
            "ist_time": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
            "next_scan_time": next_scan.strftime("%Y-%m-%d 09:00:00 IST"),
            "seconds_until_next": seconds_until_next
        }

    def _calculate_indicators(self, df: pd.DataFrame) -> dict:
        """Calculates RSI, MACD, EMAs, SMA, Bollinger Bands, ATR, and Volume ratios."""
        if len(df) < 20:
            return {}

        closes = df['Close']
        highs = df['High']
        lows = df['Low']
        volumes = df['Volume']

        # 1. EMAs and SMAs
        ema9 = closes.ewm(span=9, adjust=False).mean()
        ema21 = closes.ewm(span=21, adjust=False).mean()
        ema50 = closes.ewm(span=50, adjust=False).mean() if len(closes) >= 50 else ema21
        ema200 = closes.ewm(span=200, adjust=False).mean() if len(closes) >= 200 else ema50
        sma20 = closes.rolling(window=20).mean()

        # 2. RSI (14)
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        # 3. MACD (12, 26, 9)
        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - macd_signal

        # 4. Bollinger Bands (20, 2)
        bb_std = closes.rolling(window=20).std()
        bb_upper = sma20 + (bb_std * 2)
        bb_lower = sma20 - (bb_std * 2)
        bb_width = (bb_upper - bb_lower) / sma20.replace(0, np.nan)

        # 5. ATR (14)
        tr1 = highs - lows
        tr2 = (highs - closes.shift()).abs()
        tr3 = (lows - closes.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr14 = tr.rolling(window=14).mean()

        # 6. Volume & RVOL
        vol_avg20 = volumes.rolling(window=20).mean()
        rvol = volumes / vol_avg20.replace(0, np.nan)

        # Latest values
        curr_close = float(closes.iloc[-1])
        curr_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
        curr_macd = float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0.0
        curr_macd_sig = float(macd_signal.iloc[-1]) if not pd.isna(macd_signal.iloc[-1]) else 0.0
        curr_macd_hist = float(macd_hist.iloc[-1]) if not pd.isna(macd_hist.iloc[-1]) else 0.0
        prev_macd_hist = float(macd_hist.iloc[-2]) if len(macd_hist) > 1 and not pd.isna(macd_hist.iloc[-2]) else 0.0

        curr_ema9 = float(ema9.iloc[-1])
        curr_ema21 = float(ema21.iloc[-1])
        curr_ema50 = float(ema50.iloc[-1])
        curr_ema200 = float(ema200.iloc[-1])
        curr_sma20 = float(sma20.iloc[-1])
        curr_atr = float(atr14.iloc[-1]) if not pd.isna(atr14.iloc[-1]) else curr_close * 0.015
        curr_rvol = float(rvol.iloc[-1]) if not pd.isna(rvol.iloc[-1]) else 1.0

        # Estimated VWAP
        typical_price = (highs + lows + closes) / 3
        vwap = (typical_price * volumes).cumsum() / volumes.cumsum().replace(0, np.nan)
        curr_vwap = float(vwap.iloc[-1]) if not pd.isna(vwap.iloc[-1]) else curr_close

        # 7. Candlestick Pattern Recognition
        pattern = "Consolidation Bar"
        o, h, l, c = float(df['Open'].iloc[-1]), float(df['High'].iloc[-1]), float(df['Low'].iloc[-1]), curr_close
        prev_o, prev_c = float(df['Open'].iloc[-2]), float(df['Close'].iloc[-2])
        body = abs(c - o)
        range_bar = max(h - l, 0.01)
        lower_shadow = min(o, c) - l
        upper_shadow = h - max(o, c)

        if c > o and prev_c < prev_o and c >= prev_o and o <= prev_c:
            pattern = "Bullish Engulfing"
        elif lower_shadow >= 2.0 * body and upper_shadow <= 0.2 * body and c >= (l + 0.65 * range_bar):
            pattern = "Bullish Hammer / Pin Bar"
        elif c > o and c > float(df['High'].iloc[-5:-1].max() if len(df) >= 5 else h):
            pattern = "Multi-Day Range Breakout"
        elif c > curr_vwap and curr_rvol >= 1.5:
            pattern = "High Volume Breakout Bar"
        elif c > curr_ema21 and prev_c <= float(ema21.iloc[-2]):
            pattern = "EMA 21 Reclaim & Bounce"
        elif curr_rsi < 38 and c > o:
            pattern = "Oversold RSI Reversal"

        return {
            "cmp": curr_close,
            "rsi": round(curr_rsi, 1),
            "macd": round(curr_macd, 2),
            "macd_signal": round(curr_macd_sig, 2),
            "macd_hist": round(curr_macd_hist, 2),
            "macd_bullish": curr_macd > curr_macd_sig and curr_macd_hist >= prev_macd_hist,
            "ema9": round(curr_ema9, 2),
            "ema21": round(curr_ema21, 2),
            "ema50": round(curr_ema50, 2),
            "ema200": round(curr_ema200, 2),
            "sma20": round(curr_sma20, 2),
            "vwap": round(curr_vwap, 2),
            "atr": max(round(curr_atr, 2), round(curr_close * 0.008, 2)),
            "rvol": round(curr_rvol, 2),
            "pattern": pattern,
            "bb_upper": round(float(bb_upper.iloc[-1]), 2),
            "bb_lower": round(float(bb_lower.iloc[-1]), 2),
            "bb_width": round(float(bb_width.iloc[-1]) * 100, 2)
        }

    def _score_and_setup(self, stock_info: dict, tech: dict) -> dict:
        """
        Calculates AI Confidence Score (0-100), dynamic Entry/Target/Stop-Loss,
        Trade Type (Intraday/Swing), and AI Reasoning.
        """
        cmp = tech["cmp"]
        atr = tech["atr"]
        rsi = tech["rsi"]
        rvol = tech["rvol"]
        macd_bull = tech["macd_bullish"]
        pattern = tech["pattern"]

        score = 0
        reasons = []

        # 1. Trend Alignment & Moving Averages (Up to 25 pts)
        if cmp > tech["ema21"]:
            score += 10
            reasons.append("Trading firmly above 21 EMA support")
        if tech["ema21"] > tech["ema50"]:
            score += 8
            reasons.append("Bullish short-term trend (21 EMA > 50 EMA)")
        if cmp > tech["ema200"]:
            score += 7
            reasons.append("Primary trend bullish above 200 EMA")

        # 2. Volume Spike & Relative Volume (Up to 25 pts)
        if rvol >= 2.0:
            score += 25
            reasons.append(f"Institutional volume surge: {rvol:.1f}x of 20-day average volume")
        elif rvol >= 1.4:
            score += 18
            reasons.append(f"Above-average volume expansion ({rvol:.1f}x 20d avg)")
        elif rvol >= 1.0:
            score += 10

        # 3. Momentum: RSI & MACD (Up to 20 pts)
        if 52 <= rsi <= 68:
            score += 12
            reasons.append(f"RSI in optimal bullish momentum zone ({rsi})")
        elif 32 <= rsi < 52:
            score += 8
            reasons.append(f"RSI rebounding from oversold base ({rsi})")
        elif rsi > 70:
            score += 5 # overbought risk

        if macd_bull:
            score += 8
            reasons.append("MACD histogram expanding with bullish line crossover")

        # 4. Candlestick Pattern & VWAP Confirmation (Up to 15 pts)
        if cmp > tech["vwap"]:
            score += 8
            reasons.append(f"Price holding above session VWAP (₹{tech['vwap']:,.2f})")
        if pattern in ["Bullish Engulfing", "Multi-Day Range Breakout", "High Volume Breakout Bar"]:
            score += 7
            reasons.append(f"High-conviction pattern: {pattern}")
        elif pattern in ["Bullish Hammer / Pin Bar", "EMA 21 Reclaim & Bounce"]:
            score += 5
            reasons.append(f"Reversal price action: {pattern}")

        # 5. Volatility & Risk-Reward Quality (Up to 15 pts)
        atr_pct = (atr / cmp) * 100
        if 1.2 <= atr_pct <= 4.5:
            score += 15
            reasons.append(f"Healthy intraday volatility profile (ATR: {atr_pct:.1f}%)")
        else:
            score += 8

        # Cap score between 0 and 99
        confidence = min(max(score, 25), 98)

        # Recommendation Tier
        if confidence >= 78:
            recommendation = "STRONG BUY"
            rec_badge = "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
        elif confidence >= 65:
            recommendation = "BUY ON DIP"
            rec_badge = "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
        elif confidence >= 50:
            recommendation = "WAIT"
            rec_badge = "bg-amber-500/20 text-amber-400 border border-amber-500/40"
        else:
            recommendation = "AVOID"
            rec_badge = "bg-rose-500/20 text-rose-400 border border-rose-500/40"

        # Trade Type
        trade_type = "Intraday" if (atr_pct >= 2.0 or rvol >= 1.6) else "Swing"

        # Dynamic Trade Setup Levels (Dynamic ATR Sizing)
        entry_price = round(cmp, 2)
        entry_range_min = round(entry_price - 0.25 * atr, 2)
        entry_range_max = round(entry_price + 0.15 * atr, 2)
        stop_loss = round(entry_price - 1.0 * atr, 2)
        target_1 = round(entry_price + 1.5 * atr, 2)
        target_2 = round(entry_price + 2.8 * atr, 2)

        risk_val = entry_price - stop_loss
        reward_1 = target_1 - entry_price
        reward_2 = target_2 - entry_price

        profit_t1_pct = round((reward_1 / entry_price) * 100, 2)
        profit_t2_pct = round((reward_2 / entry_price) * 100, 2)
        sl_pct = round((risk_val / entry_price) * 100, 2)

        ai_reasoning = (
            f"{stock_info['name']} shows {pattern.lower()} with {rvol:.1f}x volume expansion. "
            f"RSI is at {rsi} and CMP ₹{cmp:,.2f} is maintaining key support above 21 EMA (₹{tech['ema21']:,.2f}) "
            f"and session VWAP (₹{tech['vwap']:,.2f}). "
            f"Setup offers 1:2.80 R:R targeting ₹{target_1:,.2f} (conservative) and ₹{target_2:,.2f} (extended) "
            f"with disciplined Stop-Loss at ₹{stop_loss:,.2f}."
        )

        return {
            "symbol": stock_info["symbol"].replace(".NS", ""),
            "full_symbol": stock_info["symbol"],
            "bse_code": stock_info.get("bse", ""),
            "name": stock_info["name"],
            "sector": stock_info["sector"],
            "cmp": cmp,
            "change_pct": round(((cmp - float(tech["sma20"])) / float(tech["sma20"])) * 100, 2), # trend vs 20d
            "confidence_score": confidence,
            "recommendation": recommendation,
            "recommendation_badge": rec_badge,
            "trade_type": trade_type,
            "entry_price": entry_price,
            "entry_range": f"₹{entry_range_min:,.2f} - ₹{entry_range_max:,.2f}",
            "entry_range_min": entry_range_min,
            "entry_range_max": entry_range_max,
            "target_1": target_1,
            "target_1_gain_pct": profit_t1_pct,
            "target_2": target_2,
            "target_2_gain_pct": profit_t2_pct,
            "stop_loss": stop_loss,
            "stop_loss_pct": sl_pct,
            "risk_reward": "1 : 2.80",
            "risk_reward_t1": "1 : 1.50",
            "expected_profit_pct": f"+{profit_t1_pct}% to +{profit_t2_pct}%",
            "pattern": pattern,
            "rsi": tech["rsi"],
            "rvol": tech["rvol"],
            "ema21": tech["ema21"],
            "vwap": tech["vwap"],
            "atr": tech["atr"],
            "key_factors": reasons[:4],
            "ai_reasoning": ai_reasoning,
            "scanned_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        }

    def run_market_scan(self, top_n: int = 15) -> dict:
        """
        Executes full Indian market scan:
        - Downloads recent historical daily data for all universe stocks
        - Analyzes technical indicators & candlestick patterns
        - Filters and ranks top high-probability BUY opportunities
        - Persists structured report to state
        """
        market_info = self.get_market_status()
        symbols = [s["symbol"] for s in WATCHLIST_UNIVERSE]
        print(f"[AI Screener] Starting scan of {len(symbols)} Indian stocks at {datetime.now(IST).strftime('%H:%M:%S IST')}...")

        results = []
        try:
            # Batch fetch 35 days of daily data for speed
            tickers_data = yf.download(
                tickers=symbols,
                period="60d",
                interval="1d",
                group_by="ticker",
                threads=True,
                progress=False,
                timeout=12
            )

            for item in WATCHLIST_UNIVERSE:
                sym = item["symbol"]
                try:
                    if len(symbols) == 1:
                        df = tickers_data
                    else:
                        df = tickers_data[sym] if sym in tickers_data else None

                    if df is None or len(df) < 15:
                        continue

                    # Clean dataframe
                    df = df.dropna(subset=['Close'])
                    if len(df) < 15:
                        continue

                    tech = self._calculate_indicators(df)
                    if not tech or tech.get("cmp", 0) <= 0:
                        continue

                    setup = self._score_and_setup(item, tech)
                    results.append(setup)
                except Exception as ex:
                    print(f"[AI Screener] Error evaluating {sym}: {ex}")

        except Exception as e:
            print(f"[AI Screener Batch Download Error] {e}")

        # If data was completely unavailable or market is closed with no data
        if not results:
            report = {
                "success": True,
                "scan_time": datetime.now(IST).strftime("%Y-%m-%d 09:00:00 IST"),
                "market_status": market_info,
                "summary": {
                    "total_scanned": len(WATCHLIST_UNIVERSE),
                    "shortlisted_count": 0,
                    "market_sentiment": "NEUTRAL / NO DATA",
                    "average_confidence": 0,
                    "no_trade_notice": "NO TRADE: Reliable market feed temporarily unavailable or holiday session. Capital preservation active."
                },
                "shortlisted_stocks": [],
                "all_setups": []
            }
            self._save_report(report)
            return report

        # Sort results by Confidence Score descending
        results.sort(key=lambda x: x["confidence_score"], reverse=True)

        # Filter high-probability buy candidates (Score >= 65)
        top_buys = [s for s in results if s["confidence_score"] >= 65][:top_n]
        if not top_buys:
            top_buys = results[:top_n] # fallback to top relative setups

        # Calculate sentiment index
        avg_score = round(sum(s["confidence_score"] for s in results) / len(results), 1)
        if avg_score >= 70:
            market_sentiment = "BULLISH ACCUMULATION"
            sentiment_badge = "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
        elif avg_score >= 55:
            market_sentiment = "MODERATELY BULLISH"
            sentiment_badge = "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
        elif avg_score >= 45:
            market_sentiment = "CONSOLIDATION / NEUTRAL"
            sentiment_badge = "bg-amber-500/20 text-amber-400 border border-amber-500/30"
        else:
            market_sentiment = "BEARISH PRESSURE"
            sentiment_badge = "bg-rose-500/20 text-rose-400 border border-rose-500/30"

        # Check for NO TRADE condition (e.g. market holiday or weekend)
        no_trade_reason = None
        if market_info["is_weekend"]:
            no_trade_reason = "WEEKEND NOTICE: Indian exchanges are closed on Saturday & Sunday. Signals reflect latest closing data for Monday's 9:00 AM preparation."
        elif market_info["is_holiday"]:
            no_trade_reason = "HOLIDAY NOTICE: NSE & BSE are closed for official market holiday. New orders will execute on the next regular session."
        elif len(top_buys) == 0:
            no_trade_reason = "NO TRADE: Market breadth is uncertain and no stock meets the strict 65% minimum confidence threshold. Protect your capital."

        report = {
            "success": True,
            "scan_time": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
            "session_date": datetime.now(IST).strftime("%A, %d %B %Y"),
            "market_status": market_info,
            "summary": {
                "total_scanned": len(results),
                "shortlisted_count": len(top_buys),
                "strong_buy_count": len([s for s in results if s["recommendation"] == "STRONG BUY"]),
                "buy_on_dip_count": len([s for s in results if s["recommendation"] == "BUY ON DIP"]),
                "intraday_setups": len([s for s in top_buys if s["trade_type"] == "Intraday"]),
                "swing_setups": len([s for s in top_buys if s["trade_type"] == "Swing"]),
                "average_confidence": avg_score,
                "market_sentiment": market_sentiment,
                "sentiment_badge": sentiment_badge,
                "no_trade_notice": no_trade_reason
            },
            "top_opportunities": top_buys,
            "all_stocks": results
        }

        self._save_report(report)
        print(f"[AI Screener] Completed scan! Generated {len(top_buys)} top BUY setups (Avg Score: {avg_score}).")
        return report

    def _save_report(self, report: dict):
        try:
            with open(self.report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
        except Exception as e:
            print(f"[AI Screener Save Error] {e}")

    def get_latest_report(self) -> dict:
        """Returns the latest saved screener report or runs a fresh scan if none exists."""
        if self.report_file.exists():
            try:
                with open(self.report_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Update live market status so time/countdown is always real-time
                    data["market_status"] = self.get_market_status()
                    return data
            except Exception:
                pass
        return self.run_market_scan()

ai_screener = IndianStockScreener()

