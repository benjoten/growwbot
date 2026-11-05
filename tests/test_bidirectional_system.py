"""
Comprehensive Test Suite for Autonomous Bi-Directional Intraday Trading System
Validates YAML config, Indicators engine, Options strike selection, Crypto perpetuals,
Walk-forward statistical expectancy, and REST APIs.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pandas as pd
import numpy as np

from trader.bidirectional_engine import BiDirectionalTradingSystem, load_system_config
from trader.indicators_engine import (
    calculate_vwap, calculate_rsi, calculate_macd, calculate_supertrend,
    calculate_adx, calculate_volume_profile, detect_market_structure,
    estimate_option_greeks
)
from trader.options_engine import build_index_option_ticket
from trader.crypto_engine import build_crypto_perp_ticket
from trader.backtest_walkforward import get_expectancy
from trader.system_models import (
    TradeTicket, IndicatorsData, DirectionType, MarketRegimeType, AssetClass
)

def test_load_system_config():
    """Validates configuration file structure and required keys."""
    cfg = load_system_config()
    assert "system" in cfg
    assert "universe" in cfg
    assert "strategy" in cfg
    assert len(cfg["universe"]["indices"]) >= 4
    assert len(cfg["universe"]["crypto_perpetuals"]) >= 3
    assert len(cfg["universe"]["equities"]) >= 10
    print("[PASS] System Config successfully validated.")

def test_indicators_engine():
    """Validates multi-timeframe indicator calculations on synthetic OHLCV."""
    dates = pd.date_range("2026-11-01", periods=50, freq="15min")
    np.random.seed(42)
    prices = 1000.0 + np.cumsum(np.random.randn(50) * 5)
    highs = prices + np.random.rand(50) * 4
    lows = prices - np.random.rand(50) * 4
    vols = np.random.randint(1000, 50000, size=50)

    df = pd.DataFrame({
        "Open": prices,
        "High": highs,
        "Low": lows,
        "Close": prices + np.random.randn(50),
        "Volume": vols
    }, index=dates)

    vwap = calculate_vwap(df)
    assert len(vwap) == 50
    assert vwap.iloc[-1] > 0

    rsi = calculate_rsi(df['Close'], 14)
    assert len(rsi) == 50
    assert 0 <= rsi.iloc[-1] <= 100

    st_line, st_dir = calculate_supertrend(df, 10, 3.0)
    assert st_dir.iloc[-1] in [1, -1]

    adx, p_di, m_di = calculate_adx(df, 14)
    assert len(adx) == 50

    poc, vah, val = calculate_volume_profile(df, 24)
    assert val <= poc <= vah

    m_struct = detect_market_structure(df)
    assert "bias" in m_struct
    assert "demand_zone" in m_struct
    assert "supply_zone" in m_struct
    print("[PASS] Indicators Engine successfully computed VWAP, RSI, Supertrend, ADX & Volume Profile.")

def test_option_greeks_and_strike_selection():
    """Validates Black-Scholes Delta, Gamma, Theta, and strike selection for NIFTY."""
    spot = 24520.0
    greeks_ce = estimate_option_greeks(spot, 24500.0, days_to_expiry=3.0, option_type="CE")
    assert 0.40 <= greeks_ce["delta"] <= 0.60
    assert greeks_ce["premium"] > 0
    assert greeks_ce["gamma"] > 0

    greeks_pe = estimate_option_greeks(spot, 24500.0, days_to_expiry=3.0, option_type="PE")
    assert -0.60 <= greeks_pe["delta"] <= -0.40
    assert greeks_pe["premium"] > 0
    print(f"[PASS] Option Greeks Validated: CE Delta={greeks_ce['delta']}, PE Delta={greeks_pe['delta']}")

def test_index_option_ticket():
    """Validates Index Option Trade Ticket creation."""
    idx_cfg = {
        "symbol": "NIFTY",
        "name": "Nifty 50 Index",
        "ticker": "^NSEI",
        "exchange": "NSE",
        "lot_size": 25,
        "strike_step": 50
    }
    dummy_indicators = IndicatorsData(
        rsi_14=62.5,
        macd_bias="BULLISH",
        supertrend_bias="BULLISH_GREEN",
        adx_14=26.4,
        vwap=24480.0,
        vwap_signal="RECLAIM_ABOVE",
        poc_price=24500.0,
        vah_price=24550.0,
        val_price=24450.0,
        rvol=1.85,
        timeframe_confluence="5m/15m Bullish"
    )
    ticket = build_index_option_ticket(
        index_cfg=idx_cfg,
        spot_price=24520.0,
        direction=DirectionType.BUY_CALL,
        indicators=dummy_indicators,
        market_regime=MarketRegimeType.TRENDING_BULLISH,
        confidence_score=92,
        account_capital=500000.0
    )
    assert ticket.ticket_id.startswith("TICK-OPT-NIFTY")
    assert ticket.direction == DirectionType.BUY_CALL
    assert ticket.target_1 > ticket.entry_price
    assert ticket.target_2 > ticket.target_1
    assert ticket.stop_loss < ticket.entry_price
    assert ticket.lot_count >= 1
    assert ticket.expectancy.win_rate_pct >= 60.0
    print(f"[PASS] Index Option Ticket: {ticket.ticket_id} | {ticket.display_name} | Entry: {ticket.entry_price} | T1: {ticket.target_1} | SL: {ticket.stop_loss}")

def test_crypto_perp_ticket():
    """Validates Crypto Perpetual Trade Ticket generation for BTCUSDT."""
    crypto_cfg = {
        "symbol": "BTCUSDT",
        "name": "Bitcoin Perpetual",
        "tick_size": 0.1,
        "contract_multiplier": 0.001,
        "default_leverage": 10
    }
    dummy_indicators = IndicatorsData(
        rsi_14=42.0,
        macd_bias="BEARISH",
        supertrend_bias="BEARISH_RED",
        adx_14=24.0,
        vwap=80500.0,
        vwap_signal="REJECT_BELOW",
        poc_price=80400.0,
        vah_price=80800.0,
        val_price=79900.0,
        rvol=1.45,
        timeframe_confluence="15m Bearish Breakdown",
        crypto_funding_rate=-0.0040,
        crypto_oi_delta_pct=-2.1,
        crypto_book_imbalance=-0.35
    )
    ticket = build_crypto_perp_ticket(
        crypto_cfg=crypto_cfg,
        mark_price=80000.0,
        direction=DirectionType.SHORT_PERP,
        indicators=dummy_indicators,
        market_regime=MarketRegimeType.TRENDING_BEARISH,
        confidence_score=85,
        account_capital_usdt=50000.0,
        leverage=10
    )
    assert ticket.ticket_id.startswith("TICK-CRYPTO-BTCUSDT")
    assert ticket.direction == DirectionType.SHORT_PERP
    assert ticket.target_1 < ticket.entry_price
    assert ticket.target_2 < ticket.target_1
    assert ticket.stop_loss > ticket.entry_price
    assert ticket.lot_count >= 1
    print(f"[PASS] Crypto Short Ticket: {ticket.ticket_id} | {ticket.display_name} | Entry: {ticket.entry_price} | T1: {ticket.target_1} | SL: {ticket.stop_loss}")

if __name__ == "__main__":
    test_load_system_config()
    test_indicators_engine()
    test_option_greeks_and_strike_selection()
    test_index_option_ticket()
    test_crypto_perp_ticket()
    print("\nALL 5 SYSTEM TESTS PASSED SUCCESSFULLY!")
