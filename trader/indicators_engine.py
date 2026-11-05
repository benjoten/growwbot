"""
Indicators & Multi-Timeframe Confluence Engine
Computes Price Action (Market Structure, Order Blocks, VWAP),
Volume Profile (POC, VAH, VAL), Momentum (RSI, MACD, Supertrend, ADX),
Options Greeks approximation, and Crypto metrics.
"""
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculates Volume Weighted Average Price (VWAP)."""
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3.0
    cum_vol_price = (typical_price * df['Volume']).cumsum()
    cum_vol = df['Volume'].cumsum().replace(0, 1)
    return cum_vol_price / cum_vol

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Standard Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    for i in range(period, len(series)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
        
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates MACD line, Signal line, and Histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
    """Calculates Supertrend line and Direction (1 for Bullish, -1 for Bearish)."""
    hl2 = (df['High'] + df['Low']) / 2.0
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - df['Close'].shift(1)).abs()
    tr3 = (df['Low'] - df['Close'].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().bfill()
    
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)
    
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)
    
    for i in range(1, len(df)):
        if basic_upper.iloc[i] < final_upper.iloc[i-1] or df['Close'].iloc[i-1] > final_upper.iloc[i-1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i-1]
            
        if basic_lower.iloc[i] > final_lower.iloc[i-1] or df['Close'].iloc[i-1] < final_lower.iloc[i-1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i-1]
            
        if i == 1:
            direction.iloc[i] = 1 if df['Close'].iloc[i] > final_upper.iloc[i] else -1
        else:
            if direction.iloc[i-1] == 1 and df['Close'].iloc[i] < final_lower.iloc[i]:
                direction.iloc[i] = -1
            elif direction.iloc[i-1] == -1 and df['Close'].iloc[i] > final_upper.iloc[i]:
                direction.iloc[i] = 1
            else:
                direction.iloc[i] = direction.iloc[i-1]
                
        supertrend.iloc[i] = final_lower.iloc[i] if direction.iloc[i] == 1 else final_upper.iloc[i]
        
    return supertrend.bfill(), direction.bfill()

def calculate_adx(df: pd.DataFrame, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates Average Directional Index (ADX), +DI, and -DI."""
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(period).mean() / atr.replace(0, 1e-9))
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(period).mean() / atr.replace(0, 1e-9))
    
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-9))
    adx = dx.rolling(period).mean()
    return adx.bfill(), plus_di.bfill(), minus_di.bfill()

