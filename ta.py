"""ta.py - WICK. Technical analysis helpers for OHLCV candles.

WICK reads the candlesticks; it is a library, not a trader.

IMPORTANT: every signal in this module is a HEURISTIC. Candlestick
patterns and indicators like RSI / MACD are widely used rule-of-thumb
descriptions of price action. A flag here means "this shape appeared
in the data", never "this stock will go up / down". Treat all output
as one input into a decision, not as a prediction.

Candles are plain dicts: {"date", "open", "high", "low", "close", "volume"}
in chronological order (oldest first).
"""

from __future__ import annotations

BULLISH_PATTERNS = {"bullish_engulfing", "hammer", "three_white_soldiers"}
BEARISH_PATTERNS = {"bearish_engulfing", "shooting_star", "three_black_crows"}


# ---------------------------------------------------------------- indicators

def sma(values, period):
    """Simple moving average of the last `period` values, or None."""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _ema_series(values, period):
    """EMA series aligned with `values` (None before the seed point)."""
    out = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1)
    e = sum(values[:period]) / period  # seed with SMA
    out[period - 1] = e
    for i in range(period, len(values)):
        e = values[i] * k + e * (1 - k)
        out[i] = e
    return out


def ema_last(values, period):
    s = _ema_series(values, period)
    return s[-1] if s else None


def rsi(closes, period=14):
    """Wilder RSI. Returns None if there is not enough history."""
    if len(closes) <= period:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - 100.0 / (1.0 + rs)


def macd(closes, fast=12, slow=26, signal=9):
    """Returns (macd_line, signal_line, histogram) at the last bar, or Nones."""
    if len(closes) < slow + signal:
        return None, None, None
    ef = _ema_series(closes, fast)
    es = _ema_series(closes, slow)
    line = [None if (a is None or b is None) else a - b for a, b in zip(ef, es)]
    valid = [v for v in line if v is not None]
    sig_series = _ema_series(valid, signal)
    sig = [None] * (len(line) - len(valid)) + sig_series
    m, s = line[-1], sig[-1]
    hist = None if (m is None or s is None) else m - s
    return m, s, hist


def atr(candles, period=14):
    """Wilder ATR over OHLC candles, or None."""
    if len(candles) <= period:
        return None
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        a = (a * (period - 1) + trs[i]) / period
    return a


# ---------------------------------------------------------------- patterns

def detect_patterns(candles):
    """Candlestick pattern flags on the most recent candle(s). Heuristics."""
    pats = []
    if len(candles) < 2:
        return pats
    c, p = candles[-1], candles[-2]
    rng = c["high"] - c["low"]
    body = abs(c["close"] - c["open"])
    if rng > 0:
        upper = c["high"] - max(c["open"], c["close"])
        lower = min(c["open"], c["close"]) - c["low"]
        eps = 1e-9
        if body <= 0.1 * rng:
            pats.append("doji")
        # Hammer: long lower shadow, tiny upper shadow (reversal shape).
        if lower >= 2 * max(body, eps) and upper <= max(body, eps) and body > 0:
            pats.append("hammer")
        # Shooting star: long upper shadow, tiny lower shadow.
        if upper >= 2 * max(body, eps) and lower <= max(body, eps) and body > 0:
            pats.append("shooting_star")
    # Engulfing: current body fully covers the prior body, opposite color.
    if p["close"] < p["open"] and c["close"] > c["open"]:
        if c["open"] <= p["close"] and c["close"] >= p["open"]:
            pats.append("bullish_engulfing")
    if p["close"] > p["open"] and c["close"] < c["open"]:
        if c["open"] >= p["close"] and c["close"] <= p["open"]:
            pats.append("bearish_engulfing")
    # Three white soldiers / black crows: 3 same-color candles closing
    # progressively higher / lower with meaningful bodies.
    if len(candles) >= 3:
        t = candles[-3:]
        def decent(cd):
            r = cd["high"] - cd["low"]
            return r > 0 and abs(cd["close"] - cd["open"]) >= 0.5 * r
        if all(cd["close"] > cd["open"] and decent(cd) for cd in t) and \
                t[0]["close"] < t[1]["close"] < t[2]["close"]:
            pats.append("three_white_soldiers")
        if all(cd["close"] < cd["open"] and decent(cd) for cd in t) and \
                t[0]["close"] > t[1]["close"] > t[2]["close"]:
            pats.append("three_black_crows")
    return pats


# ---------------------------------------------------------------- summary

def _r2(x):
    return None if x is None else round(x, 2)


def analyze(candles):
    """Full TA summary for one symbol's candle history. Heuristics only."""
    out = {
        "patterns": [], "rsi14": None, "macd": None, "macd_signal": None,
        "macd_hist": None, "sma20": None, "sma50": None, "sma200": None,
        "ema20": None, "atr14": None, "rel_volume": None,
        "trend": "unknown", "turning_up": False, "falling_knife": False,
    }
    if len(candles) < 2:
        return out
    closes = [cd["close"] for cd in candles]
    vols = [cd["volume"] for cd in candles]
    last, prev = candles[-1], candles[-2]

    pats = detect_patterns(candles)
    out["patterns"] = pats
    out["rsi14"] = _r2(rsi(closes))
    m, s, h = macd(closes)
    out["macd"], out["macd_signal"], out["macd_hist"] = _r2(m), _r2(s), _r2(h)
    out["sma20"] = _r2(sma(closes, 20))
    out["sma50"] = _r2(sma(closes, 50))
    out["sma200"] = _r2(sma(closes, 200))
    ema20_series = _ema_series(closes, 20)
    out["ema20"] = _r2(ema20_series[-1])
    out["atr14"] = _r2(atr(candles))

    if len(vols) >= 21 and vols[-1]:
        base = sum(vols[-21:-1]) / 20.0
        out["rel_volume"] = _r2(vols[-1] / base) if base > 0 else None

    s50, s200 = out["sma50"], out["sma200"]
    lc = last["close"]
    if s50 is not None and s200 is not None:
        if lc > s50 and lc > s200:
            out["trend"] = "uptrend"
        elif lc < s50 and lc < s200:
            out["trend"] = "downtrend"
        else:
            out["trend"] = "mixed"
    elif s50 is not None:
        out["trend"] = "uptrend" if lc > s50 else "downtrend"

    # Heuristic flags (see module docstring - shapes, not predictions).
    bullish = any(p in BULLISH_PATTERNS for p in pats)
    green_day = last["close"] > prev["close"] and last["close"] > last["open"]
    red_day = last["close"] < prev["close"]
    rsi_now = rsi(closes)
    rsi_prev = rsi(closes[:-1])
    rsi_bounce = (rsi_now is not None and rsi_prev is not None
                  and rsi_prev <= 35 and rsi_now > rsi_prev)
    ema_cross_up = (len(ema20_series) >= 2
                    and ema20_series[-2] is not None and ema20_series[-1] is not None
                    and prev["close"] <= ema20_series[-2]
                    and last["close"] > ema20_series[-1])
    out["turning_up"] = bool(green_day and (bullish or rsi_bounce or ema_cross_up))

    ref_ma = s50 if s50 is not None else out["sma20"]
    below_ma = ref_ma is not None and lc < ref_ma
    out["falling_knife"] = bool(red_day and below_ma and not bullish and not rsi_bounce)
    return out
