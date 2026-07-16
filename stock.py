#!/usr/bin/env python3
"""stock.py -- fetch historical stock prices from Yahoo Finance."""

import argparse
import json
import os
import re
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_OK = True
except Exception:
    MATPLOTLIB_OK = False

API_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

VALID_RANGES = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
VALID_INTERVALS = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]

# Chart constants
CHART_DPI = 150
FIG_SIZE = (10, 7)
PRICE_VOLUME_RATIO = [3, 1]
UP_COLOR = "#26a69a"
DOWN_COLOR = "#ef5350"
LINE_COLOR = "#26a69a"
BAR_WIDTH_FRACTION = 0.8
SECONDS_PER_DAY = 86400
AUCTION_SPIKE_FACTOR = 10
REQUEST_TIMEOUT = 30
TICKER_RE = re.compile(r"^[A-Za-z0-9.-]+$")


def _validate_ticker(ticker: str) -> str:
    """Validate and normalize a ticker symbol."""
    sym = ticker.strip().upper()
    if not TICKER_RE.match(sym):
        raise ValueError(f"Invalid ticker symbol: {ticker!r}")
    return sym


def fetch_chart(ticker: str, period: str, interval: str, prepost: bool = False):
    """Fetch chart data from Yahoo Finance."""
    url = API_BASE.format(ticker=ticker)
    params = f"?interval={interval}&range={period}"
    if prepost:
        params += "&includePrePost=true"
    req = urllib.request.Request(url + params, headers=DEFAULT_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise ValueError("Rate limited by Yahoo Finance. Please wait and try again.")
        raise ValueError(f"HTTP {e.code} from Yahoo Finance for {ticker}: {e.reason}")
    except urllib.error.URLError as e:
        # On macOS, Python's bundled cert bundle may be incomplete.
        # Fall back to unverified SSL only for CERTIFICATE_VERIFY_FAILED.
        if "CERTIFICATE_VERIFY_FAILED" in str(e.reason):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx) as resp:
                    data = json.load(resp)
            except urllib.error.URLError as e2:
                raise ValueError(f"Network error fetching {ticker} (SSL fallback also failed): {e2.reason}")
        else:
            raise ValueError(f"Network error fetching {ticker}: {e.reason}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON response from Yahoo Finance for {ticker}")

    result = data.get("chart", {}).get("result", [])
    if not result:
        error = data.get("chart", {}).get("error", {})
        raise ValueError(f"Yahoo Finance error for {ticker}: {error.get('description', 'unknown error')}")
    return result[0]


def parse_result(result):
    """Parse chart result into list of daily bars."""
    meta = result.get("meta", {})
    timestamps = result.get("timestamp", [])
    indicators = result.get("indicators", {})
    quotes = indicators.get("quote", [])
    if not quotes:
        return meta, []
    quote = quotes[0]
    adjclose_list = indicators.get("adjclose", [])
    adjclose = adjclose_list[0].get("adjclose", []) if adjclose_list else []

    opens = quote.get("open", [])
    highs = quote.get("high", [])
    lows = quote.get("low", [])
    closes = quote.get("close", [])
    volumes = quote.get("volume", [])

    bars = []
    for i, ts in enumerate(timestamps):
        if ts is None:
            continue
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        bar = {
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%S"),
            "open": opens[i] if i < len(opens) else None,
            "high": highs[i] if i < len(highs) else None,
            "low": lows[i] if i < len(lows) else None,
            "close": closes[i] if i < len(closes) else None,
            "volume": volumes[i] if i < len(volumes) else None,
            "adj_close": adjclose[i] if i < len(adjclose) else None,
        }
        bars.append(bar)
    return meta, bars


def _fmt_price(v):
    """Format a price value or return 'N/A' if None."""
    return f"{v:.2f}" if v is not None else "N/A"


def _display_name(meta):
    """Get the display name from metadata."""
    return meta.get("shortName") or meta.get("longName") or "N/A"


