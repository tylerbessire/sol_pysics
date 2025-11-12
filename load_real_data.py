"""
Real Market Data Loader and Analyzer

Loads actual Binance/exchange data and runs Phase 1 backtests.
Supports multiple formats: CSV, JSON, Parquet
"""

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from models.momentum import MomentumCalculator
from models.terminal_velocity import TerminalVelocityDetector, TerminalVelocityStrategy
from backtesting.engine import BacktestEngine, print_backtest_results


def load_real_data(filepath, format='auto'):
    """
    Load real market data from various formats

    Supported formats:
    - CSV (Binance format, standard OHLCV)
    - JSON
    - Parquet

    Args:
        filepath: Path to data file
        format: 'csv', 'json', 'parquet', or 'auto' (detect from extension)

    Returns:
        DataFrame with timestamp, open, high, low, close, volume
    """
    print(f"Loading data from: {filepath}")

    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return None

    # Auto-detect format
    if format == 'auto':
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.csv':
            format = 'csv'
        elif ext == '.json':
            format = 'json'
        elif ext == '.parquet':
            format = 'parquet'
        else:
            print(f"Unknown file extension: {ext}")
            return None

    # Load based on format
    try:
        if format == 'csv':
            df = load_csv_data(filepath)
        elif format == 'json':
            df = pd.read_json(filepath)
        elif format == 'parquet':
            df = pd.read_parquet(filepath)
        else:
            print(f"Unsupported format: {format}")
            return None

        # Validate and standardize
        df = standardize_dataframe(df)

        if df is not None:
            print(f"✓ Loaded {len(df)} candles")
            print(f"  Date range: {df.index[0]} to {df.index[-1]}")
            print(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

            # Calculate statistics
            returns = df['close'].pct_change().dropna()
            daily_vol = returns.std() * np.sqrt(1440) * 100  # Annualized for 1-min data
            print(f"  Daily volatility: {daily_vol:.2f}%")
            print(f"  Total return: {((df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100):.2f}%")

        return df

    except Exception as e:
        print(f"Error loading data: {e}")
        return None


def load_csv_data(filepath):
    """
    Load CSV data with flexible column detection

    Handles various formats:
    - Binance format: timestamp, open, high, low, close, volume, ...
    - Standard OHLCV: date/time, open, high, low, close, volume
    - Kaggle format: Date, Open, High, Low, Close, Volume
    """
    # Try to read with different options
    try:
        # Try standard CSV
        df = pd.read_csv(filepath)

        print(f"  Columns found: {list(df.columns)}")

        # Detect timestamp column
        timestamp_cols = ['timestamp', 'time', 'date', 'datetime', 'Date', 'Time', 'Timestamp']
        timestamp_col = None

        for col in timestamp_cols:
            if col in df.columns:
                timestamp_col = col
                break

        if timestamp_col is None and 'Unnamed: 0' in df.columns:
            timestamp_col = 'Unnamed: 0'

        if timestamp_col:
            # Try to parse timestamp
            try:
                # Try unix timestamp (milliseconds)
                if df[timestamp_col].dtype in ['int64', 'float64']:
                    df['timestamp'] = pd.to_datetime(df[timestamp_col], unit='ms')
                else:
                    # Try string datetime
                    df['timestamp'] = pd.to_datetime(df[timestamp_col])

                df.set_index('timestamp', inplace=True)
            except Exception as e:
                print(f"  Warning: Could not parse timestamp: {e}")

        return df

    except Exception as e:
        print(f"Error reading CSV: {e}")
        return None


def standardize_dataframe(df):
    """
    Standardize DataFrame to have consistent columns: open, high, low, close, volume
    """
    if df is None:
        return None

    # Column name mapping (various common formats)
    column_mapping = {
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume',
    }

    # Rename columns
    df = df.rename(columns=column_mapping)

    # Check required columns exist
    required = ['open', 'high', 'low', 'close', 'volume']
    missing = [col for col in required if col not in df.columns]

    if missing:
        print(f"Error: Missing required columns: {missing}")
        print(f"Available columns: {list(df.columns)}")
        return None

    # Keep only required columns
    df = df[required]

    # Ensure numeric types
    for col in required:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Remove NaN values
    df = df.dropna()

    # Sort by index (timestamp)
    df = df.sort_index()

    return df


def analyze_real_market_data(df, symbol='Real Data'):
    """
    Analyze real market data for trading patterns
    """
    print(f"\n{'='*80}")
    print(f"ANALYZING {symbol}")
    print(f"{'='*80}")

    prices = df['close']
    volumes = df['volume']

    # Detect potential liquidation cascades
    print("\nDetecting liquidation cascade patterns...")

    # Calculate metrics
    df['volume_ma'] = volumes.rolling(20).mean()
    df['volume_ratio'] = volumes / df['volume_ma']
    df['price_change_pct'] = ((df['close'] - df['open']) / df['open']) * 100

    # Identify cascades (volume spike + price drop)
    df['is_cascade'] = (df['volume_ratio'] > 2.0) & (df['price_change_pct'] < -0.5)

    cascade_count = df['is_cascade'].sum()
    print(f"  Potential cascades detected: {cascade_count}")

    if cascade_count > 0:
        cascades = df[df['is_cascade']]
        print(f"  Avg cascade volume ratio: {cascades['volume_ratio'].mean():.2f}x")
        print(f"  Avg cascade price drop: {cascades['price_change_pct'].mean():.2f}%")
        print(f"  Largest cascade: {cascades['price_change_pct'].min():.2f}%")

    return df


def backtest_on_real_data(df, symbol='Real Data', params=None):
    """
    Run backtest on real market data
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
    print(f"BACKTESTING ON {symbol}")
    print(f"{'='*80}")

    prices = df['close']
    volumes = df['volume']

    # Calculate physics metrics
    print("1. Calculating physics metrics...")
    calc = MomentumCalculator(window=20)
    velocities = calc.calculate_velocity(prices)
    accelerations = calc.calculate_acceleration(velocities)
    momentum = calc.calculate_momentum(prices, volumes)

    # Terminal velocity detection
    print("2. Detecting terminal velocity signals...")
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
    print(f"   ✓ Signals detected: {signal_count}")

    if signal_count == 0:
        print("   ⚠️ No signals detected! Strategy too conservative.")
        return None

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

    # Print results
    print_backtest_results(result)

    return result


def main():
    """
    Main function - load and analyze real data
    """
    print("\n" + "="*80)
    print("REAL MARKET DATA ANALYSIS")
    print("Perfect Timing Analysis - Testing on Actual Exchange Data")
    print("="*80)

    # Check for data files
    data_dir = 'data'

    # Look for common data file patterns
    patterns = [
        'data/*USDT*.csv',
        'data/*usdt*.csv',
        'data/*.csv',
        '*.csv',
        '*BTCUSDT*.csv',
        '*SOLUSDT*.csv',
        '*ETHUSDT*.csv',
    ]

    import glob

    found_files = []
    for pattern in patterns:
        files = glob.glob(pattern)
        found_files.extend(files)

    # Remove duplicates and simulated data
    found_files = list(set(found_files))
    found_files = [f for f in found_files if 'realistic' not in f.lower()]

    if not found_files:
        print("\n⚠️ No real data files found!")
        print("\nPlease provide your data file path.")
        print("Example usage:")
        print("  python load_real_data.py path/to/your/data.csv")
        print("\nSupported formats:")
        print("  - CSV with columns: timestamp, open, high, low, close, volume")
        print("  - Binance CSV format")
        print("  - Kaggle cryptocurrency data format")
        return

    print(f"\nFound {len(found_files)} data file(s):")
    for f in found_files:
        print(f"  - {f}")

    # Load and analyze each file
    results = {}

    for filepath in found_files:
        symbol = os.path.basename(filepath).replace('.csv', '')

        # Load data
        df = load_real_data(filepath)

        if df is not None and len(df) > 100:
            # Analyze patterns
            df_analyzed = analyze_real_market_data(df, symbol)

            # Run backtest
            result = backtest_on_real_data(df_analyzed, symbol)

            if result:
                results[symbol] = result

    # Summary
    if results:
        print("\n" + "="*80)
        print("REAL DATA BACKTEST SUMMARY")
        print("="*80)

        for symbol, result in results.items():
            print(f"\n{symbol}:")
            print(f"  Total Return: {result.total_return_pct:.2f}%")
            print(f"  Win Rate: {result.win_rate * 100:.1f}%")
            print(f"  Profit Factor: {result.profit_factor:.2f}")
            print(f"  Trades: {result.total_trades}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Load specific file provided as argument
        filepath = sys.argv[1]
        df = load_real_data(filepath)

        if df is not None:
            df_analyzed = analyze_real_market_data(df)
            result = backtest_on_real_data(df_analyzed)
    else:
        # Auto-detect and load all data files
        main()