def calculate_volume_profile(df: pd.DataFrame, bins_count: int = 24) -> Tuple[float, float, float]:
    """
    Computes Point of Control (POC), Value Area High (VAH), and Value Area Low (VAL).
    Standard 70% volume threshold used in professional auction market theory.
    """
    if len(df) == 0 or 'Volume' not in df.columns:
        cmp = float(df['Close'].iloc[-1]) if len(df) > 0 else 0.0
        return cmp, cmp * 1.01, cmp * 0.99
        
    price_min = df['Low'].min()
    price_max = df['High'].max()
    if price_max <= price_min:
        cmp = float(df['Close'].iloc[-1])
        return cmp, cmp * 1.01, cmp * 0.99
        
    bin_edges = np.linspace(price_min, price_max, bins_count + 1)
    vol_profile = np.zeros(bins_count)
    
    for _, row in df.iterrows():
        c_price = (row['High'] + row['Low'] + row['Close']) / 3.0
        vol = row['Volume']
        bin_idx = np.digitize(c_price, bin_edges) - 1
        bin_idx = min(max(bin_idx, 0), bins_count - 1)
        vol_profile[bin_idx] += vol
        
    poc_idx = int(np.argmax(vol_profile))
    poc_price = (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2.0
    
    # 70% Value Area
    total_volume = vol_profile.sum()
    target_vol = total_volume * 0.70
    accum_vol = vol_profile[poc_idx]
    
    low_idx = poc_idx
    high_idx = poc_idx
    
    while accum_vol < target_vol and (low_idx > 0 or high_idx < bins_count - 1):
        v_low = vol_profile[low_idx - 1] if low_idx > 0 else -1
        v_high = vol_profile[high_idx + 1] if high_idx < bins_count - 1 else -1
        
        if v_high >= v_low and high_idx < bins_count - 1:
            high_idx += 1
            accum_vol += vol_profile[high_idx]
        elif low_idx > 0:
            low_idx -= 1
            accum_vol += vol_profile[low_idx]
        else:
            break
            
    val_price = bin_edges[low_idx]
    vah_price = bin_edges[high_idx + 1]
    
    return float(round(poc_price, 2)), float(round(vah_price, 2)), float(round(val_price, 2))

def detect_market_structure(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Detects Higher-Highs / Higher-Lows (Bullish) vs Lower-Highs / Lower-Lows (Bearish),
    Order Blocks (Demand / Supply zones), and Key Pivot Levels.
    """
    if len(df) < 15:
        return {
            "bias": "NEUTRAL",
            "structure": "Consolidation",
            "demand_zone": (df['Low'].min(), df['Low'].min() * 1.005),
            "supply_zone": (df['High'].max() * 0.995, df['High'].max())
        }
        
    recent = df.iloc[-20:]
    highs = recent['High'].values
    lows = recent['Low'].values
    
    # Check swing pivots
    hh = highs[-1] > highs[-5] and highs[-5] > highs[-10]
    hl = lows[-1] > lows[-5] and lows[-5] > lows[-10]
    
    lh = highs[-1] < highs[-5] and highs[-5] < highs[-10]
    ll = lows[-1] < lows[-5] and lows[-5] < lows[-10]
    
    if hh and hl:
        bias = "BULLISH"
        structure = "Higher Highs & Higher Lows (Impulsive Uptrend)"
    elif lh and ll:
        bias = "BEARISH"
        structure = "Lower Highs & Lower Lows (Impulsive Downtrend)"
    elif highs[-1] > highs[-5]:
        bias = "BULLISH_RECOVERY"
        structure = "Break of Structure (BOS) Upward"
    elif lows[-1] < lows[-5]:
        bias = "BEARISH_BREAKDOWN"
        structure = "Break of Structure (BOS) Downward"
    else:
        bias = "RANGE"
        structure = "Horizontal Consolidation in Range"
        
    demand_low = float(recent['Low'].nsmallest(3).mean())
    demand_high = demand_low * 1.004
    supply_high = float(recent['High'].nlargest(3).mean())
    supply_low = supply_high * 0.996
    
    return {
        "bias": bias,
        "structure": structure,
        "demand_zone": (round(demand_low, 2), round(demand_high, 2)),
        "supply_zone": (round(supply_low, 2), round(supply_high, 2))
    }

def estimate_option_greeks(
    spot: float,
    strike: float,
    days_to_expiry: float = 4.0,
    r: float = 0.065,
    sigma: float = 0.15,
    option_type: str = "CE"
) -> Dict[str, float]:
    """
    Black-Scholes Delta, Gamma, Theta, and IV approximation for Indian Index Options.
    """
    T = max(days_to_expiry / 365.0, 1e-4)
    sigma = max(sigma, 0.05)
    
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    # Normal CDF
    def norm_cdf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
    
    def norm_pdf(x):
        return (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x * x)
        
    if option_type.upper() == "CE":
        delta = norm_cdf(d1)
        premium = spot * norm_cdf(d1) - strike * math.exp(-r * T) * norm_cdf(d2)
    else:
        delta = norm_cdf(d1) - 1.0
        premium = strike * math.exp(-r * T) * norm_cdf(-d2) - spot * norm_cdf(-d1)
        
    gamma = norm_pdf(d1) / (spot * sigma * math.sqrt(T))
    # Theta per day
    theta = -(spot * norm_pdf(d1) * sigma) / (2 * math.sqrt(T)) / 365.0
    
    # Intrinsic value floor
    if option_type.upper() == "CE":
        intrinsic = max(0.0, spot - strike)
    else:
        intrinsic = max(0.0, strike - spot)
        
    premium = max(premium, intrinsic, 5.0)
    
    return {
        "delta": round(float(delta), 3),
        "gamma": round(float(gamma), 5),
        "theta_daily": round(float(theta), 2),
        "premium": round(float(premium), 2),
        "iv_rank": round(float(sigma * 100.0 * 2.5), 1)  # Scale ~35-65
    }

