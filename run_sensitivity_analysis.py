"""
Sensitivity Analysis - Test strategy with different parameters
"""

import numpy as np
import pandas as pd
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from models.momentum import MomentumCalculator
from models.terminal_velocity import TerminalVelocityDetector, TerminalVelocityStrategy
from backtesting.engine import BacktestEngine

# Import data generator from main backtest
from run_backtest import generate_realistic_cascade_data


def run_sensitivity_analysis():
    """
    Test strategy with different parameter combinations
    """
    print("\n" + "="*80)
    print("SENSITIVITY ANALYSIS - Testing Different Parameters")
    print("="*80)

    # Generate data once
    print("\nGenerating data...")
    prices, volumes = generate_realistic_cascade_data(periods=10000, base_price=100.0)

    # Calculate physics metrics once
    calc = MomentumCalculator(window=20)
    velocities = calc.calculate_velocity(prices)
    accelerations = calc.calculate_acceleration(velocities)
    momentum = calc.calculate_momentum(prices, volumes)
    mean_prices = prices.rolling(20).mean()

    # Test different parameter combinations
    test_configs = [
        # (acceleration_threshold, momentum_decay_threshold, take_profit%, stop_loss%, description)
        (-0.5, 0.8, 0.2, 0.15, "Conservative (default)"),
        (-0.3, 0.85, 0.2, 0.15, "More signals"),
        (-0.7, 0.7, 0.2, 0.15, "Very conservative"),
        (-0.3, 0.85, 0.3, 0.2, "Wider targets"),
        (-0.3, 0.85, 0.15, 0.1, "Tighter targets"),
    ]

    results = []

    for accel_thresh, momentum_decay, tp_pct, sl_pct, desc in test_configs:
        print(f"\n{'='*80}")
        print(f"Testing: {desc}")
        print(f"  Acceleration threshold: {accel_thresh}")
        print(f"  Momentum decay threshold: {momentum_decay}")
        print(f"  Take profit: {tp_pct}% | Stop loss: {sl_pct}%")
        print(f"{'='*80}")

        # Create detector with these parameters
        tv_detector = TerminalVelocityDetector(
            velocity_window=5,
            acceleration_threshold=accel_thresh,
            momentum_decay_threshold=momentum_decay
        )
        tv_strategy = TerminalVelocityStrategy(
            tv_detector,
            take_profit_pct=tp_pct,
            stop_loss_pct=sl_pct
        )

        # Generate signals
        tv_signals = tv_strategy.generate_entry_signals(
            prices, volumes, velocities, accelerations, momentum, mean_prices
        )

        tv_signals['price'] = prices
        signal_count = tv_signals['final_signal'].sum()
        print(f"Signals detected: {signal_count}")

        if signal_count == 0:
            print("⚠️  No signals detected with these parameters")
            results.append({
                'config': desc,
                'signals': 0,
                'trades': 0,
                'win_rate': 0,
                'return_pct': 0,
                'profit_factor': 0,
                'max_drawdown': 0
            })
            continue

        # Run backtest
        engine = BacktestEngine(
            initial_capital=1000.0,
            leverage=500,
            take_profit_pct=tp_pct,
            stop_loss_pct=sl_pct,
            commission_pct=0.04
        )

        result = engine.run_backtest(prices, volumes, tv_signals)

        # Store results
        results.append({
            'config': desc,
            'signals': signal_count,
            'trades': result.total_trades,
            'win_rate': result.win_rate * 100,
            'return_pct': result.total_return_pct,
            'profit_factor': result.profit_factor if result.profit_factor != float('inf') else 999,
            'max_drawdown': result.max_drawdown,
            'final_capital': result.final_capital
        })

        print(f"\nResults:")
        print(f"  Total trades: {result.total_trades}")
        print(f"  Win rate: {result.win_rate * 100:.1f}%")
        print(f"  Total return: {result.total_return_pct:.2f}%")
        print(f"  Final capital: ${result.final_capital:,.2f}")
        print(f"  Profit factor: {result.profit_factor:.2f}")
        print(f"  Max drawdown: {result.max_drawdown:.2f}%")

    # Summary table
    print("\n" + "="*80)
    print("SENSITIVITY ANALYSIS SUMMARY")
    print("="*80)

    df = pd.DataFrame(results)
    print("\n" + df.to_string(index=False))

    # Best configurations
    print("\n" + "="*80)
    print("KEY FINDINGS")
    print("="*80)

    if len(df[df['return_pct'] > 0]) > 0:
        best_return = df.loc[df['return_pct'].idxmax()]
        print(f"\n✅ Best Total Return:")
        print(f"   Config: {best_return['config']}")
        print(f"   Return: {best_return['return_pct']:.2f}%")
        print(f"   Win Rate: {best_return['win_rate']:.1f}%")

        if len(df[df['trades'] > 0]) > 0:
            best_winrate = df[df['trades'] > 0].loc[df[df['trades'] > 0]['win_rate'].idxmax()]
            print(f"\n🎯 Best Win Rate:")
            print(f"   Config: {best_winrate['config']}")
            print(f"   Win Rate: {best_winrate['win_rate']:.1f}%")
            print(f"   Return: {best_winrate['return_pct']:.2f}%")

        most_trades = df.loc[df['trades'].idxmax()]
        print(f"\n📊 Most Active:")
        print(f"   Config: {most_trades['config']}")
        print(f"   Trades: {most_trades['trades']}")
        print(f"   Return: {most_trades['return_pct']:.2f}%")

    print("\n" + "="*80)


if __name__ == "__main__":
    run_sensitivity_analysis()
