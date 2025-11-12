"""
Comprehensive Backtest for Perfect Timing Analysis

Generates realistic liquidation cascade data and backtests the physics-based strategy.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from models.momentum import MomentumCalculator, MomentumSignals
from models.mean_reversion import MeanReversionDetector, MeanReversionStrategy
from models.terminal_velocity import TerminalVelocityDetector, TerminalVelocityStrategy
from analysis.liquidations import LiquidationDetector, CascadeSignalGenerator
from backtesting.engine import BacktestEngine, print_backtest_results


def generate_realistic_cascade_data(periods=10000, base_price=100.0):
    """
    Generate realistic cryptocurrency price data with liquidation cascades

    Patterns:
    - Normal trading with random walk
    - Periodic liquidation cascades (rapid drops)
    - Mean reversion after cascades
    - Realistic volume spikes
    """
    print("Generating realistic market data with liquidation cascades...")

    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=periods, freq='1min')

    prices = []
    volumes = []
    current_price = base_price

    # Parameters for cascade generation
    cascade_probability = 0.005  # 0.5% chance per period
    cascade_duration_range = (20, 60)  # 20-60 minutes
    cascade_magnitude_range = (0.5, 3.0)  # 0.5% to 3% drop

    in_cascade = False
    cascade_remaining = 0
    cascade_start_price = 0
    cascade_target_price = 0

    for i in range(periods):
        # Check if we should start a new cascade
        if not in_cascade and np.random.random() < cascade_probability:
            in_cascade = True
            cascade_remaining = np.random.randint(*cascade_duration_range)
            cascade_start_price = current_price
            cascade_magnitude = np.random.uniform(*cascade_magnitude_range)
            cascade_target_price = current_price * (1 - cascade_magnitude / 100)
            print(f"  Cascade {len([p for p in prices if p < current_price])} starting at minute {i}: {cascade_magnitude:.2f}% drop")

        if in_cascade:
            # During cascade: accelerating drop, then deceleration (terminal velocity)
            progress = 1 - (cascade_remaining / (cascade_duration_range[1]))

            # Create acceleration curve: fast at first, then slowing (terminal velocity)
            if progress < 0.6:  # Acceleration phase
                speed_factor = 1.5
            elif progress < 0.8:  # Peak momentum
                speed_factor = 1.2
            else:  # Terminal velocity / deceleration
                speed_factor = 0.5

            # Price moves toward target
            price_diff = cascade_target_price - current_price
            current_price += price_diff * 0.1 * speed_factor + np.random.randn() * 0.05

            # High volume during cascade
            volume = np.random.randint(5000, 20000)

            cascade_remaining -= 1
            if cascade_remaining <= 0:
                in_cascade = False
                # Bounce after cascade (mean reversion)
                bounce_periods = 10
                for _ in range(min(bounce_periods, periods - i - 1)):
                    pass  # Handle in next iterations
        else:
            # Normal trading: small random walk
            price_change = np.random.randn() * 0.02
            current_price += price_change

            # Normal volume
            volume = np.random.randint(1000, 3000)

        prices.append(current_price)
        volumes.append(volume)

    prices_series = pd.Series(prices, index=dates)
    volumes_series = pd.Series(volumes, index=dates)

    print(f"Generated {periods} periods of data")
    print(f"Price range: ${prices_series.min():.2f} - ${prices_series.max():.2f}")
    print(f"Total price change: {((prices_series.iloc[-1] - prices_series.iloc[0]) / prices_series.iloc[0] * 100):.2f}%")

    return prices_series, volumes_series


def run_complete_backtest(prices, volumes, leverage=500, take_profit_pct=0.2, stop_loss_pct=0.15):
    """
    Run complete backtest with all physics models
    """
    print("\n" + "="*80)
    print("RUNNING COMPLETE PHYSICS-BASED BACKTEST")
    print("="*80)

    # Step 1: Calculate physics metrics
    print("\n1. Calculating physics metrics...")
    calc = MomentumCalculator(window=20)

    velocities = calc.calculate_velocity(prices)
    accelerations = calc.calculate_acceleration(velocities)
    momentum = calc.calculate_momentum(prices, volumes)

    print(f"   ✓ Momentum range: {momentum.min():.2f} to {momentum.max():.2f}")

    # Step 2: Mean reversion analysis
    print("\n2. Analyzing mean reversion opportunities...")
    mean_detector = MeanReversionDetector(window=20, num_std=2.0)
    mean_strategy = MeanReversionStrategy(mean_detector, min_zscore=1.5)  # Lower threshold for more signals

    mean_signals = mean_strategy.generate_short_signals(prices)
    mean_signal_count = mean_signals['signal'].sum()
    print(f"   ✓ Mean reversion signals detected: {mean_signal_count}")

    # Step 3: Terminal velocity detection
    print("\n3. Detecting terminal velocity points...")
    tv_detector = TerminalVelocityDetector(
        velocity_window=5,
        acceleration_threshold=-0.3,  # More sensitive
        momentum_decay_threshold=0.85
    )
    tv_strategy = TerminalVelocityStrategy(
        tv_detector,
        take_profit_pct=take_profit_pct,
        stop_loss_pct=stop_loss_pct
    )

    mean_prices = prices.rolling(20).mean()
    tv_signals = tv_strategy.generate_entry_signals(
        prices, volumes, velocities, accelerations, momentum, mean_prices
    )

    terminal_v_count = tv_signals['final_signal'].sum()
    print(f"   ✓ Terminal velocity signals detected: {terminal_v_count}")

    # Step 4: Liquidation cascade detection
    print("\n4. Detecting liquidation cascades...")
    liq_detector = LiquidationDetector(
        volume_spike_threshold=1.8,  # More sensitive
        min_cascade_size=3
    )
    cascade_gen = CascadeSignalGenerator(liq_detector)

    cascade_signals = cascade_gen.generate_cascade_signals(
        prices, volumes, momentum, accelerations
    )

    cascade_count = cascade_signals['entry_signal'].sum()
    print(f"   ✓ Cascade entry signals detected: {cascade_count}")

    # Step 5: Combine signals (use terminal velocity as primary)
    print("\n5. Combining signals for final strategy...")

    # Add price to signals
    tv_signals['price'] = prices

    # Boost signal when multiple indicators agree
    combined_signal_strength = (
        tv_signals['signal_strength'] * 0.5 +
        mean_signals['signal'].astype(float) * 0.3 +
        cascade_signals['entry_signal'].astype(float) * 0.2
    )

    tv_signals['combined_signal_strength'] = combined_signal_strength
    tv_signals['final_signal'] = combined_signal_strength > 0.5

    final_signal_count = tv_signals['final_signal'].sum()
    print(f"   ✓ Final combined signals: {final_signal_count}")

    # Step 6: Run backtest
    print("\n6. Running backtest with {leverage}x leverage...")
    engine = BacktestEngine(
        initial_capital=1000.0,
        leverage=leverage,
        take_profit_pct=take_profit_pct,
        stop_loss_pct=stop_loss_pct,
        commission_pct=0.04
    )

    result = engine.run_backtest(prices, volumes, tv_signals)

    return result, tv_signals


def plot_backtest_results(result, prices, signals):
    """
    Create visualization of backtest results
    """
    print("\n7. Generating visualizations...")

    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    fig.patch.set_facecolor('#1e1e1e')

    for ax in axes:
        ax.set_facecolor('#2a2a2a')
        ax.tick_params(colors='white')
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.spines['bottom'].set_color('white')
        ax.spines['top'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['right'].set_color('white')

    # Plot 1: Price with entry/exit points
    ax1 = axes[0]
    ax1.plot(prices.index, prices.values, label='Price', color='#00ff00', linewidth=1, alpha=0.7)

    # Mark entry points
    entry_times = [t.entry_time for t in result.trades]
    entry_prices = [t.entry_price for t in result.trades]
    ax1.scatter(entry_times, entry_prices, color='yellow', s=50, marker='v', label='Entry', zorder=5)

    # Mark exits (wins = green, losses = red)
    win_times = [t.exit_time for t in result.trades if t.status == 'win']
    win_prices = [t.exit_price for t in result.trades if t.status == 'win']
    loss_times = [t.exit_time for t in result.trades if t.status == 'loss']
    loss_prices = [t.exit_price for t in result.trades if t.status == 'loss']

    ax1.scatter(win_times, win_prices, color='lime', s=50, marker='^', label='Win', zorder=5)
    ax1.scatter(loss_times, loss_prices, color='red', s=50, marker='x', label='Loss', zorder=5)

    ax1.set_ylabel('Price ($)', color='white')
    ax1.set_title('Price Action with Entry/Exit Points', color='white', fontsize=14, fontweight='bold')
    ax1.legend(facecolor='#2a2a2a', edgecolor='white', labelcolor='white')
    ax1.grid(True, alpha=0.2)

    # Plot 2: Signal strength
    ax2 = axes[1]
    ax2.plot(signals.index, signals['signal_strength'], label='Signal Strength', color='cyan', linewidth=1)
    ax2.axhline(y=0.7, color='yellow', linestyle='--', alpha=0.5, label='Threshold')
    ax2.fill_between(signals.index, 0, signals['signal_strength'], alpha=0.3, color='cyan')
    ax2.set_ylabel('Signal Strength', color='white')
    ax2.set_title('Terminal Velocity Signal Strength', color='white', fontsize=14, fontweight='bold')
    ax2.legend(facecolor='#2a2a2a', edgecolor='white', labelcolor='white')
    ax2.grid(True, alpha=0.2)

    # Plot 3: Equity curve
    ax3 = axes[2]
    equity_curve = result.equity_curve
    ax3.plot(equity_curve.index, equity_curve.values, color='#00ff00', linewidth=2, label='Equity')
    ax3.axhline(y=result.initial_capital, color='white', linestyle='--', alpha=0.5, label='Starting Capital')
    ax3.fill_between(equity_curve.index, result.initial_capital, equity_curve.values,
                     where=(equity_curve.values >= result.initial_capital), alpha=0.3, color='green', interpolate=True)
    ax3.fill_between(equity_curve.index, result.initial_capital, equity_curve.values,
                     where=(equity_curve.values < result.initial_capital), alpha=0.3, color='red', interpolate=True)
    ax3.set_ylabel('Equity ($)', color='white')
    ax3.set_xlabel('Time', color='white')
    ax3.set_title('Equity Curve', color='white', fontsize=14, fontweight='bold')
    ax3.legend(facecolor='#2a2a2a', edgecolor='white', labelcolor='white')
    ax3.grid(True, alpha=0.2)

    plt.tight_layout()

    # Save plot
    output_path = 'backtest_results.png'
    plt.savefig(output_path, dpi=150, facecolor='#1e1e1e')
    print(f"   ✓ Visualization saved to: {output_path}")

    return output_path


def analyze_trade_distribution(result):
    """
    Analyze distribution of wins and losses
    """
    print("\n" + "="*80)
    print("TRADE DISTRIBUTION ANALYSIS")
    print("="*80)

    if len(result.trades) == 0:
        print("No trades executed.")
        return

    wins = [t for t in result.trades if t.status == 'win']
    losses = [t for t in result.trades if t.status == 'loss']

    print(f"\nWinning Trades: {len(wins)}")
    if len(wins) > 0:
        win_pnls = [t.pnl for t in wins]
        print(f"  Total profit: ${sum(win_pnls):.2f}")
        print(f"  Average win: ${np.mean(win_pnls):.2f}")
        print(f"  Best win: ${max(win_pnls):.2f}")
        print(f"  Worst win: ${min(win_pnls):.2f}")

    print(f"\nLosing Trades: {len(losses)}")
    if len(losses) > 0:
        loss_pnls = [t.pnl for t in losses]
        print(f"  Total loss: ${sum(loss_pnls):.2f}")
        print(f"  Average loss: ${np.mean(loss_pnls):.2f}")
        print(f"  Worst loss: ${min(loss_pnls):.2f}")
        print(f"  Best loss: ${max(loss_pnls):.2f}")

    # Trade duration analysis
    print(f"\nTrade Duration Analysis:")
    durations = [(t.exit_time - t.entry_time).total_seconds() / 60 for t in result.trades if t.exit_time]
    if durations:
        print(f"  Average duration: {np.mean(durations):.1f} minutes")
        print(f"  Shortest trade: {min(durations):.1f} minutes")
        print(f"  Longest trade: {max(durations):.1f} minutes")


def main():
    """
    Run complete backtest
    """
    print("\n" + "="*80)
    print("PERFECT TIMING ANALYSIS - COMPREHENSIVE BACKTEST")
    print("Physics-Based Liquidation Cascade Trading Strategy")
    print("="*80)

    # Generate data
    prices, volumes = generate_realistic_cascade_data(periods=10000, base_price=100.0)

    # Run backtest
    result, signals = run_complete_backtest(
        prices,
        volumes,
        leverage=500,
        take_profit_pct=0.2,
        stop_loss_pct=0.15
    )

    # Print results
    print_backtest_results(result)

    # Trade distribution
    analyze_trade_distribution(result)

    # Generate visualizations
    plot_path = plot_backtest_results(result, prices, signals)

    # Final summary
    print("\n" + "="*80)
    print("BACKTEST COMPLETE")
    print("="*80)
    print(f"\nResults Summary:")
    print(f"  Initial Capital: ${result.initial_capital:,.2f}")
    print(f"  Final Capital: ${result.final_capital:,.2f}")
    print(f"  Total Return: {result.total_return_pct:.2f}%")
    print(f"  Win Rate: {result.win_rate * 100:.1f}%")
    print(f"  Profit Factor: {result.profit_factor:.2f}")
    print(f"  Max Drawdown: {result.max_drawdown:.2f}%")
    print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")

    if result.total_return_pct > 0:
        print(f"\n✅ Strategy is PROFITABLE on this backtest!")
        print(f"   Turned ${result.initial_capital:.0f} into ${result.final_capital:.0f}")
    else:
        print(f"\n❌ Strategy lost money on this backtest.")
        print(f"   Consider adjusting parameters or strategy.")

    print(f"\n📊 Visualization saved to: {plot_path}")
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
