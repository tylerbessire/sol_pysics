"""
WICK AND RED CASCADE STRATEGY

Based on user's dollar climb-retrace pattern:
1. Track climbs ($1-2 in ~26 minutes average)
2. After climb time passes, check for green wick (rejection at top)
3. Wait for 2 consecutive red candles, each with longer body than previous
4. Enter SHORT on confirmed cascade
5. Exit near original start price

This catches the "down is gold" pattern with confirmation.
"""

import pandas as pd
import numpy as np
from collections import deque


class WickAndRedCascadeDetector:
    """
    Detect: Climb → Green wick → 2+ consecutive increasing red candles → SHORT
    """

    def __init__(self,
                 min_climb_usd=1.0,
                 avg_climb_minutes=26,
                 min_wick_ratio=0.3,
                 min_red_candles=2):

        self.min_climb_usd = min_climb_usd
        self.avg_climb_minutes = avg_climb_minutes
        self.min_wick_ratio = min_wick_ratio  # Wick must be 30% of total range
        self.min_red_candles = min_red_candles

        self.candle_buffer = deque(maxlen=50)
        self.tracking_climb = False
        self.climb_start_price = None
        self.climb_start_time = None
        self.climb_high = None
        self.climb_high_time = None
        self.saw_green_wick = False
        self.red_cascade = []  # Track consecutive red candles

    def add_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Process each candle and detect entry signals
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

        if len(self.candle_buffer) < 3:
            return None

        # Calculate current stats
        current_price = close
        is_green = close > open_price
        is_red = close < open_price
        body = abs(close - open_price)
        body_pct = (body / open_price) * 100

        # Calculate wick (upper wick for green, lower wick for red)
        if is_green:
            upper_wick = high - close
            total_range = high - low
            wick_ratio = upper_wick / total_range if total_range > 0 else 0
        else:
            upper_wick = high - open_price
            total_range = high - low
            wick_ratio = upper_wick / total_range if total_range > 0 else 0

        # Get recent high and low
        df = pd.DataFrame(list(self.candle_buffer))
        recent_high = df['high'].max()
        recent_low = df['low'].min()

        # STATE 1: Not tracking climb yet - look for start of climb
        if not self.tracking_climb:
            # Check if we're in an upward move
            climb_usd = recent_high - recent_low

            if climb_usd >= self.min_climb_usd * 0.5:  # Starting to climb
                self.tracking_climb = True
                self.climb_start_price = recent_low
                self.climb_start_time = df[df['low'] == recent_low].iloc[0]['timestamp']
                self.climb_high = recent_high
                self.climb_high_time = df[df['high'] == recent_high].iloc[0]['timestamp']
                self.saw_green_wick = False
                self.red_cascade = []

                print(f"\n📈 Tracking climb starting at {self.climb_start_time}")
                print(f"   Start: ${self.climb_start_price:.2f}")

        # STATE 2: Tracking climb - update high and watch for signals
        elif self.tracking_climb:
            # Update high if we go higher
            if current_price > self.climb_high:
                self.climb_high = current_price
                self.climb_high_time = timestamp

            # Calculate climb progress
            climb_usd = self.climb_high - self.climb_start_price
            climb_duration = (timestamp - self.climb_start_time).total_seconds() / 60

            # Has climb time passed?
            if climb_duration >= self.avg_climb_minutes:

                # Check for GREEN WICK (rejection at top)
                if is_green and wick_ratio >= self.min_wick_ratio and not self.saw_green_wick:
                    self.saw_green_wick = True
                    print(f"   🕯️ GREEN WICK detected at {timestamp} | High: ${high:.2f} Close: ${close:.2f}")
                    print(f"      Wick ratio: {wick_ratio*100:.1f}% | Waiting for red cascade...")

                # Check for RED CASCADE (2+ consecutive reds with increasing bodies)
                if is_red and self.saw_green_wick:
                    # Add to cascade
                    self.red_cascade.append({
                        'timestamp': timestamp,
                        'body': body,
                        'body_pct': body_pct,
                        'close': close
                    })

                    # Check if we have increasing reds
                    if len(self.red_cascade) >= self.min_red_candles:
                        # Are bodies increasing?
                        bodies_increasing = all(
                            self.red_cascade[i]['body'] < self.red_cascade[i+1]['body']
                            for i in range(len(self.red_cascade)-1)
                        )

                        if bodies_increasing:
                            # SIGNAL! Enter SHORT
                            signal = {
                                'timestamp': timestamp,
                                'entry_price': close,
                                'climb_start_price': self.climb_start_price,
                                'climb_high': self.climb_high,
                                'climb_usd': climb_usd,
                                'climb_pct': (climb_usd / self.climb_start_price) * 100,
                                'climb_duration': climb_duration,
                                'red_cascade_count': len(self.red_cascade),
                                'red_cascade_bodies': [r['body_pct'] for r in self.red_cascade]
                            }

                            print(f"\n🎯 SHORT SIGNAL at {timestamp}")
                            print(f"   Climb: ${self.climb_start_price:.2f} → ${self.climb_high:.2f} (+${climb_usd:.2f})")
                            print(f"   Duration: {climb_duration:.1f} min")
                            print(f"   Green wick: ✅")
                            print(f"   Red cascade: {len(self.red_cascade)} candles")
                            print(f"   Red bodies: {[f'{b:.3f}%' for b in signal['red_cascade_bodies']]}")
                            print(f"   Entry: ${close:.2f}")
                            print(f"   Target: ~${self.climb_start_price:.2f} (ride it back down)")

                            # Reset tracking
                            self.tracking_climb = False
                            self.red_cascade = []

                            return signal

                elif not is_red and len(self.red_cascade) > 0:
                    # Green candle broke the cascade - reset
                    print(f"   ⚠️ Red cascade broken by green candle - resetting")
                    self.red_cascade = []

            # Reset if climb fails or goes too long
            if climb_duration > self.avg_climb_minutes * 2:  # Too long
                print(f"   ⏱️ Climb timeout - resetting")
                self.tracking_climb = False
                self.red_cascade = []

        return None


