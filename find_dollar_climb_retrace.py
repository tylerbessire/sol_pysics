"""
Find all instances where:
1. Price climbs $1.00 to $2.00 USD in 15-30 minutes
2. Then retraces back to original price (or close)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def find_climb_retrace_patterns(df, target_date=None,
                                min_climb_usd=1.0,
                                max_climb_usd=2.0,
                                min_climb_minutes=15,
                                max_climb_minutes=30,
                                max_retrace_tolerance_usd=0.10):
    """
    Find climb → retrace patterns

    Args:
        target_date: Date to filter for (YYYY-MM-DD) or None for all
        min_climb_usd: Minimum climb in USD
        max_climb_usd: Maximum climb in USD
        min_climb_minutes: Minimum time for climb
        max_climb_minutes: Maximum time for climb
        max_retrace_tolerance_usd: How close retrace must be to start price
    """

    patterns = []

    print("="*80)
    print("SEARCHING FOR DOLLAR CLIMB → RETRACE PATTERNS")
    print("="*80)
    print(f"Climb: ${min_climb_usd:.2f} to ${max_climb_usd:.2f} USD")
    print(f"Duration: {min_climb_minutes}-{max_climb_minutes} minutes")
    print(f"Retrace tolerance: ±${max_retrace_tolerance_usd:.2f}")
    if target_date:
        print(f"Date filter: {target_date}")
    print("="*80)

    # Filter by date if specified
    if target_date:
        df = df[df['timestamp'].dt.date == pd.to_datetime(target_date).date()].copy()
        print(f"\nFiltered to {len(df)} candles on {target_date}")

    if len(df) == 0:
        print("No data for specified date!")
        return patterns

    print(f"\nScanning {len(df)} candles...")
    print()

    # Scan for patterns
    for start_idx in range(len(df)):
        start_price = df.iloc[start_idx]['close']
        start_time = df.iloc[start_idx]['timestamp']

        # Look ahead for climb within time window
        end_time_min = start_time + timedelta(minutes=min_climb_minutes)
        end_time_max = start_time + timedelta(minutes=max_climb_minutes)

        # Get candles in the climb window
        climb_window = df[(df['timestamp'] > start_time) &
                         (df['timestamp'] <= end_time_max)]

        if len(climb_window) == 0:
            continue

        # Find the high point in this window
        high_idx = climb_window['high'].idxmax()
        high_price = climb_window.loc[high_idx, 'high']
        high_time = climb_window.loc[high_idx, 'timestamp']

        # Calculate climb
        climb_usd = high_price - start_price

        # Is this a valid climb?
        climb_duration = (high_time - start_time).total_seconds() / 60

        if (climb_usd >= min_climb_usd and
            climb_usd <= max_climb_usd and
            climb_duration >= min_climb_minutes and
            climb_duration <= max_climb_minutes):

            # Now check for retrace back to start price
            # Look for candles after the high
            after_high = df[(df['timestamp'] > high_time) &
                           (df['timestamp'] <= high_time + timedelta(minutes=30))]

            if len(after_high) == 0:
                continue

            # Check if price retraces back near start
            for retrace_idx, retrace_row in after_high.iterrows():
                retrace_price = retrace_row['close']
                retrace_time = retrace_row['timestamp']

                # How close to original start price?
                diff_from_start = abs(retrace_price - start_price)

                if diff_from_start <= max_retrace_tolerance_usd:
                    # FOUND A PATTERN!
                    total_duration = (retrace_time - start_time).total_seconds() / 60
                    retrace_duration = (retrace_time - high_time).total_seconds() / 60

                    pattern = {
                        'start_time': start_time,
                        'high_time': high_time,
                        'retrace_time': retrace_time,
                        'start_price': start_price,
                        'high_price': high_price,
                        'retrace_price': retrace_price,
                        'climb_usd': climb_usd,
                        'climb_pct': (climb_usd / start_price) * 100,
                        'climb_minutes': climb_duration,
                        'retrace_minutes': retrace_duration,
                        'total_minutes': total_duration,
                        'retrace_diff': diff_from_start
                    }

                    patterns.append(pattern)

                    print(f"✅ PATTERN FOUND:")
                    print(f"   Start:    {start_time} | ${start_price:.2f}")
                    print(f"   High:     {high_time} | ${high_price:.2f} (+${climb_usd:.2f} in {climb_duration:.1f} min)")
                    print(f"   Retrace:  {retrace_time} | ${retrace_price:.2f} (back to start ±${diff_from_start:.2f})")
                    print(f"   Total duration: {total_duration:.1f} minutes")
                    print()

                    break  # Found retrace for this climb, move to next start point

    return patterns


def main():
    # Load recent data
    df = pd.read_csv('SOL_USDT_1min_7days.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"\nLoaded {len(df)} candles")
    print(f"Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")

    # Get yesterday's date (Nov 11, 2025)
    latest_date = df['timestamp'].max().date()
    yesterday = latest_date - timedelta(days=1)

    print(f"\nSearching for patterns on: {yesterday}")
    print()

    # Find patterns for yesterday
    patterns = find_climb_retrace_patterns(
        df,
        target_date=str(yesterday),
        min_climb_usd=1.0,
        max_climb_usd=2.0,
        min_climb_minutes=15,
        max_climb_minutes=30,
        max_retrace_tolerance_usd=0.10  # Within 10 cents of start
    )

    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total patterns found on {yesterday}: {len(patterns)}")

    if patterns:
        patterns_df = pd.DataFrame(patterns)

        print(f"\nAverage climb: ${patterns_df['climb_usd'].mean():.2f}")
        print(f"Average climb time: {patterns_df['climb_minutes'].mean():.1f} minutes")
        print(f"Average retrace time: {patterns_df['retrace_minutes'].mean():.1f} minutes")
        print(f"Average total duration: {patterns_df['total_minutes'].mean():.1f} minutes")

        print(f"\n{'='*80}")
        print("ALL PATTERNS:")
        print(f"{'='*80}\n")

        for i, p in enumerate(patterns, 1):
            print(f"{i}. {p['start_time']} → {p['high_time']} → {p['retrace_time']}")
            print(f"   ${p['start_price']:.2f} → ${p['high_price']:.2f} (+${p['climb_usd']:.2f}) → ${p['retrace_price']:.2f}")
            print(f"   Climb: {p['climb_minutes']:.1f} min | Retrace: {p['retrace_minutes']:.1f} min | Total: {p['total_minutes']:.1f} min")
            print()

    print("="*80)

    return patterns


if __name__ == "__main__":
    patterns = main()
