# Chart Rendering Deep Dive

Details on matplotlib chart generation, bar width handling, and intraday visual fixes.

## Adaptive Bar Width

**Problem**: Fixed `width=0.6` in `ax2.bar()` means 0.6 **days** (14.4 hours). With 1-minute intraday data, bars massively overlap into unreadable solid blocks.

**Fix**: Compute width from actual minimum interval between bars:

```python
if len(dates) > 1:
    intervals = [(dates[i+1] - dates[i]).total_seconds() for i in range(len(dates)-1)]
    min_interval = min(intervals)
    width_days = (min_interval * 0.8) / 86400  # 86400 seconds = 1 day
else:
    width_days = 0.02
```

This produces:
- **1m bars**: width ≈ 0.00056 days (48 seconds) — properly separated
- **1d bars**: width ≈ 0.8 days — comfortable spacing

## Opening Auction Spike

**Problem**: The first minute of trading often has 5-10x normal volume (opening auction), which dwarfs the rest of the day and squashes all other volume bars into near-invisibility.

**Detection**: First bar volume > 10× median of remaining bars.

**Fix**: Skip the first bar from the volume chart and add an annotation:

```python
if first_vol > 10 * rest_median:
    skip_first = True
    ax2.annotate(f"Open auction: {int(first_vol):,}", xy=(0.02, 0.95), ...)

start_idx = 1 if skip_first else 0
ax2.bar(dates[start_idx:], volumes[start_idx:], ...)
```

## X-Axis Label Rules

| Period | X-Axis Format | Locator |
|--------|--------------|---------|
| `1d` intraday | `%H:%M` HH:MM hours | HourLocator |
| `5d`+ daily | `%m/%d` MM/DD dates | DayLocator |

**Detection**: `period == "1d"` AND any non-midnight timestamps. Do NOT use HH:MM for multi-day charts — it becomes unreadable.

## Candlestick Colors

| Direction | Color | Hex |
|-----------|-------|-----|
| Up (close >= open) | Green | `#26a69a` |
| Down (close < open) | Red | `#ef5350` |

Same colors used for both price candlestick bodies and volume bars.

## Matplotlib Backend

Always set `matplotlib.use("Agg")` before importing pyplot to avoid "no display name" crashes on headless servers or cron jobs.

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter, HourLocator, DayLocator
```

## Common Pitfalls

1. **Width in matplotlib `bar()`**: Width is in **date units** (fraction of a day), not pixels or data points. Forgetting this causes massive overlap or invisible bars.
2. **Date formatting in headless mode**: `fig.autofmt_xdate()` handles rotation; don't manually rotate labels before pyplot import.
3. **Volume y-axis**: Let matplotlib auto-scale. The opening auction skip handles the outlier; no need for log scale.
