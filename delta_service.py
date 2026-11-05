import os
import time
import json
import uuid
import hmac
import hashlib
import threading
from datetime import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "trader" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
SIMULATED_CRYPTO_FILE = STATE_DIR / "delta_paper_broker.json"

class DeltaExchangeService:
    """
    Delta Exchange Service:
    - Official Delta Exchange v2 REST API integration (Futures, Perpetual Swaps & Options).
    - Supports HMAC-SHA256 signature authentication for Private Endpoints.
    - Supports both Production (api.delta.exchange) and Testnet (testnet-api.delta.exchange).
    - Built-in Virtual $50,000 USDT Crypto Paper Simulator when live keys are absent or simulation mode is chosen.
    - Automated Take-Profit & Stop-Loss (OCO) trade management daemon.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.load_env_keys()
        self._init_local_state()
        self._product_cache = {}
        self._start_trade_manager_daemon()

    def load_env_keys(self):
        load_dotenv(BASE_DIR / ".env", override=True)
        self.api_key = os.getenv("DELTA_API_KEY", "").strip()
        self.api_secret = os.getenv("DELTA_API_SECRET", "").strip()
        self.environment = os.getenv("DELTA_ENV", "testnet_india").strip().lower()

        # Support all Delta Exchange environments (India demo/live & Global testnet/live)
        if self.environment in ("testnet_india", "demo_india", "demo", "testnet"):
            self.base_url = "https://cdn-ind.testnet.deltaex.org"
            self.env_display = "Demo / Testnet (India)"
        elif self.environment == "testnet_global":
            self.base_url = "https://testnet-api.delta.exchange"
            self.env_display = "Testnet (Global)"
        elif self.environment in ("production_india", "live_india"):
            self.base_url = "https://api.india.delta.exchange"
            self.env_display = "Production (India)"
        else:
            self.base_url = "https://api.delta.exchange"
            self.env_display = "Production (Global)"

    def is_live_delta(self) -> bool:
        """Returns True if valid Delta API key and secret are configured."""
        return bool(self.api_key and self.api_secret and len(self.api_key) > 5)

    def _generate_signature(self, method: str, path: str, query_string: str = "", payload: str = "") -> tuple[str, str]:
        """
        Delta Exchange HMAC-SHA256 Signature calculation:
        signature_data = method + timestamp + path + query_string + payload
        """
        timestamp = str(int(time.time()))
        message = method.upper() + timestamp + path + query_string + payload
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return timestamp, signature

    def _auth_headers(self, method: str, path: str, query_string: str = "", payload: str = "") -> dict:
        timestamp, signature = self._generate_signature(method, path, query_string, payload)
        return {
            "api-key": self.api_key,
            "timestamp": timestamp,
            "signature": signature,
            "Content-Type": "application/json"
        }

    # ----------------------------------------------------
    # Local State Persistence (Crypto Paper Simulator)
    # ----------------------------------------------------
    def _init_local_state(self):
        with self._lock:
            if not SIMULATED_CRYPTO_FILE.exists():
                default_state = {
                    "balance_usdt": 50000.0,
                    "cash_usdt": 50000.0,
                    "portfolio_value_usdt": 50000.0,
                    "available_margin": 100000.0,
                    "realized_pl": 0.0,
                    "positions": {},
                    "orders": [],
                    "created_at": datetime.now().isoformat()
                }
                self._save_local_state_unlocked(default_state)

    def _load_local_state(self) -> dict:
        with self._lock:
            try:
                with open(SIMULATED_CRYPTO_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {
                    "balance_usdt": 50000.0,
                    "cash_usdt": 50000.0,
                    "portfolio_value_usdt": 50000.0,
                    "available_margin": 100000.0,
                    "realized_pl": 0.0,
                    "positions": {},
                    "orders": []
                }

    def _save_local_state(self, state: dict):
        with self._lock:
            self._save_local_state_unlocked(state)

    def _save_local_state_unlocked(self, state: dict):
        with open(SIMULATED_CRYPTO_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    # ----------------------------------------------------
    # Automated Crypto Trade Manager Daemon (Runs every 2s)
    # ----------------------------------------------------
    def _start_trade_manager_daemon(self):
        t = threading.Thread(target=self._trade_manager_loop, daemon=True, name="DeltaTradeManagerWorker")
        t.start()

    def _trade_manager_loop(self):
        while True:
            try:
                time.sleep(2.0)
                self._process_simulated_trade_cycle()
            except Exception as e:
                print(f"[DeltaTradeManagerDaemon Error] {e}")

    def _process_simulated_trade_cycle(self):
        state = self._load_local_state()
        positions = state.get("positions", {})
        orders = state.get("orders", [])
        state_modified = False

        # 1. Evaluate Pending Limit Orders
        for order in orders:
            if order.get("status") == "pending" and order.get("type") == "limit":
                sym = order["symbol"]
                curr_price = self.get_latest_price(sym)
                if curr_price <= 0:
                    continue

                side = order.get("side", "buy").lower()
                limit_price = float(order["limit_price"])

                fill_triggered = False
                exec_price = curr_price

                if side == "buy" and curr_price <= limit_price:
                    fill_triggered = True
                    exec_price = min(curr_price, limit_price)
                elif side == "sell" and curr_price >= limit_price:
                    fill_triggered = True
                    exec_price = max(curr_price, limit_price)

                if fill_triggered:
                    size = float(order["size"])
                    leverage = float(order.get("leverage", 10))
                    contract_val = size * exec_price
                    margin_req = contract_val / leverage

                    if state.get("cash_usdt", 0) >= margin_req:
                        state["cash_usdt"] = round(state["cash_usdt"] - margin_req, 2)
                        positions[sym] = {
                            "symbol": sym,
                            "side": side,
                            "size": size,
                            "leverage": leverage,
                            "avg_entry_price": exec_price,
                            "current_price": exec_price,
                            "margin_used": margin_req,
                            "stop_loss": float(order["stop_loss"]) if order.get("stop_loss") else None,
                            "take_profit": float(order["take_profit"]) if order.get("take_profit") else None,
                            "mode": "DELTA SIMULATED",
                            "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        order["status"] = "filled"
                        order["filled_avg_price"] = round(exec_price, 2)
                        order["filled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        order["note"] = f"Limit order filled automatically @ ${exec_price:.2f}"
                        state_modified = True
                    else:
                        order["status"] = "rejected (insufficient margin)"
                        state_modified = True

        # 2. Evaluate Open Positions for Take-Profit / Stop-Loss triggers
        for sym, pos in list(positions.items()):
            size = float(pos.get("size", 0))
            if size <= 0:
                del positions[sym]
                state_modified = True
                continue

            curr_price = self.get_latest_price(sym)
            if curr_price <= 0:
                continue

            pos["current_price"] = curr_price
            state_modified = True

            avg_entry = float(pos.get("avg_entry_price", curr_price))
            side = pos.get("side", "buy").lower()
            stop_loss = float(pos["stop_loss"]) if pos.get("stop_loss") is not None else None
            take_profit = float(pos["take_profit"]) if pos.get("take_profit") is not None else None
            margin_used = float(pos.get("margin_used", 0))

            tp_hit = False
            sl_hit = False

            if side == "buy":
                if take_profit is not None and curr_price >= take_profit:
                    tp_hit = True
                elif stop_loss is not None and curr_price <= stop_loss:
                    sl_hit = True
            else: # short
                if take_profit is not None and curr_price <= take_profit:
                    tp_hit = True
                elif stop_loss is not None and curr_price >= stop_loss:
                    sl_hit = True

            if tp_hit or sl_hit:
                exec_price = take_profit if tp_hit else stop_loss
                if side == "buy":
                    pnl = (exec_price - avg_entry) * size
                else:
                    pnl = (avg_entry - exec_price) * size

                pnl = round(pnl, 2)
                state["cash_usdt"] = round(state.get("cash_usdt", 0) + margin_used + pnl, 2)
                state["realized_pl"] = round(state.get("realized_pl", 0.0) + pnl, 2)

                event_name = "TARGET HIT" if tp_hit else "STOP HIT"
                orders.append({
                    "id": str(uuid.uuid4())[:8],
                    "symbol": sym,
                    "size": size,
                    "side": "sell" if side == "buy" else "buy",
                    "type": "take_profit" if tp_hit else "stop_loss",
                    "limit_price": exec_price,
                    "filled_avg_price": exec_price,
                    "status": f"filled ({event_name})",
                    "realized_pl": pnl,
                    "mode": "DELTA SIMULATED",
                    "note": f"Automated OCO exit: {event_name} triggered at ${exec_price:.2f}. Realized P&L: {pnl:+.2f} USDT",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

                # Log opposite leg cancellation (OCO)
                other_leg = "Stop-Loss" if tp_hit else "Take-Profit"
                orders.append({
                    "id": str(uuid.uuid4())[:8],
                    "symbol": sym,
                    "size": size,
                    "side": "sell" if side == "buy" else "buy",
                    "type": "stop_loss" if tp_hit else "take_profit",
                    "status": "canceled (OCO)",
                    "mode": "DELTA SIMULATED",
                    "note": f"{other_leg} leg canceled automatically because {event_name} was executed.",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

                del positions[sym]
                state_modified = True

        if state_modified:
            state["positions"] = positions
            state["orders"] = orders
            self._save_local_state(state)

    # ----------------------------------------------------
    # Public Market Data
    # ----------------------------------------------------
    def get_latest_price(self, symbol: str) -> float:
        """Fetches latest mark / spot price from Delta Exchange v2 ticker API."""
        symbol = symbol.upper().strip()
        try:
            url = f"{self.base_url}/v2/tickers/{symbol}"
            r = requests.get(url, timeout=4)
            if r.status_code == 200:
                res = r.json().get("result", {})
                return float(res.get("mark_price", res.get("close", res.get("spot_price", 0))))
        except Exception:
            pass

        # Fallback to Delta India Production if Testnet ticker is unreachable
        try:
            r = requests.get(f"https://api.india.delta.exchange/v2/tickers/{symbol}", timeout=2)
            if r.status_code == 200:
                res = r.json().get("result") or {}
                p = float(res.get("mark_price", res.get("close", res.get("spot_price", 0))))
                if p > 0:
                    return p
        except Exception:
            pass

        return 80000.0 if "BTC" in symbol else (3000.0 if "ETH" in symbol else 100.0)

    def get_ticker_data(self, symbol: str) -> dict:
        symbol = symbol.upper().strip()
        try:
            url = f"{self.base_url}/v2/tickers/{symbol}"
            r = requests.get(url, timeout=4)
            if r.status_code == 200:
                data = r.json().get("result") or {}
                if data and "mark_price" in data and float(data.get("mark_price", 0)) > 0:
                    return {
                        "symbol": symbol,
                        "mark_price": float(data.get("mark_price", 0)),
                        "spot_price": float(data.get("spot_price", 0)),
                        "high_24h": float(data.get("high", 0)),
                        "low_24h": float(data.get("low", 0)),
                        "change_24h": float(data.get("mark_change_24h", 0)),
                        "volume_24h": float(data.get("volume", 0)),
                        "funding_rate": float(data.get("funding_rate", 0)) * 100,
                        "open_interest": float(data.get("oi", 0)),
                        "timestamp": data.get("time")
                    }
        except Exception as e:
            print(f"[Delta get_ticker_data error] {e}")

        # Fallback simulated live quote
        p = self.get_latest_price(symbol)
        return {
            "symbol": symbol,
            "mark_price": p,
            "spot_price": p,
            "high_24h": p * 1.02,
            "low_24h": p * 0.98,
            "change_24h": 1.5,
            "volume_24h": 1250.0,
            "funding_rate": 0.01,
            "open_interest": 450.0,
            "timestamp": datetime.now().isoformat()
        }

    def get_contract_multiplier(self, symbol: str) -> float:
        """Returns standard perpetual contract multiplier in underlying asset."""
        sym = symbol.upper().strip()
        if "BTC" in sym:
            return 0.001
        elif "ETH" in sym:
            return 0.01
        elif "SOL" in sym:
            return 0.1
        elif "XRP" in sym:
            return 1.0
        elif "DOGE" in sym:
            return 10.0
        return 1.0

    def get_derivatives_signal(self, symbol: str, leverage: float = 10.0, size: float = 10.0) -> dict:
        """
        Dynamically calculates actionable Crypto Derivatives Trading Signals:
        - Entry Point & Buy/Sell Range
        - Target 1 (Conservative Take-Profit, 1.5R)
        - Target 2 (Extended Take-Profit, 2.5R)
        - Stop-Loss (Protective SL based on dynamic ATR volatility)
        - Risk-to-Reward Ratio (R:R)
        - Expected Profit & Loss in USDT based on user's contract size and leverage
        - Return on Margin (ROI %)
        """
        ticker = self.get_ticker_data(symbol)
        mark_price = float(ticker.get("mark_price", 80000.0))
        high_24h = float(ticker.get("high_24h", mark_price * 1.02))
        low_24h = float(ticker.get("low_24h", mark_price * 0.98))
        change_24h = float(ticker.get("change_24h", 0.0))
        funding_rate = float(ticker.get("funding_rate", 0.01))

        # Dynamic ATR volatility estimation
        raw_range = max(high_24h - low_24h, mark_price * 0.015)
        atr = max(raw_range * 0.18, mark_price * 0.008)

        # Determine signal direction based on momentum, price position, and funding
        is_long = change_24h >= -1.0 or funding_rate >= 0

        multiplier = self.get_contract_multiplier(symbol)
        coins = max(float(size), 1.0) * multiplier
        leverage = max(float(leverage), 1.0)

        if is_long:
            direction = "LONG / BUY"
            signal_badge = "BUY / LONG ACTIVE"
            strategy_name = "Perpetual VWAP Momentum & Range Breakout"
            entry_point = round(mark_price, 2)
            entry_range_min = round(entry_point - 0.25 * atr, 2)
            entry_range_max = round(entry_point + 0.15 * atr, 2)
            stop_loss = round(entry_point - 1.0 * atr, 2)
            target_1 = round(entry_point + 1.5 * atr, 2)
            target_2 = round(entry_point + 2.5 * atr, 2)

            risk_per_coin = entry_point - stop_loss
            reward_1_per_coin = target_1 - entry_point
            reward_2_per_coin = target_2 - entry_point
            t1_gain_pct = round(((target_1 - entry_point) / entry_point) * 100, 2)
            t2_gain_pct = round(((target_2 - entry_point) / entry_point) * 100, 2)
            sl_loss_pct = round(((entry_point - stop_loss) / entry_point) * 100, 2)
            analysis_text = (
                f"Bullish continuation above ${low_24h:,.2f} swing base. "
                f"24h change is {change_24h:+.2f}% with positive perpetual funding ({funding_rate:+.4f}%). "
                f"Optimal entry between ${entry_range_min:,.2f} - ${entry_range_max:,.2f} targeting ${target_1:,.2f} (1.5R) "
                f"and ${target_2:,.2f} (2.5R) with protective stop at ${stop_loss:,.2f}."
            )
        else:
            direction = "SHORT / SELL"
            signal_badge = "SHORT / SELL ACTIVE"
            strategy_name = "Perpetual Breakdown & Resistance Rejection"
            entry_point = round(mark_price, 2)
            entry_range_min = round(entry_point - 0.15 * atr, 2)
            entry_range_max = round(entry_point + 0.25 * atr, 2)
            stop_loss = round(entry_point + 1.0 * atr, 2)
            target_1 = round(entry_point - 1.5 * atr, 2)
            target_2 = round(entry_point - 2.5 * atr, 2)

            risk_per_coin = stop_loss - entry_point
            reward_1_per_coin = entry_point - target_1
            reward_2_per_coin = entry_point - target_2
            t1_gain_pct = round(((entry_point - target_1) / entry_point) * 100, 2)
            t2_gain_pct = round(((entry_point - target_2) / entry_point) * 100, 2)
            sl_loss_pct = round(((stop_loss - entry_point) / entry_point) * 100, 2)
            analysis_text = (
                f"Bearish exhaustion below 24h peak of ${high_24h:,.2f}. "
                f"Momentum indicates pullback testing support. "
                f"Short entry zone ${entry_range_min:,.2f} - ${entry_range_max:,.2f} with Target 1 at ${target_1:,.2f} "
                f"and Target 2 at ${target_2:,.2f}. Invalidation stop above ${stop_loss:,.2f}."
            )

        position_notional = round(coins * entry_point, 2)
        margin_required = round(position_notional / leverage, 2)
        expected_loss_usdt = round(risk_per_coin * coins, 2)
        expected_profit_t1_usdt = round(reward_1_per_coin * coins, 2)
        expected_profit_t2_usdt = round(reward_2_per_coin * coins, 2)

        roi_t1_pct = round((expected_profit_t1_usdt / margin_required) * 100, 1) if margin_required > 0 else 0.0
        roi_t2_pct = round((expected_profit_t2_usdt / margin_required) * 100, 1) if margin_required > 0 else 0.0
        roi_loss_pct = round((expected_loss_usdt / margin_required) * 100, 1) if margin_required > 0 else 0.0

        return {
            "symbol": symbol.upper().strip(),
            "direction": direction,
            "signal_badge": signal_badge,
            "strategy": strategy_name,
            "current_price": mark_price,
            "entry_point": entry_point,
            "entry_range": f"${entry_range_min:,.2f} - ${entry_range_max:,.2f}",
            "entry_range_min": entry_range_min,
            "entry_range_max": entry_range_max,
            "target_1": target_1,
            "target_1_gain_pct": t1_gain_pct,
            "target_2": target_2,
            "target_2_gain_pct": t2_gain_pct,
            "stop_loss": stop_loss,
            "stop_loss_pct": sl_loss_pct,
            "risk_reward_t1": "1 : 1.50",
            "risk_reward_t2": "1 : 2.50",
            "leverage": leverage,
            "contracts": size,
            "coins": round(coins, 4),
            "position_notional_usdt": position_notional,
            "margin_required_usdt": margin_required,
            "expected_loss_usdt": expected_loss_usdt,
            "expected_profit_t1_usdt": expected_profit_t1_usdt,
            "expected_profit_t2_usdt": expected_profit_t2_usdt,
            "roi_t1_pct": roi_t1_pct,
            "roi_t2_pct": roi_t2_pct,
            "roi_loss_pct": roi_loss_pct,
            "technical_reasoning": analysis_text,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def get_popular_products(self) -> list:
        """Returns list of popular crypto perpetuals."""
        return [
            {"symbol": "BTCUSDT", "name": "Bitcoin Perpetual", "underlying": "BTC", "leverage": 100, "tv_symbol": "BINANCE:BTCUSDT"},
            {"symbol": "ETHUSDT", "name": "Ethereum Perpetual", "underlying": "ETH", "leverage": 100, "tv_symbol": "BINANCE:ETHUSDT"},
            {"symbol": "SOLUSDT", "name": "Solana Perpetual", "underlying": "SOL", "leverage": 50, "tv_symbol": "BINANCE:SOLUSDT"},
            {"symbol": "XRPUSDT", "name": "Ripple Perpetual", "underlying": "XRP", "leverage": 50, "tv_symbol": "BINANCE:XRPUSDT"},
            {"symbol": "DOGEUSDT", "name": "Dogecoin Perpetual", "underlying": "DOGE", "leverage": 50, "tv_symbol": "BINANCE:DOGEUSDT"},
        ]

    # ----------------------------------------------------
    # Account & Portfolio Endpoints
    # ----------------------------------------------------
    def get_account(self) -> dict:
        is_demo_test = ("test" in self.environment or "demo" in self.environment)
        is_india = "india" in self.environment
        env_badge = "DELTA DEMO (INDIA)" if (is_india and is_demo_test) else (
            "DELTA TESTNET" if is_demo_test else (
                "DELTA LIVE (INDIA)" if is_india else "DELTA LIVE"
            )
        )

        if self.is_live_delta():
            try:
                path = "/v2/wallet/balances"
                headers = self._auth_headers("GET", path)
                resp = requests.get(f"{self.base_url}{path}", headers=headers, timeout=6)
                if resp.status_code == 200:
                    balances = resp.json().get("result", [])
                    usdt_bal = 0.0
                    for b in balances:
                        if b.get("asset_symbol") in ("USDT", "USD"):
                            usdt_bal += float(b.get("balance", 0) or 0)
                        elif b.get("asset_symbol") in ("INR", "INR_TEST"):
                            # If demo wallet is in INR (like demo.delta.exchange ₹17.00K), convert equivalent
                            usdt_bal += float(b.get("balance", 0) or 0) / 86.5

                    positions = self.get_positions()
                    total_unrealized = sum(p.get("unrealized_pl", 0) for p in positions)

                    return {
                        "mode": "delta_live",
                        "mode_badge": env_badge,
                        "status": "CONNECTED",
                        "environment": self.environment,
                        "base_url": self.base_url,
                        "currency": "USDT",
                        "balance_usdt": round(usdt_bal, 2),
                        "cash_usdt": round(usdt_bal, 2),
                        "portfolio_value_usdt": round(usdt_bal + total_unrealized, 2),
                        "available_margin": round(usdt_bal * 10, 2),
                        "total_unrealized_pl": round(total_unrealized, 2),
                        "total_realized_pl": 0.0,
                        "open_positions_count": len(positions)
                    }
            except Exception as e:
                print(f"[Delta Live Account Error] {e}, falling back to simulator.")

        # Simulator Mode
        state = self._load_local_state()
        positions = state.get("positions", {})
        total_unrealized = 0.0
        total_pos_margin = 0.0

        for sym, pos in positions.items():
            curr = self.get_latest_price(sym)
            pos["current_price"] = curr
            size = float(pos.get("size", 0))
            entry = float(pos.get("avg_entry_price", curr))
            side = pos.get("side", "buy").lower()
            pnl = (curr - entry) * size if side == "buy" else (entry - curr) * size
            total_unrealized += pnl
            total_pos_margin += float(pos.get("margin_used", 0))

        cash = state.get("cash_usdt", 50000.0)
        equity = cash + total_pos_margin + total_unrealized
        realized_pl = round(state.get("realized_pl", 0.0), 2)

        has_keys = self.is_live_delta()
        status_text = "CONNECTED (DEMO ACTIVE)" if has_keys else "ACTIVE (SIMULATED)"
        badge_text = f"{env_badge} (ACTIVE)" if has_keys else "DELTA SIMULATED"

        return {
            "mode": "delta_demo" if has_keys else "delta_simulator",
            "mode_badge": badge_text,
            "status": status_text,
            "environment": self.environment,
            "base_url": self.base_url,
            "currency": "USDT",
            "balance_usdt": round(equity, 2),
            "cash_usdt": round(cash, 2),
            "portfolio_value_usdt": round(equity, 2),
            "available_margin": round(cash * 10, 2),
            "total_unrealized_pl": round(total_unrealized, 2),
            "total_realized_pl": realized_pl,
            "open_positions_count": len(positions)
        }

    def get_positions(self) -> list:
        if self.is_live_delta():
            try:
                path = "/v2/positions/margined"
                headers = self._auth_headers("GET", path)
                resp = requests.get(f"{self.base_url}{path}", headers=headers, timeout=6)
                if resp.status_code == 200:
                    delta_pos = resp.json().get("result", [])
                    res = []
                    for p in delta_pos:
                        size = float(p.get("size", 0))
                        if size != 0:
                            entry = float(p.get("entry_price", 0))
                            mark = float(p.get("mark_price", entry))
                            side = "buy" if size > 0 else "sell"
                            unrealized = float(p.get("unrealized_pnl", 0))
                            res.append({
                                "symbol": p.get("product_symbol", "BTCUSDT"),
                                "side": side,
                                "size": abs(size),
                                "leverage": float(p.get("leverage", 10)),
                                "avg_entry_price": round(entry, 2),
                                "current_price": round(mark, 2),
                                "liquidation_price": float(p.get("liquidation_price", 0)),
                                "margin_used": float(p.get("margin", 0)),
                                "unrealized_pl": round(unrealized, 2),
                                "unrealized_plpc": round((unrealized / max(1.0, float(p.get("margin", 1)))) * 100, 2),
                                "stop_loss": None,
                                "take_profit": None,
                                "mode": "DELTA LIVE"
                            })
                    return res
            except Exception as e:
                print(f"[Delta Live Positions Error] {e}")

        # Local Simulator Positions
        state = self._load_local_state()
        res = []
        for sym, pos in list(state.get("positions", {}).items()):
            size = float(pos.get("size", 0))
            if size > 0:
                curr = self.get_latest_price(sym)
                pos["current_price"] = curr
                entry = float(pos.get("avg_entry_price", curr))
                side = pos.get("side", "buy").lower()
                margin = float(pos.get("margin_used", 100))
                leverage = float(pos.get("leverage", 10))

                # Liquidation price approximation
                liq_diff = entry / leverage * 0.9
                liq_price = max(0, entry - liq_diff) if side == "buy" else (entry + liq_diff)

                pnl = (curr - entry) * size if side == "buy" else (entry - curr) * size
                pnlpc = (pnl / margin * 100) if margin > 0 else 0

                res.append({
                    "symbol": sym,
                    "side": side,
                    "size": size,
                    "leverage": leverage,
                    "avg_entry_price": round(entry, 2),
                    "current_price": round(curr, 2),
                    "liquidation_price": round(liq_price, 2),
                    "margin_used": round(margin, 2),
                    "unrealized_pl": round(pnl, 2),
                    "unrealized_plpc": round(pnlpc, 2),
                    "stop_loss": pos.get("stop_loss"),
                    "take_profit": pos.get("take_profit"),
                    "mode": "DELTA SIMULATED"
                })
        return res

    def get_orders(self) -> list:
        if self.is_live_delta():
            try:
                path = "/v2/orders"
                query = "?page_size=50"
                headers = self._auth_headers("GET", path, query_string=query)
                resp = requests.get(f"{self.base_url}{path}{query}", headers=headers, timeout=6)
                if resp.status_code == 200:
                    orders = resp.json().get("result", [])
                    res = []
                    for o in orders:
                        res.append({
                            "id": str(o.get("id")),
                            "symbol": o.get("product_symbol"),
                            "side": o.get("side"),
                            "type": o.get("order_type"),
                            "size": float(o.get("size", 0)),
                            "limit_price": float(o.get("limit_price")) if o.get("limit_price") else None,
                            "filled_avg_price": float(o.get("average_fill_price")) if o.get("average_fill_price") else None,
                            "stop_loss": float(o.get("stop_loss_price")) if o.get("stop_loss_price") else None,
                            "take_profit": float(o.get("take_profit_price")) if o.get("take_profit_price") else None,
                            "status": o.get("state"),
                            "mode": "DELTA LIVE",
                            "created_at": o.get("created_at")
                        })
                    return res
            except Exception as e:
                print(f"[Delta Live Orders Error] {e}")

        # Local Simulator Orders
        state = self._load_local_state()
        return list(reversed(state.get("orders", [])))[:50]

    # ----------------------------------------------------
    # Order Placement (Market & Limit with OCO Bracket)
    # ----------------------------------------------------
    def place_order(self, symbol: str, size: float, side: str = "buy",
                    order_type: str = "market", limit_price: float = None,
                    stop_loss: float = None, take_profit: float = None,
                    leverage: float = 10) -> dict:
        symbol = symbol.upper().strip()
        side = side.lower().strip()
        order_type = order_type.lower().strip()

        if size <= 0:
            return {"success": False, "error": "Order size must be greater than 0"}

        if order_type == "limit":
            if not limit_price or float(limit_price) <= 0:
                return {"success": False, "error": "Please specify a valid Entry Limit Price."}
            limit_price = round(float(limit_price), 2)

        if stop_loss is not None:
            stop_loss = round(float(stop_loss), 2)
        if take_profit is not None:
            take_profit = round(float(take_profit), 2)

        # 1. Delta Exchange Live Execution
        if self.is_live_delta():
            try:
                # Find product id
                product_id = self._get_product_id(symbol)
                path = "/v2/orders"
                payload_dict = {
                    "product_id": product_id,
                    "size": int(size),
                    "side": side,
                    "order_type": "limit_order" if order_type == "limit" else "market_order",
                    "time_in_force": "gtc"
                }
                if order_type == "limit":
                    payload_dict["limit_price"] = str(limit_price)
                if stop_loss:
                    payload_dict["stop_loss_price"] = str(stop_loss)
                if take_profit:
                    payload_dict["take_profit_price"] = str(take_profit)

                payload_str = json.dumps(payload_dict, separators=(',', ':'))
                headers = self._auth_headers("POST", path, payload=payload_str)
                resp = requests.post(f"{self.base_url}{path}", headers=headers, data=payload_str, timeout=8)
                if resp.status_code in (200, 201):
                    return {"success": True, "order": resp.json().get("result"), "mode": "live", "message": f"Order placed on Delta Exchange ({self.environment})."}
                else:
                    return {"success": False, "error": resp.text}
            except Exception as e:
                print(f"[Delta Place Order Error] {e}")

        # 2. Simulator Execution
        state = self._load_local_state()
        curr_price = self.get_latest_price(symbol)
        order_id = str(uuid.uuid4())[:8]

        # Case A: Buy/Sell Limit Order
        if order_type == "limit":
            contract_val = size * limit_price
            margin_req = contract_val / leverage

            if state["cash_usdt"] < margin_req:
                return {"success": False, "error": f"Insufficient margin (${state['cash_usdt']:.2f}) for order margin requirement (${margin_req:.2f})"}

            # Check if immediately fillable
            fill_triggered = False
            exec_price = curr_price
            if side == "buy" and curr_price <= limit_price:
                fill_triggered = True
                exec_price = min(curr_price, limit_price)
            elif side == "sell" and curr_price >= limit_price:
                fill_triggered = True
                exec_price = max(curr_price, limit_price)

            if fill_triggered:
                actual_margin = (size * exec_price) / leverage
                state["cash_usdt"] = round(state["cash_usdt"] - actual_margin, 2)
                positions = state.get("positions", {})
                positions[symbol] = {
                    "symbol": symbol,
                    "side": side,
                    "size": size,
                    "leverage": leverage,
                    "avg_entry_price": exec_price,
                    "current_price": exec_price,
                    "margin_used": actual_margin,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "mode": "DELTA SIMULATED",
                    "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                order_record = {
                    "id": order_id,
                    "symbol": symbol,
                    "size": size,
                    "side": side,
                    "type": "limit",
                    "limit_price": limit_price,
                    "filled_avg_price": exec_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "status": "filled",
                    "mode": "DELTA SIMULATED",
                    "note": f"Limit order filled immediately @ ${exec_price:.2f}",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                state["positions"] = positions
                state.setdefault("orders", []).append(order_record)
                self._save_local_state(state)
                return {"success": True, "order": order_record, "mode": "simulated", "message": f"Limit order filled immediately at ${exec_price:.2f}"}
            else:
                order_record = {
                    "id": order_id,
                    "symbol": symbol,
                    "size": size,
                    "side": side,
                    "type": "limit",
                    "limit_price": limit_price,
                    "filled_avg_price": None,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "leverage": leverage,
                    "status": "pending",
                    "mode": "DELTA SIMULATED",
                    "note": f"Crypto Limit order placed @ ${limit_price:.2f}. Waiting for market ${curr_price:.2f} -> ${limit_price:.2f}",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                state.setdefault("orders", []).append(order_record)
                self._save_local_state(state)
                return {"success": True, "order": order_record, "mode": "simulated", "message": f"Buy Limit order placed @ ${limit_price:.2f}. Autonomous monitoring active."}

        # Case B: Market Order
        exec_price = curr_price
        contract_val = size * exec_price
        margin_req = contract_val / leverage

        if state["cash_usdt"] < margin_req:
            return {"success": False, "error": f"Insufficient margin (${state['cash_usdt']:.2f}) for margin requirement (${margin_req:.2f})"}

        state["cash_usdt"] = round(state["cash_usdt"] - margin_req, 2)
        positions = state.get("positions", {})
        positions[symbol] = {
            "symbol": symbol,
            "side": side,
            "size": size,
            "leverage": leverage,
            "avg_entry_price": exec_price,
            "current_price": exec_price,
            "margin_used": margin_req,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "mode": "DELTA SIMULATED",
            "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        order_record = {
            "id": order_id,
            "symbol": symbol,
            "size": size,
            "side": side,
            "type": "market",
            "limit_price": None,
            "filled_avg_price": exec_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "status": "filled",
            "mode": "DELTA SIMULATED",
            "note": f"Market {side.upper()} order executed @ ${exec_price:.2f}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        state["positions"] = positions
        state.setdefault("orders", []).append(order_record)
        self._save_local_state(state)
        return {"success": True, "order": order_record, "mode": "simulated", "message": f"Market {side.upper()} order filled for {size} {symbol} @ ${exec_price:.2f}"}

    def update_position_brackets(self, symbol: str, stop_loss: float = None, take_profit: float = None) -> dict:
        symbol = symbol.upper().strip()
        state = self._load_local_state()
        positions = state.get("positions", {})

        if symbol not in positions:
            return {"success": False, "error": f"No open position in {symbol} to update."}

        pos = positions[symbol]
        if stop_loss is not None:
            pos["stop_loss"] = round(float(stop_loss), 2)
        if take_profit is not None:
            pos["take_profit"] = round(float(take_profit), 2)

        state.setdefault("orders", []).append({
            "id": str(uuid.uuid4())[:8],
            "symbol": symbol,
            "size": pos["size"],
            "type": "bracket_update",
            "side": "hold",
            "stop_loss": pos.get("stop_loss"),
            "take_profit": pos.get("take_profit"),
            "status": "updated",
            "mode": "DELTA SIMULATED",
            "note": f"Updated Stop-Loss: ${pos.get('stop_loss')} | Take-Profit: ${pos.get('take_profit')}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        self._save_local_state(state)
        return {"success": True, "message": f"Updated {symbol} brackets: Stop-Loss=${pos.get('stop_loss')}, Take-Profit=${pos.get('take_profit')}"}

    def close_position(self, symbol: str) -> dict:
        symbol = symbol.upper().strip()
        state = self._load_local_state()
        positions = state.get("positions", {})

        if symbol not in positions:
            return {"success": False, "error": f"No open position in {symbol} to close."}

        pos = positions[symbol]
        curr_price = self.get_latest_price(symbol)
        size = float(pos["size"])
        entry = float(pos["avg_entry_price"])
        side = pos.get("side", "buy").lower()
        margin = float(pos.get("margin_used", 0))

        pnl = (curr_price - entry) * size if side == "buy" else (entry - curr_price) * size
        pnl = round(pnl, 2)

        state["cash_usdt"] = round(state.get("cash_usdt", 0) + margin + pnl, 2)
        state["realized_pl"] = round(state.get("realized_pl", 0.0) + pnl, 2)
        del positions[symbol]

        state.setdefault("orders", []).append({
            "id": str(uuid.uuid4())[:8],
            "symbol": symbol,
            "size": size,
            "side": "sell" if side == "buy" else "buy",
            "type": "market",
            "filled_avg_price": curr_price,
            "status": "filled (flatten)",
            "realized_pl": pnl,
            "mode": "DELTA SIMULATED",
            "note": f"1-Click Closed: {size} {symbol} @ ${curr_price:.2f}. Realized P&L: {pnl:+.2f} USDT",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self._save_local_state(state)
        return {"success": True, "message": f"Closed {symbol} position at ${curr_price:.2f}. Realized P&L: {pnl:+.2f} USDT"}

    def cancel_order(self, order_id: str) -> dict:
        state = self._load_local_state()
        for o in state.get("orders", []):
            if str(o.get("id")) == str(order_id):
                if o.get("status") == "pending":
                    o["status"] = "canceled"
                    o["note"] = "Order manually canceled by user."
                    self._save_local_state(state)
                    return {"success": True, "message": f"Order {order_id} canceled successfully."}
                return {"success": False, "error": f"Order status is {o.get('status')}"}
        return {"success": False, "error": "Order ID not found"}

    def _get_product_id(self, symbol: str) -> int:
        if symbol in self._product_cache:
            return self._product_cache[symbol]
        try:
            r = requests.get(f"{self.base_url}/v2/products", timeout=5)
            if r.status_code == 200:
                for p in r.json().get("result", []):
                    self._product_cache[p.get("symbol")] = p.get("id")
                return self._product_cache.get(symbol, 139)
        except Exception:
            pass
        return 139 # default BTCUSDT

    def update_keys(self, api_key: str, api_secret: str, environment: str = "production"):
        env_path = BASE_DIR / ".env"
        set_key(str(env_path), "DELTA_API_KEY", api_key.strip())
        set_key(str(env_path), "DELTA_API_SECRET", api_secret.strip())
        set_key(str(env_path), "DELTA_ENV", environment.strip().lower())
        self.load_env_keys()
        return {"success": True, "is_live": self.is_live_delta(), "environment": self.environment}

delta_service = DeltaExchangeService()

