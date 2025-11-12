"""
GREEN CASCADE DETECTOR

The pattern from image.png:
- 2-4 consecutive STRONG green candles stacked together
- Creates a big move (≥1% total)
- Followed by immediate red candle reversal
- This is the exact visual pattern to short

Strategy:
1. Detect when we get 2-4 consecutive strong green candles
2. Calculate total move size
3. Wait for first red candle confirmation
4. Enter SHORT on the reversal
"""

import pandas as pd
import numpy as np
import json
from collections import deque


class GreenCascadeDetector:
    """
    Detect consecutive green candle cascades that reverse
    """

    def __init__(self,
                 min_consecutive_greens=2,
                 min_total_move_pct=0.75,
                 min_green_body_pct=0.15):

        self.min_consecutive_greens = min_consecutive_greens
        self.min_total_move_pct = min_total_move_pct
        self.min_green_body_pct = min_green_body_pct

        self.candle_buffer = deque(maxlen=100)
        self.active_cascade = None  # Track active green cascade

    def add_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Add candle and check for:
        1. Building green cascade
        2. Reversal of active cascade
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

        if len(self.candle_buffer) < 5:
            return None

        # Check if current candle is strong green
        is_green = close > open_price
        body_pct = abs(close - open_price) / open_price * 100

        if is_green and body_pct >= self.min_green_body_pct:
            # Building or continuing a cascade
            if self.active_cascade is None:
                # Start new cascade
                self.active_cascade = {
                    'start_idx': len(self.candle_buffer) - 1,
                    'start_price': open_price,
                    'candle_count': 1,
                    'high_price': close,
                    'start_time': timestamp
                }
            else:
                # Continue existing cascade
                self.active_cascade['candle_count'] += 1
                self.active_cascade['high_price'] = max(self.active_cascade['high_price'], close)

        elif self.active_cascade is not None:
            # Current candle is NOT green - check if cascade reverses
            cascade_move = self.active_cascade['high_price'] - self.active_cascade['start_price']
            cascade_move_pct = (cascade_move / self.active_cascade['start_price']) * 100

            # Is this a significant cascade that's now reversing?
            is_red = close < open_price
            red_body_pct = abs(close - open_price) / open_price * 100

            if (self.active_cascade['candle_count'] >= self.min_consecutive_greens and
                cascade_move_pct >= self.min_total_move_pct and
                is_red and red_body_pct >= 0.1):  # Red confirmation candle

                # REVERSAL DETECTED!
                signal = {
                    'timestamp': timestamp,
                    'entry_price': close,
                    'cascade_high': self.active_cascade['high_price'],
                    'cascade_start': self.active_cascade['start_price'],
                    'cascade_move_pct': cascade_move_pct,
                    'cascade_candles': self.active_cascade['candle_count'],
                    'cascade_start_time': self.active_cascade['start_time'],
                    'reversal_body_pct': red_body_pct
                }

                print(f"\n🎯 GREEN CASCADE REVERSAL DETECTED at {timestamp}")
                print(f"   Cascade: {self.active_cascade['candle_count']} green candles")
                print(f"   Move: ${self.active_cascade['start_price']:.2f} → ${self.active_cascade['high_price']:.2f} (+{cascade_move_pct:.2f}%)")
                print(f"   Reversal candle: {red_body_pct:.3f}% red body")
                print(f"   Entry: ${close:.2f}")

                # Reset cascade
                self.active_cascade = None

                return signal

            # Weak reversal or continuation - reset cascade
            self.active_cascade = None

        return None


class GreenCascadeStrategy:
    """
    Strategy: Short when green cascades reverse
    """

    def __init__(self,
                 min_consecutive_greens=2,
                 min_total_move_pct=0.75,
                 leverage=50,
                 take_profit_pct=0.5,
                 stop_loss_pct=0.4):

        self.detector = GreenCascadeDetector(
            min_consecutive_greens=min_consecutive_greens,
            min_total_move_pct=min_total_move_pct
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
        Generate SHORT signal after cascade reversal
        """
        entry_price = reversal['entry_price']

        # Take profit (ride it down)
        take_profit = entry_price * (1 - self.take_profit_pct / 100)

        # Stop loss (above cascade high)
        stop_loss = reversal['cascade_high'] * 1.002  # 0.2% above high

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
            'cascade_move_pct': reversal['cascade_move_pct'],
            'cascade_candles': reversal['cascade_candles']
        }


def backtest_green_cascade(data_file, min_consecutive_greens=2, min_move_pct=0.75):
    """
    Backtest the green cascade reversal strategy
    """
    print("="*80)
    print("GREEN CASCADE REVERSAL STRATEGY")
    print("="*80)
    print(f"Pattern: {min_consecutive_greens}+ consecutive green candles → red reversal")
    print(f"Min move: {min_move_pct}%")
    print("="*80)

    # Load data
    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"\nLoaded {len(df)} candles")
    days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
    print(f"Days: {days}")

    # Initialize strategy
    strategy = GreenCascadeStrategy(
        min_consecutive_greens=min_consecutive_greens,
        min_total_move_pct=min_move_pct,
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
                pnl_usd = capital * (pnl_pct / 100) * 0.92  # After fees
                capital += pnl_usd

                print(f"\n✅ TAKE PROFIT at {row['timestamp']}")
                print(f"   Entry: ${active_position['entry_price']:.2f} → TP: ${active_position['take_profit']:.2f}")
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
                print(f"   Entry: ${active_position['entry_price']:.2f} → SL: ${active_position['stop_loss']:.2f}")
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

        # Progress
        if (idx + 1) % 2000 == 0:
            print(f"\n--- Progress: {idx+1}/{len(df)} ({(idx+1)/len(df)*100:.1f}%) ---")
            print(f"Signals: {len(strategy.signals)}")
            print(f"Trades: {len(trades)}")
            print(f"Capital: ${capital:.2f}")

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

        # Cascade analysis
        if strategy.signals:
            cascade_sizes = [s['cascade_candles'] for s in strategy.signals]
            cascade_moves = [s['cascade_move_pct'] for s in strategy.signals]

            print(f"\n📈 CASCADE ANALYSIS:")
            print(f"   Avg cascade size: {np.mean(cascade_sizes):.1f} candles")
            print(f"   Avg cascade move: {np.mean(cascade_moves):.2f}%")
            print(f"   Max cascade move: {np.max(cascade_moves):.2f}%")
    else:
        print("\n❌ No trades executed")
        print(f"Signals generated: {len(strategy.signals)}")

    print("\n" + "="*80)

    return strategy, trades, capital


def main():
    """
    Test green cascade reversal strategy
    """
    print("\n🎯 GREEN CASCADE REVERSAL STRATEGY")
    print("Pattern from image.png: Multiple green candles → immediate red reversal\n")

    # Test different configurations
    configs = [
        (2, 0.75),  # 2+ greens, 0.75% move
        (2, 1.0),   # 2+ greens, 1.0% move
        (3, 0.75),  # 3+ greens, 0.75% move
        (3, 1.0),   # 3+ greens, 1.0% move
    ]

    for min_greens, min_move in configs:
        print(f"\n{'='*80}")
        print(f"TEST: {min_greens}+ consecutive greens, {min_move}% min move")
        print(f"{'='*80}")

        strategy, trades, capital = backtest_green_cascade(
            'SOL_USDT_1min_7days.csv',
            min_consecutive_greens=min_greens,
            min_move_pct=min_move
        )

        print("\n")


if __name__ == "__main__":
    main()
