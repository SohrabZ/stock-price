# Yahoo Finance Intraday Intervals

Yahoo Finance supports intraday intervals down to **1 minute** via the chart API.

## Valid intervals

`1m`, `2m`, `5m`, `15m`, `30m`, `60m`, `90m`, `1h`

## Constraints

| Period | Max interval | Notes |
|--------|--------------|-------|
| `1d` | `1m` | Full day of 1-minute ticks (~390 bars for US equities) |
| `5d` | `5m` or `15m` | 1m may return partial data or be throttled |
| `1mo` | `1h` | Hourly bars work reliably |
| `>1mo` | `1d` | Intraday intervals return truncated or empty data |

## Usage

```bash
# 1-minute intraday for today
./stock.py AAPL --period 1d --interval 1m

# 5-minute bars over 5 days
./stock.py NVDA --period 5d --interval 5m
```

## Data volume

A full day of 1-minute data for a single ticker is ~390 bars × 6 fields (OHLCV + adj close) = ~2,340 data points. JSON output for multiple tickers with 1m intervals can be very large — prefer `--format table` or `--graph` for visualization.

## Timezone

Timestamps from Yahoo are in **UTC**. The CLI converts to `%Y-%m-%d` dates and `%H:%M:%S` times for display. For intraday data, the `time` field in each bar reflects the UTC timestamp.

## Weekend/holiday gaps

The API returns no data for market holidays and weekends. The timestamp array will have gaps — the CLI handles this by iterating over available timestamps only.
