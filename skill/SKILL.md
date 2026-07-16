---
name: stock-price
version: 1.1.0
description: Fetch historical stock prices, volume, and OHLCV data from Yahoo Finance. Supports intraday ticks, candlestick charts with volume panels, and JSON export.
category: data-science
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [finance, yahoo-finance, stocks, cli, data-science]
    related_skills: []
---

# stock-price

Fetch historical stock prices, OHLCV data, and candlestick charts from Yahoo Finance via a lightweight CLI. Supports multiple tickers, configurable periods/intervals, volume statistics, dual-panel chart generation, and smart x-axis labels.

## When to use

- Need a quick price check for one or more tickers with volume stats.
- Want historical OHLCV bars for a specific period (e.g., last 5 days, 1 year, YTD).
- Need intraday tick data (1m, 5m, 15m intervals) for a given day.
- Building a watchlist report or cron job that delivers price summaries on a schedule.
- Need JSON output piped into another script or saved to a file.
- Want to generate dual-panel candlestick + volume charts as PNG images.
- Comparing price changes with volume trends to spot unusual trading activity.

No external dependencies beyond Python 3.8+ stdlib for the core CLI. To generate charts, install matplotlib:

```bash
pip install matplotlib
```

## CLI Usage

```bash
# Default: last trading day, daily candles
python3 scripts/stock.py AAPL

# Multiple tickers, 1-month period, weekly bars
python3 scripts/stock.py AAPL MSFT GOOGL --period 1mo --interval 1wk

# Intraday ticks (1-minute bars)
python3 scripts/stock.py NVDA --period 1d --interval 1m

# JSON output (for piping / saving)
python3 scripts/stock.py TSLA --period 5d --format json --output tsla.json

# Full help
python3 scripts/stock.py --help
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `tickers` | One or more ticker symbols (positional) | — |
| `-p, --period` | Time range: `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max` | `1d` |
| `-i, --interval` | Candle size: `1m`, `2m`, `5m`, `15m`, `30m`, `60m`, `90m`, `1h`, `1d`, `5d`, `1wk`, `1mo`, `3mo` | `1d` |
| `-f, --format` | Output format: `table` or `json` | `table` |
| `-g, --graph` | Generate a PNG candlestick/line chart (requires `matplotlib`) | — |
| `--graph-output` | Custom path for the PNG chart (requires `--graph`) | system temp dir |

### Chart output

```bash
# Auto-save chart to /tmp/nvda_chart.png
python3 scripts/stock.py NVDA --period 1mo --graph

# Custom chart path
python3 scripts/stock.py AAPL --period 5d --graph --graph-output ~/Desktop/aapl.png

# Intraday chart with hourly x-axis labels
python3 scripts/stock.py NVDA --period 1d --interval 15m --graph
```

## Programmatic Usage

Import the functions in another Python script:

```python
from scripts.stock import fetch_chart, parse_result, generate_graph

result = fetch_chart("NVDA", "1mo", "1d")
meta, bars = parse_result(result)

# Print volume stats
for bar in bars:
    print(bar["date"], bar["close"], bar["volume"])

# Generate chart
generate_graph("NVDA", meta, bars, period="1mo", output_path="nvda.png")
```

## CLI Output

Table output includes price data **and** volume statistics:

```
NVDA  --  NVIDIA Corporation
Exchange: NMS  |  Currency: USD
----------------------------------------------------------------------
Date               Open       High        Low      Close       Volume
----------------------------------------------------------------------
2026-07-10   210.26     211.08     205.85     210.96  148,421,000
2026-07-13   208.54     210.57     203.00     203.53  121,411,000
2026-07-14   208.20     212.55     203.80     211.80  124,379,600
2026-07-15   211.96     213.81     206.04     212.50  124,482,600
2026-07-16   210.26     211.08     205.85     206.76   74,595,599
----------------------------------------------------------------------
Period change: $-4.21 (-1.99%)
Avg volume:  118,657,959
Volume change: -73,825,401 (-49.7%)
```

## Chart Features

Charts are dual-panel PNGs:
- **Top:** Candlestick price chart (green = up, red = down)
- **Bottom:** Volume bars matching daily colors
- **X-axis:** Smart 7-tier format based on actual date span:
  - HH:MM for intraday (`--period 1d`)
  - MM/DD for short-term (up to 31 days)
  - Mon for medium-term (1-6 months)
  - Mon 'YY for ~1-5 years
  - Mon YYYY for 5+ years

## Tests

Run the test suite with pytest:

```bash
cd ~/.hermes/skills/data-science/stock-price/scripts
python3 -m pytest test_stock.py -v
```

## Cron / Automation Example

Deliver a daily watchlist briefing:

```bash
hermes cron create \
  --schedule "0 16 * * 1-5" \
  --name "market-close-watchlist" \
  --prompt "Run the stock-price skill to fetch AAPL, TSLA, NVDA for period=1d, format=json, and summarize biggest movers in a concise Telegram message." \
  --skills stock-price
