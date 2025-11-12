"""
Phase 1: Download Real Historical Data from Binance

Downloads actual liquidation cascade data from Binance for:
- SOL/USDT
- BTC/USDT
- ETH/USDT

Multiple timeframes: 1m, 5m, 15m
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os


class RealDataDownloader:
    """
    Download real historical cryptocurrency data from Binance
    """

    def __init__(self, exchange_id='binance'):
        """Initialize exchange connection"""
        print(f"Connecting to {exchange_id}...")
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}  # Use futures for liquidation data
        })
        print(f"✓ Connected to {exchange_id}")

    def download_ohlcv(self, symbol, timeframe='1m', since=None, limit=1000):
        """
        Download OHLCV data

        Args:
            symbol: Trading pair (e.g., 'SOL/USDT')
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h')
            since: Start timestamp (milliseconds)
            limit: Number of candles to fetch

        Returns:
            DataFrame with OHLCV data
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since, limit)

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            return df

        except Exception as e:
            print(f"Error downloading {symbol}: {e}")
            return None

    def download_historical_data(self, symbol, timeframe='1m', days=30):
        """
        Download historical data for specified number of days

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            days: Number of days to download

        Returns:
            Complete DataFrame with all data
        """
        print(f"\nDownloading {symbol} {timeframe} data for last {days} days...")

        # Calculate start time
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        since = int(start_time.timestamp() * 1000)

        all_data = []
        current_since = since

        while True:
            # Download batch
            df = self.download_ohlcv(symbol, timeframe, current_since, 1000)

            if df is None or len(df) == 0:
                break

            all_data.append(df)

            # Update since for next batch
            last_timestamp = df.index[-1]
            current_since = int(last_timestamp.timestamp() * 1000) + 1

            # Check if we've reached current time
            if last_timestamp >= end_time:
                break

            print(f"  Downloaded {len(df)} candles (up to {last_timestamp})")

            # Rate limiting
            time.sleep(0.5)

        if not all_data:
            print(f"  ✗ No data downloaded for {symbol}")
            return None

        # Combine all batches
        combined_df = pd.concat(all_data)
        combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
        combined_df.sort_index(inplace=True)

        print(f"  ✓ Downloaded {len(combined_df)} total candles")
        print(f"    Date range: {combined_df.index[0]} to {combined_df.index[-1]}")
        print(f"    Price range: ${combined_df['close'].min():.2f} - ${combined_df['close'].max():.2f}")

        return combined_df

    def save_to_csv(self, df, symbol, timeframe, directory='data'):
        """Save DataFrame to CSV"""
        if df is None:
            return None

        os.makedirs(directory, exist_ok=True)

        # Create filename
        symbol_clean = symbol.replace('/', '_')
        filename = f"{directory}/{symbol_clean}_{timeframe}_{datetime.now().strftime('%Y%m%d')}.csv"

        df.to_csv(filename)
        print(f"  ✓ Saved to {filename}")

        return filename


def identify_liquidation_cascades(df, volume_threshold=2.0, price_drop_threshold=0.5):
    """
    Identify likely liquidation cascades in real data

    Cascades characterized by:
    - Sudden volume spike
    - Rapid price drop
    - Sustained downward movement
    """
    # Calculate metrics
    df['volume_ma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']
    df['price_change_pct'] = ((df['close'] - df['open']) / df['open']) * 100

    # Identify potential cascades
    df['is_volume_spike'] = df['volume_ratio'] > volume_threshold
    df['is_price_drop'] = df['price_change_pct'] < -price_drop_threshold

    df['likely_cascade'] = df['is_volume_spike'] & df['is_price_drop']

    cascade_count = df['likely_cascade'].sum()

    return df, cascade_count


