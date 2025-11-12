"""
LIVE SIGNAL DETECTOR

Real-time momentum exhaustion + confirmation signal detection
for paper/live trading on 1-minute SOL/USDT data.

This system:
1. Monitors live 1-minute candles
2. Calculates momentum exhaustion in real-time
3. Detects confirmation candles
4. Generates trade signals with entry/exit levels
5. Tracks active positions
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import deque
import json


class LiveMomentumDetector:
    """
    Real-time momentum exhaustion detector
    """

    def __init__(self, window=10, exhaustion_threshold=0.6):
        self.window = window
        self.exhaustion_threshold = exhaustion_threshold
        self.candle_buffer = deque(maxlen=100)  # Keep last 100 candles

    def add_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Add new candle and calculate indicators
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

        if len(self.candle_buffer) < self.window + 5:
            return None  # Not enough data yet

        return self._calculate_exhaustion()

    def _calculate_exhaustion(self):
        """
        Calculate momentum exhaustion for current candle
        """
        # Convert buffer to DataFrame
        df = pd.DataFrame(list(self.candle_buffer))

        # Calculate indicators
        df['velocity'] = df['close'].diff()
        df['acceleration'] = df['velocity'].diff()
        df['momentum'] = df['velocity'] * df['volume']
        df['momentum_peak'] = df['momentum'].rolling(self.window).max()
        df['momentum_ratio'] = df['momentum'] / (df['momentum_peak'] + 1e-10)

        # Exhaustion signals
        df['negative_acceleration'] = (df['acceleration'] < 0).astype(float)
        df['momentum_decaying'] = (df['momentum_ratio'] < 0.8).astype(float)
        df['volume_declining'] = (df['volume'] < df['volume'].rolling(5).mean()).astype(float)

        # Combined score
        df['exhaustion_score'] = (
            df['negative_acceleration'] * 0.35 +
            df['momentum_decaying'] * 0.35 +
            df['volume_declining'] * 0.30
        )

        # Green candle analysis
        df['is_green'] = (df['close'] > df['open']).astype(float)
        df['candle_body'] = abs(df['close'] - df['open'])
        df['prev_green_body'] = df['candle_body'].shift(1)
        df['green_weakening'] = (
            (df['is_green'] == 1) &
            (df['candle_body'] < df['prev_green_body'] * 0.7)
        )

        # Exhaustion detected?
        current = df.iloc[-1]
        exhaustion_detected = (
            current['exhaustion_score'] > self.exhaustion_threshold and
            (current['green_weakening'] or df.iloc[-2]['is_green'] == 1)
        )

        return {
            'exhaustion_detected': exhaustion_detected,
            'exhaustion_score': current['exhaustion_score'],
            'velocity': current['velocity'],
            'acceleration': current['acceleration'],
            'momentum_ratio': current['momentum_ratio'],
            'is_green': current['is_green'],
            'candle_body': current['candle_body']
        }


class LiveConfirmationDetector:
    """
    Real-time confirmation candle detector
    """

    def __init__(self, min_red_retracement_pct=50, min_volume_drop_pct=20):
        self.min_red_retracement_pct = min_red_retracement_pct
        self.min_volume_drop_pct = min_volume_drop_pct
        self.recent_exhaustion_signals = []

    def check_confirmation(self, candle_data, exhaustion_signals):
        """
        Check if current candle confirms reversal

        Args:
            candle_data: dict with OHLCV for last several candles
            exhaustion_signals: Recent exhaustion detection signals
        """
        df = pd.DataFrame(candle_data)

        if len(df) < 5:
            return None

        current = df.iloc[-1]

        # Is red candle?
        is_red = current['close'] < current['open']
        if not is_red:
            return None

        # Calculate retracement
        red_body = current['open'] - current['close']
        prev_candles = df.iloc[-4:-1]  # Last 3 candles before current
        recent_green_avg = prev_candles['candle_body'].mean() if 'candle_body' in prev_candles else 0

        if recent_green_avg == 0:
            return None

        retracement_ratio = red_body / recent_green_avg

        # Calculate volume drop
        volume_ma = df['volume'].rolling(10).mean().iloc[-1]
        volume_drop_pct = ((volume_ma - current['volume']) / volume_ma) * 100

        # Check if exhaustion was recently detected (last 5 candles)
        if len(exhaustion_signals) == 0:
            has_recent_exhaustion = False
            exhaustion_score = 0
        else:
            # Get most recent exhaustion signals
            recent_sigs = exhaustion_signals[-5:] if len(exhaustion_signals) >= 5 else exhaustion_signals
            exhaustion_score = max([s['exhaustion_score'] for s in recent_sigs])
            has_recent_exhaustion = True

        # CONFIRMATION CHECK
        is_confirmed = (
            is_red and
            retracement_ratio >= (self.min_red_retracement_pct / 100) and
            volume_drop_pct >= self.min_volume_drop_pct and
            exhaustion_score > 0.6
        )

        if is_confirmed:
            return {
                'confirmed': True,
                'timestamp': current['timestamp'],
                'entry_price': current['close'],
                'retracement_ratio': retracement_ratio,
                'volume_drop_pct': volume_drop_pct,
                'exhaustion_score': exhaustion_score
            }

        return None


class LiveSignalGenerator:
    """
    Generate complete trade signals with entry/exit levels
    """

    def __init__(self, leverage=50, take_profit_pct=0.3, stop_loss_pct=0.5):
        self.leverage = leverage
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct

    def generate_signal(self, confirmation_data, recent_highs):
        """
        Generate complete trade signal
        """
        entry_price = confirmation_data['entry_price']

        # Calculate take profit (short position)
        take_profit = entry_price * (1 - self.take_profit_pct / 100)

        # Calculate stop loss (above recent high)
        recent_high = max(recent_highs)
        stop_loss_recent = recent_high * 1.002  # 0.2% above recent high
        stop_loss_percent = entry_price * (1 + self.stop_loss_pct / 100)
        stop_loss = min(stop_loss_recent, stop_loss_percent)

        # Calculate risk/reward
        tp_distance = self.take_profit_pct
        sl_distance = ((stop_loss - entry_price) / entry_price) * 100
        risk_reward = tp_distance / sl_distance if sl_distance > 0 else 0

        # Calculate position size (as % of capital)
        position_size_pct = 100 / self.leverage  # At 50x, use 2% of capital

        signal = {
            'type': 'SHORT',
            'timestamp': confirmation_data['timestamp'],
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'leverage': self.leverage,
            'position_size_pct': position_size_pct,
            'tp_distance_pct': tp_distance,
            'sl_distance_pct': sl_distance,
            'risk_reward': risk_reward,
            'exhaustion_score': confirmation_data['exhaustion_score'],
            'retracement_ratio': confirmation_data['retracement_ratio'],
            'volume_drop_pct': confirmation_data['volume_drop_pct']
        }

        # Only return signal if R:R is acceptable
        if risk_reward >= 0.5:
            return signal
        else:
            return None


class LiveTradingSystem:
    """
    Complete live trading system
    """

    def __init__(self, config=None):
        if config is None:
            config = {
                'leverage': 50,
                'take_profit_pct': 0.3,
                'stop_loss_pct': 0.5,
                'exhaustion_threshold': 0.6,
                'min_red_retracement_pct': 50,
                'min_volume_drop_pct': 20
            }

        self.config = config
        self.momentum_detector = LiveMomentumDetector(
            window=10,
            exhaustion_threshold=config['exhaustion_threshold']
        )
        self.confirmation_detector = LiveConfirmationDetector(
            min_red_retracement_pct=config['min_red_retracement_pct'],
            min_volume_drop_pct=config['min_volume_drop_pct']
        )
        self.signal_generator = LiveSignalGenerator(
            leverage=config['leverage'],
            take_profit_pct=config['take_profit_pct'],
            stop_loss_pct=config['stop_loss_pct']
        )

        self.exhaustion_signals = []
        self.trade_signals = []
        self.active_position = None

    def process_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Process new candle and generate signals
        """
        # Step 1: Check for momentum exhaustion
        exhaustion_result = self.momentum_detector.add_candle(
            timestamp, open_price, high, low, close, volume
        )

        if exhaustion_result and exhaustion_result['exhaustion_detected']:
            self.exhaustion_signals.append({
                'timestamp': timestamp,
                'exhaustion_score': exhaustion_result['exhaustion_score']
            })
            print(f"\n⚠️  EXHAUSTION DETECTED at {timestamp}")
            print(f"   Score: {exhaustion_result['exhaustion_score']:.2f}")
            print(f"   Waiting for confirmation...")

        # Step 2: Check for confirmation
        if len(self.momentum_detector.candle_buffer) >= 10:
            candle_data = []
            for candle in list(self.momentum_detector.candle_buffer)[-20:]:
                candle_data.append({
                    'timestamp': candle['timestamp'],
                    'open': candle['open'],
                    'close': candle['close'],
                    'volume': candle['volume'],
                    'candle_body': abs(candle['close'] - candle['open'])
                })

            confirmation = self.confirmation_detector.check_confirmation(
                candle_data,
                self.exhaustion_signals[-10:] if self.exhaustion_signals else []
            )

            if confirmation:
                # Step 3: Generate trade signal
                recent_highs = [c['high'] for c in list(self.momentum_detector.candle_buffer)[-20:]]
                signal = self.signal_generator.generate_signal(confirmation, recent_highs)

                if signal:
                    self.trade_signals.append(signal)
                    print(f"\n🎯 TRADE SIGNAL GENERATED at {timestamp}")
                    print(f"   Type: {signal['type']}")
                    print(f"   Entry: ${signal['entry_price']:.2f}")
                    print(f"   TP: ${signal['take_profit']:.2f} ({signal['tp_distance_pct']:.2f}%)")
                    print(f"   SL: ${signal['stop_loss']:.2f} ({signal['sl_distance_pct']:.2f}%)")
                    print(f"   R:R: {signal['risk_reward']:.2f}")
                    print(f"   Leverage: {signal['leverage']}x")
                    return signal

        return None

    def check_position_exit(self, current_price):
        """
        Check if active position should be closed
        """
        if not self.active_position:
            return None

        signal = self.active_position

        # Check TP hit
        if current_price <= signal['take_profit']:
            print(f"\n✅ TAKE PROFIT HIT at ${current_price:.2f}")
            profit_pct = ((signal['entry_price'] - current_price) / signal['entry_price']) * 100
            return_pct = profit_pct * signal['leverage']
            print(f"   Profit: {return_pct:.2f}%")
            self.active_position = None
            return {'result': 'win', 'exit_price': current_price, 'return_pct': return_pct}

        # Check SL hit
        if current_price >= signal['stop_loss']:
            print(f"\n❌ STOP LOSS HIT at ${current_price:.2f}")
            loss_pct = ((current_price - signal['entry_price']) / signal['entry_price']) * 100
            return_pct = -loss_pct * signal['leverage']
            print(f"   Loss: {return_pct:.2f}%")
            self.active_position = None
            return {'result': 'loss', 'exit_price': current_price, 'return_pct': return_pct}

        return None

    def get_status(self):
        """
        Get current system status
        """
        return {
            'total_exhaustion_signals': len(self.exhaustion_signals),
            'total_trade_signals': len(self.trade_signals),
            'active_position': self.active_position is not None,
            'last_signal': self.trade_signals[-1] if self.trade_signals else None
        }


