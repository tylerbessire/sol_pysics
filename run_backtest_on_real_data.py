"""
Phase 1 Comprehensive Backtest on Realistic Data

Tests the Perfect Timing Analysis strategy on realistic market data for:
- SOL/USDT
- BTC/USDT
- ETH/USDT

Validates strategy across multiple assets and market conditions.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from models.momentum import MomentumCalculator
from models.terminal_velocity import TerminalVelocityDetector, TerminalVelocityStrategy
from models.mean_reversion import MeanReversionDetector, MeanReversionStrategy
from analysis.liquidations import LiquidationDetector, CascadeSignalGenerator
from backtesting.engine import BacktestEngine, print_backtest_results


def load_realistic_data(symbol='SOL_USDT'):
    """Load realistic market data"""
    filename = f"data/{symbol}_1m_realistic_30d.csv"
    cascade_filename = f"data/{symbol}_cascades.json"

    if not os.path.exists(filename):
        print(f"Error: {filename} not found. Run generate_realistic_market_data.py first")
        return None, None

    df = pd.read_csv(filename, index_col='timestamp', parse_dates=True)

    # Load cascade events
    if os.path.exists(cascade_filename):
        with open(cascade_filename, 'r') as f:
            cascades = json.load(f)
    else:
        cascades = []

    print(f"✓ Loaded {symbol}: {len(df)} candles, {len(cascades)} known cascades")

    return df, cascades


def run_comprehensive_backtest(df, symbol, cascades_known=None, params=None):
    """
    Run complete backtest on realistic data
    """
    if params is None:
        params = {
            'acceleration_threshold': -0.3,
            'momentum_decay_threshold': 0.85,
            'take_profit_pct': 0.2,
            'stop_loss_pct': 0.15,
            'leverage': 500
        }

    print(f"\n{'='*80}")
    print(f"BACKTESTING {symbol}")
    print(f"{'='*80}")

    prices = df['close']
    volumes = df['volume']

    # Calculate physics metrics
    print("\n1. Calculating physics metrics...")
    calc = MomentumCalculator(window=20)
    velocities = calc.calculate_velocity(prices)
    accelerations = calc.calculate_acceleration(velocities)
    momentum = calc.calculate_momentum(prices, volumes)

    # Terminal velocity detection
    print("2. Detecting terminal velocity...")
    tv_detector = TerminalVelocityDetector(
        velocity_window=5,
        acceleration_threshold=params['acceleration_threshold'],
        momentum_decay_threshold=params['momentum_decay_threshold']
    )
    tv_strategy = TerminalVelocityStrategy(
        tv_detector,
        take_profit_pct=params['take_profit_pct'],
        stop_loss_pct=params['stop_loss_pct']
    )

    mean_prices = prices.rolling(20).mean()
    tv_signals = tv_strategy.generate_entry_signals(
        prices, volumes, velocities, accelerations, momentum, mean_prices
    )

    tv_signals['price'] = prices
    signal_count = tv_signals['final_signal'].sum()
    print(f"   ✓ Terminal velocity signals: {signal_count}")

    # Run backtest
    print("3. Running backtest...")
    engine = BacktestEngine(
        initial_capital=1000.0,
        leverage=params['leverage'],
        take_profit_pct=params['take_profit_pct'],
        stop_loss_pct=params['stop_loss_pct'],
        commission_pct=0.04
    )

    result = engine.run_backtest(prices, volumes, tv_signals)

    # Analyze signal timing vs known cascades
    if cascades_known:
        print("\n4. Analyzing signal timing...")
        analyze_signal_timing(tv_signals, cascades_known)

    return result, tv_signals


def analyze_signal_timing(signals, known_cascades):
    """
    Analyze how well signals align with known cascade events
    """
    signal_times = signals[signals['final_signal']].index

    if len(signal_times) == 0:
        print("   No signals to analyze")
        return

    # Check how many signals occur during/after cascades
    signals_during_cascades = 0
    for sig_time in signal_times:
        for cascade in known_cascades:
            cascade_start = pd.to_datetime(cascade['start_time'])
            cascade_end = cascade_start + pd.Timedelta(minutes=cascade['duration'])

            # Signal within cascade window or shortly after (for terminal velocity)
            if cascade_start <= sig_time <= cascade_end + pd.Timedelta(minutes=10):
                signals_during_cascades += 1
                break

    if len(signal_times) > 0:
        accuracy = (signals_during_cascades / len(signal_times)) * 100
        print(f"   Signals near known cascades: {signals_during_cascades}/{len(signal_times)} ({accuracy:.1f}%)")


def compare_across_assets():
    """
    Compare strategy performance across all assets
    """
    print("\n" + "="*80)
    print("PHASE 1: COMPREHENSIVE MULTI-ASSET BACKTEST")
    print("="*80)

    assets = ['SOL_USDT', 'BTC_USDT', 'ETH_USDT']

    results_summary = []

    for symbol in assets:
        # Load data
        df, cascades = load_realistic_data(symbol)

        if df is None:
            continue

        # Run backtest
        result, signals = run_comprehensive_backtest(df, symbol, cascades)

        # Store results
        results_summary.append({
            'symbol': symbol.replace('_', '/'),
            'total_return_pct': result.total_return_pct,
            'total_trades': result.total_trades,
            'winning_trades': result.winning_trades,
            'losing_trades': result.losing_trades,
            'win_rate': result.win_rate * 100,
            'profit_factor': result.profit_factor if result.profit_factor != float('inf') else 999,
            'max_drawdown': result.max_drawdown,
            'sharpe_ratio': result.sharpe_ratio,
            'final_capital': result.final_capital,
            'known_cascades': len(cascades),
            'signals_detected': signals['final_signal'].sum()
        })

        # Print individual results
        print_backtest_results(result)

    # Summary table
    print("\n" + "="*80)
    print("MULTI-ASSET PERFORMANCE SUMMARY")
    print("="*80)

    df_summary = pd.DataFrame(results_summary)
    print("\n" + df_summary.to_string(index=False))

    # Analysis
    print("\n" + "="*80)
    print("KEY FINDINGS")
    print("="*80)

    if len(df_summary) > 0:
        avg_return = df_summary['total_return_pct'].mean()
        avg_win_rate = df_summary['win_rate'].mean()
        total_trades = df_summary['total_trades'].sum()

        print(f"\nOverall Performance:")
        print(f"  Average return across assets: {avg_return:.2f}%")
        print(f"  Average win rate: {avg_win_rate:.1f}%")
        print(f"  Total trades across all assets: {total_trades}")

        profitable_assets = len(df_summary[df_summary['total_return_pct'] > 0])
        print(f"  Profitable assets: {profitable_assets}/{len(df_summary)}")

        if profitable_assets > 0:
            best_asset = df_summary.loc[df_summary['total_return_pct'].idxmax()]
            print(f"\nBest Performing Asset:")
            print(f"  Symbol: {best_asset['symbol']}")
            print(f"  Return: {best_asset['total_return_pct']:.2f}%")
            print(f"  Win Rate: {best_asset['win_rate']:.1f}%")
            print(f"  Trades: {best_asset['total_trades']}")

        # Signal detection analysis
        total_cascades = df_summary['known_cascades'].sum()
        total_signals = df_summary['signals_detected'].sum()
        print(f"\nSignal Detection:")
        print(f"  Total known cascades: {total_cascades}")
        print(f"  Total signals generated: {total_signals}")
        print(f"  Detection rate: {(total_signals / total_cascades * 100):.1f}%")

    return df_summary


def test_parameter_sensitivity():
    """
    Test different parameter combinations on realistic data
    """
    print("\n" + "="*80)
    print("PARAMETER SENSITIVITY ANALYSIS ON REALISTIC DATA")
    print("="*80)

    # Load SOL data for sensitivity analysis
    df, cascades = load_realistic_data('SOL_USDT')

    if df is None:
        return

    # Parameter combinations to test
    param_configs = [
        {'name': 'Conservative', 'accel': -0.5, 'decay': 0.8, 'tp': 0.2, 'sl': 0.15},
        {'name': 'Moderate', 'accel': -0.3, 'decay': 0.85, 'tp': 0.2, 'sl': 0.15},
        {'name': 'Aggressive', 'accel': -0.2, 'decay': 0.9, 'tp': 0.2, 'sl': 0.15},
        {'name': 'Wider Targets', 'accel': -0.3, 'decay': 0.85, 'tp': 0.3, 'sl': 0.2},
        {'name': 'Tighter Targets', 'accel': -0.3, 'decay': 0.85, 'tp': 0.15, 'sl': 0.1},
    ]

    sensitivity_results = []

    for config in param_configs:
        print(f"\n{'='*80}")
        print(f"Testing: {config['name']}")
        print(f"{'='*80}")

        params = {
            'acceleration_threshold': config['accel'],
            'momentum_decay_threshold': config['decay'],
            'take_profit_pct': config['tp'],
            'stop_loss_pct': config['sl'],
            'leverage': 500
        }

        result, signals = run_comprehensive_backtest(df, 'SOL/USDT', cascades, params)

        sensitivity_results.append({
            'config': config['name'],
            'return_pct': result.total_return_pct,
            'trades': result.total_trades,
            'win_rate': result.win_rate * 100,
            'profit_factor': result.profit_factor if result.profit_factor != float('inf') else 999,
            'final_capital': result.final_capital
        })

    # Summary
    print("\n" + "="*80)
    print("SENSITIVITY ANALYSIS SUMMARY")
    print("="*80)

    df_sens = pd.DataFrame(sensitivity_results)
    print("\n" + df_sens.to_string(index=False))

    if len(df_sens[df_sens['return_pct'] > 0]) > 0:
        best_config = df_sens.loc[df_sens['return_pct'].idxmax()]
        print(f"\nBest Configuration:")
        print(f"  Name: {best_config['config']}")
        print(f"  Return: {best_config['return_pct']:.2f}%")
        print(f"  Trades: {best_config['trades']}")

    return df_sens


def main():
    """
    Run Phase 1 comprehensive analysis
    """
    print("\n" + "="*80)
    print("PERFECT TIMING ANALYSIS - PHASE 1 VALIDATION")
    print("Backtesting on Realistic Market Data")
    print("="*80)

    # Test 1: Multi-asset comparison
    asset_results = compare_across_assets()

    # Test 2: Parameter sensitivity
    sensitivity_results = test_parameter_sensitivity()

    # Final summary
    print("\n" + "="*80)
    print("PHASE 1 COMPLETE")
    print("="*80)

    print("\nKey Takeaways:")
    if asset_results is not None and len(asset_results) > 0:
        avg_return = asset_results['total_return_pct'].mean()
        total_trades = asset_results['total_trades'].sum()

        if avg_return > 0:
            print(f"  ✅ Strategy shows positive returns on realistic data")
            print(f"  ✅ Average return: {avg_return:.2f}%")
        else:
            print(f"  ⚠️  Strategy shows negative returns on realistic data")
            print(f"  ⚠️  Average return: {avg_return:.2f}%")

        if total_trades > 20:
            print(f"  ✅ Sufficient trades for statistical significance ({total_trades})")
        else:
            print(f"  ⚠️  Low trade count ({total_trades}) - need more data or looser parameters")

    print("\nNext Steps:")
    print("  1. Review PHASE1_REPORT.md for detailed analysis")
    print("  2. If results are positive: Proceed to Phase 2 (Paper Trading)")
    print("  3. If results are negative: Adjust strategy or parameters")

    return asset_results, sensitivity_results


if __name__ == "__main__":
    main()
