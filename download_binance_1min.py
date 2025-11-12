"""
Download actual 1-minute Solana data from Binance
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time
import os

def download_binance_1min_data(symbol='SOL/USDT', days=1):
    """
    Download real 1-minute data from Binance

    Args:
        symbol: Trading pair (default SOL/USDT)
        days: Number of days to download (default 1)
    """
    print(f"Downloading {symbol} 1-minute data from Binance...")
    print(f"Period: Last {days} day(s)")

    try:
        # Initialize Binance exchange
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}  # Use spot market
        })

        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        since = int(start_time.timestamp() * 1000)

        print(f"Fetching data from {start_time} to {end_time}...")

        all_candles = []
        current_since = since

        while True:
            try:
                # Fetch OHLCV data (1m = 1 minute)
                ohlcv = exchange.fetch_ohlcv(symbol, '1m', current_since, limit=1000)

                if not ohlcv:
                    break

                all_candles.extend(ohlcv)

                # Get last timestamp
                last_timestamp = ohlcv[-1][0]
                current_since = last_timestamp + 60000  # Add 1 minute in milliseconds

                print(f"  Downloaded {len(ohlcv)} candles (total: {len(all_candles)})")

                # Check if we've reached current time
                if last_timestamp >= int(end_time.timestamp() * 1000):
                    break

                # Rate limiting
                time.sleep(exchange.rateLimit / 1000)

            except Exception as e:
                print(f"  Error fetching batch: {e}")
                break

        # Convert to DataFrame
        df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        # Remove duplicates
        df = df[~df.index.duplicated(keep='first')]
        df = df.sort_index()

        print(f"\n✓ Successfully downloaded {len(df)} 1-minute candles")
        print(f"  Date range: {df.index[0]} to {df.index[-1]}")
        print(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

        # Save to CSV
        filename = f"{symbol.replace('/', '_')}_1min_{days}day.csv"
        df.to_csv(filename)
        print(f"  Saved to: {filename}")

        return df, filename

    except Exception as e:
        print(f"Error: {e}")
        print("\nTrying alternative approach...")
        return download_alternative(symbol, days)

def download_alternative(symbol='SOL/USDT', days=1):
    """
    Alternative download method using different endpoint
    """
    try:
        import requests

        print("Using Binance public API directly...")

        # Binance API endpoint
        url = "https://api.binance.com/api/v3/klines"

        # Calculate timestamps
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        all_candles = []
        current_start = start_time

        symbol_formatted = symbol.replace('/', '')  # SOLUSDT

        while current_start < end_time:
            params = {
                'symbol': symbol_formatted,
                'interval': '1m',
                'startTime': current_start,
                'limit': 1000
            }

            response = requests.get(url, params=params)

            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                break

            data = response.json()

            if not data:
                break

            all_candles.extend(data)

            # Update start time
            current_start = data[-1][0] + 60000

            print(f"  Downloaded {len(data)} candles (total: {len(all_candles)})")

            time.sleep(0.5)  # Rate limiting

        # Convert to DataFrame
        df = pd.DataFrame(all_candles, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        # Keep only OHLCV
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        # Convert to numeric
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        df = df[~df.index.duplicated(keep='first')]
        df = df.sort_index()

        print(f"\n✓ Successfully downloaded {len(df)} 1-minute candles")
        print(f"  Date range: {df.index[0]} to {df.index[-1]}")
        print(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

        # Save to CSV
        filename = f"{symbol.replace('/', '_')}_1min_{days}day_real.csv"
        df.to_csv(filename)
        print(f"  Saved to: {filename}")

        return df, filename

    except Exception as e:
        print(f"Alternative method also failed: {e}")
        return None, None

if __name__ == "__main__":
    import sys

    # Default: download 1 day of SOL/USDT 1-minute data
    symbol = 'SOL/USDT'
    days = 1

    # Allow command line arguments
    if len(sys.argv) > 1:
        days = int(sys.argv[1])
    if len(sys.argv) > 2:
        symbol = sys.argv[2]

    print("="*80)
    print("DOWNLOADING REAL 1-MINUTE DATA FROM BINANCE")
    print("="*80)

    df, filename = download_binance_1min_data(symbol, days)

    if df is not None:
        print("\n" + "="*80)
        print("SUCCESS! Ready to backtest on real 1-minute data")
        print("="*80)
        print(f"\nNext step:")
        print(f"  python load_real_data.py {filename}")
    else:
        print("\n❌ Failed to download data")
        print("You may need to:")
        print("  1. Check internet connection")
        print("  2. Use VPN if Binance is blocked")
        print("  3. Try a different exchange")
