# stock-price

A lightweight Python CLI for fetching historical stock prices, volume, and OHLCV data from Yahoo Finance. Supports intraday ticks, daily/weekly/monthly bars, JSON export, and candlestick charts with volume panels.

## Features

- **Zero core dependencies** — pure Python 3.9+ stdlib (matplotlib optional for charts)
- **Intraday ticks** — 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h intervals
- **Daily/weekly/monthly** — 1d, 5d, 1wk, 1mo, 3mo intervals
- **Flexible periods** — 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
- **Volume stats in CLI** — avg volume and volume change % printed in table output
- **Dual-panel charts** — price candlesticks + volume bars (green/red)
- **Smart x-axis labels** — HH:MM for intraday, MM/DD for daily
- **Table or JSON output** — human-readable or machine-parsable
- **Error-resilient** — invalid tickers print to stderr and continue

## Installation

```bash
git clone https://github.com/SohrabZ/stock-price.git
cd stock-price
chmod +x stock.py

# Optional: for chart generation
pip install matplotlib
```

## Usage

### Quick price check (1 day)
```bash
./stock.py AAPL
```

### Multiple tickers, 5-day history
```bash
./stock.py PYPL MCHX OPEN --period 5d --interval 1d
```

### Intraday ticks (1-minute bars)
```bash
./stock.py NVDA --period 1d --interval 1m
```

### JSON output
```bash
./stock.py TSLA --period 1mo --format json --output tsla.json
```

### Generate a chart (requires matplotlib)
```bash
# Auto-save to /tmp/<ticker>_chart.png
./stock.py NVDA --period 1mo --graph

# Custom output path
./stock.py AAPL --period 5d --graph --graph-output ~/Desktop/aapl.png

# Intraday chart with hourly x-axis labels
./stock.py NVDA --period 1d --interval 15m --graph
```

### Full help
```bash
./stock.py --help
```

## CLI Output

Table output includes price data **and** volume statistics:

```
NVDA  —  NVIDIA Corporation
Exchange: NMS  |  Currency: USD
----------------------------------------------------------------------
Date               Open       High        Low      Close       Volume
----------------------------------------------------------------------
2026-07-10   210.26     211.08     205.85     206.73   67,417,317
2026-07-13   208.54     210.57     203.00     203.53  121,411,000
2026-07-14   208.20     212.55     203.80     211.80  124,379,600
2026-07-15   211.96     213.81     206.04     212.50  124,482,600
2026-07-16   210.26     211.08     205.85     206.73   67,417,317
----------------------------------------------------------------------
Period change: $-4.23 (-2.01%)
Avg volume:  117,222,303
Volume change: -81,003,683 (-54.6%)
```

## Chart Features

Charts are dual-panel PNGs:
- **Top:** Candlestick price chart (green = up, red = down)
- **Bottom:** Volume bars matching daily colors
- **X-axis:** HH:MM for intraday, MM/DD for daily

## Programmatic Use

Import the functions in another Python script:

```python
from stock import fetch_chart, parse_result, generate_graph

result = fetch_chart("NVDA", "1mo", "1d")
meta, bars = parse_result(result)

# Print volume stats
for bar in bars:
    print(bar["date"], bar["close"], bar["volume"])

# Generate chart
generate_graph("NVDA", meta, bars, output_path="nvda.png")
```

## Tests

```bash
python3 -m pytest test_stock.py -v
```

## Limitations

- Uses Yahoo Finance's unofficial API (no API key needed, but subject to rate limits)
- SSL verification is relaxed for macOS compatibility — **do not use this pattern for authenticated endpoints**
- Pre/post market data is not separately surfaced

## License

MIT
