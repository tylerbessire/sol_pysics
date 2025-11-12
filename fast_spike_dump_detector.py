"""
FAST SPIKE-AND-DUMP DETECTOR

Looking for the EXACT pattern user described:
- Big price spike (≥1% in 1-2 candles)
- Immediate reversal within 1-5 candles
- Total episode: 3-10 minutes (spike to reversal completion)

This is NOT about slow climbs. This is about rapid pump-and-dump patterns.
"""

import pandas as pd
import numpy as np
import json


def find_fast_spike_dumps(df, min_spike_pct=0.75, min_dump_pct=0.5, max_candles_to_reverse=10):
    """
    Find patterns where:
    1. Price spikes up ≥min_spike_pct in 1-2 candles
    2. Price dumps down ≥min_dump_pct within next max_candles_to_reverse
    3. Total pattern completes quickly (spike + dump)
    """
    episodes = []

    print(f"Scanning for fast spike-dump patterns...")
    print(f"Criteria: ≥{min_spike_pct}% spike → ≥{min_dump_pct}% dump within {max_candles_to_reverse} candles")
    print("="*80)

    for idx in range(2, len(df) - max_candles_to_reverse):
        # Check for spike (1-2 candle move)
        current_price = df.iloc[idx]['close']
        price_2_ago = df.iloc[idx-2]['close']

        spike_usd = current_price - price_2_ago
        spike_pct = (spike_usd / price_2_ago) * 100

        # Is this a significant upward spike?
        if spike_pct >= min_spike_pct:
            spike_high = current_price
            spike_idx = idx

            # Now look for reversal in next N candles
            for future_idx in range(idx + 1, min(idx + max_candles_to_reverse + 1, len(df))):
                future_price = df.iloc[future_idx]['close']

                # How much has it dumped from the spike high?
                dump_usd = spike_high - future_price
                dump_pct = (dump_usd / spike_high) * 100

                # Is this a significant dump?
                if dump_pct >= min_dump_pct:
                    # FOUND A SPIKE-DUMP PATTERN!
                    candles_to_reverse = future_idx - spike_idx
                    total_duration_minutes = (df.iloc[future_idx]['timestamp'] - df.iloc[idx-2]['timestamp']).total_seconds() / 60

                    episode = {
                        'episode_num': len(episodes) + 1,
                        'spike_start_idx': idx - 2,
                        'spike_high_idx': spike_idx,
                        'dump_end_idx': future_idx,
                        'spike_start_time': df.iloc[idx-2]['timestamp'],
                        'spike_high_time': df.iloc[spike_idx]['timestamp'],
                        'dump_end_time': df.iloc[future_idx]['timestamp'],
                        'spike_start_price': price_2_ago,
                        'spike_high_price': spike_high,
                        'dump_end_price': future_price,
                        'spike_usd': spike_usd,
                        'spike_pct': spike_pct,
                        'dump_usd': dump_usd,
                        'dump_pct': dump_pct,
                        'candles_to_reverse': candles_to_reverse,
                        'total_duration_minutes': total_duration_minutes,
                        'candles_in_episode': future_idx - (idx - 2)
                    }

                    episodes.append(episode)

                    print(f"\n✅ SPIKE-DUMP #{len(episodes)} FOUND")
                    print(f"   Spike: ${price_2_ago:.2f} → ${spike_high:.2f} (+{spike_pct:.2f}%)")
                    print(f"   Dump: ${spike_high:.2f} → ${future_price:.2f} (-{dump_pct:.2f}%)")
                    print(f"   Reversal: {candles_to_reverse} candles ({total_duration_minutes:.1f} min)")
                    print(f"   Time: {df.iloc[spike_idx]['timestamp']}")

                    break  # Found reversal, move to next spike

    print(f"\n{'='*80}")
    print(f"FOUND {len(episodes)} FAST SPIKE-DUMP EPISODES")
    print(f"{'='*80}\n")

    return episodes


