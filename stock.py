#!/usr/bin/env python3
"""stock.py — fetch historical stock prices from Yahoo Finance."""

import argparse
import json
import ssl
import sys
import urllib.request
from datetime import datetime, timezone

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
        # Single-bar period (e.g., 1d): compare against previous close from meta
        last_close = bars[0].get("close")
        first_close = meta.get("chartPreviousClose")
    else:
        first_close = last_close = None

    if first_close and last_close:
        change = last_close - first_close
        pct = (change / first_close) * 100
        print(f"Period change: ${change:+.2f} ({pct:+.2f}%)")


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
    args = parser.parse_args()

    all_data = {}
    for ticker in args.tickers:
        try:
            result = fetch_chart(ticker.upper(), args.period, args.interval)
            meta, bars = parse_result(result)
            all_data[ticker.upper()] = {"meta": meta, "bars": bars}

            if args.format == "table":
                print_table(ticker.upper(), meta, bars)
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
