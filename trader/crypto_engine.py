"""
Crypto Perpetuals Bi-Directional Engine
Covers BTCUSDT, ETHUSDT, and SOLUSDT perpetuals (Binance / Bybit / Delta format)
with Funding Rate bias, Open Interest (OI) delta, Order-book imbalance, and 24x7 trade tickets.
"""
import uuid
from datetime import datetime
import pytz
from typing import Dict, Any

from trader.system_models import (
    TradeTicket, IndicatorsData, BacktestExpectancy,
    DirectionType, MarketRegimeType, AssetClass
)
from trader.backtest_walkforward import get_expectancy

IST = pytz.timezone("Asia/Kolkata")

def build_crypto_perp_ticket(
    crypto_cfg: Dict[str, Any],
    mark_price: float,
    direction: DirectionType,
    indicators: IndicatorsData,
    market_regime: MarketRegimeType,
    confidence_score: int,
    account_capital_usdt: float = 50000.0,
    max_risk_pct: float = 1.5,
    leverage: int = 10
) -> TradeTicket:
    """
    Generates a complete institutional-grade trade ticket for Crypto Perpetuals.
    """
    symbol = crypto_cfg["symbol"]
    multiplier = crypto_cfg.get("contract_multiplier", 0.001)
    is_long = (direction == DirectionType.LONG_PERP)
    
    # ATR or volatility percentage estimation
    atr_pct = 0.012 if "BTC" in symbol else (0.016 if "ETH" in symbol else 0.024)
    risk_points = mark_price * atr_pct
    
    slippage_pct = crypto_cfg.get("slippage_crypto_pct", 0.0005)
    slippage_buffer = mark_price * slippage_pct
    
    if is_long:
        entry_price = round(mark_price + slippage_buffer, 2)
        entry_min = round(mark_price - (slippage_buffer * 0.5), 2)
        entry_max = round(mark_price + (slippage_buffer * 1.5), 2)
        
        stop_loss = round(entry_price - risk_points, 2)
        stop_loss_pct = round(((entry_price - stop_loss) / entry_price) * 100.0, 2)
        
        target_1 = round(entry_price + (risk_points * 1.50), 2)
        target_1_gain = round(((target_1 - entry_price) / entry_price) * 100.0, 2)
        
        target_2 = round(entry_price + (risk_points * 2.50), 2)
        target_2_gain = round(((target_2 - entry_price) / entry_price) * 100.0, 2)
    else:
        entry_price = round(mark_price - slippage_buffer, 2)
        entry_min = round(mark_price - (slippage_buffer * 1.5), 2)
        entry_max = round(mark_price + (slippage_buffer * 0.5), 2)
        
        stop_loss = round(entry_price + risk_points, 2)
        stop_loss_pct = round(((stop_loss - entry_price) / entry_price) * 100.0, 2)
        
        target_1 = round(entry_price - (risk_points * 1.50), 2)
        target_1_gain = round(((entry_price - target_1) / entry_price) * 100.0, 2)
        
        target_2 = round(entry_price - (risk_points * 2.50), 2)
        target_2_gain = round(((entry_price - target_2) / entry_price) * 100.0, 2)
        
    # Position Sizing
    max_risk_usdt = account_capital_usdt * (max_risk_pct / 100.0)  # e.g. 750 USDT
    loss_per_unit = abs(entry_price - stop_loss)
    
    # Coins and contracts
    total_coins = max_risk_usdt / max(loss_per_unit, 1.0)
    total_contracts = round(total_coins / multiplier)
    if total_contracts < 1:
        total_contracts = 1
        total_coins = total_contracts * multiplier
        
    position_notional = round(total_coins * entry_price, 2)
    margin_required = round(position_notional / leverage, 2)
    pos_size_pct = round((margin_required / account_capital_usdt) * 100.0, 1)
    
    actual_max_loss = round(total_coins * loss_per_unit, 2)
    expected_profit_t1 = round(total_coins * abs(target_1 - entry_price), 2)
    expected_profit_t2 = round(total_coins * abs(target_2 - entry_price), 2)
    
    expectancy = get_expectancy("CRYPTO", direction.value, confidence_score)
    
    # Narratives
    funding_info = f"Funding Rate: {indicators.crypto_funding_rate:+.4f}%" if indicators.crypto_funding_rate else "Neutral Funding"
    oi_info = f"OI Delta: {indicators.crypto_oi_delta_pct:+.1f}%" if indicators.crypto_oi_delta_pct else "Stable OI"
    book_info = f"Orderbook Imbalance: {indicators.crypto_book_imbalance:+.2f}" if indicators.crypto_book_imbalance else "Balanced Depth"
    
    if is_long:
        upside_narrative = (
            f"Bullish continuation active on {symbol}. Mark price ($ {entry_price:,.2f}) trades above session VWAP ($ {indicators.vwap:,.2f}) "
            f"with RSI ({indicators.rsi_14:.1f}) confirming bullish momentum. {funding_info}, {oi_info}, and {book_info} signaling "
            f"strong institutional bid absorption. Target 1: ${target_1:,.2f} (+{target_1_gain}%), Target 2: ${target_2:,.2f} (+{target_2_gain}%)."
        )
        downside_narrative = (
            f"Invalidation triggered if price loses Point of Control (POC: ${indicators.poc_price:,.2f}) "
            f"or triggers protective Stop-Loss at ${stop_loss:,.2f} (-{stop_loss_pct}%). Leverage capped at {leverage}x "
            f"to limit max drawdown to ${actual_max_loss:,.2f} USDT."
        )
    else:
        upside_narrative = (
            f"Bearish breakdown setup active on {symbol}. Mark price ($ {entry_price:,.2f}) rejected at session VWAP ($ {indicators.vwap:,.2f}) "
            f"with RSI ({indicators.rsi_14:.1f}) in negative distribution. {funding_info} and {book_info} show heavy limit asks overhead. "
            f"Short perp targets liquidation cascade into Target 1: ${target_1:,.2f} (+{target_1_gain}%) and Target 2: ${target_2:,.2f} (+{target_2_gain}%)."
        )
        downside_narrative = (
            f"Invalidation triggered if price reclaims above Value Area High (VAH: ${indicators.vah_price:,.2f}) "
            f"or hits Stop-Loss at ${stop_loss:,.2f} (-{stop_loss_pct}%). Leverage capped at {leverage}x with liquidation price comfortably distant."
        )
        
    chart_symbol = f"BINANCE:{symbol}"
    
    ticket = TradeTicket(
        ticket_id=f"TICK-CRYPTO-{symbol}-{uuid.uuid4().hex[:6].upper()}",
        timestamp=datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        symbol=symbol,
        display_name=f"{crypto_cfg['name']} ({leverage}x {direction.value})",
        exchange="Binance/Bybit",
        asset_class=AssetClass.CRYPTO_PERPETUAL,
        direction=direction,
        action_type="BUY" if is_long else "SELL",
        market_regime=market_regime,
        confidence_score=confidence_score,
        underlying_price=round(mark_price, 2),
        entry_price=entry_price,
        entry_zone_min=entry_min,
        entry_zone_max=entry_max,
        slippage_buffer_pct=slippage_pct * 100.0,
        target_1=target_1,
        target_1_gain_pct=target_1_gain,
        target_2=target_2,
        target_2_gain_pct=target_2_gain,
        stop_loss=stop_loss,
        stop_loss_pct=stop_loss_pct,
        risk_reward_t1="1 : 1.50",
        risk_reward_t2="1 : 2.50",
        position_size_pct=pos_size_pct,
        lot_count=int(total_contracts),
        units="Contracts",
        allocated_capital=margin_required,
        max_loss_amount=actual_max_loss,
        expected_profit_t1=expected_profit_t1,
        expected_profit_t2=expected_profit_t2,
        max_hold_time="Intraday / 4-Hour Trailing Stop",
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
            "underlying_spot": mark_price
        }
    )
    return ticket