def simulate_live_trading(data_file, system):
    """
    Simulate live trading on historical data (for testing)
    """
    print("="*80)
    print("LIVE TRADING SYSTEM SIMULATION")
    print("="*80)

    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"\nLoaded {len(df)} candles from {data_file}")
    print(f"Simulating live candle-by-candle processing...\n")

    trades_executed = []

    for idx, row in df.iterrows():
        # Process candle
        signal = system.process_candle(
            row['timestamp'],
            row['open'],
            row['high'],
            row['low'],
            row['close'],
            row['volume']
        )

        # If signal generated and no active position, open position
        if signal and not system.active_position:
            system.active_position = signal
            print(f"   📍 Position opened")

        # Check for exit
        if system.active_position:
            # Save position data before checking exit
            entry_time = system.active_position['timestamp']
            entry_price = system.active_position['entry_price']

            exit_result = system.check_position_exit(row['close'])
            if exit_result:
                exit_result['entry_time'] = entry_time
                exit_result['entry_price'] = entry_price
                exit_result['exit_time'] = row['timestamp']
                trades_executed.append(exit_result)

        # Progress update every 1000 candles
        if (idx + 1) % 1000 == 0:
            status = system.get_status()
            print(f"\n--- Progress: {idx+1}/{len(df)} candles ---")
            print(f"Exhaustion signals: {status['total_exhaustion_signals']}")
            print(f"Trade signals: {status['total_trade_signals']}")
            print(f"Trades executed: {len(trades_executed)}")

    # Final statistics
    print("\n" + "="*80)
    print("SIMULATION COMPLETE")
    print("="*80)

    if trades_executed:
        wins = [t for t in trades_executed if t['result'] == 'win']
        losses = [t for t in trades_executed if t['result'] == 'loss']

        win_rate = len(wins) / len(trades_executed)
        avg_win = np.mean([t['return_pct'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['return_pct'] for t in losses]) if losses else 0

        print(f"\nTrades Executed: {len(trades_executed)}")
        print(f"Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"Win Rate: {win_rate*100:.1f}%")
        print(f"Average Win: {avg_win:.2f}%")
        print(f"Average Loss: {avg_loss:.2f}%")

    status = system.get_status()
    print(f"\nTotal Exhaustion Signals: {status['total_exhaustion_signals']}")
    print(f"Total Trade Signals Generated: {status['total_trade_signals']}")


def main():
    """
    Test live trading system on 7-day real data
    """
    # Initialize system with proven parameters
    config = {
        'leverage': 50,
        'take_profit_pct': 0.3,
        'stop_loss_pct': 0.5,
        'exhaustion_threshold': 0.6,
        'min_red_retracement_pct': 50,
        'min_volume_drop_pct': 20
    }

    system = LiveTradingSystem(config)

    # Simulate on real 7-day data
    simulate_live_trading('SOL_USDT_1min_7days.csv', system)


if __name__ == "__main__":
    main()
