"""
SINGLE SPIKE REVERSAL DETECTOR

The REAL pattern from image.png:
- ONE massive green candle (≥1.5-2%)
- Followed by immediate strong red candle (≥0.3%)
- This is the exact "spike and dump" pattern

Only ~4 occurrences in 7 days = 0.6 per day
But when it happens, it's a strong signal!
"""

import pandas as pd
import numpy as np
from collections import deque


class SingleSpikeReversalDetector:
    """
    Detect: BIG green candle → immediate red reversal
    """

    def __init__(self,
                 min_spike_body_pct=1.5,
                 min_reversal_body_pct=0.3):

        self.min_spike_body_pct = min_spike_body_pct
        self.min_reversal_body_pct = min_reversal_body_pct

        self.candle_buffer = deque(maxlen=50)
        self.last_spike = None  # Track if previous candle was a spike

    def add_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Check if current candle reverses a previous spike
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

        if len(self.candle_buffer) < 2:
            return None

        current = self.candle_buffer[-1]
        prev = self.candle_buffer[-2]

        # Calculate current candle characteristics
        current_is_green = current['close'] > current['open']
        current_body_pct = abs(current['close'] - current['open']) / current['open'] * 100

        # Calculate previous candle characteristics
        prev_is_green = prev['close'] > prev['open']
        prev_body_pct = abs(prev['close'] - prev['open']) / prev['open'] * 100

        # Check if previous candle was a SPIKE
        if prev_is_green and prev_body_pct >= self.min_spike_body_pct:
            self.last_spike = {
                'timestamp': prev['timestamp'],
                'high': prev['close'],
                'body_pct': prev_body_pct
            }

        # Check if current candle REVERSES the spike
        if self.last_spike is not None:
            # Is current candle a strong red?
            current_is_red = not current_is_green

            if current_is_red and current_body_pct >= self.min_reversal_body_pct:
                # REVERSAL CONFIRMED!
                signal = {
                    'timestamp': timestamp,
                    'entry_price': close,
                    'spike_high': self.last_spike['high'],
                    'spike_body_pct': self.last_spike['body_pct'],
                    'reversal_body_pct': current_body_pct,
                    'spike_time': self.last_spike['timestamp']
                }

                print(f"\n🎯 SPIKE REVERSAL DETECTED at {timestamp}")
                print(f"   Spike candle: {self.last_spike['timestamp']} (+{self.last_spike['body_pct']:.2f}%)")
                print(f"   Spike high: ${self.last_spike['high']:.2f}")
                print(f"   Reversal candle: -{current_body_pct:.2f}%")
                print(f"   Entry: ${close:.2f}")

                # Reset
                self.last_spike = None

                return signal

        return None


class SingleSpikeStrategy:
    """
    Strategy: Short on spike reversals
    """

    def __init__(self,
                 min_spike_body_pct=1.5,
                 min_reversal_body_pct=0.3,
                 leverage=50,
                 take_profit_pct=0.5,
                 stop_loss_pct=0.4):

        self.detector = SingleSpikeReversalDetector(
            min_spike_body_pct=min_spike_body_pct,
            min_reversal_body_pct=min_reversal_body_pct
        )
        self.leverage = leverage
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct

        self.signals = []

    def process_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Process candle and generate signals
        """
        reversal = self.detector.add_candle(timestamp, open_price, high, low, close, volume)

        if reversal:
            signal = self._generate_signal(reversal)
            self.signals.append(signal)
            return signal

        return None

    def _generate_signal(self, reversal):
        """
        Generate SHORT signal
        """
        entry_price = reversal['entry_price']

        # Take profit
        take_profit = entry_price * (1 - self.take_profit_pct / 100)

        # Stop loss (above spike high)
        stop_loss = reversal['spike_high'] * 1.002  # 0.2% above

        # Calculate distances
        tp_distance_pct = self.take_profit_pct
        sl_distance_pct = ((stop_loss - entry_price) / entry_price) * 100

        return {
            'type': 'SHORT',
            'timestamp': reversal['timestamp'],
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'leverage': self.leverage,
            'tp_distance_pct': tp_distance_pct,
            'sl_distance_pct': sl_distance_pct,
            'risk_reward': tp_distance_pct / sl_distance_pct if sl_distance_pct > 0 else 0,
            'spike_body_pct': reversal['spike_body_pct'],
            'reversal_body_pct': reversal['reversal_body_pct']
        }


def backtest_single_spike(data_file, min_spike_pct=1.5, min_reversal_pct=0.3):
    """
    Backtest the single spike reversal strategy
    """
    print("="*80)
    print("SINGLE SPIKE REVERSAL STRATEGY")
    print("="*80)
    print(f"Pattern: BIG green (≥{min_spike_pct}%) → red reversal (≥{min_reversal_pct}%)")
    print("="*80)

    # Load data
    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"\nLoaded {len(df)} candles")
    days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
    print(f"Days: {days}")

    # Initialize strategy
    strategy = SingleSpikeStrategy(
        min_spike_body_pct=min_spike_pct,
        min_reversal_body_pct=min_reversal_pct,
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
    Test single spike reversal strategy
    """
    print("\n🎯 SINGLE SPIKE REVERSAL - The Pattern from image.png\n")

    # Test different thresholds
    configs = [
        (1.5, 0.3),  # Spike ≥1.5%, reversal ≥0.3%
        (1.5, 0.5),  # Spike ≥1.5%, reversal ≥0.5%
        (2.0, 0.3),  # Spike ≥2.0%, reversal ≥0.3%
        (2.0, 0.5),  # Spike ≥2.0%, reversal ≥0.5%
    ]

    for spike_pct, reversal_pct in configs:
        print(f"\n{'='*80}")
        print(f"TEST: Spike ≥{spike_pct}%, Reversal ≥{reversal_pct}%")
        print(f"{'='*80}")

        strategy, trades, capital = backtest_single_spike(
            'SOL_USDT_1min_7days.csv',
            min_spike_pct=spike_pct,
            min_reversal_pct=reversal_pct
        )

        print("\n")


if __name__ == "__main__":
    main()
