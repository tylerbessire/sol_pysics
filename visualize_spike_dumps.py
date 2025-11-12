"""
Visualize the fast spike-dump episodes
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import json


def plot_spike_dump_episode(df, episode, ax):
    """
    Plot candlestick chart for a spike-dump episode
    """
    # Get episode data with context
    start_idx = episode['spike_start_idx']
    end_idx = episode['dump_end_idx']

    context_before = 20
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
            color = 'yellow'
            alpha = 1.0
            edgecolor = 'black'
            linewidth = 2
        elif idx == episode['spike_high_idx']:
            color = 'orange'
            alpha = 1.0
            edgecolor = 'black'
            linewidth = 2
        elif idx == end_idx:
            color = 'purple'
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

    # Shade the spike and dump zones
    spike_start_candle = start_idx - plot_start
    spike_high_candle = episode['spike_high_idx'] - plot_start
    dump_end_candle = end_idx - plot_start

    ax.axvspan(spike_start_candle, spike_high_candle, alpha=0.15, color='green', label='Spike')
    ax.axvspan(spike_high_candle, dump_end_candle, alpha=0.15, color='red', label='Dump')

    # Mark key prices
    ax.axhline(episode['spike_start_price'], color='blue', linestyle='--', linewidth=1, alpha=0.5)
    ax.axhline(episode['spike_high_price'], color='orange', linestyle='--', linewidth=1, alpha=0.5)
    ax.axhline(episode['dump_end_price'], color='purple', linestyle='--', linewidth=1, alpha=0.5)

    # Title
    title = (f"Episode #{episode['episode_num']}: "
            f"${episode['spike_start_price']:.2f} → ${episode['spike_high_price']:.2f} (+{episode['spike_pct']:.1f}%) → "
            f"${episode['dump_end_price']:.2f} (-{episode['dump_pct']:.1f}%)\\n"
            f"Duration: {episode['total_duration_minutes']:.1f} min ({episode['candles_in_episode']} candles)")
    ax.set_title(title, fontsize=9, fontweight='bold')

    ax.set_xlabel('Candles')
    ax.set_ylabel('Price ($)')
    ax.grid(True, alpha=0.3)


def main():
    print("="*80)
    print("SPIKE-DUMP EPISODE VISUALIZATION")
    print("="*80)

    # Load data
    df = pd.read_csv('SOL_USDT_1min_7days.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Load episodes
    with open('spike_dump_episodes.json', 'r') as f:
        episodes = json.load(f)

    print(f"\\nLoaded {len(episodes)} spike-dump episodes")

    if not episodes:
        print("No episodes to visualize")
        return

    # Create grid
    num_episodes = len(episodes)
    cols = 2
    rows = (num_episodes + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(16, 5 * rows))
    fig.suptitle('Fast Spike-Dump Episodes', fontsize=14, fontweight='bold')

    if rows == 1:
        axes = axes.reshape(1, -1)
    axes = axes.flatten()

    # Plot each episode
    for i, episode in enumerate(episodes):
        plot_spike_dump_episode(df, episode, axes[i])

    # Hide unused
    for i in range(num_episodes, len(axes)):
        axes[i].axis('off')

    plt.tight_layout()
    plt.savefig('spike_dump_episodes.png', dpi=150, bbox_inches='tight')
    print(f"✓ Saved visualization: spike_dump_episodes.png")


if __name__ == "__main__":
    main()
