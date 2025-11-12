"""
Check if big 2-3 candle moves reverse immediately
"""

import pandas as pd

df = pd.read_csv('SOL_USDT_1min_7days.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Find big upward moves
big_up_moves = []

for i in range(3, len(df)):
    # 2-candle upward move
    move_2 = df.iloc[i]['close'] - df.iloc[i-2]['close']
    move_2_pct = (move_2 / df.iloc[i-2]['close']) * 100

    # 3-candle upward move
    move_3 = df.iloc[i]['close'] - df.iloc[i-3]['close']
    move_3_pct = (move_3 / df.iloc[i-3]['close']) * 100

    if move_2_pct >= 1.5:  # Big upward move
        big_up_moves.append({
            'end_idx': i,
            'candles': 2,
            'move_pct': move_2_pct,
            'timestamp': df.iloc[i]['timestamp']
        })

    if move_3_pct >= 1.5:  # Big upward move
        big_up_moves.append({
            'end_idx': i,
            'candles': 3,
            'move_pct': move_3_pct,
            'timestamp': df.iloc[i]['timestamp']
        })

print(f"Found {len(big_up_moves)} big upward moves (≥1.5%)")
print("="*80)
print("Checking what happens after each spike...")
print("="*80)

reversals = []

for move in big_up_moves:
    end_idx = move['end_idx']

    # Check next 5 candles
    if end_idx + 5 >= len(df):
        continue

    spike_high = df.iloc[end_idx]['close']

    # Does it retrace significantly in next 5 candles?
    max_retrace_pct = 0
    for i in range(1, 6):
        price = df.iloc[end_idx + i]['close']
        retrace = spike_high - price
        retrace_pct = (retrace / spike_high) * 100
        max_retrace_pct = max(max_retrace_pct, retrace_pct)

    # Check if first candle is red
    next_candle = df.iloc[end_idx + 1]
    first_red = next_candle['close'] < next_candle['open']
    first_red_body = abs(next_candle['close'] - next_candle['open']) / next_candle['open'] * 100

    if max_retrace_pct >= 0.3:  # ANY retrace
        reversals.append({
            'timestamp': move['timestamp'],
            'spike_pct': move['move_pct'],
            'max_retrace_pct': max_retrace_pct,
            'first_red': first_red,
            'first_red_body': first_red_body if first_red else 0
        })

print(f"\nSpikes that retrace ≥0.3% within 5 candles: {len(reversals)}/{len(big_up_moves)}")

if reversals:
    reversals_df = pd.DataFrame(reversals)

    # How many have immediate red candle?
    immediate_red = reversals_df[reversals_df['first_red'] == True]
    print(f"  With immediate red candle: {len(immediate_red)}/{len(reversals)}")

    # Strong reversals
    strong = reversals_df[reversals_df['max_retrace_pct'] >= 0.5]
    print(f"  Strong reversals (≥0.5%): {len(strong)}")

    print(f"\nTop 10 strongest reversals:")
    print(reversals_df.nlargest(10, 'max_retrace_pct')[['timestamp', 'spike_pct', 'max_retrace_pct', 'first_red', 'first_red_body']].to_string())
else:
    print("\n❌ NO REVERSALS FOUND")
    print("Conclusion: Big upward spikes in this data DO NOT reverse - they continue!")
