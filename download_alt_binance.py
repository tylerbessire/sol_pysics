"""
Alternative Binance data downloader using multiple methods
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import json

def download_from_alternative_api(symbol='SOLUSDT', days=7):
    """
    Try multiple alternative data sources
    """

    # Method 1: Try CryptoCompare (free, no API key needed)
    print("Method 1: Trying CryptoCompare API...")
    try:
        data = []
        end_time = int(datetime.now().timestamp())
        hours_to_fetch = days * 24

        # CryptoCompare allows 2000 candles per request
        for batch in range(0, hours_to_fetch, 24):
            url = "https://min-api.cryptocompare.com/data/v2/histominute"
            params = {
                'fsym': 'SOL',
                'tsym': 'USDT',
                'limit': 1440,  # 24 hours of minutes
                'toTs': end_time - (batch * 3600)
            }

            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get('Response') == 'Success':
                    data.extend(result['Data']['Data'])
                    print(f"  Downloaded batch {batch//24 + 1}/{(hours_to_fetch-1)//24 + 1}")
                    time.sleep(1)  # Rate limiting
                else:
                    print(f"  API returned error: {result.get('Message')}")
                    break
            else:
                print(f"  HTTP Error: {response.status_code}")
                break

        if data:
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['time'], unit='s')
            df = df.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volumeto': 'volume'
            })
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df.set_index('timestamp', inplace=True)
            df = df.sort_index()

            print(f"\n✓ Successfully downloaded {len(df)} candles from CryptoCompare")
            print(f"  Date range: {df.index[0]} to {df.index[-1]}")
            print(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

            filename = f'SOL_USDT_1min_{days}day_cryptocompare.csv'
            df.to_csv(filename)
            print(f"  Saved to: {filename}")

            return df, filename

    except Exception as e:
        print(f"  CryptoCompare failed: {e}")

    # Method 2: Try Binance with proxy-like headers
    print("\nMethod 2: Trying Binance with enhanced headers...")
    try:
        url = "https://data-api.binance.vision/api/v3/klines"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        all_data = []
        current_start = start_time

        while current_start < end_time:
            params = {
                'symbol': 'SOLUSDT',
                'interval': '1m',
                'startTime': current_start,
                'limit': 1000
            }

            response = requests.get(url, params=params, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if not data:
                    break

                all_data.extend(data)
                current_start = data[-1][0] + 60000
                print(f"  Downloaded {len(data)} candles (total: {len(all_data)})")
                time.sleep(0.5)
            else:
                print(f"  HTTP Error: {response.status_code}")
                break

        if all_data:
            df = pd.DataFrame(all_data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])

            df = df.sort_index()

            print(f"\n✓ Successfully downloaded {len(df)} candles from Binance")
            print(f"  Date range: {df.index[0]} to {df.index[-1]}")
            print(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

            filename = f'SOL_USDT_1min_{days}day_binance.csv'
            df.to_csv(filename)
            print(f"  Saved to: {filename}")

            return df, filename

    except Exception as e:
        print(f"  Binance data-api failed: {e}")

    # Method 3: Try Coingecko (limited but works)
    print("\nMethod 3: Trying CoinGecko API...")
    try:
        url = "https://api.coingecko.com/api/v3/coins/solana/market_chart"
        params = {
            'vs_currency': 'usd',
            'days': days,
            'interval': 'minute' if days <= 1 else 'hourly'
        }

        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()

            # Create DataFrame
            prices = data['prices']
            volumes = data['total_volumes']

            df = pd.DataFrame({
                'timestamp': [p[0] for p in prices],
                'close': [p[1] for p in prices],
                'volume': [v[1] for v in volumes]
            })

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # Estimate OHLC from close prices
            df['open'] = df['close'].shift(1).fillna(df['close'])
            df['high'] = df[['open', 'close']].max(axis=1) * 1.001
            df['low'] = df[['open', 'close']].min(axis=1) * 0.999

            df = df[['open', 'high', 'low', 'close', 'volume']]

            print(f"\n✓ Successfully downloaded {len(df)} candles from CoinGecko")
            print(f"  Date range: {df.index[0]} to {df.index[-1]}")
            print(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
            print(f"  Note: OHLC estimated from close prices (CoinGecko limitation)")

            filename = f'SOL_USDT_1min_{days}day_coingecko.csv'
            df.to_csv(filename)
            print(f"  Saved to: {filename}")

            return df, filename

    except Exception as e:
        print(f"  CoinGecko failed: {e}")

    print("\n❌ All download methods failed")
    print("The network may be restricted or APIs may be rate-limited")
    return None, None


if __name__ == "__main__":
    import sys

    days = 7 if len(sys.argv) <= 1 else int(sys.argv[1])

    print("="*80)
    print(f"DOWNLOADING SOL/USDT 1-MINUTE DATA ({days} DAYS)")
    print("="*80)
    print()

    df, filename = download_from_alternative_api('SOLUSDT', days)

    if df is not None:
        print("\n" + "="*80)
        print("SUCCESS! Data downloaded and ready for backtesting")
        print("="*80)
        print(f"\nRun backtest with:")
        print(f"  python load_real_data.py {filename}")
    else:
        print("\n❌ Could not download data from any source")
        print("Possible solutions:")
        print("  1. Check internet connection")
        print("  2. Try again later (rate limits)")
        print("  3. Use VPN if APIs are blocked")
        print("  4. Manually download data from exchange")
