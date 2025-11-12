"""
VISUALIZE CLIMB EPISODES

Create candlestick charts for each climb episode so we can SEE the patterns
like they appear on a real trading screen.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
import json
from datetime import datetime


def plot_candlestick_episode(df, episode, ax):
    """
    Plot candlestick chart for a single episode
    """
    # Get episode data
    start_idx = episode['start_idx']
    end_idx = episode['end_idx']
    high_idx = episode['high_idx']

    # Add some context - 10 candles before and after
    context_before = 10
    context_after = 20
    plot_start = max(0, start_idx - context_before)
    plot_end = min(len(df) - 1, end_idx + context_after)

    episode_df = df.iloc[plot_start:plot_end + 1].copy()
    episode_df['idx'] = range(len(episode_df))

    # Plot candlesticks
    for idx, row in episode_df.iterrows():
        candle_idx = episode_df.loc[idx, 'idx']

        # Determine color
        if row['close'] >= row['open']:
            color = 'green'
            body_low = row['open']
            body_high = row['close']
        else:
            color = 'red'
            body_low = row['close']
            body_high = row['open']

        # Highlight key candles
        if idx == start_idx:
            color = 'yellow'  # Spike start
            alpha = 1.0
            edgecolor = 'black'
            linewidth = 2
        elif idx == high_idx:
            color = 'orange'  # Peak
            alpha = 1.0
            edgecolor = 'black'
            linewidth = 2
        elif idx == end_idx:
            color = 'purple'  # Retracement
            alpha = 1.0
            edgecolor = 'black'
            linewidth = 2
        else:
            alpha = 0.7
            edgecolor = color
            linewidth = 0.5

        # Wick
        ax.plot([candle_idx, candle_idx], [row['low'], row['high']],
                color=color, linewidth=1, alpha=alpha)

        # Body
        body_height = body_high - body_low
        body = Rectangle((candle_idx - 0.3, body_low), 0.6, body_height,
                        facecolor=color, edgecolor=edgecolor,
                        alpha=alpha, linewidth=linewidth)
        ax.add_patch(body)

    # Mark the climb zone
    climb_start_candle = start_idx - plot_start
    climb_high_candle = high_idx - plot_start
    climb_end_candle = end_idx - plot_start

    # Shade the climbing phase
    ax.axvspan(climb_start_candle, climb_high_candle, alpha=0.1, color='green', label='Climb')
    ax.axvspan(climb_high_candle, climb_end_candle, alpha=0.1, color='red', label='Retracement')

    # Mark key prices
    ax.axhline(episode['start_price'], color='blue', linestyle='--', linewidth=1, alpha=0.5, label='Start')
    ax.axhline(episode['high_price'], color='orange', linestyle='--', linewidth=1, alpha=0.5, label='Peak')
    ax.axhline(episode['end_price'], color='purple', linestyle='--', linewidth=1, alpha=0.5, label='End')

    # Title with key stats
    title = (f"Episode #{episode['episode_num']}: "
            f"${episode['start_price']:.2f} → ${episode['high_price']:.2f} (+{episode['total_climb_pct']:.1f}%)\n"
            f"Duration: {episode['duration_minutes']:.0f}min | "
            f"Retracement: {episode['retracement_pct']:.1f}%")
    ax.set_title(title, fontsize=10, fontweight='bold')

    # Labels
    ax.set_xlabel('Candles')
    ax.set_ylabel('Price ($)')
    ax.grid(True, alpha=0.3)

    # Legend
    legend_elements = [
        mpatches.Patch(facecolor='yellow', edgecolor='black', label='Spike Start'),
        mpatches.Patch(facecolor='orange', edgecolor='black', label='Peak'),
        mpatches.Patch(facecolor='purple', edgecolor='black', label='Retracement End'),
        mpatches.Patch(facecolor='green', alpha=0.3, label='Climbing Phase'),
        mpatches.Patch(facecolor='red', alpha=0.3, label='Reversal Phase')
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=8)


def create_episode_charts(df, episodes, output_file='climb_episodes_charts.png'):
    """
    Create a grid of charts showing all episodes
    """
    num_episodes = len(episodes)
    cols = 4
    rows = (num_episodes + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(20, 5 * rows))
    fig.suptitle('All Climb Episodes - Visual Analysis', fontsize=16, fontweight='bold')

    # Flatten axes for easier iteration
    if rows == 1:
        axes = axes.reshape(1, -1)
    axes = axes.flatten()

    # Plot each episode
    for i, episode in enumerate(episodes):
        plot_candlestick_episode(df, episode, axes[i])

    # Hide unused subplots
    for i in range(num_episodes, len(axes)):
        axes[i].axis('off')

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n✓ Saved chart to {output_file}")

    return fig


def create_detailed_top_episodes(df, episodes, top_n=3):
    """
    Create detailed individual charts for the top N biggest episodes
    """
    # Sort by climb size
    sorted_episodes = sorted(episodes, key=lambda x: x['total_climb_pct'], reverse=True)

    for i, episode in enumerate(sorted_episodes[:top_n]):
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10))

        # Get episode data with more context
        start_idx = episode['start_idx']
        end_idx = episode['end_idx']
        plot_start = max(0, start_idx - 20)
        plot_end = min(len(df) - 1, end_idx + 30)

        episode_df = df.iloc[plot_start:plot_end + 1].copy()
        episode_df['idx'] = range(len(episode_df))

        # Plot 1: Candlestick chart
        plot_candlestick_episode(df, episode, ax1)

        # Plot 2: Velocity and Volume
        episode_df['velocity_pct'] = episode_df['close'].pct_change() * 100
        episode_df['volume_ma'] = episode_df['volume'].rolling(10).mean()

        ax2_twin = ax2.twinx()

        # Velocity
        ax2.plot(episode_df['idx'], episode_df['velocity_pct'],
                color='blue', linewidth=2, label='Velocity (%)')
        ax2.axhline(0, color='gray', linestyle='--', linewidth=0.5)
        ax2.set_ylabel('Velocity (%)', color='blue')
        ax2.tick_params(axis='y', labelcolor='blue')

        # Volume
        ax2_twin.bar(episode_df['idx'], episode_df['volume'],
                    alpha=0.3, color='purple', label='Volume')
        ax2_twin.plot(episode_df['idx'], episode_df['volume_ma'],
                     color='purple', linewidth=2, label='Volume MA')
        ax2_twin.set_ylabel('Volume', color='purple')
        ax2_twin.tick_params(axis='y', labelcolor='purple')

        # Mark key points
        climb_start = start_idx - plot_start
        climb_high = episode['high_idx'] - plot_start
        climb_end = end_idx - plot_start

        ax2.axvline(climb_start, color='yellow', linestyle='--', linewidth=2, alpha=0.7)
        ax2.axvline(climb_high, color='orange', linestyle='--', linewidth=2, alpha=0.7)
        ax2.axvline(climb_end, color='purple', linestyle='--', linewidth=2, alpha=0.7)

        ax2.set_xlabel('Candles')
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='upper left')

        fig.suptitle(f"Episode #{episode['episode_num']} Detailed Analysis\n"
                    f"${episode['start_price']:.2f} → ${episode['high_price']:.2f} "
                    f"(+{episode['total_climb_pct']:.1f}%, {episode['duration_minutes']:.0f} min)",
                    fontsize=14, fontweight='bold')

        plt.tight_layout()
        output_file = f"episode_{episode['episode_num']}_detailed.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"✓ Saved detailed chart: {output_file}")
        plt.close()


def analyze_last_5_candles_before_peak(df, episodes):
    """
    Visual analysis of the last 5 candles before each peak
    """
    fig, axes = plt.subplots(4, 4, figsize=(20, 16))
    fig.suptitle('Last 5 Candles Before Peak - All Episodes', fontsize=16, fontweight='bold')

    axes = axes.flatten()

    for i, episode in enumerate(episodes):
        high_idx = episode['high_idx']

        # Get last 5 candles before peak
        last_5 = df.iloc[high_idx-4:high_idx+1].copy()
        last_5['idx'] = range(len(last_5))

        ax = axes[i]

        # Plot candlesticks
        for idx, row in last_5.iterrows():
            candle_idx = last_5.loc[idx, 'idx']

            if row['close'] >= row['open']:
                color = 'green'
                body_low = row['open']
                body_high = row['close']
            else:
                color = 'red'
                body_low = row['close']
                body_high = row['open']

            # Wick
            ax.plot([candle_idx, candle_idx], [row['low'], row['high']],
                   color=color, linewidth=1)

            # Body
            body_height = body_high - body_low
            body = Rectangle((candle_idx - 0.3, body_low), 0.6, body_height,
                           facecolor=color, alpha=0.7)
            ax.add_patch(body)

        # Calculate velocity trend
        velocities = last_5['close'].pct_change() * 100
        slowing = "SLOWING" if abs(velocities.iloc[-1]) < abs(velocities.iloc[1]) else "ACCELERATING"

        ax.set_title(f"Ep #{episode['episode_num']}: +{episode['total_climb_pct']:.1f}% | {slowing}",
                    fontsize=9)
        ax.set_xlim(-0.5, 4.5)
        ax.grid(True, alpha=0.3)
        ax.set_xticks(range(5))
        ax.set_xticklabels(['-4', '-3', '-2', '-1', 'PEAK'])

    # Hide unused
    for i in range(len(episodes), len(axes)):
        axes[i].axis('off')

    plt.tight_layout()
    plt.savefig('last_5_candles_analysis.png', dpi=150, bbox_inches='tight')
    print(f"✓ Saved last 5 candles analysis: last_5_candles_analysis.png")


def main():
    """
    Main visualization
    """
    print("="*80)
    print("CLIMB EPISODE VISUALIZATION")
    print("="*80)
    print("\nCreating visual analysis of all climb episodes...")

    # Load data
    df = pd.read_csv('SOL_USDT_1min_7days.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Load episodes
    with open('climb_episodes.json', 'r') as f:
        episodes = json.load(f)

    print(f"\nLoaded {len(episodes)} episodes")

    # 1. Create overview grid
    print("\n1. Creating overview grid of all episodes...")
    create_episode_charts(df, episodes)

    # 2. Create detailed charts for top 3
    print("\n2. Creating detailed analysis for top 3 biggest climbs...")
    create_detailed_top_episodes(df, episodes, top_n=3)

    # 3. Analyze last 5 candles before peak
    print("\n3. Analyzing last 5 candles before each peak...")
    analyze_last_5_candles_before_peak(df, episodes)

    print("\n" + "="*80)
    print("VISUALIZATION COMPLETE")
    print("="*80)
    print("\nGenerated files:")
    print("  - climb_episodes_charts.png (overview of all 16 episodes)")
    print("  - episode_1_detailed.png (detailed view of episode #1)")
    print("  - episode_7_detailed.png (detailed view of episode #7)")
    print("  - episode_12_detailed.png (detailed view of episode #12)")
    print("  - last_5_candles_analysis.png (pre-peak patterns)")
    print("\nNow you can SEE the patterns like on a trading screen!")


if __name__ == "__main__":
    main()
