# Candlestick Chart Implementation Notes

## Dual-Panel Price + Volume Chart

The CLI generates a two-subplot chart using `matplotlib.gridspec`:
- **Top panel (70% height):** Candlestick price chart
- **Bottom panel (30% height):** Volume bars with matching colors

### Candlestick rendering

Each bar is rendered as:
1. A thin vertical line (wick) from low to high, colored by direction
2. A thick vertical bar (body) from open to close, colored by direction

```python
color = "#26a69a" if close >= open else "#ef5350"
ax.plot([date, date], [low, high], color=color, linewidth=1)        # wick
ax.plot([date, date], [open, close], color=color, linewidth=4, solid_capstyle="butt")  # body
```

Colors:
- Green `#26a69a` = bullish (close >= open)
- Red `#ef5350` = bearish (close < open)

### Volume bars

Volume bars share the same color as the corresponding candlestick:
```python
colors = ["#26a69a" if bar["close"] >= bar["open"] else "#ef5350" for bar in bars]
ax2.bar(dates, volumes, color=colors, width=0.6)
```

### Headless / cron safety

Always set `matplotlib.use("Agg")` **before** importing `pyplot`:
```python
import matplotlib
matplotlib.use("Agg")  # must be first
import matplotlib.pyplot as plt
```

Without this, headless environments throw:
```
_tkinter.TclError: no display name and no $DISPLAY environment variable
```

### Shared X-axis

Both subplots share the same x-axis via `sharex=True` so zoom/pan stays synchronized.

### Date formatting

Use **MM/DD** date labels for multi-day charts (1w, 1mo, etc.). Only use **HH:MM** hour labels for single-day intraday charts (`--period 1d` with `--interval 1m|2m|5m|...`). Hour labels on multi-day charts are unreadable.

```python
# Detect intraday: single day period AND non-midnight timestamps
is_intraday = period == "1d" and any(d.hour != 0 or d.minute != 0 for d in dates)

if is_intraday:
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, len(dates) // 8)))
else:
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 6)))
```
