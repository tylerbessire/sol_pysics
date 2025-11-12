"""
CLIMB EPISODE ANALYZER

Step 1: Find all big upward climbs in historical data
Step 2: Mark the complete climb (spike → continuation → big red retracement)
Step 3: Flag these episodes for detailed study
Step 4: Analyze what happens RIGHT BEFORE the climb ends

This is pure learning - no trading yet. Study first, trade later.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json


class ClimbEpisodeDetector:
    """
    Detect complete climb episodes: big spike → climb → significant retracement
    """

    def __init__(self, min_spike_pct=1.0, min_total_climb_pct=1.5, min_retracement_pct=30):
        self.min_spike_pct = min_spike_pct
        self.min_total_climb_pct = min_total_climb_pct
        self.min_retracement_pct = min_retracement_pct

    def find_all_episodes(self, df):
        """
        Scan through data and find ALL climb episodes
        """
        episodes = []
        in_climb = False
        climb_start_idx = None
        climb_low = None
        climb_high = None
        climb_high_idx = None

        print(f"Scanning {len(df)} candles for climb episodes...")
        print(f"Criteria: ≥{self.min_spike_pct}% spike → climb ≥{self.min_total_climb_pct}% total → ≥{self.min_retracement_pct}% retrace")
        print("="*80)

        for idx in range(1, len(df)):
            current_price = df.iloc[idx]['close']
            prev_price = df.iloc[idx-1]['close']

            # Detect new spike (start of potential climb)
            spike_pct = ((current_price - prev_price) / prev_price) * 100

            if spike_pct >= self.min_spike_pct and not in_climb:
                # New climb starting!
                in_climb = True
                climb_start_idx = idx - 1
                climb_low = df.iloc[idx-1]['close']
                climb_high = current_price
                climb_high_idx = idx

                print(f"\n🚀 CLIMB STARTED at {df.iloc[idx]['timestamp']}")
                print(f"   Spike: ${prev_price:.2f} → ${current_price:.2f} (+{spike_pct:.2f}%)")

            # Track climb continuation (update high)
            if in_climb:
                if current_price > climb_high:
                    climb_high = current_price
                    climb_high_idx = idx

                # Check for significant retracement (end of climb)
                total_climb = climb_high - climb_low
                total_climb_pct = (total_climb / climb_low) * 100
                retracement = climb_high - current_price
                retracement_pct = (retracement / total_climb) * 100 if total_climb > 0 else 0

                # Is this a significant retracement that ends the climb?
                is_red = current_price < df.iloc[idx]['open']
                red_body = abs(df.iloc[idx]['open'] - current_price)
                red_body_pct = (red_body / df.iloc[idx]['open']) * 100

                if (retracement_pct >= self.min_retracement_pct and
                    is_red and
                    red_body_pct >= 0.2 and
                    total_climb_pct >= self.min_total_climb_pct):

                    # CLIMB ENDED!
                    climb_end_idx = idx

                    episode = {
                        'episode_num': len(episodes) + 1,
                        'start_idx': climb_start_idx,
                        'high_idx': climb_high_idx,
                        'end_idx': climb_end_idx,
                        'start_time': df.iloc[climb_start_idx]['timestamp'],
                        'high_time': df.iloc[climb_high_idx]['timestamp'],
                        'end_time': df.iloc[climb_end_idx]['timestamp'],
                        'start_price': climb_low,
                        'high_price': climb_high,
                        'end_price': current_price,
                        'total_climb_usd': total_climb,
                        'total_climb_pct': total_climb_pct,
                        'retracement_usd': retracement,
                        'retracement_pct': retracement_pct,
                        'duration_candles': climb_high_idx - climb_start_idx,
                        'duration_minutes': (df.iloc[climb_high_idx]['timestamp'] - df.iloc[climb_start_idx]['timestamp']).total_seconds() / 60
                    }

                    episodes.append(episode)

                    print(f"\n✅ CLIMB #{len(episodes)} ENDED at {df.iloc[idx]['timestamp']}")
                    print(f"   Total climb: ${climb_low:.2f} → ${climb_high:.2f} (+{total_climb_pct:.2f}%)")
                    print(f"   Retracement: ${retracement:.2f} ({retracement_pct:.1f}% of climb)")
                    print(f"   Duration: {episode['duration_minutes']:.0f} minutes")

                    in_climb = False
                    climb_start_idx = None

        print(f"\n{'='*80}")
        print(f"FOUND {len(episodes)} COMPLETE CLIMB EPISODES")
        print(f"{'='*80}\n")

        return episodes

    def extract_episode_data(self, df, episode):
        """
        Extract all candles for a specific episode
        """
        # Get candles from start to end
        episode_df = df.iloc[episode['start_idx']:episode['end_idx']+1].copy()

        # Add relative position in climb
        episode_df['candles_from_start'] = range(len(episode_df))
        episode_df['candles_to_high'] = episode['high_idx'] - episode_df.index

        return episode_df


class ClimbPatternAnalyzer:
    """
    Analyze patterns in climb episodes to learn when they end
    """

    def __init__(self):
        pass

    def analyze_all_episodes(self, df, episodes):
        """
        Study all episodes to find common patterns before the top
        """
        print("\n" + "="*80)
        print("PATTERN ANALYSIS: What happens RIGHT BEFORE climbs end?")
        print("="*80)

        # Analyze candles leading up to the high
        lookback_candles = 5  # Study last 5 candles before peak

        patterns = []

        for ep in episodes:
            high_idx = ep['high_idx']

            # Get candles before the high
            if high_idx - lookback_candles < 0:
                continue

            pre_high_candles = df.iloc[high_idx - lookback_candles:high_idx + 1]

            # Calculate patterns
            pattern = self._analyze_pre_high_pattern(pre_high_candles, ep)
            patterns.append(pattern)

        # Aggregate patterns
        self._print_pattern_summary(patterns)

        return patterns

    def _analyze_pre_high_pattern(self, candles, episode):
        """
        Analyze the pattern in candles before the high
        """
        if len(candles) < 2:
            return None

        # Calculate metrics
        candles = candles.copy()
        candles['velocity'] = candles['close'].diff()
        candles['velocity_pct'] = candles['close'].pct_change() * 100
        candles['body'] = abs(candles['close'] - candles['open'])
        candles['body_pct'] = (candles['body'] / candles['open']) * 100
        candles['is_green'] = (candles['close'] > candles['open']).astype(int)

        # Volume analysis
        candles['volume_ma'] = candles['volume'].rolling(3).mean()
        candles['volume_declining'] = (candles['volume'] < candles['volume_ma']).astype(int)

        # Momentum
        candles['momentum'] = candles['velocity'] * candles['volume']
        candles['momentum_ma'] = candles['momentum'].rolling(3).mean()
        candles['momentum_declining'] = (candles['momentum'] < candles['momentum_ma']).astype(int)

        # Analyze last few candles
        last_3 = candles.tail(3)

        pattern = {
            'episode_num': episode['episode_num'],
            'total_climb_pct': episode['total_climb_pct'],

            # Candle characteristics
            'last_candle_green': last_3.iloc[-1]['is_green'],
            'last_candle_body_pct': last_3.iloc[-1]['body_pct'],
            'last_candle_velocity_pct': last_3.iloc[-1]['velocity_pct'],

            # Green candle weakening
            'green_candles_in_last_3': last_3['is_green'].sum(),
            'body_sizes_last_3': last_3['body_pct'].tolist(),
            'bodies_declining': (last_3['body_pct'].iloc[-1] < last_3['body_pct'].iloc[0]),

            # Volume
            'volume_declining_last_3': last_3['volume_declining'].sum(),

            # Momentum
            'momentum_declining_last_3': last_3['momentum_declining'].sum(),

            # Velocity slowing
            'velocities_last_3': last_3['velocity_pct'].tolist(),
            'velocity_slowing': (abs(last_3['velocity_pct'].iloc[-1]) < abs(last_3['velocity_pct'].iloc[0]))
        }

        return pattern

    def _print_pattern_summary(self, patterns):
        """
        Print summary of common patterns
        """
        patterns_df = pd.DataFrame(patterns)

        print(f"\nAnalyzed {len(patterns)} climb episodes\n")

        print("=" * 80)
        print("COMMON PATTERNS BEFORE CLIMB ENDS:")
        print("=" * 80)

        # How many were still green at the peak?
        green_at_peak = patterns_df['last_candle_green'].sum()
        print(f"\n1. Last candle before peak:")
        print(f"   Green: {green_at_peak}/{len(patterns)} ({green_at_peak/len(patterns)*100:.1f}%)")
        print(f"   Red: {len(patterns)-green_at_peak}/{len(patterns)} ({(len(patterns)-green_at_peak)/len(patterns)*100:.1f}%)")

        # Body size declining?
        bodies_declining = patterns_df['bodies_declining'].sum()
        print(f"\n2. Candle bodies declining:")
        print(f"   Yes: {bodies_declining}/{len(patterns)} ({bodies_declining/len(patterns)*100:.1f}%)")

        # Volume declining?
        avg_vol_declining = patterns_df['volume_declining_last_3'].mean()
        print(f"\n3. Volume declining (avg in last 3 candles):")
        print(f"   {avg_vol_declining:.1f}/3 candles")

        # Momentum declining?
        avg_momentum_declining = patterns_df['momentum_declining_last_3'].mean()
        print(f"\n4. Momentum declining (avg in last 3 candles):")
        print(f"   {avg_momentum_declining:.1f}/3 candles")

        # Velocity slowing?
        velocity_slowing = patterns_df['velocity_slowing'].sum()
        print(f"\n5. Velocity slowing:")
        print(f"   Yes: {velocity_slowing}/{len(patterns)} ({velocity_slowing/len(patterns)*100:.1f}%)")

        # Show individual episodes
        print(f"\n{'='*80}")
        print("INDIVIDUAL EPISODES:")
        print(f"{'='*80}\n")

        for i, pattern in enumerate(patterns[:10]):  # Show first 10
            print(f"\nEpisode #{pattern['episode_num']}: +{pattern['total_climb_pct']:.2f}% climb")
            print(f"  Last 3 velocities: {[f'{v:.3f}%' for v in pattern['velocities_last_3']]}")
            print(f"  Last 3 bodies: {[f'{b:.3f}%' for b in pattern['body_sizes_last_3']]}")
            print(f"  Volume declining: {pattern['volume_declining_last_3']}/3 candles")
            print(f"  Momentum declining: {pattern['momentum_declining_last_3']}/3 candles")
            print(f"  Last candle: {'GREEN' if pattern['last_candle_green'] else 'RED'}")


def main():
    """
    Main analysis: Find and study all climb episodes
    """
    print("\n" + "="*80)
    print("CLIMB EPISODE LEARNING SYSTEM")
    print("="*80)
    print("\nPhase 1: Find all big climbs in historical data")
    print("Phase 2: Study patterns before they end")
    print("Phase 3: Learn the signals\n")

    # Load data
    df = pd.read_csv('SOL_USDT_1min_7days.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"Loaded {len(df)} candles")
    print(f"Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    print()

    # Step 1: Find all episodes
    detector = ClimbEpisodeDetector(
        min_spike_pct=1.0,          # Initial spike ≥1%
        min_total_climb_pct=1.5,    # Total climb ≥1.5%
        min_retracement_pct=30       # End when ≥30% retrace
    )

    episodes = detector.find_all_episodes(df)

    # Save episodes
    with open('climb_episodes.json', 'w') as f:
        json.dump(episodes, f, indent=2, default=str)

    print(f"✓ Saved {len(episodes)} episodes to climb_episodes.json")

    # Step 2: Analyze patterns
    analyzer = ClimbPatternAnalyzer()
    patterns = analyzer.analyze_all_episodes(df, episodes)

    # Step 3: Show detailed view of a few episodes
    print("\n" + "="*80)
    print("DETAILED VIEW OF FIRST 3 EPISODES")
    print("="*80)

    for ep in episodes[:3]:
        print(f"\n{'='*80}")
        print(f"EPISODE #{ep['episode_num']}")
        print(f"{'='*80}")
        print(f"Start: {ep['start_time']}")
        print(f"Peak:  {ep['high_time']}")
        print(f"End:   {ep['end_time']}")
        print(f"Climb: ${ep['start_price']:.2f} → ${ep['high_price']:.2f} (+{ep['total_climb_pct']:.2f}%)")
        print(f"Duration: {ep['duration_minutes']:.0f} minutes")

        # Show the candles
        episode_data = detector.extract_episode_data(df, ep)
        print(f"\nCandles in this episode:")
        print(episode_data[['timestamp', 'open', 'high', 'low', 'close', 'volume']].to_string())

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print(f"\nNext steps:")
    print(f"1. Review climb_episodes.json for all {len(episodes)} episodes")
    print(f"2. Study the common patterns identified above")
    print(f"3. Build detection logic based on these patterns")
    print(f"4. THEN we can start trading")


if __name__ == "__main__":
    main()
