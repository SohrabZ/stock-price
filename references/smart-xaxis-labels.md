# Smart X-Axis Labels

The chart automatically selects x-axis labels based on the **actual date range** of the data, not the `--period` parameter. This prevents overcrowded or sparse labels.

## Logic

```python
if len(dates) > 1:
    date_range_days = (dates[-1] - dates[0]).days
else:
    date_range_days = 0

if is_intraday or date_range_days <= 1:
    # Intraday: HH:MM
    formatter = "%H:%M"
    locator = HourLocator(interval=max(1, len(dates) // 8))
elif date_range_days <= 31:
    # Short term (up to 1 month): MM/DD
    formatter = "%m/%d"
    locator = DayLocator(interval=max(1, date_range_days // 6))
elif date_range_days <= 180:
    # Medium term (1-6 months): abbreviated month name
    formatter = "%b"
    locator = MonthLocator()
elif date_range_days <= 400:
    # ~1 year: month name (add year if spanning year boundary)
    spans_years = dates[0].year != dates[-1].year
    formatter = "%b '%y" if spans_years else "%b"
    locator = MonthLocator(interval=1)
elif date_range_days <= 800:
    # 1-2 years: Mon 'YY every 2 months
    formatter = "%b '%y"
    locator = MonthLocator(interval=2)
elif date_range_days <= 1800:
    # 2-5 years: Mon 'YY every 3 months
    formatter = "%b '%y"
    locator = MonthLocator(interval=3)
else:
    # 5+ years: Mon YYYY every 12-24 months depending on total span
    formatter = "%b %Y"
    year_span = date_range_days / 365
    if year_span <= 10:
        interval = 12  # every year
    elif year_span <= 20:
        interval = 18  # every 1.5 years
    else:
        interval = 24  # every 2 years
    locator = MonthLocator(interval=interval)
```

## Format Examples

| Time Span | Format | Example |
|-----------|--------|---------|
| Intraday (<=1 day) | HH:MM | 09:30, 12:00 |
| Short-term (<=31 days) | MM/DD | 07/01, 07/15 |
| Medium-term (<=6 months) | Mon | Apr, May, Jun |
| ~1 year | Mon 'YY | Jul '25, Aug '25 |
| 1-2 years | Mon 'YY every 2mo | Jul '25, Sep '25 |
| 2-5 years | Mon 'YY every 3mo | Jul '25, Oct '25 |
| 5+ years | Mon YYYY every 1-2yr | Jun 1999, Jun 2001 |

## Pitfall: Using period parameter instead of actual range

Using the `--period` string (e.g. "1y") to pick labels fails when:
- `ytd` spans variable months (Jan-Jul vs Jan-Dec)
- `max` spans different years for different tickers
- Data has gaps (holidays, weekends)

Always compute `date_range_days = (dates[-1] - dates[0]).days` from the actual bar timestamps.