def analyze_real_data(df, symbol):
    """
    Analyze real market data for liquidation patterns
    """
    print(f"\n{'='*80}")
    print(f"ANALYZING {symbol} REAL DATA")
    print(f"{'='*80}")

    # Basic statistics
    print(f"\nBasic Statistics:")
    print(f"  Total candles: {len(df)}")
    print(f"  Date range: {df.index[0]} to {df.index[-1]}")
    print(f"  Duration: {(df.index[-1] - df.index[0]).total_seconds() / 86400:.1f} days")

    # Price statistics
    print(f"\nPrice Statistics:")
    print(f"  Start price: ${df['close'].iloc[0]:.2f}")
    print(f"  End price: ${df['close'].iloc[-1]:.2f}")
    print(f"  Price change: {((df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100):.2f}%")
    print(f"  Min price: ${df['close'].min():.2f}")
    print(f"  Max price: ${df['close'].max():.2f}")
    print(f"  Volatility (std): ${df['close'].std():.2f}")

    # Volume statistics
    print(f"\nVolume Statistics:")
    print(f"  Average volume: {df['volume'].mean():.2f}")
    print(f"  Max volume: {df['volume'].max():.2f}")
    print(f"  Volume std dev: {df['volume'].std():.2f}")

    # Identify cascades
    df_analyzed, cascade_count = identify_liquidation_cascades(df)

    print(f"\nLiquidation Cascade Analysis:")
    print(f"  Likely cascades detected: {cascade_count}")

    if cascade_count > 0:
        cascade_periods = df_analyzed[df_analyzed['likely_cascade']]
        print(f"  Average cascade volume ratio: {cascade_periods['volume_ratio'].mean():.2f}x")
        print(f"  Average cascade price drop: {cascade_periods['price_change_pct'].mean():.2f}%")
        print(f"  Largest cascade drop: {cascade_periods['price_change_pct'].min():.2f}%")

        print(f"\nRecent cascades (last 10):")
        recent_cascades = cascade_periods.tail(10)
        for idx, row in recent_cascades.iterrows():
            print(f"    {idx}: Price ${row['close']:.2f}, Drop {row['price_change_pct']:.2f}%, Volume {row['volume_ratio']:.1f}x")

    return df_analyzed


def main():
    """
    Download and analyze real cryptocurrency data
    """
    print("\n" + "="*80)
    print("PHASE 1: REAL DATA DOWNLOAD & ANALYSIS")
    print("Perfect Timing Analysis - Real Market Validation")
    print("="*80)

    # Initialize downloader
    downloader = RealDataDownloader()

    # Assets to test
    assets = [
        ('SOL/USDT', '1m', 30),   # Solana, 1-minute, 30 days
        ('BTC/USDT', '1m', 30),   # Bitcoin, 1-minute, 30 days
        ('ETH/USDT', '1m', 30),   # Ethereum, 1-minute, 30 days
    ]

    downloaded_data = {}

    # Download data
    for symbol, timeframe, days in assets:
        try:
            df = downloader.download_historical_data(symbol, timeframe, days)

            if df is not None:
                # Save to CSV
                filename = downloader.save_to_csv(df, symbol, timeframe)

                # Analyze
                df_analyzed = analyze_real_data(df, symbol)

                downloaded_data[symbol] = {
                    'data': df_analyzed,
                    'filename': filename,
                    'timeframe': timeframe
                }

        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            continue

    # Summary
    print("\n" + "="*80)
    print("DOWNLOAD SUMMARY")
    print("="*80)

    for symbol, info in downloaded_data.items():
        df = info['data']
        print(f"\n{symbol}:")
        print(f"  File: {info['filename']}")
        print(f"  Candles: {len(df)}")
        print(f"  Cascades: {df['likely_cascade'].sum()}")
        print(f"  Date range: {df.index[0]} to {df.index[-1]}")

    print("\n✓ Phase 1 data download complete!")
    print(f"  Total assets downloaded: {len(downloaded_data)}")
    print(f"\nNext step: Run backtests on real data")
    print(f"  Command: python run_backtest_real_data.py")

    return downloaded_data


if __name__ == "__main__":
    main()
