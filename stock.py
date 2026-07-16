#!/usr/bin/env python3
"""stock.py — fetch historical stock prices from Yahoo Finance."""

import argparse
import json
import os
import ssl
import sys
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


def fetch_chart(ticker: str, period: str, interval: str):
    """Fetch chart data from Yahoo Finance."""
    url = API_BASE.format(ticker=ticker)
    params = f"?interval={interval}&range={period}"
    req = urllib.request.Request(url + params, headers=DEFAULT_HEADERS)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        data = json.load(resp)
    result = data.get("chart", {}).get("result", [])
    if not result:
        error = data.get("chart", {}).get("error", {})
        raise ValueError(f"Yahoo Finance error for {ticker}: {error.get('description', 'unknown error')}")
    return result[0]


def parse_result(result):
    """Parse chart result into list of daily bars."""
    meta = result["meta"]
    timestamps = result.get("timestamp", [])
    indicators = result["indicators"]
    quote = indicators["quote"][0]
    adjclose_list = indicators.get("adjclose", [])
    adjclose = adjclose_list[0].get("adjclose", []) if adjclose_list else []

    bars = []
    for i, ts in enumerate(timestamps):
        if ts is None:
            continue
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        bar = {
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%S"),
            "open": quote.get("open", [])[i] if i < len(quote.get("open", [])) else None,
            "high": quote.get("high", [])[i] if i < len(quote.get("high", [])) else None,
            "low": quote.get("low", [])[i] if i < len(quote.get("low", [])) else None,
            "close": quote.get("close", [])[i] if i < len(quote.get("close", [])) else None,
            "volume": quote.get("volume", [])[i] if i < len(quote.get("volume", [])) else None,
            "adj_close": adjclose[i] if i < len(adjclose) else None,
        }
        bars.append(bar)
    return meta, bars


def print_table(ticker, meta, bars):
    """Print human-readable table."""
    currency = meta.get("currency", "USD")
    print(f"\n{ticker}  —  {meta.get('shortName', meta.get('longName', 'N/A'))}")
    print(f"Exchange: {meta.get('exchangeName', 'N/A')}  |  Currency: {currency}")
    print("-" * 70)
    print(f"{'Date':12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>12}")
    print("-" * 70)
    for bar in bars:
        vol = f"{int(bar['volume']):,}" if bar.get("volume") is not None else "N/A"
        print(
            f"{bar['date']:12} "
            f"{bar['open'] or 'N/A':>10} "
            f"{bar['high'] or 'N/A':>10} "
            f"{bar['low'] or 'N/A':>10} "
            f"{bar['close'] or 'N/A':>10} "
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

    if first_close and last_close:
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


def generate_graph(ticker, meta, bars, output_path=None):
    """Render a candlestick/line chart from bars."""
    if not MATPLOTLIB_OK:
        raise RuntimeError("matplotlib is not installed. Run: pip install matplotlib")
    if not bars:
        raise ValueError("No data to graph")

    dates = [datetime.strptime(b["date"], "%Y-%m-%d") for b in bars if b["date"]]
    closes = [b["close"] for b in bars if b["close"] is not None]
    volumes = [b["volume"] for b in bars if b["volume"] is not None]
    highs = [b["high"] for b in bars if b["high"] is not None]
    lows = [b["low"] for b in bars if b["low"] is not None]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), gridspec_kw={"height_ratios": [3, 1]}, sharex=True)

    # Price chart
    if len(bars) > 1 and all(h is not None for h in highs) and all(l is not None for l in lows):
        for i, bar in enumerate(bars):
            if bar["close"] is None or bar["open"] is None or bar["high"] is None or bar["low"] is None:
                continue
            color = "#26a69a" if bar["close"] >= bar["open"] else "#ef5350"
            ax1.plot([dates[i], dates[i]], [bar["low"], bar["high"]], color=color, linewidth=1)
            ax1.plot([dates[i], dates[i]], [bar["open"], bar["close"]], color=color, linewidth=4, solid_capstyle="butt")
    else:
        ax1.plot(dates, closes, color="#26a69a", linewidth=2)

    ax1.set_title(f"{ticker}  —  {meta.get('shortName', meta.get('longName', ''))}", fontsize=14)
    ax1.set_ylabel(f"Price ({meta.get('currency', 'USD')})")
    ax1.grid(True, alpha=0.3)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Volume chart
    if volumes:
        colors = ["#26a69a" if b["close"] and b["open"] and b["close"] >= b["open"] else "#ef5350" for b in bars]
        ax2.bar(dates[:len(volumes)], volumes, color=colors, width=0.6)
        ax2.set_ylabel("Volume")
        ax2.grid(True, alpha=0.3)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 6)))
    fig.autofmt_xdate()
    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Graph saved to {output_path}")
    else:
        tmp_path = f"/tmp/{ticker.lower()}_chart.png"
        fig.savefig(tmp_path, dpi=150, bbox_inches="tight")
        print(f"Graph saved to {tmp_path}")

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
    args = parser.parse_args()

    all_data = {}
    for ticker in args.tickers:
        try:
            result = fetch_chart(ticker.upper(), args.period, args.interval)
            meta, bars = parse_result(result)
            all_data[ticker.upper()] = {"meta": meta, "bars": bars}

            if args.format == "table":
                print_table(ticker.upper(), meta, bars)
            if args.graph:
                try:
                    generate_graph(ticker.upper(), meta, bars, output_path=args.graph_output)
                except Exception as ge:
                    print(f"ERROR generating graph for {ticker.upper()}: {ge}", file=sys.stderr)
            # json printed after loop if requested

        except Exception as e:
            print(f"ERROR fetching {ticker.upper()}: {e}", file=sys.stderr)
            all_data[ticker.upper()] = {"error": str(e)}

    if args.format == "json":
        payload = json.dumps(all_data, indent=2, default=str)
        if args.output:
            with open(args.output, "w") as f:
                f.write(payload)
            print(f"JSON written to {args.output}")
        else:
            print(payload)


if __name__ == "__main__":
    main()
