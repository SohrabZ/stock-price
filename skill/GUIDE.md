---
name: stock-cli-guide
version: 1.0.0
description: Guide for AI agents using the stock-price CLI effectively
category: data-science
author: Hermes Agent
---

# stock-cli-guide

Best practices for AI agents using the stock-price CLI to fetch market data and generate charts.

## Quick Reference

```bash
# Basic price check
python3 ~/Codes/stock-price/stock.py <TICKER>

# With period and interval
python3 ~/Codes/stock-price/stock.py <TICKER> --period <PERIOD> --interval <INTERVAL>

# Generate chart
python3 ~/Codes/stock-price/stock.py <TICKER> --period <PERIOD> --graph

# Multiple tickers
python3 ~/Codes/stock-price/stock.py AAPL MSFT GOOGL --period 5d
```

## Period vs Interval Matrix

| Period | Recommended Interval | Use Case |
|--------|---------------------|----------|
| `1d` | `1m`, `5m`, `15m`, `30m`, `1h` | Intraday analysis, day trading |
| `5d` | `1h`, `1d` | Short-term swing analysis |
| `1mo` | `1d` | Monthly performance review |
| `3mo` | `1d`, `1wk` | Quarterly trend analysis |
| `6mo` | `1wk`, `1mo` | Half-year performance |
| `1y` | `1mo` | Annual performance |
| `ytd` | `1d`, `1wk` | Year-to-date tracking |

## Common Patterns

### 1. Daily Market Summary
```bash
python3 ~/Codes/stock-price/stock.py AAPL MSFT NVDA TSLA --period 1d --interval 1d
```
Shows: Open, High, Low, Close, Volume, Period change, Avg volume

### 2. Intraday Analysis
```bash
python3 ~/Codes/stock-price/stock.py NVDA --period 1d --interval 5m --graph
```
Shows: Minute-by-minute price action with HH:MM x-axis labels

### 3. Weekly Performance with Chart
```bash
python3 ~/Codes/stock-price/stock.py AAPL --period 5d --interval 1d --graph --graph-output /tmp/aapl_week.png
```
Shows: 5-day candlesticks with MM/DD dates and volume panel

### 4. Monthly Trend
```bash
python3 ~/Codes/stock-price/stock.py SPY --period 1mo --interval 1d --graph
```
Shows: Monthly price action with clean date labels

### 5. JSON for Processing
```bash
python3 ~/Codes/stock-price/stock.py AAPL --period 1mo --format json --output aapl.json
```

## Interpreting Output

### Table Columns
- **Date**: Trading date (or time for intraday)
- **Open**: First traded price
- **High**: Highest price
- **Low**: Lowest price
- **Close**: Last traded price
- **Volume**: Shares traded

### Summary Lines
- **Period change**: $ change and % change from first to last bar
- **Avg volume**: Average shares traded per period
- **Volume change**: Volume trend (last vs first bar)

### Chart Output
- **Top panel**: Candlesticks (green = up, red = down)
- **Bottom panel**: Volume bars matching candle colors
- **X-axis**: HH:MM for intraday, MM/DD for daily+

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `CERTIFICATE_VERIFY_FAILED` | macOS SSL issue | Already handled in CLI |
| `matplotlib not installed` | Missing chart dependency | `pip install matplotlib` |
| `No data found` | Invalid/delisted ticker | Check ticker symbol |
| Empty JSON response | Missing User-Agent | Already handled in CLI |

## Best Practices

1. **Install skill for agents**: Copy `skill/` to `~/.hermes/skills/data-science/stock-price/` or `.claude/skills/`
2. **Rate limiting**: Don't run rapid-fire requests; Yahoo limits aggressively
3. **Period/interval compatibility**: Don't use `1m` interval with `1mo` period (too many bars)
4. **Chart paths**: Default saves to `/tmp/<ticker>_chart.png`; use `--graph-output` for custom paths
5. **Volume context**: Always check volume stats alongside price changes for confirmation

## One-Liners for Common Tasks

```bash
# Quick price + change
python3 ~/Codes/stock-price/stock.py AAPL | tail -5

# Just the chart
python3 ~/Codes/stock-price/stock.py NVDA --period 5d --graph >/dev/null 2>&1 && open /tmp/nvda_chart.png

# Multiple tickers to JSON
python3 ~/Codes/stock-price/stock.py AAPL MSFT --period 1mo --format json | python3 -m json.tool

# Watchlist summary
cat << 'EOF' | while read t; do python3 ~/Codes/stock-price/stock.py "$t" --period 1d | tail -2; done
AAPL
MSFT
NVDA
TSLA
EOF
```

## Integration Examples

### Fetch and analyze in Python
```python
import sys
sys.path.insert(0, '/Users/sohrabz/Codes/stock-price')
from stock import fetch_chart, parse_result

meta, bars = parse_result(fetch_chart('AAPL', '5d', '1d'))
changes = [(b['date'], b['close'] - b['open']) for b in bars]
```

### Generate and deliver chart
```bash
python3 ~/Codes/stock-price/stock.py NVDA --period 1mo --graph --graph-output /tmp/chart.png
# Then attach /tmp/chart.png to message
```