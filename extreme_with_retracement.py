"""
EXTREME MOVE + RETRACEMENT STRATEGY

The RIGHT way:
1. Detect big upward spike ($2-4 in 30 seconds) ✅
2. WAIT for price to retrace significantly (30-50% of the spike)
3. THEN short on the confirmed slide down

Current problem: We short immediately after spike → price continues up → we lose
Solution: Wait for big red candle that retraces the spike → confirms exhaustion → ride it down
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import deque


class ExtremeMoveWithRetracementDetector:
    """
    Detect extreme moves, then wait for retracement confirmation
    """

    def __init__(self, min_spike_pct=1.0, min_retracement_pct=30):
        self.min_spike_pct = min_spike_pct
        self.min_retracement_pct = min_retracement_pct

        self.candle_buffer = deque(maxlen=100)
        self.recent_spikes = []  # Track spikes waiting for retracement

    def add_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Add candle and check for:
        1. New extreme upward spike
        2. Retracement of recent spike
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

        df = pd.DataFrame(list(self.candle_buffer))

        # Step 1: Check for new extreme spike
        spike = self._detect_spike(df)
        if spike:
            self.recent_spikes.append(spike)
            print(f"\n🚨 EXTREME SPIKE DETECTED at {timestamp}")
            print(f"   Size: ${spike['spike_usd']:.2f} ({spike['spike_pct']:.2f}%)")
            print(f"   High: ${spike['spike_high']:.2f}")
            print(f"   ⏳ Waiting for retracement...")

        # Step 2: Check if current candle retraces any recent spike
        signal = self._detect_retracement(df, timestamp)
        if signal:
            return signal

        # Clean up old spikes (older than 10 candles)
        self.recent_spikes = [
            s for s in self.recent_spikes
            if (timestamp - s['timestamp']).total_seconds() < 600  # 10 minutes
        ]

        return None

    def _detect_spike(self, df):
        """
        Detect if current candle is an extreme upward spike
        """
        if len(df) < 2:
            return None

        current = df.iloc[-1]
        prev = df.iloc[-2]

        # Calculate spike
        spike_usd = current['close'] - prev['close']
        spike_pct = (spike_usd / prev['close']) * 100

        # Is this an extreme upward spike?
        if spike_pct >= self.min_spike_pct:
            return {
                'timestamp': current['timestamp'],
                'spike_low': prev['close'],
                'spike_high': current['close'],
                'spike_usd': spike_usd,
                'spike_pct': spike_pct
            }

        return None

    def _detect_retracement(self, df, timestamp):
        """
        Check if current candle retraces a recent spike
        """
        if len(self.recent_spikes) == 0:
            return None

        current = df.iloc[-1]

        # Check each recent spike
        for spike in self.recent_spikes:
            # How much has price retraced from the spike high?
            retracement_usd = spike['spike_high'] - current['close']
            retracement_pct = (retracement_usd / spike['spike_usd']) * 100

            # Is this a significant retracement?
            if retracement_pct >= self.min_retracement_pct:
                # Check if current candle is red and strong
                is_red = current['close'] < current['open']
                candle_body = abs(current['close'] - current['open'])
                candle_body_pct = (candle_body / current['open']) * 100

                # Strong red candle (body > 0.2%)
                if is_red and candle_body_pct >= 0.2:
                    print(f"\n✅ RETRACEMENT CONFIRMED at {timestamp}")
                    print(f"   Spike was: ${spike['spike_usd']:.2f} ({spike['spike_pct']:.2f}%)")
                    print(f"   Retraced: ${retracement_usd:.2f} ({retracement_pct:.1f}% of spike)")
                    print(f"   Entry: ${current['close']:.2f}")

                    # Remove this spike from tracking
                    self.recent_spikes.remove(spike)

                    return {
                        'timestamp': timestamp,
                        'entry_price': current['close'],
                        'spike_high': spike['spike_high'],
                        'spike_size': spike['spike_usd'],
                        'spike_pct': spike['spike_pct'],
                        'retracement_pct': retracement_pct,
                        'candle_body_pct': candle_body_pct
                    }

        return None


class ExtremRetracementStrategy:
    """
    Strategy: Only trade extreme spikes with confirmed retracement
    """

    def __init__(self,
                 min_spike_pct=1.0,
                 min_retracement_pct=30,
                 leverage=50,
                 take_profit_pct=0.5,
                 stop_loss_pct=0.6):

        self.detector = ExtremeMoveWithRetracementDetector(
            min_spike_pct=min_spike_pct,
            min_retracement_pct=min_retracement_pct
        )
        self.leverage = leverage
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct

        self.signals = []

    def process_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Process candle and generate signals
        """
        retracement = self.detector.add_candle(
            timestamp, open_price, high, low, close, volume
        )

        if retracement:
            signal = self._generate_signal(retracement)
            self.signals.append(signal)
            return signal

        return None

    def _generate_signal(self, retracement):
        """
        Generate SHORT signal after confirmed retracement
        """
        entry_price = retracement['entry_price']

        # Take profit
        take_profit = entry_price * (1 - self.take_profit_pct / 100)

        # Stop loss (above the spike high)
        stop_loss = retracement['spike_high'] * 1.002  # 0.2% above spike high

        # Calculate R:R
        tp_distance_pct = self.take_profit_pct
        sl_distance_pct = ((stop_loss - entry_price) / entry_price) * 100

        return {
            'type': 'SHORT',
            'timestamp': retracement['timestamp'],
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'leverage': self.leverage,
            'tp_distance_pct': tp_distance_pct,
            'sl_distance_pct': sl_distance_pct,
            'risk_reward': tp_distance_pct / sl_distance_pct if sl_distance_pct > 0 else 0,
            'spike_size': retracement['spike_size'],
            'retracement_pct': retracement['retracement_pct']
        }


