"""
DayTrader System Data Models
Typed Pydantic structures for bi-directional trade tickets, market regimes, options Greeks, and backtest expectancy.
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class DirectionType(str, Enum):
    BUY_CALL = "BUY CALL"
    BUY_PUT = "BUY PUT"
    LONG_PERP = "LONG PERP"
    SHORT_PERP = "SHORT PERP"
    BUY_EQUITY = "BUY (LONG)"
    SELL_EQUITY = "SELL (SHORT)"

class MarketRegimeType(str, Enum):
    TRENDING_BULLISH = "TRENDING_BULLISH"
    TRENDING_BEARISH = "TRENDING_BEARISH"
    MEAN_REVERTING_RANGE = "MEAN_REVERTING_RANGE"
    VOLATILE_CHOPPY = "VOLATILE_CHOPPY"

class AssetClass(str, Enum):
    INDEX_OPTION = "INDEX_OPTION"
    EQUITY = "EQUITY"
    CRYPTO_PERPETUAL = "CRYPTO_PERPETUAL"

class OptionStrike(BaseModel):
    strike_price: float
    option_type: str  # CE or PE
    delta: float
    iv_rank: float
    expiry_date: str
    lot_size: int
    estimated_premium: float
    strike_tag: str  # e.g., "ATM Delta 0.50" or "OTM Delta 0.35"
    open_interest: Optional[int] = 0
    gamma: Optional[float] = 0.0

class IndicatorsData(BaseModel):
    rsi_14: float
    macd_bias: str
    supertrend_bias: str
    adx_14: float
    vwap: float
    vwap_signal: str  # "RECLAIM_ABOVE" or "REJECT_BELOW"
    poc_price: float  # Point of Control
    vah_price: float  # Value Area High
    val_price: float  # Value Area Low
    rvol: float       # Relative Volume Surge
    timeframe_confluence: str  # e.g. "5m Bullish / 15m Bullish / 1h Neutral"
    crypto_funding_rate: Optional[float] = None
    crypto_oi_delta_pct: Optional[float] = None
    crypto_book_imbalance: Optional[float] = None

class BacktestExpectancy(BaseModel):
    sample_period: str
    total_trades: int
    win_rate_pct: float
    loss_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    avg_r_multiple: float
    expectancy_r: float

class TradeTicket(BaseModel):
    ticket_id: str
    timestamp: str
    symbol: str
    display_name: str
    exchange: str
    asset_class: AssetClass
    direction: DirectionType
    action_type: str  # "BUY" or "SELL"
    market_regime: MarketRegimeType
    confidence_score: int
    
    # Prices
    underlying_price: float
    entry_price: float
    entry_zone_min: float
    entry_zone_max: float
    slippage_buffer_pct: float
    
    # Exits
    target_1: float
    target_1_gain_pct: float
    target_2: float
    target_2_gain_pct: float
    stop_loss: float
    stop_loss_pct: float
    risk_reward_t1: str
    risk_reward_t2: str
    
    # Position Sizing
    position_size_pct: float
    lot_count: int
    units: str  # "Lots", "Shares", "Contracts"
    allocated_capital: float
    max_loss_amount: float
    expected_profit_t1: float
    expected_profit_t2: float
    max_hold_time: str
    
    # Option specific
    option_strike: Optional[OptionStrike] = None
    
    # Technical & Indicators
    indicators: IndicatorsData
    expectancy: BacktestExpectancy
    
    # Scenario Narratives
    scenario_narrative_upside: str
    scenario_narrative_downside: str
    market_regime_narrative: str
    
    # Charting
    chart_symbol: str
    setup_candle_time: Optional[str] = None
    chart_overlays: Dict[str, Any] = Field(default_factory=dict)