def print_table(ticker, meta, bars):
    """Print human-readable table."""
    currency = meta.get("currency", "USD")
    print(f"\n{ticker}  --  {_display_name(meta)}")
    print(f"Exchange: {meta.get('exchangeName', 'N/A')}  |  Currency: {currency}")
    print("-" * 70)

    # Check if we have intraday data (non-midnight times)
    is_intraday = any(b.get("time") and b["time"] != "00:00:00" for b in bars)

    if is_intraday:
        print(f"{'Date':12} {'Time':8} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>12}")
    else:
        print(f"{'Date':12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>12}")
    print("-" * 70)
    for bar in bars:
        vol = f"{int(bar['volume']):,}" if bar.get("volume") is not None else "N/A"
        if is_intraday:
            print(
                f"{bar['date']:12} "
                f"{bar['time'][:8]:8} "
                f"{_fmt_price(bar['open']):>10} "
                f"{_fmt_price(bar['high']):>10} "
                f"{_fmt_price(bar['low']):>10} "
                f"{_fmt_price(bar['close']):>10} "
                f"{vol:>12}"
            )
        else:
            print(
                f"{bar['date']:12} "
                f"{_fmt_price(bar['open']):>10} "
                f"{_fmt_price(bar['high']):>10} "
                f"{_fmt_price(bar['low']):>10} "
                f"{_fmt_price(bar['close']):>10} "
                f"{vol:>12}"
            )
    print("-" * 70)
    if len(bars) >= 2:
        first_close = bars[0].get("close")
        last_close = bars[-1].get("close")
    elif len(bars) == 1:
        last_close = bars[0].get("close")
        first_close = meta.get("chartPreviousClose")
    else:
        first_close = last_close = None

    if first_close is not None and last_close is not None and first_close != 0:
        change = last_close - first_close
        pct = (change / first_close) * 100
        print(f"Period change: ${change:+.2f} ({pct:+.2f}%)")

    # Volume stats
    volumes = [b["volume"] for b in bars if b.get("volume") is not None]
    if volumes:
        avg_vol = sum(volumes) / len(volumes)
        print(f"Avg volume:  {int(avg_vol):,}")
        if len(volumes) >= 2:
            vol_change = volumes[-1] - volumes[0]
            vol_pct = (vol_change / volumes[0]) * 100 if volumes[0] else 0
            print(f"Volume change: {int(vol_change):+,} ({vol_pct:+.1f}%)")

    # Extended hours note
    has_prepost = meta.get("hasPrePostMarketData")
    if has_prepost:
        periods = meta.get("currentTradingPeriod", {})
        pre = periods.get("pre") or {}
        post = periods.get("post") or {}
        # Guard against missing/None timestamps
        ts_keys = [pre.get("start"), pre.get("end"), post.get("start"), post.get("end")]
        if all(isinstance(ts, (int, float)) for ts in ts_keys):
            def _et(ts):
                t = time.localtime(ts)
                return f"{t.tm_hour:02d}:{t.tm_min:02d}"
            print(f"Pre-market: {_et(ts_keys[0])} - {_et(ts_keys[1])} ET  |  After-hours: {_et(ts_keys[2])} - {_et(ts_keys[3])} ET")


def _bar_color(bar):
    """Return up/down color for a bar based on open vs close."""
    if bar["close"] is None or bar["open"] is None:
        return UP_COLOR  # neutral for incomplete bars
    return UP_COLOR if bar["close"] >= bar["open"] else DOWN_COLOR


def _draw_candles(ax, bars, dates):
    """Draw candlesticks on the price axis."""
    for i, bar in enumerate(bars):
        if bar["close"] is None or bar["open"] is None or bar["high"] is None or bar["low"] is None:
            continue
        color = _bar_color(bar)
        ax.plot([dates[i], dates[i]], [bar["low"], bar["high"]], color=color, linewidth=1)
        ax.plot([dates[i], dates[i]], [bar["open"], bar["close"]], color=color, linewidth=4, solid_capstyle="butt")


def _configure_xaxis(ax, dates, is_intraday):
    """Configure smart x-axis labels based on date range."""
    if len(dates) > 1:
        date_range_days = (dates[-1] - dates[0]).days
    else:
        date_range_days = 0

    if is_intraday or date_range_days <= 1:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, len(dates) // 8)))
    elif date_range_days <= 31:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        interval = max(1, date_range_days // 6)
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))
    elif date_range_days <= 180:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    elif date_range_days <= 400:
        spans_years = dates[0].year != dates[-1].year
        fmt = "%b '%y" if spans_years else "%b"
        ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    elif date_range_days <= 800:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    elif date_range_days <= 1800:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        year_span = date_range_days / 365
        if year_span <= 10:
            interval = 12
        elif year_span <= 20:
            interval = 18
        else:
            interval = 24
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=interval))


