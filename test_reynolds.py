"""
Quick test to see actual Reynolds numbers in the data
"""
import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('SOL_USDT_1min_7days.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

lookback = 20

# Calculate Reynolds for every candle
reynolds_values = []

for i in range(lookback, len(df)):
    recent = df.iloc[i-lookback:i]

    # Velocity = price velocity (rate of change)
    velocity = recent['close'].pct_change().abs().mean()

    # Length scale = ATR (average true range)
    high_low = recent['high'] - recent['low']
    high_close = (recent['high'] - recent['close'].shift(1)).abs()
    low_close = (recent['low'] - recent['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    length_scale = tr.mean()

    # Viscosity = rolling std (resistance to change)
    viscosity = recent['close'].pct_change().std()

    if viscosity > 0:
        reynolds = (velocity * length_scale) / viscosity
        reynolds_values.append(reynolds)

reynolds_values = np.array(reynolds_values)

print("="*80)
print("REYNOLDS NUMBER ANALYSIS")
print("="*80)
print(f"Total candles analyzed: {len(reynolds_values)}")
print(f"\nReynolds Number Statistics:")
print(f"  Min:     {reynolds_values.min():.4f}")
print(f"  Max:     {reynolds_values.max():.4f}")
print(f"  Mean:    {reynolds_values.mean():.4f}")
print(f"  Median:  {np.median(reynolds_values):.4f}")
print(f"  Std:     {reynolds_values.std():.4f}")
print(f"\nPercentiles:")
print(f"  10th:    {np.percentile(reynolds_values, 10):.4f}")
print(f"  25th:    {np.percentile(reynolds_values, 25):.4f}")
print(f"  50th:    {np.percentile(reynolds_values, 50):.4f}")
print(f"  75th:    {np.percentile(reynolds_values, 75):.4f}")
print(f"  90th:    {np.percentile(reynolds_values, 90):.4f}")
print(f"  95th:    {np.percentile(reynolds_values, 95):.4f}")
print(f"  99th:    {np.percentile(reynolds_values, 99):.4f}")

print(f"\nPercentage above thresholds:")
print(f"  Re > 0.5:  {(reynolds_values > 0.5).sum() / len(reynolds_values) * 100:.1f}%")
print(f"  Re > 1.0:  {(reynolds_values > 1.0).sum() / len(reynolds_values) * 100:.1f}%")
print(f"  Re > 1.5:  {(reynolds_values > 1.5).sum() / len(reynolds_values) * 100:.1f}%")
print(f"  Re > 2.0:  {(reynolds_values > 2.0).sum() / len(reynolds_values) * 100:.1f}%")

print("="*80)