def analyze_spike_dump_patterns(df, episodes):
    """
    Analyze what happens in the candles DURING the spike and BEFORE the dump
    """
    print("\n" + "="*80)
    print("SPIKE-DUMP PATTERN ANALYSIS")
    print("="*80)

    if not episodes:
        print("\nNo episodes to analyze")
        return

    # Statistics
    durations = [ep['total_duration_minutes'] for ep in episodes]
    candle_counts = [ep['candles_in_episode'] for ep in episodes]
    spike_sizes = [ep['spike_pct'] for ep in episodes]
    dump_sizes = [ep['dump_pct'] for ep in episodes]

    print(f"\n📊 EPISODE STATISTICS:")
    print(f"   Total episodes: {len(episodes)}")
    print(f"   Avg duration: {np.mean(durations):.1f} minutes (min: {np.min(durations):.1f}, max: {np.max(durations):.1f})")
    print(f"   Avg candles: {np.mean(candle_counts):.1f} (min: {np.min(candle_counts)}, max: {np.max(candle_counts)})")
    print(f"   Avg spike size: {np.mean(spike_sizes):.2f}% (max: {np.max(spike_sizes):.2f}%)")
    print(f"   Avg dump size: {np.mean(dump_sizes):.2f}% (max: {np.max(dump_sizes):.2f}%)")

    # Filter for ULTRA-FAST episodes (≤10 minutes, ≤10 candles)
    ultra_fast = [ep for ep in episodes if ep['total_duration_minutes'] <= 10 and ep['candles_in_episode'] <= 10]

    print(f"\n🚀 ULTRA-FAST EPISODES (≤10 min, ≤10 candles):")
    print(f"   Count: {len(ultra_fast)} ({len(ultra_fast)/len(episodes)*100:.1f}% of all episodes)")

    if ultra_fast:
        print(f"   Avg duration: {np.mean([ep['total_duration_minutes'] for ep in ultra_fast]):.1f} minutes")
        print(f"   Avg spike: {np.mean([ep['spike_pct'] for ep in ultra_fast]):.2f}%")
        print(f"   Avg dump: {np.mean([ep['dump_pct'] for ep in ultra_fast]):.2f}%")

    # Show top 10 fastest
    print(f"\n{'='*80}")
    print("TOP 10 FASTEST SPIKE-DUMPS (by duration):")
    print(f"{'='*80}")

    sorted_by_speed = sorted(episodes, key=lambda x: x['total_duration_minutes'])

    for ep in sorted_by_speed[:10]:
        print(f"\nEpisode #{ep['episode_num']}: {ep['total_duration_minutes']:.1f} min ({ep['candles_in_episode']} candles)")
        print(f"   {ep['spike_start_time']} → {ep['dump_end_time']}")
        print(f"   Spike: ${ep['spike_start_price']:.2f} → ${ep['spike_high_price']:.2f} (+{ep['spike_pct']:.2f}%)")
        print(f"   Dump: ${ep['spike_high_price']:.2f} → ${ep['dump_end_price']:.2f} (-{ep['dump_pct']:.2f}%)")


def main():
    print("\n" + "="*80)
    print("FAST SPIKE-DUMP PATTERN DETECTOR")
    print("="*80)
    print("\nLooking for rapid pump-and-dump patterns:")
    print("- Big spike up (≥0.75%)")
    print("- Quick reversal down (≥0.5%)")
    print("- Complete episode in a few minutes\n")

    # Load data
    df = pd.read_csv('SOL_USDT_1min_7days.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"Loaded {len(df)} candles")
    print(f"Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
    print(f"Days: {days}\n")

    # Find spike-dump patterns
    episodes = find_fast_spike_dumps(
        df,
        min_spike_pct=0.75,     # Spike ≥0.75%
        min_dump_pct=0.5,       # Dump ≥0.5%
        max_candles_to_reverse=10  # Reverse within 10 candles
    )

    # Save episodes
    if episodes:
        with open('spike_dump_episodes.json', 'w') as f:
            json.dump(episodes, f, indent=2, default=str)
        print(f"✓ Saved {len(episodes)} episodes to spike_dump_episodes.json")

        # Analyze patterns
        analyze_spike_dump_patterns(df, episodes)

        print(f"\n\n{'='*80}")
        print("Per day rate:")
        print(f"  All episodes: {len(episodes)/days:.1f} per day")
        ultra_fast = [ep for ep in episodes if ep['total_duration_minutes'] <= 10]
        print(f"  Ultra-fast (≤10 min): {len(ultra_fast)/days:.1f} per day")
        print(f"{'='*80}\n")
    else:
        print("\n❌ No spike-dump episodes found with current criteria")


if __name__ == "__main__":
    main()
