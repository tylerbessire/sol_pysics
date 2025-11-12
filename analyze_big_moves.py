"""
Analyze the actual big moves in the data to find the right thresholds
"""

import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('SOL_USDT_1min_7days.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

print("="*80)
print("ANALYZING BIG MOVES IN 7-DAY SOL/USDT DATA")
print("="*80)

print(f"\nData: {len(df)} candles ({(len(df)/1440):.1f} days)")
print(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

# Calculate move statistics
df['price_change'] = df['close'].diff()
df['price_change_pct'] = df['close'].pct_change() * 100
df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()

# Look at different time windows
for lookback in [1, 2, 3, 5]:
    df[f'move_{lookback}min'] = df['close'].diff(lookback)
    df[f'move_{lookback}min_pct'] = (df['close'].pct_change(lookback) * 100).abs()

# Find the biggest moves
print("\n" + "="*80)
print("TOP 50 BIGGEST MOVES (1-minute)")
print("="*80)

# Sort by 1-minute move
top_moves = df.nlargest(50, 'move_1min_pct')[['timestamp', 'close', 'volume', 'price_change', 'price_change_pct', 'volume_ratio']]

print(f"\n{'Time':<20} {'Price':<10} {'Change':<12} {'%':<8} {'Vol Spike':<10}")
print("-"*80)
for idx, row in top_moves.head(20).iterrows():
    print(f"{str(row['timestamp']):<20} ${row['close']:<9.2f} ${row['price_change']:<11.2f} "
          f"{row['price_change_pct']:<7.2f}% {row['volume_ratio']:<9.1f}x")

# Statistics on big moves
print("\n" + "="*80)
print("MOVE SIZE DISTRIBUTION")
print("="*80)

for window in [1, 2, 3, 5]:
    col = f'move_{window}min_pct'
    moves = df[col].dropna()

    print(f"\n{window}-Minute Moves:")
    print(f"  Mean: {moves.mean():.3f}%")
    print(f"  Median: {moves.median():.3f}%")
    print(f"  90th percentile: {moves.quantile(0.90):.3f}%")
    print(f"  95th percentile: {moves.quantile(0.95):.3f}%")
    print(f"  99th percentile: {moves.quantile(0.99):.3f}%")
    print(f"  Max: {moves.max():.3f}%")

    # Count moves above various thresholds
    for threshold_pct in [0.2, 0.3, 0.5, 0.75, 1.0]:
        count = (moves >= threshold_pct).sum()
        per_day = count / (len(df) / 1440)
        print(f"  Moves ≥{threshold_pct}%: {count} ({per_day:.1f}/day)")

# Find consecutive strong candles (liquidation cascades)
print("\n" + "="*80)
print("LIQUIDATION CASCADE PATTERNS")
print("="*80)

# Find 3+ consecutive candles moving in same direction with strong bodies
df['is_strong_green'] = (
    (df['close'] > df['open']) &  # Green
    ((df['close'] - df['open']) / df['open'] > 0.001) &  # Body >0.1%
    (df['volume'] > df['volume'].rolling(10).mean())  # Volume above average
)

# Count consecutive streaks
cascades = []
streak_start = None
streak_length = 0

for idx, row in df.iterrows():
    if row['is_strong_green']:
        if streak_start is None:
            streak_start = idx
        streak_length += 1
    else:
        if streak_length >= 3:
            # Found a cascade
            cascade_data = df.loc[streak_start:idx-1]
            total_move = cascade_data['close'].iloc[-1] - cascade_data['close'].iloc[0]
            total_move_pct = (total_move / cascade_data['close'].iloc[0]) * 100
            max_volume_spike = (cascade_data['volume'] / df['volume'].rolling(20).mean()).max()

            cascades.append({
                'start': cascade_data['timestamp'].iloc[0],
                'length': streak_length,
                'move_usd': total_move,
                'move_pct': total_move_pct,
                'volume_spike': max_volume_spike
            })

        streak_start = None
        streak_length = 0

print(f"\nFound {len(cascades)} liquidation cascades (3+ consecutive strong green candles)")

if cascades:
    cascades_df = pd.DataFrame(cascades)
    print(f"\nCascade Statistics:")
    print(f"  Average length: {cascades_df['length'].mean():.1f} candles")
    print(f"  Average move: ${cascades_df['move_usd'].mean():.2f} ({cascades_df['move_pct'].mean():.2f}%)")
    print(f"  Average volume spike: {cascades_df['volume_spike'].mean():.1f}x")

    print(f"\n  Cascades per day: {len(cascades) / (len(df)/1440):.1f}")

    # Show biggest cascades
    print(f"\nTop 10 Biggest Cascades:")
    print(f"{'Time':<20} {'Length':<8} {'Move':<15} {'%':<10} {'Vol Spike'}")
    print("-"*80)
    for _, cascade in cascades_df.nlargest(10, 'move_pct').iterrows():
        print(f"{str(cascade['start']):<20} {cascade['length']:<8.0f} "
              f"${cascade['move_usd']:<14.2f} {cascade['move_pct']:<9.2f}% "
              f"{cascade['volume_spike']:<.1f}x")

    # Recommended threshold
    if len(cascades) > 0:
        # Target 10 per day = top ~1.5% of moves
        target_per_day = 10
        total_days = len(df) / 1440
        target_total = int(target_per_day * total_days)

        if len(cascades) >= target_total:
            threshold_move = cascades_df.nlargest(target_total, 'move_pct')['move_pct'].min()
            print(f"\n{'='*80}")
            print(f"RECOMMENDED THRESHOLD for ~{target_per_day} trades/day:")
            print(f"  Minimum cascade move: {threshold_move:.2f}%")
            print(f"  This gives {target_total} trades over {total_days:.1f} days = {target_total/total_days:.1f}/day")
            print(f"{'='*80}")

print("\n")
