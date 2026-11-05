import os
import time
import json
import uuid
import threading
from datetime import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "trader" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
SIMULATED_ACCOUNT_FILE = STATE_DIR / "paper_broker.json"

class AlpacaService:
    """
    Complete Automated Order Placement & Trade Management System:
    1. Dual Mode: Official Alpaca Broker API (Paper/Live) or Built-in Paper Broker Simulator.
    2. Buy Limit Orders with custom entry price & quantity (triggers when market reaches specified price or better).
    3. Take-Profit (Target) & Stop-Loss (OCO - One-Cancels-Other) Bracket monitoring.
    4. Automated background trade loop for real-time price monitoring, automatic exit execution,
       profit/loss booking (Realized P&L), and opposite bracket cancellation.
    5. Editing/Modifying SL & TP on active positions anytime without manual intervention.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.load_env_keys()
        self._init_local_state()
        self._start_trade_manager_daemon()

    def load_env_keys(self):
        load_dotenv(BASE_DIR / ".env", override=True)
        self.api_key = os.getenv("ALPACA_API_KEY", "").strip()
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "").strip()
        self.base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets").rstrip("/")

    def is_live_alpaca(self) -> bool:
        """Returns True if valid Alpaca API credentials are configured."""
        return bool(self.api_key and self.secret_key and len(self.api_key) > 5)

    def _alpaca_headers(self):
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json"
        }

    # ----------------------------------------------------
    # Local State Persistence
    # ----------------------------------------------------
    def _init_local_state(self):
        with self._lock:
            if not SIMULATED_ACCOUNT_FILE.exists():
                default_state = {
                    "balance": 100000.0,
                    "cash": 100000.0,
                    "portfolio_value": 100000.0,
                    "buying_power": 200000.0,
                    "realized_pl": 0.0,
                    "positions": {},
                    "orders": [],
                    "created_at": datetime.now().isoformat()
                }
                self._save_local_state_unlocked(default_state)
            else:
                try:
                    with open(SIMULATED_ACCOUNT_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "realized_pl" not in data:
                        data["realized_pl"] = 0.0
                        self._save_local_state_unlocked(data)
                except Exception:
                    pass

    def _load_local_state(self) -> dict:
        with self._lock:
            try:
                with open(SIMULATED_ACCOUNT_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {
                    "balance": 100000.0,
                    "cash": 100000.0,
                    "portfolio_value": 100000.0,
                    "buying_power": 200000.0,
                    "realized_pl": 0.0,
                    "positions": {},
                    "orders": []
                }

    def _save_local_state(self, state: dict):
        with self._lock:
            self._save_local_state_unlocked(state)

    def _save_local_state_unlocked(self, state: dict):
        with open(SIMULATED_ACCOUNT_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    # ----------------------------------------------------
    # Automated Trade Manager Daemon (Runs every 2s)
    # ----------------------------------------------------
    def _start_trade_manager_daemon(self):
        t = threading.Thread(target=self._trade_manager_loop, daemon=True, name="TradeManagerWorker")
        t.start()

    def _trade_manager_loop(self):
        """
        Background autonomous engine:
        - Monitors pending Buy Limit orders and fills them when market <= limit_price.
        - Monitors open positions for Take-Profit & Stop-Loss triggers.
        - Automatically books Realized P&L and cancels the other bracket leg (OCO).
        """
        while True:
            try:
                time.sleep(2.0)
                self._process_simulated_trade_cycle()
            except Exception as e:
                print(f"[TradeManagerDaemon Error] {e}")

    def _process_simulated_trade_cycle(self):
        state = self._load_local_state()
        positions = state.get("positions", {})
        orders = state.get("orders", [])
        state_modified = False

        # 1. Evaluate Pending Limit Orders
        for order in orders:
            if order.get("status") == "pending" and order.get("type") == "limit":
                sym = order["symbol"]
                curr_price = self._get_latest_price(sym)
                if curr_price <= 0:
                    continue

                side = order.get("side", "buy").lower()
                limit_price = float(order["limit_price"])

                # Buy Limit executes when market price is at or below specified limit
                fill_triggered = False
                exec_price = curr_price

                if side == "buy" and curr_price <= limit_price:
                    fill_triggered = True
                    exec_price = min(curr_price, limit_price)
                elif side == "sell" and curr_price >= limit_price:
                    fill_triggered = True
                    exec_price = max(curr_price, limit_price)

                if fill_triggered:
                    qty = float(order["qty"])
                    total_cost = qty * exec_price

                    if side == "buy":
                        if state.get("cash", 0) >= total_cost:
                            state["cash"] = round(state["cash"] - total_cost, 2)
                            # Create or add to open position
                            if sym in positions:
                                prev_qty = positions[sym]["qty"]
                                prev_cost = prev_qty * positions[sym]["avg_entry_price"]
                                new_qty = prev_qty + qty
                                positions[sym]["qty"] = new_qty
                                positions[sym]["avg_entry_price"] = round((prev_cost + total_cost) / new_qty, 2)
                                positions[sym]["current_price"] = exec_price
                                if order.get("stop_loss"): positions[sym]["stop_loss"] = float(order["stop_loss"])
                                if order.get("take_profit"): positions[sym]["take_profit"] = float(order["take_profit"])
                            else:
                                positions[sym] = {
                                    "symbol": sym,
                                    "qty": qty,
                                    "avg_entry_price": exec_price,
                                    "current_price": exec_price,
                                    "stop_loss": float(order["stop_loss"]) if order.get("stop_loss") else None,
                                    "take_profit": float(order["take_profit"]) if order.get("take_profit") else None,
                                    "side": "long",
                                    "mode": "SIMULATED",
                                    "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                }

                            order["status"] = "filled"
                            order["filled_qty"] = qty
                            order["filled_avg_price"] = round(exec_price, 2)
                            order["filled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            order["note"] = f"Limit order filled automatically @ ${exec_price:.2f}"
                            state_modified = True
                        else:
                            order["status"] = "rejected (insufficient cash)"
                            state_modified = True

        # 2. Evaluate Open Positions: Real-time OCO Take-Profit & Stop-Loss triggers
        for sym, pos in list(positions.items()):
            qty = float(pos.get("qty", 0))
            if qty <= 0:
                del positions[sym]
                state_modified = True
                continue

            curr_price = self._get_latest_price(sym)
            if curr_price <= 0:
                continue

            pos["current_price"] = curr_price
            state_modified = True

            avg_entry = float(pos.get("avg_entry_price", curr_price))
            stop_loss = float(pos["stop_loss"]) if pos.get("stop_loss") is not None else None
            take_profit = float(pos["take_profit"]) if pos.get("take_profit") is not None else None

            # Condition A: Take-Profit Target Hit
            if take_profit is not None and curr_price >= take_profit:
                exec_price = take_profit
                proceeds = qty * exec_price
                cost = qty * avg_entry
                realized = round(proceeds - cost, 2)

                state["cash"] = round(state.get("cash", 0) + proceeds, 2)
                state["realized_pl"] = round(state.get("realized_pl", 0.0) + realized, 2)

                # Record exit order (Target Hit)
                exit_order_id = str(uuid.uuid4())[:8]
                orders.append({
                    "id": exit_order_id,
                    "symbol": sym,
                    "qty": qty,
                    "filled_qty": qty,
                    "type": "take_profit",
                    "side": "sell",
                    "limit_price": take_profit,
                    "filled_avg_price": round(exec_price, 2),
                    "status": "filled (TARGET HIT)",
                    "realized_pl": realized,
                    "mode": "SIMULATED",
                    "note": f"Take-Profit triggered automatically at ${exec_price:.2f}. Booked profit: +${realized:.2f}",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

                # Cancel opposite Stop-Loss leg (OCO behavior)
                if stop_loss is not None:
                    orders.append({
                        "id": str(uuid.uuid4())[:8],
                        "symbol": sym,
                        "qty": qty,
                        "filled_qty": 0,
                        "type": "stop_loss",
                        "side": "sell",
                        "limit_price": stop_loss,
                        "filled_avg_price": None,
                        "status": "canceled (OCO)",
                        "mode": "SIMULATED",
                        "note": f"Stop-Loss leg canceled automatically because Target was reached.",
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })

                del positions[sym]
                state_modified = True
                continue

            # Condition B: Stop-Loss Hit
            elif stop_loss is not None and curr_price <= stop_loss:
                exec_price = stop_loss
                proceeds = qty * exec_price
                cost = qty * avg_entry
                realized = round(proceeds - cost, 2)

                state["cash"] = round(state.get("cash", 0) + proceeds, 2)
                state["realized_pl"] = round(state.get("realized_pl", 0.0) + realized, 2)

                # Record exit order (Stop Hit)
                exit_order_id = str(uuid.uuid4())[:8]
                orders.append({
                    "id": exit_order_id,
                    "symbol": sym,
                    "qty": qty,
                    "filled_qty": qty,
                    "type": "stop_loss",
                    "side": "sell",
                    "limit_price": stop_loss,
                    "filled_avg_price": round(exec_price, 2),
                    "status": "filled (STOP HIT)",
                    "realized_pl": realized,
                    "mode": "SIMULATED",
                    "note": f"Stop-Loss triggered automatically at ${exec_price:.2f}. Booked loss: ${realized:.2f}",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

                # Cancel opposite Take-Profit leg (OCO behavior)
                if take_profit is not None:
                    orders.append({
                        "id": str(uuid.uuid4())[:8],
                        "symbol": sym,
                        "qty": qty,
                        "filled_qty": 0,
                        "type": "take_profit",
                        "side": "sell",
                        "limit_price": take_profit,
                        "filled_avg_price": None,
                        "status": "canceled (OCO)",
                        "mode": "SIMULATED",
                        "note": f"Take-Profit leg canceled automatically because Stop-Loss was triggered.",
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })

                del positions[sym]
                state_modified = True
                continue

        if state_modified:
            state["positions"] = positions
            state["orders"] = orders
            self._save_local_state(state)

    # ----------------------------------------------------
    # Account & Portfolio Endpoints
    # ----------------------------------------------------
    def get_account(self) -> dict:
        if self.is_live_alpaca():
            try:
                resp = requests.get(f"{self.base_url}/v2/account", headers=self._alpaca_headers(), timeout=6)
                if resp.status_code == 200:
                    data = resp.json()
                    equity = float(data.get("equity", 0))
                    cash = float(data.get("cash", 0))
                    # Fetch alpaca positions to compute total unrealized pl
                    positions = self.get_positions()
                    total_unrealized = sum(p.get("unrealized_pl", 0) for p in positions)

                    return {
                        "mode": "alpaca_live_paper",
                        "mode_badge": "ALPACA PAPER",
                        "status": data.get("status", "ACTIVE"),
                        "currency": "USD",
                        "cash": round(cash, 2),
                        "portfolio_value": round(equity, 2),
                        "equity": round(equity, 2),
                        "buying_power": float(data.get("buying_power", 0)),
                        "total_unrealized_pl": round(total_unrealized, 2),
                        "total_realized_pl": 0.0,
                        "daytrade_count": int(data.get("daytrade_count", 0)),
                        "pattern_day_trader": bool(data.get("pattern_day_trader", False)),
                        "open_positions_count": len(positions)
                    }
            except Exception as e:
                print(f"[Alpaca API Error] {e}, falling back to simulator.")

        # Local Simulator Mode
        state = self._load_local_state()
        positions = state.get("positions", {})
        total_pos_value = 0.0
        total_unrealized = 0.0

        for sym, pos in positions.items():
            qty = pos.get("qty", 0)
            curr = pos.get("current_price", pos.get("avg_entry_price", 0))
            entry = pos.get("avg_entry_price", 0)
            mkt = qty * curr
            total_pos_value += mkt
            total_unrealized += (mkt - (qty * entry))

        cash = state.get("cash", 100000.0)
        equity = cash + total_pos_value
        realized_pl = round(state.get("realized_pl", 0.0), 2)

        return {
            "mode": "paper_simulator",
            "mode_badge": "SIMULATED",
            "status": "ACTIVE (SIMULATED)",
            "currency": "USD",
            "cash": round(cash, 2),
            "portfolio_value": round(equity, 2),
            "equity": round(equity, 2),
            "buying_power": round(cash * 2, 2),
            "total_unrealized_pl": round(total_unrealized, 2),
            "total_realized_pl": realized_pl,
            "daytrade_count": 0,
            "pattern_day_trader": False,
            "open_positions_count": len(positions)
        }

    def get_positions(self) -> list:
        if self.is_live_alpaca():
            try:
                resp = requests.get(f"{self.base_url}/v2/positions", headers=self._alpaca_headers(), timeout=6)
                if resp.status_code == 200:
                    alpaca_pos = resp.json()
                    # Also fetch open & held orders to match child bracket legs
                    orders_resp = requests.get(f"{self.base_url}/v2/orders?status=all&limit=100", headers=self._alpaca_headers(), timeout=6)
                    open_orders = orders_resp.json() if orders_resp.status_code == 200 else []

                    res = []
                    for p in alpaca_pos:
                        sym = p.get("symbol")
                        # Find open/held stop or limit child order for this symbol
                        stop_val = None
                        target_val = None
                        for o in open_orders:
                            if o.get("symbol") == sym and o.get("side") == "sell" and o.get("status") in ("new", "held", "open", "accepted"):
                                if o.get("type") in ("stop", "stop_limit") and o.get("stop_price"):
                                    stop_val = float(o["stop_price"])
                                if o.get("type") == "limit" and o.get("limit_price"):
                                    target_val = float(o["limit_price"])

                        res.append({
                            "symbol": sym,
                            "qty": float(p.get("qty", 0)),
                            "avg_entry_price": float(p.get("avg_entry_price", 0)),
                            "current_price": float(p.get("current_price", 0)),
                            "market_value": float(p.get("market_value", 0)),
                            "cost_basis": float(p.get("cost_basis", 0)),
                            "unrealized_pl": float(p.get("unrealized_pl", 0)),
                            "unrealized_plpc": float(p.get("unrealized_plpc", 0)) * 100,
                            "side": p.get("side", "long"),
                            "stop_loss": stop_val,
                            "take_profit": target_val,
                            "mode": "ALPACA PAPER"
                        })
                    return res
            except Exception as e:
                print(f"[Alpaca Positions Error] {e}")

        # Local Simulator Positions
        state = self._load_local_state()
        res = []
        state_modified = False

        for sym, pos in list(state.get("positions", {}).items()):
            if pos.get("qty", 0) > 0:
                live_price = self._get_latest_price(sym)
                if live_price > 0:
                    pos["current_price"] = live_price
                    state_modified = True

                curr = pos.get("current_price", pos["avg_entry_price"])
                cost = pos["qty"] * pos["avg_entry_price"]
                market_val = pos["qty"] * curr
                pl = market_val - cost
                plpc = (pl / cost * 100) if cost > 0 else 0

                res.append({
                    "symbol": sym,
                    "qty": pos["qty"],
                    "avg_entry_price": round(pos["avg_entry_price"], 2),
                    "current_price": round(curr, 2),
                    "market_value": round(market_val, 2),
                    "cost_basis": round(cost, 2),
                    "unrealized_pl": round(pl, 2),
                    "unrealized_plpc": round(plpc, 2),
                    "side": pos.get("side", "long"),
                    "stop_loss": pos.get("stop_loss"),
                    "take_profit": pos.get("take_profit"),
                    "mode": "SIMULATED"
                })

        if state_modified:
            self._save_local_state(state)

        return res

    def get_orders(self) -> list:
        if self.is_live_alpaca():
            try:
                resp = requests.get(f"{self.base_url}/v2/orders?nested=true&status=all&limit=50", headers=self._alpaca_headers(), timeout=6)
                if resp.status_code == 200:
                    orders = resp.json()
                    res = []
                    for o in orders:
                        stop_val = float(o.get("stop_price")) if o.get("stop_price") else None
                        target_val = float(o.get("limit_price")) if (o.get("type") == "limit" and o.get("side") == "sell") else None

                        # Check nested legs for bracket parent orders
                        if o.get("legs"):
                            for leg in o["legs"]:
                                if leg.get("stop_price"):
                                    stop_val = float(leg["stop_price"])
                                if leg.get("limit_price") and leg.get("side") == "sell":
                                    target_val = float(leg["limit_price"])

                        res.append({
                            "id": o.get("id"),
                            "symbol": o.get("symbol"),
                            "qty": float(o.get("qty", 0)),
                            "filled_qty": float(o.get("filled_qty", 0)),
                            "type": o.get("type"),
                            "side": o.get("side"),
                            "time_in_force": o.get("time_in_force"),
                            "limit_price": float(o.get("limit_price")) if o.get("limit_price") else None,
                            "stop_loss": stop_val,
                            "take_profit": target_val,
                            "filled_avg_price": float(o.get("filled_avg_price")) if o.get("filled_avg_price") else None,
                            "status": o.get("status"),
                            "mode": "ALPACA PAPER",
                            "note": f"Alpaca {o.get('order_class', 'bracket')} order",
                            "created_at": o.get("created_at")
                        })
                    return res
            except Exception as e:
                print(f"[Alpaca Orders Error] {e}")

        # Local Simulator Orders
        state = self._load_local_state()
        return list(reversed(state.get("orders", [])))[:60]

    # ----------------------------------------------------
    # Automated Order Placement (Market & Buy Limit Orders)
    # ----------------------------------------------------
    def place_order(self, symbol: str, qty: float, side: str = "buy",
                    order_type: str = "market", limit_price: float = None,
                    stop_loss: float = None, take_profit: float = None,
                    time_in_force: str = "day") -> dict:
        symbol = symbol.upper().strip()
        side = side.lower().strip()
        order_type = order_type.lower().strip()

        if qty <= 0:
            return {"success": False, "error": "Order quantity must be greater than 0"}

        # Validate Limit Orders
        if order_type == "limit":
            if limit_price is None or float(limit_price) <= 0:
                return {"success": False, "error": "Please specify a valid Entry Limit Price for Limit Orders."}
            limit_price = round(float(limit_price), 2)

        if stop_loss is not None:
            stop_loss = round(float(stop_loss), 2)
        if take_profit is not None:
            take_profit = round(float(take_profit), 2)

        # 1. Live Alpaca Broker API Execution
        if self.is_live_alpaca():
            try:
                base_price = float(limit_price) if (order_type == "limit" and limit_price) else self._get_latest_price(symbol)
                if base_price <= 0: base_price = 100.0

                # Validate and adjust bracket bounds strictly adhering to Alpaca rules
                if side == "buy":
                    if stop_loss is not None and stop_loss >= (base_price - 0.01):
                        stop_loss = round(base_price - max(0.50, base_price * 0.015), 2)
                    if take_profit is not None and take_profit <= (base_price + 0.01):
                        take_profit = round(base_price + max(1.00, base_price * 0.03), 2)
                elif side == "sell":
                    if stop_loss is not None and stop_loss <= (base_price + 0.01):
                        stop_loss = round(base_price + max(0.50, base_price * 0.015), 2)
                    if take_profit is not None and take_profit >= (base_price - 0.01):
                        take_profit = round(base_price - max(1.00, base_price * 0.03), 2)

                payload = {
                    "symbol": symbol,
                    "qty": str(qty),
                    "side": side,
                    "type": order_type,
                    "time_in_force": time_in_force
                }
                if order_type == "limit" and limit_price:
                    payload["limit_price"] = str(limit_price)

                if stop_loss or take_profit:
                    payload["order_class"] = "bracket"
                    if take_profit:
                        payload["take_profit"] = {"limit_price": str(take_profit)}
                    if stop_loss:
                        payload["stop_loss"] = {"stop_price": str(stop_loss)}

                resp = requests.post(f"{self.base_url}/v2/orders", headers=self._alpaca_headers(), json=payload, timeout=8)
                if resp.status_code in (200, 201):
                    return {"success": True, "order": resp.json(), "mode": "alpaca", "message": f"Order submitted to Alpaca Broker."}
                else:
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("message", resp.text)
                    except Exception:
                        err_msg = resp.text
                    return {"success": False, "error": err_msg, "mode": "alpaca"}
            except Exception as e:
                print(f"[Alpaca Place Order Error] {e}")

        # 2. Local Paper Simulator Execution
        state = self._load_local_state()
        curr_price = self._get_latest_price(symbol)
        if curr_price <= 0:
            curr_price = 100.0

        order_id = str(uuid.uuid4())[:8]

        # Case A: Buy Limit Order
        if order_type == "limit" and side == "buy":
            total_cost = qty * limit_price
            if state["cash"] < total_cost:
                return {"success": False, "error": f"Insufficient cash ($ {state['cash']:.2f}) for Limit Order cost ($ {total_cost:.2f})"}

            # Check if market already satisfies limit order immediately
            if curr_price <= limit_price:
                exec_price = min(curr_price, limit_price)
                actual_cost = qty * exec_price
                state["cash"] = round(state["cash"] - actual_cost, 2)

                positions = state.get("positions", {})
                if symbol in positions:
                    prev_qty = positions[symbol]["qty"]
                    prev_cost = prev_qty * positions[symbol]["avg_entry_price"]
                    new_qty = prev_qty + qty
                    positions[symbol]["qty"] = new_qty
                    positions[symbol]["avg_entry_price"] = round((prev_cost + actual_cost) / new_qty, 2)
                    positions[symbol]["current_price"] = exec_price
                    if stop_loss: positions[symbol]["stop_loss"] = stop_loss
                    if take_profit: positions[symbol]["take_profit"] = take_profit
                else:
                    positions[symbol] = {
                        "symbol": symbol,
                        "qty": qty,
                        "avg_entry_price": exec_price,
                        "current_price": exec_price,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "side": "long",
                        "mode": "SIMULATED",
                        "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                order_record = {
                    "id": order_id,
                    "symbol": symbol,
                    "qty": qty,
                    "filled_qty": qty,
                    "type": "limit",
                    "side": "buy",
                    "limit_price": limit_price,
                    "filled_avg_price": round(exec_price, 2),
                    "status": "filled",
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "mode": "SIMULATED",
                    "note": f"Limit order filled immediately @ ${exec_price:.2f} (market was below limit)",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                state["positions"] = positions
                state.setdefault("orders", []).append(order_record)
                self._save_local_state(state)
                return {"success": True, "order": order_record, "mode": "simulated", "message": f"Buy Limit filled immediately at ${exec_price:.2f}."}

            else:
                # Order stays PENDING until market drops to limit_price
                order_record = {
                    "id": order_id,
                    "symbol": symbol,
                    "qty": qty,
                    "filled_qty": 0,
                    "type": "limit",
                    "side": "buy",
                    "limit_price": limit_price,
                    "filled_avg_price": None,
                    "status": "pending",
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "mode": "SIMULATED",
                    "note": f"Buy Limit placed @ ${limit_price:.2f}. Waiting for market ${curr_price:.2f} -> ${limit_price:.2f}",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                state.setdefault("orders", []).append(order_record)
                self._save_local_state(state)
                return {
                    "success": True,
                    "order": order_record,
                    "mode": "simulated",
                    "message": f"Buy Limit order placed at ${limit_price:.2f}. Auto-monitoring activated."
                }

        # Case B: Market Order Execution
        exec_price = curr_price
        total_cost = qty * exec_price
        positions = state.get("positions", {})

        if side == "buy":
            if state["cash"] < total_cost:
                return {"success": False, "error": f"Insufficient cash ($ {state['cash']:.2f}) for order cost ($ {total_cost:.2f})"}
            state["cash"] = round(state["cash"] - total_cost, 2)

            if symbol in positions:
                prev_qty = positions[symbol]["qty"]
                prev_cost = prev_qty * positions[symbol]["avg_entry_price"]
                new_qty = prev_qty + qty
                positions[symbol]["qty"] = new_qty
                positions[symbol]["avg_entry_price"] = round((prev_cost + total_cost) / new_qty, 2)
                positions[symbol]["current_price"] = exec_price
                if stop_loss: positions[symbol]["stop_loss"] = stop_loss
                if take_profit: positions[symbol]["take_profit"] = take_profit
            else:
                positions[symbol] = {
                    "symbol": symbol,
                    "qty": qty,
                    "avg_entry_price": exec_price,
                    "current_price": exec_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "side": "long",
                    "mode": "SIMULATED",
                    "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
        elif side == "sell":
            if symbol not in positions or positions[symbol]["qty"] < qty:
                return {"success": False, "error": f"Cannot sell {qty} shares of {symbol}: only {positions.get(symbol, {}).get('qty', 0)} shares owned."}

            cost = qty * positions[symbol]["avg_entry_price"]
            realized = round(total_cost - cost, 2)
            state["cash"] = round(state["cash"] + total_cost, 2)
            state["realized_pl"] = round(state.get("realized_pl", 0.0) + realized, 2)

            positions[symbol]["qty"] -= qty
            positions[symbol]["current_price"] = exec_price
            if positions[symbol]["qty"] <= 0:
                del positions[symbol]

        order_record = {
            "id": order_id,
            "symbol": symbol,
            "qty": qty,
            "filled_qty": qty,
            "type": order_type,
            "side": side,
            "limit_price": limit_price,
            "filled_avg_price": round(exec_price, 2),
            "status": "filled",
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "mode": "SIMULATED",
            "note": "Market order executed immediately.",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        state["positions"] = positions
        state.setdefault("orders", []).append(order_record)
        self._save_local_state(state)

        return {"success": True, "order": order_record, "mode": "simulated", "message": f"Market {side.upper()} order executed for {qty} {symbol} @ ${exec_price:.2f}"}

    # ----------------------------------------------------
    # Position Bracket Modification (Update SL & TP on Active Positions)
    # ----------------------------------------------------
    def update_position_brackets(self, symbol: str, stop_loss: float = None, take_profit: float = None) -> dict:
        symbol = symbol.upper().strip()

        if self.is_live_alpaca():
            # In Alpaca, cancel open/held stop/limit child orders and replace them with native OCO bracket
            try:
                orders_resp = requests.get(f"{self.base_url}/v2/orders?status=all&limit=100", headers=self._alpaca_headers(), timeout=6)
                if orders_resp.status_code == 200:
                    for o in orders_resp.json():
                        if o.get("symbol") == symbol and o.get("side") == "sell" and o.get("status") in ("new", "held", "open", "accepted"):
                            requests.delete(f"{self.base_url}/v2/orders/{o['id']}", headers=self._alpaca_headers(), timeout=4)

                # Fetch position to know quantity
                pos_resp = requests.get(f"{self.base_url}/v2/positions/{symbol}", headers=self._alpaca_headers(), timeout=6)
                if pos_resp.status_code == 200:
                    pos = pos_resp.json()
                    qty = pos.get("qty")
                    if stop_loss and take_profit:
                        # Native OCO bracket order
                        requests.post(f"{self.base_url}/v2/orders", headers=self._alpaca_headers(), json={
                            "symbol": symbol,
                            "qty": qty,
                            "side": "sell",
                            "type": "limit",
                            "time_in_force": "gtc",
                            "order_class": "oco",
                            "take_profit": {"limit_price": str(round(float(take_profit), 2))},
                            "stop_loss": {"stop_price": str(round(float(stop_loss), 2))}
                        }, timeout=6)
                    elif stop_loss:
                        requests.post(f"{self.base_url}/v2/orders", headers=self._alpaca_headers(), json={
                            "symbol": symbol, "qty": qty, "side": "sell", "type": "stop", "time_in_force": "gtc",
                            "stop_price": str(round(float(stop_loss), 2))
                        }, timeout=6)
                    elif take_profit:
                        requests.post(f"{self.base_url}/v2/orders", headers=self._alpaca_headers(), json={
                            "symbol": symbol, "qty": qty, "side": "sell", "type": "limit", "time_in_force": "gtc",
                            "limit_price": str(round(float(take_profit), 2))
                        }, timeout=6)
                    return {"success": True, "message": f"Updated Alpaca bracket orders for {symbol}."}
            except Exception as e:
                return {"success": False, "error": f"Alpaca bracket update error: {e}"}

        # Simulator Mode
        state = self._load_local_state()
        positions = state.get("positions", {})
        if symbol not in positions:
            return {"success": False, "error": f"No open position in {symbol} to update."}

        pos = positions[symbol]
        if stop_loss is not None:
            pos["stop_loss"] = round(float(stop_loss), 2)
        if take_profit is not None:
            pos["take_profit"] = round(float(take_profit), 2)

        # Log adjustment order
        state.setdefault("orders", []).append({
            "id": str(uuid.uuid4())[:8],
            "symbol": symbol,
            "qty": pos["qty"],
            "filled_qty": 0,
            "type": "bracket_update",
            "side": "hold",
            "stop_loss": pos["stop_loss"],
            "take_profit": pos["take_profit"],
            "status": "updated",
            "mode": "SIMULATED",
            "note": f"Updated Stop-Loss to ${pos['stop_loss']} and Take-Profit to ${pos['take_profit']}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        self._save_local_state(state)
        return {
            "success": True,
            "message": f"Updated {symbol} brackets: Stop-Loss = ${pos.get('stop_loss')}, Take-Profit = ${pos.get('take_profit')}"
        }

    # ----------------------------------------------------
    # Position Flattening & Order Cancellation
    # ----------------------------------------------------
    def flatten_position(self, symbol: str) -> dict:
        symbol = symbol.upper().strip()
        if self.is_live_alpaca():
            try:
                resp = requests.delete(f"{self.base_url}/v2/positions/{symbol}", headers=self._alpaca_headers(), timeout=6)
                if resp.status_code in (200, 204):
                    return {"success": True, "message": f"Closed position in {symbol} via Alpaca"}
                elif resp.status_code == 404:
                    return {"success": False, "error": f"No open position in {symbol} to flatten. Place a trade first!"}
                else:
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("message", resp.text)
                    except Exception:
                        err_msg = resp.text
                    return {"success": False, "error": err_msg}
            except Exception as e:
                return {"success": False, "error": str(e)}

        # Local simulator flatten
        state = self._load_local_state()
        positions = state.get("positions", {})
        if symbol not in positions or positions[symbol]["qty"] <= 0:
            return {"success": False, "error": f"No open position in {symbol} to flatten."}

        qty = positions[symbol]["qty"]
        price = self._get_latest_price(symbol)
        cost = qty * positions[symbol]["avg_entry_price"]
        proceeds = qty * price
        realized = round(proceeds - cost, 2)

        state["cash"] = round(state.get("cash", 0) + proceeds, 2)
        state["realized_pl"] = round(state.get("realized_pl", 0.0) + realized, 2)
        del positions[symbol]

        state.setdefault("orders", []).append({
            "id": str(uuid.uuid4())[:8],
            "symbol": symbol,
            "qty": qty,
            "filled_qty": qty,
            "type": "market",
            "side": "sell",
            "filled_avg_price": round(price, 2),
            "status": "filled (flatten)",
            "realized_pl": realized,
            "mode": "SIMULATED",
            "note": f"Manual flatten: closed {qty} shares @ ${price:.2f}. Realized P&L: {realized:+.2f}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self._save_local_state(state)
        return {"success": True, "message": f"Flattened {qty} shares of {symbol} at ${price:.2f} (P&L: {realized:+.2f})"}

    def cancel_order(self, order_id: str) -> dict:
        if self.is_live_alpaca():
            try:
                resp = requests.delete(f"{self.base_url}/v2/orders/{order_id}", headers=self._alpaca_headers(), timeout=6)
                return {"success": resp.status_code in (200, 204)}
            except Exception as e:
                return {"success": False, "error": str(e)}

        state = self._load_local_state()
        for o in state.get("orders", []):
            if o.get("id") == order_id:
                if o.get("status") == "pending":
                    o["status"] = "canceled"
                    o["note"] = "Order manually canceled by user."
                    self._save_local_state(state)
                    return {"success": True, "message": f"Order {order_id} canceled successfully."}
                else:
                    return {"success": False, "error": f"Cannot cancel order: current status is '{o.get('status')}'"}
        return {"success": False, "error": "Order ID not found"}

    def _get_latest_price(self, symbol: str) -> float:
        """Fetches latest quote price for symbol from Yahoo spark/chart endpoint."""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=5m&range=1d"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                meta = r.json()["chart"]["result"][0]["meta"]
                return float(meta.get("regularMarketPrice", meta.get("chartPreviousClose", 100.0)))
        except Exception:
            pass
        return 100.0

    def update_keys(self, api_key: str, secret_key: str):
        """Saves new Alpaca keys to .env and updates runtime instance."""
        env_path = BASE_DIR / ".env"
        set_key(str(env_path), "ALPACA_API_KEY", api_key.strip())
        set_key(str(env_path), "ALPACA_SECRET_KEY", secret_key.strip())
        self.load_env_keys()
        return {"success": True, "is_live": self.is_live_alpaca()}

alpaca_service = AlpacaService()
