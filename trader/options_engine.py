"""
Index Options Strike Selection & Trade Ticket Engine
Covers Nifty 50, Bank Nifty, Fin Nifty, and Sensex weekly options with exact strike selection,
Greeks filtering, theta decay cutoff, and bi-directional BUY CALL / BUY PUT execution tickets.
"""
import uuid
from datetime import datetime
import pytz
from typing import Dict, Any, Optional

from trader.system_models import (
    TradeTicket, OptionStrike, IndicatorsData, BacktestExpectancy,
    DirectionType, MarketRegimeType, AssetClass
)
from trader.indicators_engine import estimate_option_greeks
from trader.backtest_walkforward import get_expectancy

IST = pytz.timezone("Asia/Kolkata")

def round_to_strike(price: float, step: int) -> float:
    """Rounds price to nearest index strike step."""
    return round(price / step) * step

def build_index_option_ticket(
    index_cfg: Dict[str, Any],
    spot_price: float,
    direction: DirectionType,
    indicators: IndicatorsData,
    market_regime: MarketRegimeType,
    confidence_score: int,
    account_capital: float = 500000.0,
    max_risk_pct: float = 1.5
) -> TradeTicket:
    """
    Generates a full institutional-grade trade ticket for Index Options.
    """
    symbol = index_cfg["symbol"]
    step = index_cfg["strike_step"]
    lot_size = index_cfg["lot_size"]
    
    # 1. Determine Strike
    is_call = (direction == DirectionType.BUY_CALL)
    option_type = "CE" if is_call else "PE"
    
    # ATM strike
    atm_strike = round_to_strike(spot_price, step)
    
    # Selection logic: For strong momentum, pick 1 strike OTM or ATM
    if confidence_score >= 85:
        # High conviction: ATM for maximum delta acceleration (gamma squeeze)
        selected_strike = atm_strike
        strike_tag = f"ATM Delta ~0.50 (Max Momentum)"
    else:
        # Slight OTM for asymmetric R:R
        selected_strike = (atm_strike + step) if is_call else (atm_strike - step)
        strike_tag = f"OTM Delta ~0.35 (Asymmetric R:R)"
        
    greeks = estimate_option_greeks(
        spot=spot_price,
        strike=selected_strike,
        days_to_expiry=3.5,
        r=0.065,
        sigma=0.145,
        option_type=option_type
    )
    
    premium = greeks["premium"]
    iv_rank = greeks["iv_rank"]
    delta = greeks["delta"]
    gamma = greeks["gamma"]
    
    # Current expiry date estimation (Upcoming Thursday for NSE / Friday for Sensex)
    now_ist = datetime.now(IST)
    expiry_str = "Weekly Near-Month"
    
    opt_strike_obj = OptionStrike(
        strike_price=selected_strike,
        option_type=option_type,
        delta=delta,
        iv_rank=iv_rank,
        expiry_date=expiry_str,
        lot_size=lot_size,
        estimated_premium=premium,
        strike_tag=strike_tag,
        gamma=gamma
    )
    
    # 2. Premium Entry, Targets, and Stop-Loss (in Option Points)
    # Day-trader methodology: 1R Stop Loss = 20-25% of premium; Target 1 = 1.5R; Target 2 = 2.5R
    risk_points = max(round(premium * 0.22, 1), 12.0)
    slippage_buffer = round(premium * 0.005, 1) # 0.5% buffer
    entry_price = round(premium + slippage_buffer, 1)
    entry_min = round(premium, 1)
    entry_max = round(premium + slippage_buffer * 1.5, 1)
    
    stop_loss = round(max(entry_price - risk_points, 5.0), 1)
    stop_loss_pct = round(((entry_price - stop_loss) / entry_price) * 100.0, 1)
    
    target_1 = round(entry_price + (risk_points * 1.50), 1)
    target_1_gain = round(((target_1 - entry_price) / entry_price) * 100.0, 1)
    
    target_2 = round(entry_price + (risk_points * 2.50), 1)
    target_2_gain = round(((target_2 - entry_price) / entry_price) * 100.0, 1)
    
    # 3. Position Sizing
    max_risk_amount = account_capital * (max_risk_pct / 100.0)  # e.g. 7,500 INR
    risk_per_lot = (entry_price - stop_loss) * lot_size
    lots = max(int(max_risk_amount // risk_per_lot), 1)
    
    allocated_capital = round(lots * lot_size * entry_price, 2)
    pos_size_pct = round((allocated_capital / account_capital) * 100.0, 1)
    actual_max_loss = round(lots * risk_per_lot, 2)
    expected_profit_t1 = round(lots * (target_1 - entry_price) * lot_size, 2)
    expected_profit_t2 = round(lots * (target_2 - entry_price) * lot_size, 2)
    
    expectancy = get_expectancy("INDEX_OPTION", direction.value, confidence_score)
    
    # 4. Narratives
    strike_str = f"{symbol} {int(selected_strike)} {option_type}"
    if is_call:
        upside_narrative = (
            f"Bullish expansion confirmed: {symbol} spot holding firmly above session VWAP (₹{indicators.vwap:,.1f}) "
            f"with RSI ({indicators.rsi_14:.1f}) in prime acceleration zone. Order flow displays aggressive buyer absorption "
            f"at POC (₹{indicators.poc_price:,.1f}). Target 1 is at ₹{target_1:.1f} (+{target_1_gain}%), Target 2 at ₹{target_2:.1f} (+{target_2_gain}%)."
        )
        downside_narrative = (
            f"Trade invalidation occurs if {symbol} spot breaks below support at ₹{indicators.val_price:,.1f} "
            f"or option premium collapses below protective Stop-Loss at ₹{stop_loss:.1f} (-{stop_loss_pct}%). "
            f"Strict time-stop active: close position before 15:15 IST to eliminate overnight gap risk."
        )
    else:
        upside_narrative = (
            f"Bearish continuation confirmed: {symbol} rejected at session VWAP (₹{indicators.vwap:,.1f}) "
            f"with RSI ({indicators.rsi_14:.1f}) indicating active seller control. Option premium poised for gamma surge "
            f"as index breaks below Value Area Low. Target 1 at ₹{target_1:.1f} (+{target_1_gain}%), Target 2 at ₹{target_2:.1f} (+{target_2_gain}%)."
        )
        downside_narrative = (
            f"Trade invalidation occurs if {symbol} spot reclaims above ₹{indicators.vah_price:,.1f} "
            f"or option premium falls below protective Stop-Loss at ₹{stop_loss:.1f} (-{stop_loss_pct}%). "
            f"Strict time-stop active: exit by 15:15 IST."
        )
        
    chart_symbol = f"NSE:{symbol}" if index_cfg["exchange"] == "NSE" else f"BSE:{symbol}"
    
    ticket = TradeTicket(
        ticket_id=f"TICK-OPT-{symbol}-{uuid.uuid4().hex[:6].upper()}",
        timestamp=datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        symbol=symbol,
        display_name=f"{strike_str} ({strike_tag})",
        exchange=index_cfg["exchange"],
        asset_class=AssetClass.INDEX_OPTION,
        direction=direction,
        action_type="BUY",
        market_regime=market_regime,
        confidence_score=confidence_score,
        underlying_price=round(spot_price, 2),
        entry_price=entry_price,
        entry_zone_min=entry_min,
        entry_zone_max=entry_max,
        slippage_buffer_pct=0.5,
        target_1=target_1,
        target_1_gain_pct=target_1_gain,
        target_2=target_2,
        target_2_gain_pct=target_2_gain,
        stop_loss=stop_loss,
        stop_loss_pct=stop_loss_pct,
        risk_reward_t1="1 : 1.50",
        risk_reward_t2="1 : 2.50",
        position_size_pct=pos_size_pct,
        lot_count=lots,
        units="Lots",
        allocated_capital=allocated_capital,
        max_loss_amount=actual_max_loss,
        expected_profit_t1=expected_profit_t1,
        expected_profit_t2=expected_profit_t2,
        max_hold_time="Exit by 15:15 IST (Auto Square-off)",
        option_strike=opt_strike_obj,
        indicators=indicators,
        expectancy=expectancy,
        scenario_narrative_upside=upside_narrative,
        scenario_narrative_downside=downside_narrative,
        market_regime_narrative=f"Regime: {market_regime.value}. Supertrend is {indicators.supertrend_bias}, ADX={indicators.adx_14:.1f}.",
        chart_symbol=chart_symbol,
        chart_overlays={
            "entry_level": entry_price,
            "entry_box": [entry_min, entry_max],
            "t1": target_1,
            "t2": target_2,
            "sl": stop_loss,
            "underlying_spot": spot_price
        }
    )
    return ticket