class WickRedCascadeStrategy:
    """
    Strategy: Trade wick + red cascade signals
    """

    def __init__(self,
                 min_climb_usd=1.0,
                 avg_climb_minutes=26,
                 leverage=50,
                 exit_tolerance_usd=0.15):

        self.detector = WickAndRedCascadeDetector(
            min_climb_usd=min_climb_usd,
            avg_climb_minutes=avg_climb_minutes
        )
        self.leverage = leverage
        self.exit_tolerance_usd = exit_tolerance_usd

        self.signals = []

    def process_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Process candle and generate signals
        """
        signal = self.detector.add_candle(timestamp, open_price, high, low, close, volume)

        if signal:
            trade = self._generate_trade(signal)
            self.signals.append(trade)
            return trade

        return None

    def _generate_trade(self, signal):
        """
        Generate trade with entry and exit targets
        """
        entry_price = signal['entry_price']
        target_price = signal['climb_start_price']

        # Take profit near original start
        take_profit = target_price + self.exit_tolerance_usd  # Slightly above start

        # Stop loss above the climb high
        stop_loss = signal['climb_high'] * 1.002  # 0.2% above high

        # Calculate distances
        tp_distance = entry_price - take_profit
        tp_distance_pct = (tp_distance / entry_price) * 100

        sl_distance = stop_loss - entry_price
        sl_distance_pct = (sl_distance / entry_price) * 100

        return {
            'type': 'SHORT',
            'timestamp': signal['timestamp'],
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'leverage': self.leverage,
            'tp_distance_pct': tp_distance_pct,
            'sl_distance_pct': sl_distance_pct,
            'risk_reward': tp_distance_pct / sl_distance_pct if sl_distance_pct > 0 else 0,
            'climb_usd': signal['climb_usd'],
            'expected_drop_usd': tp_distance,
            'red_cascade_count': signal['red_cascade_count']
        }


def backtest_wick_red_cascade(data_file, min_climb_usd=1.0, avg_climb_minutes=26):
    """
    Backtest the wick and red cascade strategy
    """
    print("="*80)
    print("WICK + RED CASCADE STRATEGY")
    print("="*80)
    print(f"Pattern: ${min_climb_usd}+ climb → green wick → 2+ increasing red candles")
    print(f"Average climb time: {avg_climb_minutes} minutes")
    print("="*80)

    # Load data
    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"\nLoaded {len(df)} candles")
    days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
    print(f"Days: {days}")

    # Initialize strategy
    strategy = WickRedCascadeStrategy(
        min_climb_usd=min_climb_usd,
        avg_climb_minutes=avg_climb_minutes,
        leverage=50,
        exit_tolerance_usd=0.15
    )

    # Track results
    trades = []
    capital = 1000
    initial_capital = 1000
    active_position = None

    print("\nProcessing candles...\n")

    for idx, row in df.iterrows():
        # Check for exit
        if active_position:
            # Check TP
            if row['low'] <= active_position['take_profit']:
                pnl_pct = active_position['tp_distance_pct'] * strategy.leverage
                pnl_usd = capital * (pnl_pct / 100) * 0.92
                capital += pnl_usd

                print(f"\n✅ TAKE PROFIT at {row['timestamp']}")
                print(f"   Dropped: ${active_position['expected_drop_usd']:.2f}")
                print(f"   P&L: +{pnl_pct:.1f}% (${pnl_usd:.2f})")
                print(f"   Capital: ${capital:.2f}")

                trades.append({'result': 'win', 'pnl_pct': pnl_pct, 'pnl_usd': pnl_usd})
                active_position = None

            # Check SL
            elif row['high'] >= active_position['stop_loss']:
                pnl_pct = -active_position['sl_distance_pct'] * strategy.leverage
                pnl_usd = capital * (pnl_pct / 100) * 0.92
                capital += pnl_usd

                print(f"\n❌ STOP LOSS at {row['timestamp']}")
                print(f"   P&L: {pnl_pct:.1f}% (${pnl_usd:.2f})")
                print(f"   Capital: ${capital:.2f}")

                trades.append({'result': 'loss', 'pnl_pct': pnl_pct, 'pnl_usd': pnl_usd})
                active_position = None

        # Process new candle
        signal = strategy.process_candle(
            row['timestamp'],
            row['open'],
            row['high'],
            row['low'],
            row['close'],
            row['volume']
        )

        # Open position
        if signal and not active_position:
            active_position = signal
            print(f"   📍 Position opened")

    # Results
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
        print(f"   Total: {len(trades)} ({len(trades)/days:.1f}/day)")
        print(f"   Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"   Win Rate: {win_rate*100:.1f}%")

        print(f"\n💵 PROFITABILITY:")
        print(f"   Avg Win: +{avg_win:.1f}%")
        print(f"   Avg Loss: -{avg_loss:.1f}%")
        print(f"   R:R Ratio: {avg_win/avg_loss if avg_loss > 0 else 0:.2f}")

        profit_factor = (len(wins) * avg_win) / (len(losses) * avg_loss) if losses else float('inf')
        print(f"   Profit Factor: {profit_factor:.2f}")

        print(f"\n💰 CAPITAL:")
        print(f"   Initial: ${initial_capital:,.2f}")
        print(f"   Final: ${capital:,.2f}")
        print(f"   Return: {total_return:,.1f}%")
    else:
        print("\n❌ No trades executed")
        print(f"Signals generated: {len(strategy.signals)}")

    print("\n" + "="*80)

    return strategy, trades, capital


def main():
    """
    Test wick + red cascade strategy
    """
    print("\n🎯 WICK + RED CASCADE - The 'Down is Gold' Confirmation Strategy\n")

    # Test on 7-day data
    strategy, trades, capital = backtest_wick_red_cascade(
        'SOL_USDT_1min_7days.csv',
        min_climb_usd=1.0,
        avg_climb_minutes=26
    )


if __name__ == "__main__":
    main()
