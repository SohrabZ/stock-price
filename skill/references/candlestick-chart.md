# Candlestick Chart Implementation Notes

## Dual-Panel Price + Volume Chart

The CLI generates a two-subplot chart using `plt.subplots(..., gridspec_kw={...})`:
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

Volume bars share the same color as the corresponding candlestick, with **adaptive width** computed from the actual time interval between bars:

```python
# Compute adaptive width: ~80% of the minimum interval between consecutive bars
if len(dates) > 1:
    intervals = [(dates[i+1] - dates[i]).total_seconds() for i in range(len(dates)-1)]
    min_interval = min(intervals) if intervals else 86400
    width_days = (min_interval * 0.8) / 86400  # matplotlib uses fraction of a day
else:
    width_days = 0.02  # fallback single bar

# Coerce None volumes to 0 for matplotlib
volumes = [b["volume"] if b["volume"] is not None else 0 for b in bars]
colors = [_bar_color(b) for b in bars]
ax.bar(dates, volumes, color=colors, width=width_days)
```

> **Never hardcode `width=0.6`** — that means 0.6 days (14.4 hours), causing massive overlap on 1-minute data.

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

### Smart X-axis Labels

The x-axis uses a **7-tier** format based on actual date span (not the period parameter):

```python
def _configure_xaxis(ax, dates, is_intraday):
    date_range_days = (dates[-1] - dates[0]).days if len(dates) > 1 else 0

    if is_intraday or date_range_days <= 1:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, len(dates) // 8)))
    elif date_range_days <= 31:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, date_range_days // 6)))
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
```

| Time Span | Format | Example |
|-----------|--------|---------|
| Intraday (≤1 day) | HH:MM | 09:30, 12:00 |
| Short-term (≤31 days) | MM/DD | 07/01, 07/15 |
| Medium-term (≤6 months) | Mon | Apr, May, Jun |
| ~1 year | Mon 'YY | Jul '25, Aug '25 |
| 1-2 years | Mon 'YY every 2mo | Jul '25, Sep '25 |
| 2-5 years | Mon 'YY every 3mo | Jul '25, Oct '25 |
| 5+ years | Mon YYYY every 1-2yr | Jun 1999, Jun 2001 |

For the full implementation, see `smart-xaxis-labels.md`.
