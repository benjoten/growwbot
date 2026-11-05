import json
import math
import datetime
from pathlib import Path
from skills_engine import skills_engine

class BacktestEngine:
    """
    Simulates historical execution of day-trader skills over 60 days of 5-minute bars.
    Calculates:
    - Win Rate (%)
    - Total Profit/Loss (%)
    - Average P/L per trade (%)
    - Profit Factor
    - Maximum Drawdown (%)
    - Sharpe Ratio (annualized)
    - Cumulative Equity Curve time series
    """

    def run_backtest(self, symbol: str, active_skills: list,
                     stop_rule: str = "or-mid", target_rule: str = "2R",
                     initial_capital: float = 10000.0, risk_per_trade_usd: float = 100.0) -> dict:
        symbol = symbol.upper().strip()

        # Fetch 60-day 5-minute bars from Yahoo
        try:
            chart = skills_engine.fetch_yahoo_chart(symbol, interval="5m", range_str="60d")
        except Exception as e:
            return {"success": False, "error": f"Failed to fetch historical data for backtest: {e}"}

        timestamps = chart.get("timestamp", [])
        quote = chart.get("indicators", {}).get("quote", [{}])[0]
        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])

        # Filter out nulls and group by date
        valid_bars = []
        for i in range(len(timestamps)):
            if (i < len(opens) and opens[i] is not None and
                i < len(highs) and highs[i] is not None and
                i < len(lows) and lows[i] is not None and
                i < len(closes) and closes[i] is not None):
                dt = datetime.datetime.fromtimestamp(timestamps[i])
                valid_bars.append({
                    "dt": dt,
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M"),
                    "open": float(opens[i]),
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "close": float(closes[i])
                })

        if len(valid_bars) < 78:
            return {"success": False, "error": "Insufficient historical bars to run backtest."}

        # Group bars into individual daily trading sessions
        sessions = {}
        for b in valid_bars:
            d = b["date"]
            sessions.setdefault(d, []).append(b)

        # Strategy parameters
        target_r = 2.0
        if target_rule == "1R": target_r = 1.0
        elif target_rule == "1.5R": target_r = 1.5
        elif target_rule == "2R": target_r = 2.0
        elif target_rule == "3R": target_r = 3.0

        trades = []
        equity = initial_capital
        equity_curve = [{"date": "Start", "equity": round(equity, 2), "pnl_pct": 0.0}]

        sorted_dates = sorted(sessions.keys())

        for d in sorted_dates:
            day_bars = sessions[d]
            if len(day_bars) < 10:
                continue

            # 1. Opening Range (first 3 5m bars: 15 minutes)
            or_bars = day_bars[:3]
            or_high = max(b["high"] for b in or_bars)
            or_low = min(b["low"] for b in or_bars)
            or_mid = (or_high + or_low) / 2.0

            # 2. Check for entry trigger among subsequent bars
            in_trade = False
            entry_price = 0.0
            stop_price = 0.0
            target_price = 0.0
            entry_time = ""
            entry_idx = 0

            for idx, bar in enumerate(day_bars[3:], start=3):
                # Trigger condition: 5m bar CLOSES above range high
                if bar["close"] > or_high:
                    in_trade = True
                    entry_price = bar["close"]
                    entry_time = bar["time"]
                    entry_idx = idx

                    # Compute stop
                    if stop_rule == "or-mid":
                        stop_price = or_mid
                    elif stop_rule == "or-low":
                        stop_price = or_low
                    elif stop_rule.startswith("pct"):
                        pct = 2.0
                        try:
                            if ":" in stop_rule: pct = float(stop_rule.split(":")[1])
                        except ValueError: pass
                        stop_price = entry_price * (1.0 - (pct / 100.0))
                    else:
                        stop_price = or_mid

                    # Sanity check
                    if stop_price >= entry_price:
                        stop_price = entry_price * 0.985

                    risk_share = entry_price - stop_price
                    target_price = entry_price + (risk_share * target_r)
                    break

            if not in_trade:
                continue

            # 3. Simulate trade resolution through remaining session bars
            exit_price = entry_price
            exit_time = "15:55"
            outcome = "TIME_EXIT"

            for bar in day_bars[entry_idx+1:]:
                # Check stop first (conservative assumption)
                if bar["low"] <= stop_price:
                    exit_price = stop_price
                    exit_time = bar["time"]
                    outcome = "LOSS"
                    break
                elif bar["high"] >= target_price:
                    exit_price = target_price
                    exit_time = bar["time"]
                    outcome = "WIN"
                    break
            else:
                # Flat by market close
                exit_price = day_bars[-1]["close"]
                exit_time = day_bars[-1]["time"]
                outcome = "WIN" if exit_price > entry_price else "LOSS"

            # Sizing & PnL
            risk_share = max(0.1, entry_price - stop_price)
            shares = max(1, math.floor(risk_per_trade_usd / risk_share))
            pnl_dollars = round(shares * (exit_price - entry_price), 2)
            pnl_pct = round(((exit_price - entry_price) / entry_price) * 100, 2)
            r_multiple = round((exit_price - entry_price) / risk_share, 2)

            equity += pnl_dollars

            trades.append({
                "date": d,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_price": round(entry_price, 2),
                "stop_price": round(stop_price, 2),
                "target_price": round(target_price, 2),
                "exit_price": round(exit_price, 2),
                "shares": shares,
                "outcome": outcome,
                "pnl_dollars": pnl_dollars,
                "pnl_pct": pnl_pct,
                "r_multiple": r_multiple,
                "equity_after": round(equity, 2)
            })

            equity_curve.append({
                "date": d,
                "equity": round(equity, 2),
                "pnl_pct": round(((equity - initial_capital) / initial_capital) * 100, 2)
            })

        # Calculate performance statistics
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "success": True,
                "total_trades": 0,
                "win_rate": 0.0,
                "total_return_pct": 0.0,
                "avg_trade_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "profit_factor": 0.0,
                "equity_curve": equity_curve,
                "trades": []
            }

        wins = [t for t in trades if t["pnl_dollars"] > 0]
        losses = [t for t in trades if t["pnl_dollars"] < 0]
        win_rate = round((len(wins) / total_trades) * 100, 1)

        total_return_pct = round(((equity - initial_capital) / initial_capital) * 100, 2)
        avg_trade_pct = round(sum(t["pnl_pct"] for t in trades) / total_trades, 2)

        gross_profit = sum(t["pnl_dollars"] for t in wins)
        gross_loss = abs(sum(t["pnl_dollars"] for t in losses))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 1.0)

        # Max Drawdown calculation
        peak = initial_capital
        max_dd_dollars = 0.0
        max_dd_pct = 0.0

        for pt in equity_curve:
            eq = pt["equity"]
            if eq > peak:
                peak = eq
            dd = peak - eq
            dd_pct = (dd / peak) * 100 if peak > 0 else 0.0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                max_dd_dollars = dd

        # Annualized Sharpe Ratio calculation
        returns_list = [t["pnl_pct"] / 100.0 for t in trades]
        mean_ret = sum(returns_list) / len(returns_list)
        var = sum((r - mean_ret)**2 for r in returns_list) / len(returns_list) if len(returns_list) > 1 else 0.0001
        std_ret = math.sqrt(var)
        # Annualized assuming ~250 trading days per year
        sharpe = round((mean_ret / std_ret) * math.sqrt(250), 2) if std_ret > 0 else 0.0

        return {
            "success": True,
            "symbol": symbol,
            "period": "Past 60 Trading Days",
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": win_rate,
            "total_return_pct": total_return_pct,
            "total_profit_dollars": round(equity - initial_capital, 2),
            "avg_trade_pct": avg_trade_pct,
            "profit_factor": profit_factor,
            "max_drawdown_pct": round(max_dd_pct, 2),
            "sharpe_ratio": sharpe,
            "equity_curve": equity_curve,
            "trades": list(reversed(trades))[:20]  # Latest 20 trades
        }

backtest_engine = BacktestEngine()

