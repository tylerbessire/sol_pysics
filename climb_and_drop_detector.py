"""
CLIMB AND DROP DETECTOR

The pattern the user found manually:
- Price climbs significantly over 10-20 minutes (e.g., 153.8 → 155.275 in 15 min)
- Then DROPS back down in 5-10 minutes (e.g., 155.275 → 153.8 in 7 min) ← GOLD!

We want to catch the DROP, not predict the top.

Strategy:
1. Track when price is making a significant upward move
2. Detect when it starts dropping back down
3. Enter SHORT on the confirmed drop
4. Ride it down for 0.5-1%
"""

import pandas as pd
import numpy as np
from collections import deque


class ClimbAndDropDetector:
    """
    Detect: Rapid climb → Fast drop back down
    """

    def __init__(self,
                 min_climb_pct=0.75,
                 min_drop_pct=0.3,
                 lookback_minutes=30):

        self.min_climb_pct = min_climb_pct
        self.min_drop_pct = min_drop_pct
        self.lookback_minutes = lookback_minutes

        self.candle_buffer = deque(maxlen=50)
        self.tracking_climb = False
        self.climb_low = None
        self.climb_high = None
        self.climb_high_time = None

    def add_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Track climbs and detect drops
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

        df = pd.DataFrame(list(self.candle_buffer))

        # Get recent high and low over lookback period
        recent_high = df['high'].max()
        recent_low = df['close'].min()

        # Calculate total move from recent low to high
        total_move_pct = ((recent_high - recent_low) / recent_low) * 100

        # Are we in a significant upward move?
        if total_move_pct >= self.min_climb_pct:
            self.tracking_climb = True
            self.climb_low = recent_low
            self.climb_high = recent_high

            # Find when the high occurred
            high_idx = df['high'].idxmax()
            self.climb_high_time = df.loc[high_idx, 'timestamp']

        # Check for DROP from the climb high
        if self.tracking_climb and self.climb_high is not None:
            current_price = close

            # How much has it dropped from the high?
            drop_usd = self.climb_high - current_price
            drop_pct = (drop_usd / self.climb_high) * 100

            # Is current candle red and showing momentum down?
            is_red = close < open_price
            red_body_pct = abs(close - open_price) / open_price * 100 if is_red else 0

            # Has it dropped significantly?
            if drop_pct >= self.min_drop_pct and is_red and red_body_pct >= 0.1:
                # DROPDETECTED!
                signal = {
                    'timestamp': timestamp,
                    'entry_price': close,
                    'climb_low': self.climb_low,
                    'climb_high': self.climb_high,
                    'climb_high_time': self.climb_high_time,
                    'climb_pct': ((self.climb_high - self.climb_low) / self.climb_low) * 100,
                    'drop_pct': drop_pct,
                    'red_body_pct': red_body_pct
                }

                print(f"\n🎯 CLIMB → DROP DETECTED at {timestamp}")
                print(f"   Climb: ${self.climb_low:.2f} → ${self.climb_high:.2f} (+{signal['climb_pct']:.2f}%)")
                print(f"   Peak time: {self.climb_high_time}")
                print(f"   Drop: ${self.climb_high:.2f} → ${close:.2f} (-{drop_pct:.2f}%)")
                print(f"   Entry: ${close:.2f}")

                # Reset tracking
                self.tracking_climb = False
                self.climb_high = None

                return signal

        return None


class ClimbDropStrategy:
    """
    Strategy: Short on climb → drop patterns
    """

    def __init__(self,
                 min_climb_pct=0.75,
                 min_drop_pct=0.3,
                 leverage=50,
                 take_profit_pct=0.5,
                 stop_loss_pct=0.4):

        self.detector = ClimbAndDropDetector(
            min_climb_pct=min_climb_pct,
            min_drop_pct=min_drop_pct
        )
        self.leverage = leverage
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct

        self.signals = []

    def process_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Process candle and generate signals
        """
        drop = self.detector.add_candle(timestamp, open_price, high, low, close, volume)

        if drop:
            signal = self._generate_signal(drop)
            self.signals.append(signal)
            return signal

        return None

    def _generate_signal(self, drop):
        """
        Generate SHORT signal
        """
        entry_price = drop['entry_price']

        # Take profit (ride it down further)
        take_profit = entry_price * (1 - self.take_profit_pct / 100)

        # Stop loss (above the climb high)
        stop_loss = drop['climb_high'] * 1.002

        # Calculate distances
        tp_distance_pct = self.take_profit_pct
        sl_distance_pct = ((stop_loss - entry_price) / entry_price) * 100

        return {
            'type': 'SHORT',
            'timestamp': drop['timestamp'],
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'leverage': self.leverage,
            'tp_distance_pct': tp_distance_pct,
            'sl_distance_pct': sl_distance_pct,
            'risk_reward': tp_distance_pct / sl_distance_pct if sl_distance_pct > 0 else 0,
            'climb_pct': drop['climb_pct'],
            'drop_pct': drop['drop_pct']
        }


def backtest_climb_drop(data_file, min_climb_pct=0.75, min_drop_pct=0.3):
    """
    Backtest the climb → drop strategy
    """
    print("="*80)
    print("CLIMB → DROP STRATEGY")
    print("="*80)
    print(f"Pattern: Climb ≥{min_climb_pct}% → Drop ≥{min_drop_pct}%")
    print("Example: 153.8 → 155.275 in 15 min → 153.8 in 7 min")
    print("="*80)

    # Load data
    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"\nLoaded {len(df)} candles")
    days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
    print(f"Days: {days}")

    # Initialize strategy
    strategy = ClimbDropStrategy(
        min_climb_pct=min_climb_pct,
        min_drop_pct=min_drop_pct,
        leverage=50,
        take_profit_pct=0.5,
        stop_loss_pct=0.4
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
    Test climb → drop strategy
    """
    print("\n🎯 CLIMB → DROP PATTERN - The 'down seven is gold'  pattern\n")

    # Test different thresholds
    configs = [
        (0.75, 0.3),  # Climb ≥0.75%, drop ≥0.3%
        (0.75, 0.5),  # Climb ≥0.75%, drop ≥0.5%
        (1.0, 0.3),   # Climb ≥1.0%, drop ≥0.3%
        (1.0, 0.5),   # Climb ≥1.0%, drop ≥0.5%
    ]

    for climb_pct, drop_pct in configs:
        print(f"\n{'='*80}")
        print(f"TEST: Climb ≥{climb_pct}%, Drop ≥{drop_pct}%")
        print(f"{'='*80}")

        strategy, trades, capital = backtest_climb_drop(
            'SOL_USDT_1min_7days.csv',
            min_climb_pct=climb_pct,
            min_drop_pct=drop_pct
        )

        print("\n")


if __name__ == "__main__":
    main()
