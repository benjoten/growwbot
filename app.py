import os
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from config import CONFIG
from groww_client import groww_manager
from alpaca_service import alpaca_service
from delta_service import delta_service
from skills_engine import skills_engine, DEFAULT_US_WATCHLIST
from backtest_engine import backtest_engine
from trader.ai_screener_engine import ai_screener
from trader.ai_screener_scheduler import screener_scheduler
from trader.bidirectional_engine import BiDirectionalTradingSystem, load_system_config
from trader.system_scheduler import SystemScheduler
import pyotp

app = Flask(__name__)
app.secret_key = CONFIG["flask_secret"]

# Initialize Autonomous Bi-Directional Trading System & Daemon
bidirectional_system = BiDirectionalTradingSystem()
system_scheduler = SystemScheduler(bidirectional_system)
system_scheduler.start()

# --------------------------------------------------------
# Web Page Views
# --------------------------------------------------------
@app.route("/")
@app.route("/us")
def index():
    """Renders the US Stocks & ETFs Day Trading Dashboard."""
    return render_template("us_trader.html")

@app.route("/system")
@app.route("/daytrader")
def daytrader_dashboard():
    """Renders the DayTrader Autonomous Bi-Directional Intraday System Dashboard."""
    return render_template("trading_system.html")

@app.route("/groww")
def groww_dashboard():
    """Renders the Groww Indian Stock Broker Dashboard."""
    return render_template("index.html")

@app.route("/crypto")
@app.route("/delta")
def crypto_dashboard():
    """Renders the Delta Exchange Crypto Derivatives Terminal."""
    return render_template("delta_trader.html")

@app.route("/screener")
def screener_dashboard():
    """Renders the AI-Powered Indian Stock Market Screener Dashboard."""
    return render_template("ai_screener.html")

# --------------------------------------------------------
# US Day Trading & Skills REST API
# --------------------------------------------------------
@app.route("/api/us/watchlist")
def api_us_watchlist():
    """Returns liquid US Stocks and ETFs watchlist."""
    return jsonify({"success": True, "watchlist": DEFAULT_US_WATCHLIST})

@app.route("/api/us/quote/<symbol>")
def api_us_quote(symbol):
    """Fetches real-time price, opening range, ATR, SMA20, and RSI."""
    try:
        metrics = skills_engine.get_market_quote_and_metrics(symbol)
        return jsonify({"success": True, "data": metrics})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/us/signals", methods=["POST"])
def api_us_signals():
    """
    Computes Entry, Stop-Loss, Take-Profit, Position Size, and Risk Gatekeeper
    based on the user's active skill selection.
    """
    try:
        data = request.get_json() or {}
        symbol = data.get("symbol", "TSLA").upper()
        active_skills = data.get("active_skills", ["orb"])
        stop_rule = data.get("stop_rule", "or-mid")
        target_rule = data.get("target_rule", "2R")
        account_budget = float(data.get("account_budget", 5000.0))
        max_loss_usd = float(data.get("max_loss_usd", 50.0))

        signals = skills_engine.compute_strategy_signals(
            symbol=symbol,
            active_skills=active_skills,
            stop_rule=stop_rule,
            target_rule=target_rule,
            account_budget=account_budget,
            max_loss_usd=max_loss_usd
        )
        return jsonify({"success": True, "signals": signals})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/us/backtest", methods=["POST"])
