# Volume Statistics in CLI Output

The `print_table()` function calculates and prints two volume metrics after the price data:

## Avg volume

Mean volume across all bars in the period:
```python
avg_vol = sum(volumes) / len(volumes)
```

Printed as: `Avg volume:  {int(avg_vol):,}`

## Volume change

Difference between the last bar's volume and the first bar's volume, with percentage:
```python
vol_change = volumes[-1] - volumes[0]
vol_pct = (vol_change / volumes[0]) * 100 if volumes[0] else 0
```

Printed as: `Volume change: {int(vol_change):+,} ({vol_pct:+.1f}%)`

## Example output

```
Period change: $-4.23 (-2.01%)
Avg volume:  117,222,303
Volume change: -81,003,683 (-54.6%)
```

## Edge cases

- If no volume data is available, both lines are skipped.
- If only one bar has volume, only `Avg volume` is printed (no change calculation).
- Volume of `0` is valid and prints normally.