def backtest_retracement_strategy(data_file, min_spike_pct=1.0, min_retracement_pct=30):
    """
    Backtest the extreme spike + retracement strategy
    """
    print("="*80)
    print("EXTREME SPIKE + RETRACEMENT STRATEGY")
    print("="*80)
    print(f"Step 1: Detect spikes ≥{min_spike_pct}%")
    print(f"Step 2: Wait for ≥{min_retracement_pct}% retracement")
    print(f"Step 3: SHORT on confirmed slide down")
    print("="*80)

    # Load data
    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"\nLoaded {len(df)} candles")
    days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
    print(f"Days: {days}")

    # Initialize strategy
    strategy = ExtremRetracementStrategy(
        min_spike_pct=min_spike_pct,
        min_retracement_pct=min_retracement_pct,
        leverage=50,
        take_profit_pct=0.5,
        stop_loss_pct=0.6
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
                print(f"   ${active_position['entry_price']:.2f} → ${active_position['take_profit']:.2f}")
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
                print(f"   ${active_position['entry_price']:.2f} → ${active_position['stop_loss']:.2f}")
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
    else:
        print("\n❌ No trades executed")
        print(f"Signals generated: {len(strategy.signals)}")

    print("\n" + "="*80)

    return strategy, trades, capital


def main():
    """
    Test different retracement thresholds
    """
    print("\n🎯 EXTREME SPIKE + RETRACEMENT STRATEGY")
    print("Wait for big pullback before entering\n")

    # Test different retracement requirements
    configs = [
        (1.0, 10),  # 1% spike, 10% retracement
        (1.0, 15),  # 1% spike, 15% retracement
        (1.0, 20),  # 1% spike, 20% retracement
        (1.0, 25),  # 1% spike, 25% retracement
    ]

    for spike_pct, retrace_pct in configs:
        print(f"\n{'='*80}")
        print(f"TEST: {spike_pct}% spike + {retrace_pct}% retracement required")
        print(f"{'='*80}")

        strategy, trades, capital = backtest_retracement_strategy(
            'SOL_USDT_1min_7days.csv',
            min_spike_pct=spike_pct,
            min_retracement_pct=retrace_pct
        )

        print("\n")


if __name__ == "__main__":
    main()