def api_us_backtest():
    """Runs a historical simulation on 60 days of 5m bars for chosen skills."""
    try:
        data = request.get_json() or {}
        symbol = data.get("symbol", "TSLA").upper()
        active_skills = data.get("active_skills", ["orb"])
        stop_rule = data.get("stop_rule", "or-mid")
        target_rule = data.get("target_rule", "2R")
        initial_capital = float(data.get("initial_capital", 10000.0))
        risk_per_trade_usd = float(data.get("risk_per_trade_usd", 100.0))

        result = backtest_engine.run_backtest(
            symbol=symbol,
            active_skills=active_skills,
            stop_rule=stop_rule,
            target_rule=target_rule,
            initial_capital=initial_capital,
            risk_per_trade_usd=risk_per_trade_usd
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/us/projection", methods=["POST"])
def api_us_projection():
    """Runs trader-timemachine Monte Carlo simulation (1,000 - 10,000 replays)."""
    try:
        data = request.get_json() or {}
        symbol = data.get("symbol", "TSLA").upper()
        entry = float(data.get("entry", 100.0))
        stop = float(data.get("stop", 98.0))
        target = float(data.get("target", 104.0))
        replays = int(data.get("replays", 2000))

        result = skills_engine.run_monte_carlo_timemachine(
            symbol=symbol,
            entry=entry,
            stop=stop,
            target=target,
            replays=replays
        )
        return jsonify({"success": True, "projection": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/us/scanner")
def api_us_scanner():
    """Scans the liquid universe for setups (ORB, Breakout 20D, Bull Flag, etc.)."""
    try:
        setup_type = request.args.get("setup", "orb")
        hits = skills_engine.run_market_scanner(setup_type=setup_type)
        return jsonify({"success": True, "setup": setup_type, "hits": hits})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# --------------------------------------------------------
# Paper Trading & Broker REST API (Alpaca / Simulator)
# --------------------------------------------------------
@app.route("/api/us/account")
def api_us_account():
    """Returns paper trading account balance and buying power."""
    try:
        acc = alpaca_service.get_account()
        return jsonify({"success": True, "account": acc})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/us/positions")
def api_us_positions():
    """Returns open paper positions with real-time P&L."""
    try:
        positions = alpaca_service.get_positions()
        return jsonify({"success": True, "positions": positions})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/us/orders")
def api_us_orders():
    """Returns paper order book."""
    try:
        orders = alpaca_service.get_orders()
        return jsonify({"success": True, "orders": orders})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/us/order", methods=["POST"])
def api_us_place_order():
    """Places a paper trading order (Market, Limit, or Bracket with Stop/Target)."""
    try:
        data = request.get_json() or {}
        symbol = data.get("symbol")
        qty = float(data.get("qty", 1))
        side = data.get("side", "buy")
        order_type = data.get("order_type", "market")
        limit_price = float(data["limit_price"]) if data.get("limit_price") else None
        stop_loss = float(data["stop_loss"]) if data.get("stop_loss") else None
        take_profit = float(data["take_profit"]) if data.get("take_profit") else None

        res = alpaca_service.place_order(
            symbol=symbol,
            qty=qty,
            side=side,
            order_type=order_type,
            limit_price=limit_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/us/flatten", methods=["POST"])
def api_us_flatten():
    """1-click closes/flattens position in symbol."""
    try:
        data = request.get_json() or {}
        symbol = data.get("symbol")
        res = alpaca_service.flatten_position(symbol)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/us/position/update_brackets", methods=["POST"])
def api_us_update_brackets():
    """Updates Take-Profit and Stop-Loss prices on an active position."""
    try:
        data = request.get_json() or {}
        symbol = data.get("symbol")
        stop_loss = float(data["stop_loss"]) if data.get("stop_loss") is not None and str(data["stop_loss"]).strip() != "" else None
        take_profit = float(data["take_profit"]) if data.get("take_profit") is not None and str(data["take_profit"]).strip() != "" else None
        res = alpaca_service.update_position_brackets(symbol=symbol, stop_loss=stop_loss, take_profit=take_profit)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/us/cancel_order", methods=["POST"])
def api_us_cancel_order():
    """Cancels open paper order."""
    try:
        data = request.get_json() or {}
        order_id = data.get("order_id")
        res = alpaca_service.cancel_order(order_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/us/alpaca_config", methods=["POST"])
def api_us_alpaca_config():
    """Updates Alpaca API credentials in .env."""
    try:
        data = request.get_json() or {}
        api_key = data.get("api_key", "").strip()
        secret_key = data.get("secret_key", "").strip()
        res = alpaca_service.update_keys(api_key, secret_key)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# --------------------------------------------------------
# Research & Intelligence APIs (News, Analyst, Pelosi)
# --------------------------------------------------------
@app.route("/api/us/news/<symbol>")
def api_us_news(symbol):
    """Fetches real-time news headlines (trader-news)."""
    try:
        news = skills_engine.fetch_news(symbol)
        return jsonify({"success": True, "news": news})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/us/analyst/<symbol>")
def api_us_analyst(symbol):
    """Fetches quarterly financials & margins (trader-analyst)."""
    try:
        facts = skills_engine.get_sec_analyst(symbol)
        return jsonify({"success": True, "analyst": facts})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/us/pelosi/<symbol>")
def api_us_pelosi(symbol):
    """Fetches congressional stock disclosures (trader-pelosi)."""
    try:
        trades = skills_engine.get_congress_trades(symbol)
        return jsonify({"success": True, "trades": trades})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --------------------------------------------------------
# Groww Indian Broker Endpoints (Maintained)
# --------------------------------------------------------
@app.route("/api/summary")
def api_summary():
    summary = groww_manager.get_dashboard_summary()
    return jsonify(summary)

@app.route("/api/profile")
def api_profile():
    try:
        return jsonify({"success": True, "profile": groww_manager.get_profile()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/funds")
def api_funds():
    try:
        return jsonify({"success": True, "funds": groww_manager.get_funds()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/holdings")
def api_holdings():
    try:
        holdings = groww_manager.get_holdings()
        total_invested = sum((float(h.get("quantity", 0)) * float(h.get("average_price", 0))) for h in holdings)
        return jsonify({"success": True, "holdings": holdings, "count": len(holdings), "total_invested": round(total_invested, 2)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/totp")
def api_totp():
    try:
        secret = groww_manager.totp_secret
        if not secret: return jsonify({"success": False, "error": "No TOTP secret configured"})
        code = pyotp.TOTP(secret).now()
        seconds_remaining = 30 - (int(time.time()) % 30)
        return jsonify({"success": True, "code": code, "remaining_seconds": seconds_remaining})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/reconnect", methods=["POST"])
def api_reconnect():
    try:
        groww_manager.authenticate(force=True)
        return jsonify({"success": True, "message": "Successfully refreshed Groww API session token with TOTP!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --------------------------------------------------------
# Multi-Broker Status & Account Switcher API
# --------------------------------------------------------
@app.route("/api/brokers/status")
def api_brokers_status():
    """Returns connected status and quick summaries for Groww, Alpaca, and Delta Exchange."""
    try:
        # Groww status
        groww_conn = bool(groww_manager.api_key and len(groww_manager.api_key) > 10)
        groww_info = {
            "id": "groww",
            "name": "Groww India",
            "market": "NSE / BSE Stocks & F&O",
            "connected": groww_conn,
            "status": "Connected (Active)" if groww_conn else "Requires Token",
            "mode": "GROWW TOTP LIVE",
            "url": "/groww"
        }

        # Alpaca status
        alpaca_acc = alpaca_service.get_account()
        alpaca_info = {
            "id": "alpaca",
            "name": "Alpaca US",
            "market": "US Stocks & ETFs",
            "connected": True,
            "status": alpaca_acc.get("mode_badge", "SIMULATED"),
            "mode": alpaca_acc.get("mode", "paper_simulator"),
            "cash": alpaca_acc.get("cash", 100000.0),
            "unrealized_pl": alpaca_acc.get("total_unrealized_pl", 0.0),
            "realized_pl": alpaca_acc.get("total_realized_pl", 0.0),
            "open_positions": alpaca_acc.get("open_positions_count", 0),
            "url": "/us"
        }

        # Delta Exchange status
        delta_acc = delta_service.get_account()
        delta_info = {
            "id": "delta",
            "name": "Delta Exchange",
            "market": "Crypto Perpetual Futures (BTC, ETH)",
            "connected": True,
            "status": delta_acc.get("mode_badge", "DELTA SIMULATED"),
            "mode": delta_acc.get("mode", "delta_simulator"),
            "environment": delta_service.environment,
            "cash": delta_acc.get("cash_usdt", 50000.0),
            "unrealized_pl": delta_acc.get("total_unrealized_pl", 0.0),
            "realized_pl": delta_acc.get("total_realized_pl", 0.0),
            "open_positions": delta_acc.get("open_positions_count", 0),
            "url": "/crypto"
        }

        # AI Indian Stock Screener Status
        market_st = ai_screener.get_market_status()
        screener_info = {
            "id": "screener",
            "name": "AI Indian Stock Screener",
            "market": "NSE / BSE 9:00 AM Top Setups",
            "connected": True,
            "mode": "AI 9:00 AM IST ENGINE",
            "status": market_st.get("status_text", "DAILY 9:00 AM SCANNER ACTIVE"),
            "url": "/screener"
        }

        return jsonify({
            "success": True,
            "brokers": {
                "groww": groww_info,
                "alpaca": alpaca_info,
                "delta": delta_info,
                "screener": screener_info
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --------------------------------------------------------
# Delta Exchange Crypto Derivatives REST API
# --------------------------------------------------------
@app.route("/api/crypto/account")
def api_crypto_account():
    try:
        acc = delta_service.get_account()
        return jsonify({"success": True, "account": acc})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/crypto/positions")
def api_crypto_positions():
    try:
        positions = delta_service.get_positions()
        return jsonify({"success": True, "positions": positions})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/crypto/orders")
def api_crypto_orders():
    try:
        orders = delta_service.get_orders()
        return jsonify({"success": True, "orders": orders})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/crypto/order", methods=["POST"])
def api_crypto_place_order():
    try:
        data = request.get_json() or {}
        symbol = data.get("symbol", "BTCUSDT")
        size = float(data.get("size", 1))
        side = data.get("side", "buy")
        order_type = data.get("order_type", "market")
        limit_price = float(data["limit_price"]) if data.get("limit_price") else None
        stop_loss = float(data["stop_loss"]) if data.get("stop_loss") else None
        take_profit = float(data["take_profit"]) if data.get("take_profit") else None
        leverage = float(data.get("leverage", 10))

        res = delta_service.place_order(
            symbol=symbol,
            size=size,
            side=side,
            order_type=order_type,
            limit_price=limit_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            leverage=leverage
        )
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/crypto/position/update_brackets", methods=["POST"])
def api_crypto_update_brackets():
    try:
        data = request.get_json() or {}
        symbol = data.get("symbol")
        stop_loss = float(data["stop_loss"]) if data.get("stop_loss") is not None and str(data["stop_loss"]).strip() != "" else None
        take_profit = float(data["take_profit"]) if data.get("take_profit") is not None and str(data["take_profit"]).strip() != "" else None
        res = delta_service.update_position_brackets(symbol=symbol, stop_loss=stop_loss, take_profit=take_profit)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/crypto/close_position", methods=["POST"])
def api_crypto_close_position():
    try:
        data = request.get_json() or {}
        symbol = data.get("symbol")
        res = delta_service.close_position(symbol)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/crypto/cancel_order", methods=["POST"])
def api_crypto_cancel_order():
    try:
        data = request.get_json() or {}
        order_id = data.get("order_id")
        res = delta_service.cancel_order(order_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/crypto/ticker/<symbol>")
def api_crypto_ticker(symbol):
    try:
        ticker = delta_service.get_ticker_data(symbol)
        return jsonify({"success": True, "ticker": ticker})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/crypto/signal/<symbol>")
def api_crypto_signal(symbol):
    try:
        leverage = float(request.args.get("leverage", 10))
        size = float(request.args.get("size", 10))
        signal_data = delta_service.get_derivatives_signal(symbol, leverage=leverage, size=size)
        return jsonify({"success": True, "signal": signal_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/crypto/products")
def api_crypto_products():
    try:
        products = delta_service.get_popular_products()
        return jsonify({"success": True, "products": products})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/crypto/config", methods=["GET", "POST"])
def api_crypto_config():
    if request.method == "GET":
        return jsonify({
            "api_key": delta_service.api_key,
            "api_secret": delta_service.api_secret,
            "environment": delta_service.environment,
            "base_url": delta_service.base_url,
            "is_live": delta_service.is_live_delta()
        })
    try:
        data = request.get_json() or {}
        api_key = data.get("api_key", "").strip()
        api_secret = data.get("api_secret", "").strip()
        environment = data.get("environment", "testnet_india").strip()
        res = delta_service.update_keys(api_key, api_secret, environment)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# --------------------------------------------------------
# AI-Powered Indian Stock Market Screener REST API
# --------------------------------------------------------
@app.route("/api/screener/latest")
def api_screener_latest():
    try:
        report = ai_screener.get_latest_report()
        return jsonify(report)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/screener/run", methods=["POST"])
def api_screener_run():
    try:
        report = screener_scheduler.run_scan_and_alert()
        return jsonify(report)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/screener/status")
def api_screener_status():
    try:
        status_info = ai_screener.get_market_status()
        alerts_cfg = screener_scheduler.get_alerts_config()
        return jsonify({
            "success": True,
            "market_status": status_info,
            "alerts_enabled": {
                "telegram": alerts_cfg.get("telegram_enabled", False),
                "email": alerts_cfg.get("email_enabled", False),
                "auto_scan_9am": alerts_cfg.get("auto_scan_at_9am", True)
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/screener/alerts/config", methods=["GET", "POST"])
def api_screener_alerts_config():
    if request.method == "GET":
        cfg = screener_scheduler.get_alerts_config()
        safe_cfg = cfg.copy()
        if safe_cfg.get("smtp_password"):
            safe_cfg["smtp_password"] = "******"
        return jsonify({"success": True, "config": safe_cfg})
    try:
        data = request.get_json() or {}
        res = screener_scheduler.save_alerts_config(data)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/screener/alerts/test", methods=["POST"])
def api_screener_alerts_test():
    try:
        data = request.get_json() or {}
        channel = data.get("channel", "telegram")
        cfg = screener_scheduler.get_alerts_config()
        
        # Allow overriding with live inputs from modal
        bot_token = (data.get("bot_token") or cfg.get("telegram_bot_token", "")).strip()
        chat_id = (data.get("chat_id") or cfg.get("telegram_chat_id", "")).strip()

        test_msg = (
            "🔔 <b>AI Indian Stock Screener — Connection Test</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ <b>Telegram Alert System Active & Verified!</b>\n\n"
            "📊 <b>Sample Alert Format (Daily 9:00 AM IST):</b>\n"
            "• <b>Stock:</b> ICICI Bank Ltd (<code>ICICIBANK</code> / BSE: 532174)\n"
            "• <b>Recommendation:</b> 🟢 STRONG BUY (93% AI Confidence)\n"
            "• <b>CMP:</b> ₹1,500.00 | <b>Entry Range:</b> ₹1,492 - ₹1,504\n"
            "• <b>Target 1:</b> ₹1,545.66 (+3.04%)\n"
            "• <b>Target 2:</b> ₹1,585.23 (+5.68%)\n"
            "• <b>Stop-Loss:</b> ₹1,469.56 (-2.03%)\n"
            "• <b>Risk:Reward:</b> 1 : 2.80\n"
            "• <b>Setup:</b> Multi-Day Range Breakout with 2.8x Volume\n\n"
            "⏰ <i>Every trading weekday at ~9:00 AM IST, your top shortlisted opportunities will arrive here automatically.</i>"
        )
        if channel == "telegram":
            ok, msg = screener_scheduler._send_telegram(bot_token, chat_id, test_msg)
            return jsonify({"success": ok, "message": msg})
        elif channel == "email":
            ok = screener_scheduler._send_email(cfg, "AI Stock Screener: Connection Test", test_msg)
            return jsonify({"success": ok, "message": "Email test alert sent" if ok else "Email delivery failed. Check SMTP settings."})
        return jsonify({"success": False, "error": "Unknown channel"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/screener/alerts/telegram/detect_chat", methods=["POST"])
def api_screener_telegram_detect():
    """Detects numeric chat_id from recent bot updates."""
    try:
        data = request.get_json() or {}
        cfg = screener_scheduler.get_alerts_config()
        bot_token = (data.get("bot_token") or cfg.get("telegram_bot_token", "")).strip()
        if not bot_token:
            return jsonify({"success": False, "error": "Bot Token required"}), 400

        chat_id, msg = screener_scheduler.detect_telegram_chat_id(bot_token)
        if chat_id:
            cfg["telegram_chat_id"] = chat_id
            cfg["telegram_enabled"] = True
            screener_scheduler.save_alerts_config(cfg)
            return jsonify({"success": True, "chat_id": chat_id, "message": msg})
        else:
            return jsonify({"success": False, "error": msg}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --------------------------------------------------------
# Autonomous Bi-Directional Trading System REST API
# --------------------------------------------------------
@app.route("/api/system/live_prices")
def api_system_live_prices():
    """Returns streaming live prices for all active tickers (Crypto 24x7, Equities, Indices)."""
    try:
        prices = bidirectional_system.get_live_prices()
        return jsonify({
            "success": True,
            "timestamp": int(time.time()),
            "ist_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
            "prices": prices
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/system/signals")
def api_system_signals():
    """Returns all active bi-directional trade tickets (Equities, Index Options, Crypto)."""
    try:
        json_path = os.path.join(os.path.dirname(__file__), "trader", "state", "trade_tickets_latest.json")
        if os.path.exists(json_path):
            import json
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return jsonify({"success": True, **data})
        else:
            tickets = bidirectional_system.scan_all_universe()
            return jsonify({
                "success": True,
                "system_name": "DayTrader System",
                "scan_time": bidirectional_system.last_scan_time,
                "total_tickets": len(tickets),
                "tickets": [t.model_dump() for t in tickets]
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/system/candles/<symbol>")
def api_system_candles(symbol):
    """Returns real candlestick bars formatted for TradingView Lightweight Charts."""
    try:
        interval = request.args.get("interval", "15m")
        candles = bidirectional_system.get_candle_history(symbol, interval=interval)
        return jsonify({
            "success": True,
            "symbol": symbol,
            "interval": interval,
            "count": len(candles),
            "candles": candles
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "candles": []}), 500

@app.route("/api/system/scan", methods=["POST"])
def api_system_scan():
    """Triggers an on-demand bi-directional universe scan."""
    try:
        tickets = bidirectional_system.scan_all_universe()
        return jsonify({
            "success": True,
            "total_tickets": len(tickets),
            "scan_time": bidirectional_system.last_scan_time,
            "tickets": [t.model_dump() for t in tickets]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/system/execute", methods=["POST"])
def api_system_execute():
    """Places a simulated paper trade order for the selected ticket."""
    try:
        payload = request.get_json() or {}
        ticket = payload.get("ticket", {})
        if not ticket:
            return jsonify({"success": False, "error": "No ticket provided"}), 400
            
        orders_file = os.path.join(os.path.dirname(__file__), "trader", "state", "system_paper_orders.json")
        import json, uuid
        orders = []
        if os.path.exists(orders_file):
            try:
                with open(orders_file, "r", encoding="utf-8") as f:
                    orders = json.load(f)
            except Exception:
                orders = []
                
        order_entry = {
            "order_id": f"ORD-SYS-{uuid.uuid4().hex[:8].upper()}",
            "executed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
            "ticket_id": ticket.get("ticket_id"),
            "symbol": ticket.get("symbol"),
            "display_name": ticket.get("display_name"),
            "asset_class": ticket.get("asset_class", "EQUITY"),
            "direction": ticket.get("direction"),
            "units": ticket.get("units", "Shares"),
            "lot_count": ticket.get("lot_count", 1),
            "entry_price": float(ticket.get("entry_price", 0)),
            "underlying_price": float(ticket.get("underlying_price", ticket.get("entry_price", 0))),
            "target_1": float(ticket.get("target_1", 0)),
            "target_2": float(ticket.get("target_2", 0)),
            "stop_loss": float(ticket.get("stop_loss", 0)),
            "allocated_capital": float(ticket.get("allocated_capital", 0)),
            "max_loss_amount": float(ticket.get("max_loss_amount", 0)),
            "status": "OPEN",
            "brackets_active": True
        }
        orders.insert(0, order_entry)
        with open(orders_file, "w", encoding="utf-8") as f:
            json.dump(orders, f, indent=2)
            
        return jsonify({"success": True, "message": "Order executed in Paper Simulation", "order": order_entry})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/system/positions")
def api_system_positions():
    """Returns active paper positions with live mark-to-market P&L and closed order history."""
    try:
        orders_file = os.path.join(os.path.dirname(__file__), "trader", "state", "system_paper_orders.json")
        import json
        orders = []
        if os.path.exists(orders_file):
            try:
                with open(orders_file, "r", encoding="utf-8") as f:
                    orders = json.load(f)
            except Exception:
                orders = []

        live_prices = bidirectional_system.get_live_prices()
        open_positions = []
        closed_orders = []

        total_unrealized_inr = 0.0
        total_unrealized_usdt = 0.0
        total_realized_pnl = 0.0

        for ord_item in orders:
            status = ord_item.get("status", "OPEN")
            if status == "OPEN":
                sym = ord_item.get("symbol")
                entry_p = float(ord_item.get("entry_price", 0))
                direction = str(ord_item.get("direction", "")).upper()
                asset_class = str(ord_item.get("asset_class", "EQUITY"))
                qty = float(ord_item.get("lot_count", 1))
                capital = float(ord_item.get("allocated_capital", 1))

                # Find current market price
                live_item = live_prices.get(sym, {})
                curr_p = float(live_item.get("price", entry_p))
                currency = live_item.get("currency", "$" if "USDT" in sym or "CRYPTO" in asset_class else "₹")

                # P&L calculation
                is_short = ("SHORT" in direction or "PUT" in direction or "SELL" in direction)
                
                if "CRYPTO" in asset_class or "USDT" in sym:
                    # Multipliers: 0.001 BTC, 0.01 ETH, 0.1 SOL
                    mult = 0.001 if "BTC" in sym else (0.01 if "ETH" in sym else 0.1)
                    coins = qty * mult
                    if is_short:
                        pnl = (entry_p - curr_p) * coins
                    else:
                        pnl = (curr_p - entry_p) * coins
                    total_unrealized_usdt += pnl
                elif "INDEX_OPTION" in asset_class:
                    # Option premium change estimate
                    delta = 0.50
                    underlying_entry = float(ord_item.get("underlying_price", entry_p))
                    spot_diff = curr_p - underlying_entry
                    prem_change = spot_diff * delta if not is_short else -spot_diff * delta
                    curr_option_prem = max(entry_p + prem_change, 1.0)
                    lot_size = 25 if "NIFTY" in sym else (15 if "BANKNIFTY" in sym else 10)
                    pnl = (curr_option_prem - entry_p) * qty * lot_size
                    total_unrealized_inr += pnl
                else:
                    # Equity shares
                    if is_short:
                        pnl = (entry_p - curr_p) * qty
                    else:
                        pnl = (curr_p - entry_p) * qty
                    total_unrealized_inr += pnl

                roi_pct = round((pnl / max(capital, 1.0)) * 100.0, 2)
                pnl = round(pnl, 2)

                # Check bracket exits
                t1 = float(ord_item.get("target_1", 0))
                t2 = float(ord_item.get("target_2", 0))
                sl = float(ord_item.get("stop_loss", 0))
                bracket_status = "HOLDING_ACTIVE"

                if is_short:
                    if curr_p <= t1 and t1 > 0:
                        bracket_status = "TARGET 1 REACHED (+PROFIT)"
                    elif curr_p >= sl and sl > 0:
                        bracket_status = "STOP LOSS TRIGGERED"
                else:
                    if curr_p >= t1 and t1 > 0:
                        bracket_status = "TARGET 1 REACHED (+PROFIT)"
                    elif curr_p <= sl and sl > 0:
                        bracket_status = "STOP LOSS TRIGGERED"

                open_positions.append({
                    **ord_item,
                    "current_price": curr_p,
                    "currency": currency,
                    "unrealized_pnl": pnl,
                    "roi_pct": roi_pct,
                    "bracket_status": bracket_status
                })
            else:
                total_realized_pnl += float(ord_item.get("realized_pnl", 0))
                closed_orders.append(ord_item)

        return jsonify({
            "success": True,
            "open_count": len(open_positions),
            "closed_count": len(closed_orders),
            "total_unrealized_inr": round(total_unrealized_inr, 2),
            "total_unrealized_usdt": round(total_unrealized_usdt, 2),
            "total_realized_pnl": round(total_realized_pnl, 2),
            "open_positions": open_positions,
            "closed_orders": closed_orders
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/system/close_position", methods=["POST"])
def api_system_close_position():
    """Closes an open paper order and realizes P&L."""
    try:
        data = request.get_json() or {}
        order_id = data.get("order_id")
        if not order_id:
            return jsonify({"success": False, "error": "order_id required"}), 400

        orders_file = os.path.join(os.path.dirname(__file__), "trader", "state", "system_paper_orders.json")
        import json
        if not os.path.exists(orders_file):
            return jsonify({"success": False, "error": "No orders found"}), 404

        with open(orders_file, "r", encoding="utf-8") as f:
            orders = json.load(f)

        live_prices = bidirectional_system.get_live_prices()
        closed_item = None

        for ord_item in orders:
            if ord_item.get("order_id") == order_id and ord_item.get("status") == "OPEN":
                sym = ord_item.get("symbol")
                entry_p = float(ord_item.get("entry_price", 0))
                direction = str(ord_item.get("direction", "")).upper()
                asset_class = str(ord_item.get("asset_class", "EQUITY"))
                qty = float(ord_item.get("lot_count", 1))

                live_item = live_prices.get(sym, {})
                curr_p = float(live_item.get("price", entry_p))
                is_short = ("SHORT" in direction or "PUT" in direction or "SELL" in direction)

                if "CRYPTO" in asset_class or "USDT" in sym:
                    mult = 0.001 if "BTC" in sym else (0.01 if "ETH" in sym else 0.1)
                    coins = qty * mult
                    pnl = (entry_p - curr_p) * coins if is_short else (curr_p - entry_p) * coins
                else:
                    pnl = (entry_p - curr_p) * qty if is_short else (curr_p - entry_p) * qty

                ord_item["status"] = "CLOSED"
                ord_item["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
                ord_item["exit_price"] = curr_p
                ord_item["realized_pnl"] = round(pnl, 2)
                ord_item["exit_reason"] = data.get("reason", "Manual 1-Click Close")
                closed_item = ord_item
                break

        if not closed_item:
            return jsonify({"success": False, "error": "Open order not found"}), 404

        with open(orders_file, "w", encoding="utf-8") as f:
            json.dump(orders, f, indent=2)

        return jsonify({
            "success": True,
            "message": f"Position closed. Realized P&L: {closed_item['realized_pnl']}",
            "order": closed_item
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/system/flatten", methods=["POST"])
def api_system_flatten():
    """Flattens all open positions immediately at market prices."""
    try:
        orders_file = os.path.join(os.path.dirname(__file__), "trader", "state", "system_paper_orders.json")
        import json
        if not os.path.exists(orders_file):
            return jsonify({"success": True, "closed_count": 0, "message": "No orders"})

        with open(orders_file, "r", encoding="utf-8") as f:
            orders = json.load(f)

        live_prices = bidirectional_system.get_live_prices()
        count = 0

        for ord_item in orders:
            if ord_item.get("status") == "OPEN":
                sym = ord_item.get("symbol")
                entry_p = float(ord_item.get("entry_price", 0))
                direction = str(ord_item.get("direction", "")).upper()
                asset_class = str(ord_item.get("asset_class", "EQUITY"))
                qty = float(ord_item.get("lot_count", 1))

                live_item = live_prices.get(sym, {})
                curr_p = float(live_item.get("price", entry_p))
                is_short = ("SHORT" in direction or "PUT" in direction or "SELL" in direction)

                if "CRYPTO" in asset_class or "USDT" in sym:
                    mult = 0.001 if "BTC" in sym else (0.01 if "ETH" in sym else 0.1)
                    coins = qty * mult
                    pnl = (entry_p - curr_p) * coins if is_short else (curr_p - entry_p) * coins
                else:
                    pnl = (entry_p - curr_p) * qty if is_short else (curr_p - entry_p) * qty

                ord_item["status"] = "CLOSED"
                ord_item["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
                ord_item["exit_price"] = curr_p
                ord_item["realized_pnl"] = round(pnl, 2)
                ord_item["exit_reason"] = "1-Click Flatten All"
                count += 1

        with open(orders_file, "w", encoding="utf-8") as f:
            json.dump(orders, f, indent=2)

        return jsonify({"success": True, "closed_count": count, "message": f"Flattened {count} open positions."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/system/config")
def api_system_config():
    """Returns the trading system YAML configuration."""
    try:
        cfg = load_system_config()
        return jsonify({"success": True, "config": cfg})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = CONFIG["flask_port"]
    debug = CONFIG["flask_debug"]
    print(f">> Starting Trading Terminal on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
