# stock-price

A lightweight, dependency-free Python CLI for fetching historical stock prices and OHLCV data from Yahoo Finance.

## Features

- **Zero dependencies** — pure Python 3.9+ stdlib
- **Multiple tickers** in one command
- **Flexible periods**: `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max`
- **Flexible intervals**: `1m`, `2m`, `5m`, `15m`, `30m`, `60m`, `90m`, `1h`, `1d`, `5d`, `1wk`, `1mo`, `3mo`
- **Table or JSON output** — human-readable or machine-parsable
- **Error-resilient** — invalid tickers print to stderr and continue

## Installation

```bash
git clone https://github.com/SohrabZ/stock-price.git
cd stock-price
chmod +x stock.py
```

## Usage

### Quick price check
```bash
./stock.py AAPL
```

### Multiple tickers, specific period
```bash
./stock.py PYPL MCHX OPEN --period 5d --interval 1d
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
```

### Full help
```bash
./stock.py --help
```

## Programmatic Use

Import the functions in another Python script:

```python
from stock import fetch_chart, parse_result

result = fetch_chart("NVDA", "1mo", "1d")
meta, bars = parse_result(result)

for bar in bars:
    print(bar["date"], bar["close"])
```

## Tests

```bash
python3 -m pytest test_stock.py -v
```

## Example Output

```
AAPL  —  Apple Inc.
Exchange: NMS  |  Currency: USD
----------------------------------------------------------------------
Date               Open       High        Low      Close       Volume
----------------------------------------------------------------------
2026-07-10   314.72     316.91     312.17     315.32   34,132,300
2026-07-13   317.02     323.45     315.78     317.31   43,257,800
2026-07-14   313.76     316.19     311.91     314.86   36,336,800
2026-07-15   317.62     328.73     317.32     327.50   60,884,500
2026-07-16   328.01     333.55     326.79     332.58   29,725,285
----------------------------------------------------------------------
Period change: $+17.26 (+5.47%)
```

## Limitations

- Uses Yahoo Finance's unofficial API (no API key needed, but subject to rate limits)
- SSL verification is relaxed for macOS compatibility — **do not use this pattern for authenticated endpoints**
- Pre/post market data is not separately surfaced

## License

MIT
