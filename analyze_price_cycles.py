"""
Price Movement Analyzer - Study Large Moves and Mean Reversion

Approach:
1. Identify large price jumps (>1% in <15 minutes)
2. Find the apoapsis (peak) of the movement
3. Track the mean reversion (profit-taking red candle)
4. Count frequency per day
5. Calculate liquidation levels using Gains Network math

This helps identify ACTUAL patterns in real data instead of trying to predict them.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json


class PriceMovementAnalyzer:
    """
    Analyze large price movements and their reversions
    """

    def __init__(self, threshold_pct=1.0, window_minutes=15):
        """
        Args:
            threshold_pct: Minimum % move to classify as "large" (default 1%)
            window_minutes: Time window to measure moves (default 15 min)
        """
        self.threshold_pct = threshold_pct
        self.window_minutes = window_minutes

    def identify_large_moves(self, df):
        """
        Identify all large price movements (up or down)

        Returns:
            DataFrame with large move events
        """
        print(f"\nIdentifying large moves (>{self.threshold_pct}% in {self.window_minutes} min)...")

        # Calculate rolling price change
        window = self.window_minutes  # For 1-min data, this is the number of periods

        df['price_change_pct'] = ((df['close'] - df['close'].shift(window)) / df['close'].shift(window)) * 100
        df['price_change_abs'] = df['close'] - df['close'].shift(window)

        # Identify large moves
        df['is_large_move_up'] = df['price_change_pct'] > self.threshold_pct
        df['is_large_move_down'] = df['price_change_pct'] < -self.threshold_pct
        df['is_large_move'] = df['is_large_move_up'] | df['is_large_move_down']

        large_moves = df[df['is_large_move']].copy()

        print(f"  Found {len(large_moves)} large moves:")
        print(f"    Up moves: {large_moves['is_large_move_up'].sum()}")
        print(f"    Down moves: {large_moves['is_large_move_down'].sum()}")

        return large_moves

    def find_apoapsis(self, df, move_start_idx, direction='up', lookforward_periods=30):
        """
        Find the peak (apoapsis) after a large move starts

        Args:
            df: Full DataFrame
            move_start_idx: Index where large move was detected
            direction: 'up' or 'down'
            lookforward_periods: How many periods to look forward for peak

        Returns:
            Dict with apoapsis information
        """
        # Get the window after the move
        start_loc = df.index.get_loc(move_start_idx)
        end_loc = min(start_loc + lookforward_periods, len(df) - 1)

        window = df.iloc[start_loc:end_loc]

        if len(window) == 0:
            return None

        if direction == 'up':
            # Find highest high in the window
            peak_idx = window['high'].idxmax()
            peak_price = window.loc[peak_idx, 'high']
        else:
            # Find lowest low in the window
            peak_idx = window['low'].idxmin()
            peak_price = window.loc[peak_idx, 'low']

        # Calculate time to peak
        time_to_peak = (peak_idx - move_start_idx).total_seconds() / 60

        # Calculate magnitude
        start_price = df.loc[move_start_idx, 'close']
        magnitude_pct = ((peak_price - start_price) / start_price) * 100

        return {
            'apoapsis_time': peak_idx,
            'apoapsis_price': peak_price,
            'start_time': move_start_idx,
            'start_price': start_price,
            'time_to_peak_minutes': time_to_peak,
            'magnitude_pct': magnitude_pct,
            'direction': direction
        }

    def find_reversion_point(self, df, apoapsis_info, lookforward_periods=30):
        """
        Find the mean reversion / profit-taking red candle after apoapsis

        Returns:
            Dict with reversion information
        """
        if apoapsis_info is None:
            return None

        apoapsis_idx = apoapsis_info['apoapsis_time']
        apoapsis_price = apoapsis_info['apoapsis_price']
        direction = apoapsis_info['direction']

        # Get window after apoapsis
        start_loc = df.index.get_loc(apoapsis_idx)
        end_loc = min(start_loc + lookforward_periods, len(df) - 1)

        window = df.iloc[start_loc:end_loc]

        if len(window) == 0:
            return None

        # Find first significant reversion
        if direction == 'up':
            # After up move, look for down move (red candle with body)
            window['is_red'] = window['close'] < window['open']
            window['candle_body_pct'] = ((window['open'] - window['close']) / window['open']) * 100

            # Find red candles with >0.2% body
            red_candles = window[(window['is_red']) & (window['candle_body_pct'] > 0.2)]

            if len(red_candles) > 0:
                reversion_idx = red_candles.index[0]
                reversion_price = red_candles.loc[reversion_idx, 'close']
            else:
                return None
        else:
            # After down move, look for up move (green candle)
            window['is_green'] = window['close'] > window['open']
            window['candle_body_pct'] = ((window['close'] - window['open']) / window['open']) * 100

            green_candles = window[(window['is_green']) & (window['candle_body_pct'] > 0.2)]

            if len(green_candles) > 0:
                reversion_idx = green_candles.index[0]
                reversion_price = green_candles.loc[reversion_idx, 'close']
            else:
                return None

        # Calculate reversion metrics
        time_to_reversion = (reversion_idx - apoapsis_idx).total_seconds() / 60
        reversion_magnitude_pct = ((reversion_price - apoapsis_price) / apoapsis_price) * 100

        return {
            'reversion_time': reversion_idx,
            'reversion_price': reversion_price,
            'time_to_reversion_minutes': time_to_reversion,
            'reversion_magnitude_pct': reversion_magnitude_pct
        }

    def analyze_complete_cycle(self, df):
        """
        Analyze complete cycles: large move → apoapsis → reversion

        Returns:
            List of complete cycle dictionaries
        """
        print("\nAnalyzing complete price cycles...")

        large_moves = self.identify_large_moves(df)

        cycles = []

        for idx, move in large_moves.iterrows():
            direction = 'up' if move['is_large_move_up'] else 'down'

            # Find apoapsis
            apoapsis_info = self.find_apoapsis(df, idx, direction)

            if apoapsis_info is None:
                continue

            # Find reversion
            reversion_info = self.find_reversion_point(df, apoapsis_info)

            if reversion_info is None:
                continue

            # Combine into complete cycle
            cycle = {
                **apoapsis_info,
                **reversion_info,
                'initial_move_pct': move['price_change_pct']
            }

            cycles.append(cycle)

        print(f"  Found {len(cycles)} complete cycles (move → peak → reversion)")

        return cycles


class GainsNetworkLiquidationCalculator:
    """
    Calculate liquidation prices using Gains Network math (sol.gains.trade)

    Based on official docs:
    https://docs.gains.trade/gtrade-leveraged-trading/opening-closing-trades
    """

    def __init__(self, leverage=500):
        """
        Args:
            leverage: Trading leverage (default 500x for degen pairs)
        """
        self.leverage = leverage

        # Fees (from Gains Network docs)
        self.opening_fee_pct = 0.06  # 0.06%
        self.closing_fee_pct = 0.06  # 0.06%

        # Liquidation threshold (estimated for 500x, very tight)
        # Docs show 67% at 100x, so 500x is much tighter
        self.liquidation_threshold_pct = 0.90  # 90% for extreme leverage

    def calculate_position_size(self, collateral, leverage=None):
        """
        Position Size = Collateral × Leverage
        """
        lev = leverage if leverage else self.leverage
        return collateral * lev

    def calculate_liquidation_price(self, entry_price, collateral, side='long',
                                   leverage=None, borrowing_fees=0):
        """
        Calculate liquidation price using Gains Network formula

        Formula:
        Distance = Entry Price × (Collateral × Liq_Threshold - Closing_Fee - Borrowing_Fees) / (Collateral × Leverage)

        Liquidation Price = Entry - Distance (long) or Entry + Distance (short)

        Args:
            entry_price: Entry price
            collateral: Collateral amount in USD
            side: 'long' or 'short'
            leverage: Override default leverage
            borrowing_fees: Accumulated borrowing fees

        Returns:
            Dict with liquidation info
        """
        lev = leverage if leverage else self.leverage

        # Calculate fees
        position_size = self.calculate_position_size(collateral, lev)
        opening_fee = position_size * (self.opening_fee_pct / 100)
        closing_fee = position_size * (self.closing_fee_pct / 100)

        # Liquidation threshold amount
        liq_threshold_amount = collateral * (self.liquidation_threshold_pct / 100)

        # Calculate liquidation distance
        numerator = (collateral * self.liquidation_threshold_pct / 100) - closing_fee - borrowing_fees
        denominator = collateral * lev

        if denominator == 0:
            liquidation_distance_pct = 0
        else:
            liquidation_distance_pct = (numerator / denominator) * 100

        liquidation_distance = entry_price * (liquidation_distance_pct / 100)

        # Calculate liquidation price
        if side == 'long':
            liquidation_price = entry_price - liquidation_distance
        else:  # short
            liquidation_price = entry_price + liquidation_distance

        # Calculate how far price can move before liquidation
        max_adverse_move_pct = (liquidation_distance / entry_price) * 100

        return {
            'entry_price': entry_price,
            'liquidation_price': liquidation_price,
            'liquidation_distance': liquidation_distance,
            'max_adverse_move_pct': max_adverse_move_pct,
            'position_size': position_size,
            'collateral': collateral,
            'leverage': lev,
            'opening_fee': opening_fee,
            'closing_fee': closing_fee,
            'side': side
        }


def analyze_trading_opportunities(cycles, df, collateral=100, leverage=500):
    """
    Analyze which cycles would be profitable trading opportunities

    Strategy: Short at apoapsis, take profit at reversion

    Args:
        cycles: List of complete cycles
        df: Full price DataFrame
        collateral: Trading collateral in USD
        leverage: Trading leverage

    Returns:
        Analysis of profitable vs unprofitable opportunities
    """
    print(f"\n{'='*80}")
    print("ANALYZING TRADING OPPORTUNITIES")
    print(f"Collateral: ${collateral}, Leverage: {leverage}x")
    print(f"{'='*80}")

    liq_calc = GainsNetworkLiquidationCalculator(leverage=leverage)

    profitable_trades = []
    losing_trades = []
    liquidated_trades = []

    for cycle in cycles:
        # Strategy: Short at apoapsis
        entry_price = cycle['apoapsis_price']
        exit_price = cycle['reversion_price']

        # Calculate liquidation
        liq_info = liq_calc.calculate_liquidation_price(
            entry_price=entry_price,
            collateral=collateral,
            side='short',
            leverage=leverage
        )

        # Check if price hit liquidation before reversion
        apoapsis_loc = df.index.get_loc(cycle['apoapsis_time'])
        reversion_loc = df.index.get_loc(cycle['reversion_time'])

        window = df.iloc[apoapsis_loc:reversion_loc + 1]
        highest_high = window['high'].max()

        if highest_high >= liq_info['liquidation_price']:
            # Got liquidated
            liquidated_trades.append({
                **cycle,
                **liq_info,
                'highest_high_in_trade': highest_high,
                'got_liquidated': True
            })
            continue

        # Calculate P&L (short trade)
        price_move_pct = ((entry_price - exit_price) / entry_price) * 100
        pnl_pct = price_move_pct * leverage

        # Account for fees
        total_fees = liq_info['opening_fee'] + liq_info['closing_fee']
        pnl_usd = (collateral * pnl_pct / 100) - total_fees

        trade_info = {
            **cycle,
            **liq_info,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'price_move_pct': price_move_pct,
            'pnl_pct': pnl_pct,
            'pnl_usd': pnl_usd,
            'got_liquidated': False
        }

        if pnl_usd > 0:
            profitable_trades.append(trade_info)
        else:
            losing_trades.append(trade_info)

    # Summary
    total = len(profitable_trades) + len(losing_trades) + len(liquidated_trades)

    print(f"\nTotal Cycles Analyzed: {total}")
    print(f"  Profitable Trades: {len(profitable_trades)} ({len(profitable_trades)/total*100:.1f}%)")
    print(f"  Losing Trades: {len(losing_trades)} ({len(losing_trades)/total*100:.1f}%)")
    print(f"  Liquidated: {len(liquidated_trades)} ({len(liquidated_trades)/total*100:.1f}%)")

    if profitable_trades:
        avg_profit = np.mean([t['pnl_usd'] for t in profitable_trades])
        print(f"\n  Average Profit: ${avg_profit:.2f}")

    if losing_trades:
        avg_loss = np.mean([abs(t['pnl_usd']) for t in losing_trades])
        print(f"  Average Loss: ${avg_loss:.2f}")

    if liquidated_trades:
        avg_liq_distance = np.mean([t['max_adverse_move_pct'] for t in liquidated_trades])
        print(f"  Average Liquidation Distance: {avg_liq_distance:.3f}%")

    return {
        'profitable': profitable_trades,
        'losing': losing_trades,
        'liquidated': liquidated_trades,
        'total': total
    }


def main():
    """
    Main analysis pipeline
    """
    print("\n" + "="*80)
    print("PRICE MOVEMENT CYCLE ANALYZER")
    print("Study Large Moves → Apoapsis → Mean Reversion")
    print("="*80)

    # Load data
    import sys
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        # Default to recent generated file
        filename = 'SOL_USDT_1min_24h_realistic.csv'

    print(f"\nLoading data from: {filename}")
    df = pd.read_csv(filename)

    # Parse timestamp
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
    elif 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

    print(f"✓ Loaded {len(df)} candles")

    # Analyze
    analyzer = PriceMovementAnalyzer(threshold_pct=1.0, window_minutes=15)
    cycles = analyzer.analyze_complete_cycle(df)

    if len(cycles) == 0:
        print("\n⚠️ No complete cycles found. Try:")
        print("  - Lower threshold (currently 1.0%)")
        print("  - More data (currently analyzing limited timeframe)")
        return

    # Calculate frequency
    time_span_hours = (df.index[-1] - df.index[0]).total_seconds() / 3600
    cycles_per_day = (len(cycles) / time_span_hours) * 24

    print(f"\n  Average cycles per day: {cycles_per_day:.1f}")

    # Analyze trading opportunities
    opportunities = analyze_trading_opportunities(cycles, df, collateral=100, leverage=500)

    # Calculate win rate and expectancy
    if opportunities['total'] > 0:
        win_rate = len(opportunities['profitable']) / opportunities['total']
        print(f"\n{'='*80}")
        print(f"STRATEGY PERFORMANCE")
        print(f"{'='*80}")
        print(f"Win Rate: {win_rate * 100:.1f}%")

        if opportunities['profitable'] and opportunities['losing']:
            avg_win = np.mean([t['pnl_usd'] for t in opportunities['profitable']])
            avg_loss = np.mean([abs(t['pnl_usd']) for t in opportunities['losing']])

            if avg_loss > 0:
                profit_factor = (len(opportunities['profitable']) * avg_win) / (len(opportunities['losing']) * avg_loss)
                print(f"Profit Factor: {profit_factor:.2f}")

                expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
                print(f"Expected Value per Trade: ${expectancy:.2f}")

    # Show sample cycles
    print(f"\n{'='*80}")
    print("SAMPLE CYCLES (First 5)")
    print(f"{'='*80}")

    for i, cycle in enumerate(cycles[:5]):
        print(f"\nCycle {i+1}:")
        print(f"  Direction: {cycle['direction']}")
        print(f"  Initial move: {cycle['initial_move_pct']:.2f}%")
        print(f"  Time to peak: {cycle['time_to_peak_minutes']:.1f} minutes")
        print(f"  Peak magnitude: {cycle['magnitude_pct']:.2f}%")
        print(f"  Time to reversion: {cycle['time_to_reversion_minutes']:.1f} minutes")
        print(f"  Reversion magnitude: {cycle['reversion_magnitude_pct']:.2f}%")


if __name__ == "__main__":
    main()
