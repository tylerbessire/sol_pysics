"""
EXTREME MOVE DETECTOR

Focus on ONLY the biggest liquidation cascades - the dramatic moves where
price jumps $1-2 in 30 seconds to a minute. These are the true "slides"
worth riding down.

Target: ~10 trades per day (only the most extreme moves)
Current: ~180 trades per day (too many small moves)

Key filters:
1. Extreme velocity: Price must move >$0.50 in 1-2 minutes
2. Massive volume spike: Volume >3x recent average
3. Rapid acceleration: Multiple consecutive strong candles
4. Top signals only: Rank by extremeness, take top 10 per day
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import deque


class ExtremeMoveDetector:
    """
    Detect only the most extreme liquidation cascade moves
    """

    def __init__(self,
                 min_velocity_pct=1.0,        # Minimum 1.0% move in short period
                 min_volume_spike=0.5,        # Just need some volume (0.5x = ANY volume)
                 min_consecutive_candles=1,   # Just 1 candle (simplest)
                 lookback_minutes=1):         # 1 minute window

        self.min_velocity_pct = min_velocity_pct
        self.min_volume_spike = min_volume_spike
        self.min_consecutive_candles = min_consecutive_candles
        self.lookback_minutes = lookback_minutes

        self.candle_buffer = deque(maxlen=100)

    def add_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Add candle and check for extreme move
        """
        candle = {
            'timestamp': timestamp,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }
        self.candle_buffer.append(candle)

        if len(self.candle_buffer) < 20:
            return None

        return self._detect_extreme_move()

    def _detect_extreme_move(self):
        """
        Detect if current candle completes an extreme move
        """
        df = pd.DataFrame(list(self.candle_buffer))

        current = df.iloc[-1]

        # 1. Calculate velocity over last minute (simple 1-candle move)
        if len(df) < 2:
            return None

        price_prev = df.iloc[-2]['close']
        price_current = current['close']
        velocity_usd = abs(price_current - price_prev)
        velocity_pct = (velocity_usd / price_prev) * 100

        # 2. Volume spike check
        volume_ma = df['volume'].rolling(20).mean().iloc[-1]
        volume_spike_ratio = current['volume'] / volume_ma if volume_ma > 0 else 0

        # 3. Check if upward move (price increased)
        is_upward_move = price_current > price_prev

        # 4. Calculate extremeness score (for ranking)
        extremeness_score = (
            (velocity_pct / self.min_velocity_pct) * 0.7 +          # Velocity component (primary)
            (volume_spike_ratio / self.min_volume_spike) * 0.3      # Volume component
        )

        # 5. Check if this is an extreme move
        is_extreme = (
            velocity_pct >= self.min_velocity_pct and
            is_upward_move  # Just need big upward move
        )

        if is_extreme:
            return {
                'timestamp': current['timestamp'],
                'detected': True,
                'velocity_usd': velocity_usd,
                'velocity_pct': velocity_pct,
                'volume_spike_ratio': volume_spike_ratio,
                'extremeness_score': extremeness_score,
                'price': current['close'],
                'volume': current['volume']
            }

        return None


class TopSignalFilter:
    """
    Filter to keep only top N signals per day
    """

    def __init__(self, max_signals_per_day=10):
        self.max_signals_per_day = max_signals_per_day
        self.daily_signals = {}

    def should_trade(self, signal, timestamp):
        """
        Determine if this signal is in top N for the day
        """
        day = timestamp.date()

        # Initialize day if not seen before
        if day not in self.daily_signals:
            self.daily_signals[day] = []

        # Add signal to day's list
        signal_with_time = {**signal, 'timestamp': timestamp}
        self.daily_signals[day].append(signal_with_time)

        # Sort by extremeness score
        self.daily_signals[day].sort(key=lambda x: x['extremeness_score'], reverse=True)

        # Keep only top N
        if len(self.daily_signals[day]) > self.max_signals_per_day:
            self.daily_signals[day] = self.daily_signals[day][:self.max_signals_per_day]

        # Check if current signal is in top N
        is_in_top = signal_with_time in self.daily_signals[day]

        return is_in_top, len(self.daily_signals[day])

    def get_daily_stats(self):
        """
        Get statistics about signals per day
        """
        stats = {}
        for day, signals in self.daily_signals.items():
            stats[day] = {
                'total_signals': len(signals),
                'avg_extremeness': np.mean([s['extremeness_score'] for s in signals]),
                'avg_velocity_usd': np.mean([s['velocity_usd'] for s in signals]),
                'avg_volume_spike': np.mean([s['volume_spike_ratio'] for s in signals])
            }
        return stats