def _draw_volume(ax, bars, dates):
    """Draw volume bars with adaptive width."""
    # Coerce None volumes to 0 for matplotlib
    volumes = [b["volume"] if b["volume"] is not None else 0 for b in bars]
    colors = [_bar_color(b) for b in bars]

    # Compute adaptive width
    if len(dates) > 1:
        intervals = [(dates[i + 1] - dates[i]).total_seconds() for i in range(len(dates) - 1)]
        min_interval = min(intervals) if intervals else SECONDS_PER_DAY
        width_days = (min_interval * BAR_WIDTH_FRACTION) / SECONDS_PER_DAY
    else:
        width_days = 0.02

    # Skip opening auction spike
    skip_first = False
    if len(volumes) > 2:
        first_vol = volumes[0]
        rest = sorted(volumes[1:])
        rest_median = rest[len(rest) // 2] if len(rest) % 2 == 1 else (rest[len(rest) // 2 - 1] + rest[len(rest) // 2]) / 2
        if first_vol > AUCTION_SPIKE_FACTOR * rest_median:
            skip_first = True
            ax.annotate(f"Open auction: {int(first_vol):,}", xy=(0.02, 0.95), xycoords="axes fraction",
                        fontsize=9, ha="left", va="top", color="#888888",
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#cccccc", alpha=0.9))

    start_idx = 1 if skip_first else 0
    ax.bar(dates[start_idx:], volumes[start_idx:], color=colors[start_idx:], width=width_days)

    ax.set_ylabel("Volume")
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def generate_graph(ticker, meta, bars, period=None, output_path=None):
    """Render a candlestick/line chart from bars."""
    if not MATPLOTLIB_OK:
        raise RuntimeError("matplotlib is not installed. Run: pip install matplotlib")
    if not bars:
        raise ValueError("No data to graph")

    dates = [datetime.strptime(f"{b['date']} {b['time']}", "%Y-%m-%d %H:%M:%S") for b in bars]
    is_intraday = period == "1d" and any(d.hour != 0 or d.minute != 0 for d in dates)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=FIG_SIZE, gridspec_kw={"height_ratios": PRICE_VOLUME_RATIO}, sharex=True)

    try:
        # Price chart
        if len(bars) > 1 and all(b["high"] is not None and b["low"] is not None for b in bars):
            _draw_candles(ax1, bars, dates)
        else:
            closes = [b["close"] for b in bars if b["close"] is not None]
            valid_dates = [d for d, b in zip(dates, bars) if b["close"] is not None]
            ax1.plot(valid_dates, closes, color=LINE_COLOR, linewidth=2)

        ax1.set_title(f"{ticker}  --  {_display_name(meta)}", fontsize=14)
        ax1.set_ylabel(f"Price ({meta.get('currency', 'USD')})")
        ax1.grid(True, alpha=0.3)
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)

        # Volume chart
        if any(b["volume"] is not None for b in bars):
            _draw_volume(ax2, bars, dates)

        # X-axis labels
        _configure_xaxis(ax2, dates, is_intraday)

        fig.autofmt_xdate()
        fig.tight_layout()

        path = output_path or os.path.join(tempfile.gettempdir(), f"{ticker.lower()}_chart.png")
        fig.savefig(path, dpi=CHART_DPI, bbox_inches="tight")
        print(f"Graph saved to {path}", file=sys.stderr)
    finally:
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Fetch stock prices from Yahoo Finance.")
    parser.add_argument("tickers", nargs="+", help="Stock ticker symbols (e.g., AAPL MSFT)")
    parser.add_argument("-p", "--period", default="1d", choices=VALID_RANGES,
                        help="Time period (default: 1d)")
    parser.add_argument("-i", "--interval", default="1d", choices=VALID_INTERVALS,
                        help="Candle interval (default: 1d)")
    parser.add_argument("-f", "--format", default="table", choices=["table", "json"],
                        help="Output format (default: table)")
    parser.add_argument("-o", "--output", help="Write JSON output to file")
    parser.add_argument("-g", "--graph", action="store_true",
                        help="Generate a PNG chart (requires matplotlib)")
    parser.add_argument("--graph-output", help="Custom path for the PNG chart")
    parser.add_argument("--prepost", action="store_true",
                        help="Include pre-market and after-hours data (1d intraday only)")
    args = parser.parse_args()

    all_data = {}
    has_errors = False
    for ticker in args.tickers:
        try:
            sym = _validate_ticker(ticker)
            result = fetch_chart(sym, args.period, args.interval, prepost=args.prepost)
            meta, bars = parse_result(result)
            all_data[sym] = {"meta": meta, "bars": bars}

            if args.format == "table":
                print_table(sym, meta, bars)
            if args.graph:
                try:
                    generate_graph(sym, meta, bars, period=args.period, output_path=args.graph_output)
                except Exception as ge:
                    print(f"ERROR generating graph for {sym}: {ge}", file=sys.stderr)
                    has_errors = True

        except ValueError as e:
            print(f"ERROR fetching {ticker.upper()}: {e}", file=sys.stderr)
            all_data[ticker.upper()] = {"error": str(e)}
            has_errors = True

    if args.format == "json":
        payload = json.dumps(all_data, indent=2, default=str)
        if args.output:
            try:
                with open(args.output, "w") as f:
                    f.write(payload)
                print(f"JSON written to {args.output}")
            except OSError as e:
                print(f"ERROR writing JSON to {args.output}: {e}", file=sys.stderr)
                has_errors = True
        else:
            print(payload)

    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
