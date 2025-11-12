"""
Diagnose why daily strategy fails while 1-minute strategy succeeds
"""

import pandas as pd
import numpy as np
from refined_strategy_daily import DailyMomentumExhaustionDetector, DailyConfirmationEntrySystem

# Load data
df = pd.read_csv('Solana_daily_data_2018_2024.csv')
df = df.rename(columns={
    'time': 'timestamp',
    'Open': 'open',
    'High': 'high',
    'Low': 'low',
    'Close': 'close',
    'Volume': 'volume'
})
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp', inplace=True)
df['Open'] = df['open']
df['High'] = df['high']
df['Low'] = df['low']
df['Close'] = df['close']
df['Volume'] = df['volume']

print("="*80)
print("DIAGNOSTIC: Why Daily Strategy Fails")
print("="*80)

# Step 1: Detect signals
detector = DailyMomentumExhaustionDetector(window=20)
df = detector.calculate_momentum_exhaustion(df)
df = detector.detect_green_candle_exhaustion(df)

entry_system = DailyConfirmationEntrySystem(min_red_retracement_pct=40, min_volume_drop_pct=15)
df = entry_system.detect_confirmation_candles(df)

print(f"\nTotal candles: {len(df)}")
print(f"Exhaustion signals: {df['exhaustion_detected'].sum()}")
print(f"Confirmation signals: {df['confirmation_signal'].sum()}")

# Step 2: Analyze confirmation signals
confirmations = df[df['confirmation_signal']].copy()

print(f"\n{'='*80}")
print(f"ANALYZING {len(confirmations)} CONFIRMATION SIGNALS")
print(f"{'='*80}")

# Calculate what would happen to each signal
results = []

for idx in confirmations.index:
    # Calculate entry levels
    levels = entry_system.calculate_entry_levels(
        df, idx,
        leverage=50,
        take_profit_pct=2.0,
        stop_loss_pct=3.0
    )

    # Check risk/reward
    if levels['risk_reward_ratio'] < 0.5:
        results.append({
            'date': idx,
            'entry_price': levels['entry_price'],
            'risk_reward': levels['risk_reward_ratio'],
            'status': 'rejected_rr'
        })
        continue

    # Simulate what happens
    entry_loc = df.index.get_loc(idx)
    if entry_loc >= len(df) - 5:
        results.append({
            'date': idx,
            'entry_price': levels['entry_price'],
            'risk_reward': levels['risk_reward_ratio'],
            'status': 'no_future_data'
        })
        continue

    future = df.iloc[entry_loc + 1:entry_loc + 31]

    # Check for TP or SL
    hit_tp = (future['Low'] <= levels['take_profit']).any()
    hit_sl = (future['High'] >= levels['stop_loss']).any()

    if hit_tp and hit_sl:
        tp_idx = future[future['Low'] <= levels['take_profit']].index[0]
        sl_idx = future[future['High'] >= levels['stop_loss']].index[0]
        outcome = 'win' if tp_idx < sl_idx else 'loss'
    elif hit_tp:
        outcome = 'win'
    elif hit_sl:
        outcome = 'loss'
    else:
        # Check if it moved in our direction
        final_price = future['Close'].iloc[-1]
        price_change_pct = ((levels['entry_price'] - final_price) / levels['entry_price']) * 100
        outcome = 'timeout_profit' if price_change_pct > 0 else 'timeout_loss'

    results.append({
        'date': idx,
        'entry_price': levels['entry_price'],
        'tp': levels['take_profit'],
        'sl': levels['stop_loss'],
        'risk_reward': levels['risk_reward_ratio'],
        'sl_distance_pct': levels['sl_distance_pct'],
        'status': 'accepted',
        'outcome': outcome
    })

results_df = pd.DataFrame(results)

print(f"\nSignal Breakdown:")
print(f"  Rejected (poor R:R): {len(results_df[results_df['status'] == 'rejected_rr'])}")
print(f"  No future data: {len(results_df[results_df['status'] == 'no_future_data'])}")
print(f"  Accepted for trading: {len(results_df[results_df['status'] == 'accepted'])}")

if len(results_df[results_df['status'] == 'accepted']) > 0:
    accepted = results_df[results_df['status'] == 'accepted']

    print(f"\nAccepted Signals Outcomes:")
    for outcome in ['win', 'loss', 'timeout_profit', 'timeout_loss']:
        count = len(accepted[accepted['outcome'] == outcome])
        pct = count / len(accepted) * 100
        print(f"  {outcome}: {count} ({pct:.1f}%)")

    win_rate = len(accepted[accepted['outcome'] == 'win']) / len(accepted) * 100
    print(f"\nTrue Win Rate (if all signals traded): {win_rate:.1f}%")

    # Show first few signals
    print(f"\n{'='*80}")
    print("FIRST 10 ACCEPTED SIGNALS:")
    print("="*80)
    for i, row in accepted.head(10).iterrows():
        print(f"\n{i}: {row['date'].strftime('%Y-%m-%d')}")
        print(f"  Entry: ${row['entry_price']:.2f}")
        print(f"  TP: ${row['tp']:.2f} | SL: ${row['sl']:.2f}")
        print(f"  R:R: {row['risk_reward']:.2f} | SL Distance: {row['sl_distance_pct']:.2f}%")
        print(f"  Outcome: {row['outcome']}")

# Show rejected signals
if len(results_df[results_df['status'] == 'rejected_rr']) > 0:
    rejected = results_df[results_df['status'] == 'rejected_rr']
    print(f"\n{'='*80}")
    print(f"REJECTED SIGNALS (Poor Risk:Reward < 0.5)")
    print(f"{'='*80}")
    print(f"Total rejected: {len(rejected)}")
    print(f"\nRisk:Reward distribution:")
    print(rejected['risk_reward'].describe())

print(f"\n{'='*80}")
print("KEY INSIGHT")
print("="*80)

if len(results_df[results_df['status'] == 'accepted']) > 10:
    print("\n✓ Problem is NOT signal filtering")
    print("  - Plenty of signals pass R:R filter")
    print(f"  - {len(results_df[results_df['status'] == 'accepted'])} signals would trade")
    print("\n⚠️ Problem is likely:")
    print("  - Daily timeframe has different mean reversion characteristics")
    print("  - Stop losses being hit before take profits")
    print("  - Need wider stops or different entry timing for daily TF")
else:
    print("\n⚠️ Problem is SIGNAL FILTERING")
    print("  - Risk:Reward filter is rejecting most signals")
    print("  - Stop losses are too wide relative to take profits")
    print("  - Need to adjust R:R threshold or TP/SL ratios")