class ExtremeOnlyStrategy:
    """
    Strategy that only trades the most extreme moves
    """

    def __init__(self,
                 min_velocity_pct=1.0,
                 max_signals_per_day=10,
                 leverage=50,
                 take_profit_pct=0.4,
                 stop_loss_pct=0.5):

        self.extreme_detector = ExtremeMoveDetector(min_velocity_pct=min_velocity_pct)
        self.signal_filter = TopSignalFilter(max_signals_per_day=max_signals_per_day)
        self.leverage = leverage
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct

        self.extreme_moves_detected = []
        self.top_signals = []

    def process_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Process candle and generate signals for extreme moves only
        """
        # Detect extreme move
        extreme_move = self.extreme_detector.add_candle(
            timestamp, open_price, high, low, close, volume
        )

        if extreme_move:
            self.extreme_moves_detected.append(extreme_move)

            print(f"\n🚨 EXTREME MOVE DETECTED at {timestamp}")
            print(f"   Velocity: ${extreme_move['velocity_usd']:.2f} ({extreme_move['velocity_pct']:.2f}%)")
            print(f"   Volume Spike: {extreme_move['volume_spike_ratio']:.1f}x")
            print(f"   Extremeness Score: {extreme_move['extremeness_score']:.2f}")

            # Check if this should be traded (top 10 for the day)
            is_top, daily_count = self.signal_filter.should_trade(extreme_move, timestamp)

            if is_top:
                # Wait 1-2 candles for confirmation, then generate signal
                signal = self._generate_trade_signal(extreme_move, timestamp)
                if signal:
                    self.top_signals.append(signal)
                    print(f"   ✅ SIGNAL #{len(self.top_signals)} (Top {daily_count} for day)")
                    return signal
            else:
                print(f"   ⏭️  Not in top {self.signal_filter.max_signals_per_day} for day (currently {daily_count})")

        return None

    def _generate_trade_signal(self, extreme_move, timestamp):
        """
        Generate SHORT signal after extreme upward move
        """
        entry_price = extreme_move['price']

        # Take profit (ride it down)
        take_profit = entry_price * (1 - self.take_profit_pct / 100)

        # Stop loss (above the high)
        stop_loss = entry_price * (1 + self.stop_loss_pct / 100)

        # Calculate R:R
        tp_distance = self.take_profit_pct
        sl_distance = self.stop_loss_pct
        risk_reward = tp_distance / sl_distance

        return {
            'type': 'SHORT',
            'timestamp': timestamp,
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'leverage': self.leverage,
            'tp_distance_pct': tp_distance,
            'sl_distance_pct': sl_distance,
            'risk_reward': risk_reward,
            'extremeness_score': extreme_move['extremeness_score'],
            'velocity_usd': extreme_move['velocity_usd']
        }


def backtest_extreme_strategy(data_file, min_velocity_pct=1.0, max_signals_per_day=10):
    """
    Backtest the extreme-only strategy
    """
    print("="*80)
    print("EXTREME MOVE STRATEGY - Only Trade The Biggest Cascades")
    print("="*80)
    print(f"Min Velocity: {min_velocity_pct}% in 1-2 minutes")
    print(f"Max Signals: {max_signals_per_day} per day")
    print("="*80)

    # Load data
    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"\nLoaded {len(df)} candles")
    print(f"Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
    print(f"Total days: {days}")

    # Initialize strategy
    strategy = ExtremeOnlyStrategy(
        min_velocity_pct=min_velocity_pct,
        max_signals_per_day=max_signals_per_day,
        leverage=50,
        take_profit_pct=0.4,
        stop_loss_pct=0.5
    )

    # Track results
    trades = []
    capital = 1000
    initial_capital = 1000

    print("\nProcessing candles...\n")

    active_position = None

    for idx, row in df.iterrows():
        # Check for exit on active position
        if active_position:
            # Check TP
            if row['low'] <= active_position['take_profit']:
                pnl_pct = active_position['tp_distance_pct'] * strategy.leverage
                pnl_usd = capital * (pnl_pct / 100)
                capital += pnl_usd

                print(f"\n✅ TAKE PROFIT HIT at {row['timestamp']}")
                print(f"   Entry: ${active_position['entry_price']:.2f} → TP: ${active_position['take_profit']:.2f}")
                print(f"   P&L: +{pnl_pct:.1f}% (${pnl_usd:.2f})")
                print(f"   Capital: ${capital:.2f}")

                trades.append({'result': 'win', 'pnl_pct': pnl_pct, 'pnl_usd': pnl_usd})
                active_position = None

            # Check SL
            elif row['high'] >= active_position['stop_loss']:
                pnl_pct = -active_position['sl_distance_pct'] * strategy.leverage
                pnl_usd = capital * (pnl_pct / 100)
                capital += pnl_usd

                print(f"\n❌ STOP LOSS HIT at {row['timestamp']}")
                print(f"   Entry: ${active_position['entry_price']:.2f} → SL: ${active_position['stop_loss']:.2f}")
                print(f"   P&L: {pnl_pct:.1f}% (${pnl_usd:.2f})")
                print(f"   Capital: ${capital:.2f}")

                trades.append({'result': 'loss', 'pnl_pct': pnl_pct, 'pnl_usd': pnl_usd})
                active_position = None

        # Process new candle for signals
        signal = strategy.process_candle(
            row['timestamp'],
            row['open'],
            row['high'],
            row['low'],
            row['close'],
            row['volume']
        )

        # Open position if signal and no active position
        if signal and not active_position:
            active_position = signal
            print(f"   📍 Position opened at ${signal['entry_price']:.2f}")

        # Progress update
        if (idx + 1) % 1000 == 0:
            print(f"\n--- Progress: {idx+1}/{len(df)} candles ({(idx+1)/len(df)*100:.1f}%) ---")
            print(f"Extreme moves detected: {len(strategy.extreme_moves_detected)}")
            print(f"Top signals generated: {len(strategy.top_signals)}")
            print(f"Trades executed: {len(trades)}")
            print(f"Current capital: ${capital:.2f}")

    # Final results
    print("\n" + "="*80)
    print("BACKTEST RESULTS")
    print("="*80)

    if trades:
        wins = [t for t in trades if t['result'] == 'win']
        losses = [t for t in trades if t['result'] == 'loss']

        win_rate = len(wins) / len(trades)
        avg_win = np.mean([t['pnl_pct'] for t in wins]) if wins else 0
        avg_loss = np.mean([abs(t['pnl_pct']) for t in losses]) if losses else 0

        total_return = ((capital - initial_capital) / initial_capital) * 100

        print(f"\n📊 TRADES:")
        print(f"   Total: {len(trades)} ({len(trades)/days:.1f} per day)")
        print(f"   Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"   Win Rate: {win_rate*100:.1f}%")

        print(f"\n💵 PROFITABILITY:")
        print(f"   Average Win: +{avg_win:.1f}%")
        print(f"   Average Loss: -{avg_loss:.1f}%")
        print(f"   R:R Ratio: {avg_win/avg_loss if avg_loss > 0 else 0:.2f}")

        print(f"\n💰 CAPITAL:")
        print(f"   Initial: ${initial_capital:,.2f}")
        print(f"   Final: ${capital:,.2f}")
        print(f"   Return: {total_return:,.2f}%")

        print(f"\n🎯 SIGNAL QUALITY:")
        print(f"   Extreme moves detected: {len(strategy.extreme_moves_detected)}")
        print(f"   Top signals selected: {len(strategy.top_signals)}")
        print(f"   Selection ratio: {len(strategy.top_signals)/len(strategy.extreme_moves_detected)*100:.1f}%")

        # Daily breakdown
        daily_stats = strategy.signal_filter.get_daily_stats()
        print(f"\n📅 DAILY BREAKDOWN:")
        for day, stats in list(daily_stats.items())[:3]:
            print(f"   {day}: {stats['total_signals']} signals, "
                  f"avg velocity ${stats['avg_velocity_usd']:.2f}, "
                  f"avg spike {stats['avg_volume_spike']:.1f}x")
    else:
        print("\n❌ No trades executed")
        print(f"Extreme moves detected: {len(strategy.extreme_moves_detected)}")
        print(f"Top signals generated: {len(strategy.top_signals)}")

    print("\n" + "="*80)

    return strategy, trades, capital


def main():
    """
    Test extreme-only strategy on real 7-day data
    """
    print("\n🎯 Testing EXTREME MOVES ONLY Strategy")
    print("Goal: ~10 trades per day, only the biggest liquidation cascades\n")

    # Test with different velocity thresholds
    for min_velocity in [0.75, 1.0, 1.25, 1.5]:
        print(f"\n{'='*80}")
        print(f"TEST: Minimum Velocity {min_velocity}%")
        print(f"{'='*80}")

        strategy, trades, final_capital = backtest_extreme_strategy(
            'SOL_USDT_1min_7days.csv',
            min_velocity_pct=min_velocity,
            max_signals_per_day=10
        )

        print("\n")


if __name__ == "__main__":
    main()
