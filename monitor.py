#!/usr/bin/env python3
"""
Trend monitor for SPCX and SLV.
Fetches 5-day hourly data, detects downtrend status, and alerts on changes.

State is persisted to ~/.hermes/cron/stock-monitor-state.json
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Import from the stock-price skill
sys.path.insert(0, os.path.expanduser("~/.hermes/skills/data-science/stock-price/scripts"))
from stock import fetch_chart, parse_result

TICKERS = ["SPCX", "SLV"]
STATE_PATH = Path(os.path.expanduser("~/.hermes/cron/stock-monitor-state.json"))


def market_session():
    """Return the current US equity market session label."""
    now = datetime.now(timezone.utc)
    et_offset = -4
    et_hour = (now.hour + et_offset) % 24
    et_minute = now.minute
    et_time = et_hour * 60 + et_minute

    if 240 <= et_time < 570:
        return "Pre-market"
    elif 570 <= et_time < 960:
        return "Regular hours"
    elif 960 <= et_time < 1200:
        return "After-hours"
    else:
        return "Market closed"


def fmt_big(n: int) -> str:
    """Format large numbers as 6.8M, 1.2B, etc."""
    if abs(n) >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def last_bar_time(result):
    """Return the timestamp of the most recent bar from Yahoo data."""
    timestamps = result.get("timestamp", [])
    if not timestamps:
        return None
    return datetime.fromtimestamp(timestamps[-1], tz=timezone.utc)

# User positions (from broker screenshot)
# SLV: two lots -- 457 @ $54.99 and 513 @ $63.61  (blended avg ≈ $59.55)
POSITIONS = {
    "SPCX": {"qty": 90, "avg": 142.03},
    "SLV":  {"qty": 970, "avg": 59.55, "lots": [(457, 54.99), (513, 63.61)]},
}

def position_pnl(ticker: str, last_price: float):
    """Compute unrealized P&L for a held position."""
    pos = POSITIONS.get(ticker)
    if not pos:
        return None
    qty = pos["qty"]
    avg = pos["avg"]
    value = qty * last_price
    cost = qty * avg
    pnl = value - cost
    pnl_pct = (pnl / cost) * 100 if cost else 0.0
    return {
        "qty": qty,
        "avg": avg,
        "value": round(value, 2),
        "cost": round(cost, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "breakeven": avg,
        "dist_to_breakeven_pct": round((last_price - avg) / avg * 100, 2) if avg else 0.0,
    }


def ensure_dir(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state: dict):
    ensure_dir(STATE_PATH)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, default=str)


def is_stale(result: dict, session: str) -> bool:
    """Check if data is stale for the current session."""
    meta = result.get("meta", {})
    timestamps = result.get("timestamp", [])
    if not timestamps:
        return True

    now = datetime.now(timezone.utc)
    et_offset = -4
    et_hour = (now.hour + et_offset) % 24
    et_minute = now.minute
    et_time = et_hour * 60 + et_minute  # minutes since midnight ET

    # Convert last bar to ET
    last_ts = timestamps[-1]
    last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
    last_et_hour = (last_dt.hour + et_offset) % 24
    last_et_time = last_et_hour * 60 + last_dt.minute

    if session == "After-hours":
        # After-hours starts at 4:00 PM ET (960). If last bar is at or before 4:00 PM, it's stale.
        return last_et_time <= 960
    elif session == "Pre-market":
        # Pre-market starts at 4:00 AM ET (240). If last bar is before 4:00 AM, it's stale.
        return last_et_time < 240
    else:
        # Regular hours: stale if last bar is older than 90 minutes
        return (now - last_dt).total_seconds() > 5400


def analyze_ticker(ticker: str):
    """
    Fetch 5-day hourly data and compute trend metrics.
    Returns a dict with trend info or None on error.
    """
    try:
        result = fetch_chart(ticker, "5d", "1h", prepost=True)
    except Exception as e:
        return {"error": str(e)}

    meta, bars = parse_result(result)
    if not bars:
        return {"error": "no data"}

    closes = [b["close"] for b in bars if b.get("close") is not None]
    volumes = [b["volume"] for b in bars if b.get("volume") is not None]

    if len(closes) < 10:
        return {"error": f"only {len(closes)} bars"}

    # --- Price trend: linear regression slope on last N hours ---
    def slope(vals):
        n = len(vals)
        x_mean = (n - 1) / 2.0
        y_mean = sum(vals) / n
        num = sum((i - x_mean) * (vals[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den else 0.0

    # Full-period slope vs recent slope
    full_slope = slope(closes)
    recent_n = min(20, len(closes) // 2)
    recent_slope = slope(closes[-recent_n:])

    # Key price levels
    first_price = closes[0]
    last_price = closes[-1]
    high = max(closes)
    low = min(closes)
    avg = sum(closes) / len(closes)

    # --- Daily change (vs previous close from metadata) ---
    # previousClose = yesterday's close (what we want for "today")
    # chartPreviousClose = first bar of the chart period (5d ago)
    previous_close = meta.get("previousClose")
    if not previous_close:
        previous_close = meta.get("chartPreviousClose")
    daily_change_pct = None
    if previous_close and previous_close > 0:
        daily_change_pct = round((last_price - previous_close) / previous_close * 100, 2)
    daily_change_abs = round(last_price - previous_close, 2) if previous_close else None

    # --- Volume trend ---
    if volumes:
        avg_vol = sum(volumes) / len(volumes)
        recent_vol = sum(volumes[-recent_n:]) / recent_n if recent_n else avg_vol
        vol_ratio = recent_vol / avg_vol if avg_vol else 1.0
    else:
        avg_vol = recent_vol = vol_ratio = 0.0

    # --- Downtrend classification ---
    # Downtrend = price is declining over the period AND below average
    is_downtrend = (full_slope < -0.01) and (last_price < avg)

    # --- Reversal signals ---
    reversal_signals = []
    # 1. Slope turned positive after being negative (full period still down, recent up)
    if full_slope < -0.01 and recent_slope > 0.02:
        reversal_signals.append("slope reversal (recent turning up)")
    # 2. Price bounced > 2% off the low
    if low > 0 and last_price > low * 1.02:
        reversal_signals.append(f"bounced +{((last_price/low)-1)*100:.1f}% off low")
    # 3. Volume spike on recent upward price action
    if vol_ratio > 1.3 and recent_slope > 0:
        reversal_signals.append(f"volume spike ({vol_ratio:.1f}x avg) with rising price")
    # 4. Price recovered above the period average
    if last_price > avg and first_price < avg:
        reversal_signals.append("recovered above period average")

    # --- Acceleration signals (downtrend worsening) ---
    acceleration_signals = []
    if full_slope < -0.01 and recent_slope < full_slope:
        acceleration_signals.append("downtrend accelerating")
    if vol_ratio > 1.5 and recent_slope < 0:
        acceleration_signals.append(f"volume spike ({vol_ratio:.1f}x avg) with falling price")
    if last_price < low * 1.005:
        acceleration_signals.append("near period low")

    # --- Stale check for after-hours / pre-market ---
    data_stale = False
    session_now = market_session()
    if session_now in ("After-hours", "Pre-market"):
        timestamps = result.get("timestamp", [])
        if timestamps:
            last_ts = timestamps[-1]
            last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
            et_offset = -4
            last_et_hour = (last_dt.hour + et_offset) % 24
            last_et_time = last_et_hour * 60 + last_dt.minute
            if session_now == "After-hours" and last_et_time <= 960:
                data_stale = True
            elif session_now == "Pre-market" and last_et_time < 240:
                data_stale = True

    return {
        "ticker": ticker,
        "name": meta.get("shortName") or meta.get("longName") or ticker,
        "last_price": round(last_price, 2),
        "change_pct": round((last_price - first_price) / first_price * 100, 2) if first_price else 0.0,
        "daily_change_pct": daily_change_pct,
        "daily_change_abs": daily_change_abs,
        "high": round(high, 2),
        "low": round(low, 2),
        "avg_price": round(avg, 2),
        "full_slope": round(full_slope, 4),
        "recent_slope": round(recent_slope, 4),
        "avg_vol": int(avg_vol),
        "recent_vol": int(recent_vol),
        "vol_ratio": round(vol_ratio, 2),
        "is_downtrend": is_downtrend,
        "reversal_signals": reversal_signals,
        "acceleration_signals": acceleration_signals,
        "bar_count": len(closes),
        "last_bar_time": last_bar_time(result).isoformat() if last_bar_time(result) else None,
        "data_stale": data_stale,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def format_alert(new, old=None):
    """Format a compact, scannable Telegram alert for a single ticker."""
    t = new["ticker"]
    lp = new["last_price"]
    session = market_session()
    stale = new.get("data_stale", False)

    session_tag = f"[🕐 {session}]"
    if stale:
        session_tag = f"[🕐 {session} — stale data (no trades)]"

    lines = []
    lines.append(f"**{t}**  {session_tag}")

    # Position block (needed for assessment)
    pnl_info = position_pnl(t, lp)

    # One-line assessment based on the data
    assess = []
    if new["is_downtrend"]:
        if new["acceleration_signals"]:
            assess.append("downtrend worsening")
        elif new["reversal_signals"]:
            assess.append("downtrend but reversal signals appearing")
        else:
            assess.append("downtrend intact")
    else:
        if new["reversal_signals"]:
            assess.append("potential bottom forming")
        else:
            assess.append("not in downtrend")

    if pnl_info:
        dist = pnl_info["dist_to_breakeven_pct"]
        if dist <= -20:
            assess.append(f"deep loss ({pnl_info['pnl_pct']:+.1f}%)")
        elif dist <= -10:
            assess.append(f"significant loss ({pnl_info['pnl_pct']:+.1f}%)")
        elif dist >= -2:
            assess.append("near breakeven")

    if new.get("vol_ratio", 1.0) > 1.5:
        assess.append("heavy volume")
    elif new.get("vol_ratio", 1.0) < 0.7:
        assess.append("very quiet")

    if new["acceleration_signals"] and "near period low" in new["acceleration_signals"]:
        assess.append("at period low")

    lines.append(f"{' | '.join(assess)}")

    dc = new.get("daily_change_pct", 0)
    dc_emoji = "🟢" if dc >= 0 else "🔴"
    fd_emoji = "🟢" if new['change_pct'] >= 0 else "🔴"
    lines.append(f"• 💵 **${lp:.2f}**  |  {dc_emoji} Today **{dc:+.2f}%**  |  {fd_emoji} 5d **{new['change_pct']:+.2f}%**")

    # Position details
    if pnl_info:
        pnl = pnl_info["pnl"]
        pnl_pct = pnl_info["pnl_pct"]
        dist = pnl_info["dist_to_breakeven_pct"]
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        lines.append(f"• 📦 Position: {pnl_info['qty']} @ **${pnl_info['avg']:.2f}**")
        lines.append(f"• {pnl_emoji} 💰 P&L: **${pnl:,.0f} ({pnl_pct:+.1f}%)**  |  🎯 BE: **{dist:+.1f}%**")

    # Trend + volume + signals
    status_emoji = "📉" if new["is_downtrend"] else "📈"
    status = "**DOWN**" if new["is_downtrend"] else "**UP**"
    sigs = new.get("reversal_signals", []) + new.get("acceleration_signals", [])
    sig_str = f"  |  ⚠️ {', '.join(sigs)}" if sigs else ""

    vr = new['vol_ratio']
    if vr < 0.7:
        vol_desc = "low volume (quiet)"
    elif vr < 0.9:
        vol_desc = "light volume (below avg)"
    elif vr <= 1.1:
        vol_desc = "normal volume"
    elif vr <= 1.5:
        vol_desc = "elevated volume (active)"
    elif vr <= 2.5:
        vol_desc = "high volume (spike)"
    else:
        vol_desc = "very heavy volume (unusual)"

    avg_vol = new.get("avg_vol", 0)
    recent_vol = new.get("recent_vol", 0)
    lines.append(f"• {status_emoji} Status: {status}")
    lines.append(f"• 📊 Vol: **{vr:.2f}x** ({vol_desc})  |  Recent: {fmt_big(recent_vol)}  |  Avg: {fmt_big(avg_vol)}{sig_str}")

    # Change detection vs previous run
    if old:
        old_downtrend = old.get("is_downtrend", False)
        if old_downtrend and not new["is_downtrend"]:
            lines.append("🚨 **ALERT: Downtrend ending**")
        elif not old_downtrend and new["is_downtrend"]:
            lines.append("🚨 **ALERT: Downtrend beginning**")
        elif new["reversal_signals"] and not old.get("reversal_signals"):
            lines.append("🚨 **ALERT: Reversal signal**")
        elif new["acceleration_signals"] and not old.get("acceleration_signals"):
            lines.append("🚨 **ALERT: Downtrend accelerating**")

        # Position-level alerts
        if pnl_info:
            old_pnl = None
            old_lp = old.get("last_price")
            if old_lp:
                old_pnl_data = position_pnl(t, old_lp)
                if old_pnl_data:
                    old_pnl = old_pnl_data["pnl"]
            dist = pnl_info["dist_to_breakeven_pct"]
            pnl_pct = pnl_info["pnl_pct"]
            if old_pnl is not None and old_pnl > -10000 and pnl <= -10000:
                lines.append("🚨 **ALERT: Loss crossed -$10K**")
            if -2.0 <= dist < 0 and old:
                old_dist_data = position_pnl(t, old.get("last_price", lp))
                old_dist = old_dist_data["dist_to_breakeven_pct"] if old_dist_data else -999
                if old_dist < -2.0:
                    lines.append(f"🚨 **ALERT: Near breakeven ({dist:.1f}%)**")
            if old_pnl is not None:
                old_pnl_pct = old.get("_pnl_pct")
                if old_pnl_pct is not None and old_pnl_pct > -20 and pnl_pct <= -20:
                    lines.append("🚨 **ALERT: Loss exceeded -20%**")
        new["_pnl_pct"] = pnl_info["pnl_pct"] if pnl_info else None

    return "\n".join(lines)


def main():
    state = load_state()
    alerts = []
    any_error = False

    for ticker in TICKERS:
        new_data = analyze_ticker(ticker)
        if "error" in new_data:
            alerts.append(f"*{ticker}* ERROR: {new_data['error']}")
            any_error = True
            continue

        old_data = state.get(ticker)
        msg = format_alert(new_data, old_data)
        alerts.append(msg)
        state[ticker] = new_data

    save_state(state)

    # Print for cron delivery — clean Telegram format, no headers
    for i, a in enumerate(alerts):
        print(a)
        if i < len(alerts) - 1:
            print("---")
        else:
            print()

    # Exit code: 1 if errors so cron error-alert fires
    sys.exit(1 if any_error else 0)


if __name__ == "__main__":
    main()