```

## Pitfalls

- **SSL on macOS**: The CLI attempts verified SSL first, and only falls back to unverified SSL when the specific error is `CERTIFICATE_VERIFY_FAILED` (common on macOS systems with incomplete Python cert bundles). Data is read-only from Yahoo Finance — this is low-risk, but do not use this pattern for authenticated endpoints.
- **User-Agent required**: Yahoo Finance rejects requests without a realistic `User-Agent` header and returns an empty body. The CLI includes a WebKit/macOS-style header; if adapting the code, preserve this header or requests will fail with a JSON decode error on empty response.
- **matplotlib backend in headless/cron mode**: The CLI sets `matplotlib.use("Agg")` before importing pyplot to avoid "no display name" crashes on headless servers or when running via cron. If you adapt the chart code into another script, always set the backend before any pyplot import.
- **Adaptive bar width in matplotlib**: Fixed `width=0.6` means 0.6 **days** (14.4 hours), causing massive overlap on 1-minute intraday charts. The CLI now computes width from actual minimum bar interval: `(min_interval_seconds * 0.8) / 86400`. For 1m data this produces ~0.00056 days (48 seconds), creating properly separated bars. If adapting the code, always compute bar width from data density, never hardcode.
- **Opening auction volume spike**: The first minute of trading often has 5-10x normal volume, squashing all other volume bars. The CLI detects this (first bar > 10x median of rest), skips it from the volume chart, and adds an annotation showing the exact opening volume. When building charts for other assets, always handle opening auction outliers.
- **Single-bar period change (1d)**: When `--period 1d` is used there is only one OHLC bar, so `first_close == last_close`. The CLI falls back to `chartPreviousClose` from Yahoo metadata to show the change since yesterday's close. If adapting the code, handle `len(bars) == 1` explicitly.
- **Hour labels only for intraday**: Use HH:MM x-axis labels **only** for `--period 1d` intraday charts. On multi-day charts (5d, 1mo, etc.) hour labels are unreadable — use MM/DD dates instead. The CLI detects this via `period == "1d"` combined with non-midnight timestamps.
- **Invalid tickers**: Yahoo returns a structured error for delisted/invalid symbols. The CLI prints an `ERROR` line to stderr and continues with remaining tickers.
- **Rate limits**: Yahoo Finance is unofficial and rate-limits aggressively. Do not hammer it in tight loops. For production workloads, consider a paid data provider (IEX Cloud, Polygon, Alpaca).

## Skill / Repo Sync

This skill is backed by a public GitHub repo. Any update to the skill files must be pushed to the repo to stay in sync:

```bash
cd ~/Codes/stock-price   # canonical clone
git pull origin main
cp ~/.hermes/skills/data-science/stock-price/scripts/* .
git commit -am "fix: description"
git push origin main
```

## Reference Files

| File | Topic |
|------|-------|
| `references/candlestick-chart.md` | Chart rendering, color scheme, headless/cron safety |
| `references/chart-rendering.md` | Adaptive bar widths, figure sizing, matplotlib best practices |
| `references/intraday-intervals.md` | Interval constraints, max period per interval, data volume notes |
| `references/repo-sync-workflow.md` | How to keep skill files and GitHub repo in sync after edits |
| `references/smart-xaxis-labels.md` | Period-aware x-axis label selection (HH:MM / MM/DD / Mon / Mon 'YY / Mon YYYY) |
| `references/volume-statistics.md` | How volume stats are calculated and displayed in CLI output |

## File Layout

In this repo:
```
stock-price/
├── skill/
│   ├── SKILL.md              # This file - Hermes skill manifest
│   ├── GUIDE.md              # Agent quick-reference
│   └── references/
│       ├── candlestick-chart.md
│       ├── chart-rendering.md
│       ├── intraday-intervals.md
│       ├── repo-sync-workflow.md
│       ├── smart-xaxis-labels.md
│       └── volume-statistics.md
├── stock.py                  # CLI + library
├── test_stock.py             # pytest suite
├── README.md                 # User documentation
└── screenshots/              # Chart examples
```

When installed as a Hermes skill:
```
~/.hermes/skills/data-science/stock-price/
├── SKILL.md
├── GUIDE.md
├── references/
│   ├── candlestick-chart.md
│   ├── chart-rendering.md
│   ├── intraday-intervals.md
│   ├── repo-sync-workflow.md
│   ├── smart-xaxis-labels.md
│   └── volume-statistics.md
└── scripts/
    ├── stock.py
    └── test_stock.py
```