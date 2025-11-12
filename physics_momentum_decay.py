"""
PHYSICS-BASED MOMENTUM DECAY STRATEGY

Based on rocket/ball physics:
- Rocket launches with momentum = mass × velocity (volume × price_velocity)
- As it climbs, fuel burns out → momentum decays
- Velocity slows, volume drops
- Eventually can't sustain altitude → reverses and falls

For $1-2 climbs:
1. Track climb momentum in real-time
2. Detect momentum decay (slowing velocity + dropping volume)
3. When momentum drops below threshold → peak is near
4. Wait for first strong red confirmation (gravity takes over)
5. Enter SHORT to ride it back down to original price

Pure physics - no arbitrary wicks, just momentum equations.
"""

import pandas as pd
import numpy as np
from collections import deque


class PhysicsMomentumDetector:
    """
    Detect climbs using momentum = mass × velocity
    Signal when momentum decays indicating peak
    """

    def __init__(self,
                 min_climb_usd=1.0,
                 momentum_lookback=5,
                 momentum_decay_threshold=0.6):

        self.min_climb_usd = min_climb_usd
        self.momentum_lookback = momentum_lookback  # Candles to average
        self.momentum_decay_threshold = momentum_decay_threshold  # Momentum must drop to 60% of peak

        self.candle_buffer = deque(maxlen=100)
        self.tracking_climb = False
        self.climb_start_price = None
        self.climb_start_time = None
        self.climb_high = None
        self.climb_high_time = None
        self.peak_momentum = None
        self.momentum_decaying = False

    def add_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Process candle and detect momentum decay
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

        if len(self.candle_buffer) < self.momentum_lookback + 2:
            return None

        df = pd.DataFrame(list(self.candle_buffer))

        # Calculate physics variables
        df['velocity'] = df['close'].diff()  # Price change (velocity)
        df['velocity_pct'] = df['close'].pct_change() * 100
        df['abs_velocity'] = df['velocity'].abs()

        # Momentum = mass × velocity (volume × price_velocity)
        df['momentum'] = df['volume'] * df['abs_velocity']

        # Rolling momentum average
        df['momentum_ma'] = df['momentum'].rolling(self.momentum_lookback).mean()

        current = df.iloc[-1]
        current_price = current['close']
        current_momentum = current['momentum_ma']

        # Get recent stats
        recent_high = df['high'].max()
        recent_low = df['low'].min()

        # STATE 1: Not tracking - look for climb start
        if not self.tracking_climb:
            climb_usd = recent_high - recent_low

            if climb_usd >= self.min_climb_usd * 0.5:  # Starting to climb
                self.tracking_climb = True
                self.climb_start_price = recent_low
                self.climb_start_time = df[df['low'] == recent_low].iloc[0]['timestamp']
                self.climb_high = recent_high
                self.climb_high_time = timestamp
                self.peak_momentum = current_momentum
                self.momentum_decaying = False

                print(f"\n🚀 CLIMB STARTED at {self.climb_start_time}")
                print(f"   Launch price: ${self.climb_start_price:.2f}")
                print(f"   Initial momentum: {self.peak_momentum:.2f}")

        # STATE 2: Tracking climb - monitor momentum
        elif self.tracking_climb:
            # Update high
            if current_price > self.climb_high:
                self.climb_high = current_price
                self.climb_high_time = timestamp

            # Track peak momentum
            if current_momentum > self.peak_momentum:
                self.peak_momentum = current_momentum

            climb_usd = self.climb_high - self.climb_start_price
            climb_pct = (climb_usd / self.climb_start_price) * 100
            climb_duration = (timestamp - self.climb_start_time).total_seconds() / 60

            # Calculate momentum ratio (current vs peak)
            momentum_ratio = current_momentum / self.peak_momentum if self.peak_momentum > 0 else 0

            # PHYSICS CHECK: Is momentum decaying?
            if momentum_ratio <= self.momentum_decay_threshold:
                if not self.momentum_decaying:
                    self.momentum_decaying = True
                    print(f"   ⚠️ MOMENTUM DECAY detected at {timestamp}")
                    print(f"      Peak momentum: {self.peak_momentum:.2f}")
                    print(f"      Current momentum: {current_momentum:.2f}")
                    print(f"      Ratio: {momentum_ratio:.2%} (threshold: {self.momentum_decay_threshold:.0%})")
                    print(f"      Climb so far: ${self.climb_start_price:.2f} → ${self.climb_high:.2f} (+${climb_usd:.2f})")
                    print(f"      🔴 Waiting for gravity (red candle)...")

                # Check for RED CANDLE (gravity takes over)
                is_red = current_price < current['open']
                red_body = abs(current_price - current['open'])
                red_body_pct = (red_body / current['open']) * 100

                if is_red and red_body_pct >= 0.1:  # Strong enough red
                    # SIGNAL!
                    signal = {
                        'timestamp': timestamp,
                        'entry_price': current_price,
                        'climb_start_price': self.climb_start_price,
                        'climb_high': self.climb_high,
                        'climb_usd': climb_usd,
                        'climb_pct': climb_pct,
                        'climb_duration': climb_duration,
                        'peak_momentum': self.peak_momentum,
                        'entry_momentum': current_momentum,
                        'momentum_decay_ratio': momentum_ratio,
                        'red_body_pct': red_body_pct,
                        'current_volume': current['volume'],
                        'current_velocity': current['velocity_pct']
                    }

                    print(f"\n🎯 SHORT SIGNAL - MOMENTUM EXHAUSTION")
                    print(f"   Climb: ${self.climb_start_price:.2f} → ${self.climb_high:.2f} (+${climb_usd:.2f}, +{climb_pct:.2f}%)")
                    print(f"   Duration: {climb_duration:.1f} minutes")
                    print(f"   Peak momentum: {self.peak_momentum:.2f}")
                    print(f"   Current momentum: {current_momentum:.2f} ({momentum_ratio:.1%} of peak)")
                    print(f"   Red confirmation: {red_body_pct:.3f}% body")
                    print(f"   Entry: ${current_price:.2f}")
                    print(f"   Target: ~${self.climb_start_price:.2f} (gravity pulls it back)")

                    # Reset
                    self.tracking_climb = False
                    self.momentum_decaying = False

                    return signal

            # Reset if too long or goes way higher (momentum recovered)
            if climb_duration > 60:  # 1 hour timeout
                print(f"   ⏱️ Timeout - resetting")
                self.tracking_climb = False
            elif momentum_ratio > 1.2:  # Momentum recovered strongly
                print(f"   🚀 Momentum recovered - new peak!")
                self.momentum_decaying = False

        return None


class PhysicsMomentumStrategy:
    """
    Strategy using physics-based momentum decay
    """

    def __init__(self,
                 min_climb_usd=1.0,
                 momentum_decay_threshold=0.6,
                 leverage=50,
                 exit_tolerance_usd=0.20):

        self.detector = PhysicsMomentumDetector(
            min_climb_usd=min_climb_usd,
            momentum_decay_threshold=momentum_decay_threshold
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
        Generate trade with physics-based parameters

        PHYSICS PRINCIPLE: Initial gravity effect happens FAST (within 2 candles).
        We're scalping the immediate drop after momentum exhaustion:
        - TP: Quick 0.4% drop (achievable in 2 candles)
        - SL: Tight 0.5% above entry
        - Max hold: 2 candles (defined in backtest)
        """
        entry_price = signal['entry_price']

        # Take profit: Quick scalp - 0.4% drop
        # At $200, this is $0.80 - achievable in 1-2 candles
        tp_pct = 0.4
        take_profit = entry_price * (1 - tp_pct / 100)

        # Stop loss: 0.5% above entry
        sl_pct = 0.5
        stop_loss = entry_price * (1 + sl_pct / 100)

        return {
            'type': 'SHORT',
            'timestamp': signal['timestamp'],
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'leverage': self.leverage,
            'tp_distance_pct': tp_pct,
            'sl_distance_pct': sl_pct,
            'risk_reward': tp_pct / sl_pct,  # Should be 0.8 (good R:R)
            'climb_usd': signal['climb_usd'],
            'expected_drop_usd': entry_price - take_profit,
            'momentum_decay_ratio': signal['momentum_decay_ratio'],
            'peak_momentum': signal['peak_momentum']
        }


def backtest_physics_momentum(data_file, min_climb_usd=1.0, momentum_decay_threshold=0.6):
    """
    Backtest the physics momentum decay strategy
    """
    print("="*80)
    print("PHYSICS-BASED MOMENTUM DECAY STRATEGY")
    print("="*80)
    print("Rocket/Ball Physics:")
    print("- Launch: High momentum (volume × velocity)")
    print("- Ascent: Momentum peaks")
    print("- Decay: Fuel runs out, momentum drops")
    print("- Peak: Momentum < threshold → can't sustain")
    print("- Fall: Gravity (mean reversion) pulls it down")
    print("="*80)
    print(f"Min climb: ${min_climb_usd:.2f}")
    print(f"Momentum decay threshold: {momentum_decay_threshold:.0%} of peak")
    print("="*80)

    # Load data
    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"\nLoaded {len(df)} candles")
    days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
    print(f"Days: {days}")

    # Initialize strategy
    strategy = PhysicsMomentumStrategy(
        min_climb_usd=min_climb_usd,
        momentum_decay_threshold=momentum_decay_threshold,
        leverage=50,
        exit_tolerance_usd=0.20
    )

    # Track results
    trades = []
    capital = 1000
    initial_capital = 1000
    active_position = None
    candles_in_trade = 0

    print("\nProcessing candles...\n")

    for idx, row in df.iterrows():
        # Check for exit
        if active_position:
            candles_in_trade += 1

            # Check TP
            if row['low'] <= active_position['take_profit']:
                pnl_pct = active_position['tp_distance_pct'] * strategy.leverage
                pnl_usd = capital * (pnl_pct / 100) * 0.92
                capital += pnl_usd

                print(f"\n✅ TAKE PROFIT at {row['timestamp']} (after {candles_in_trade} candles)")
                print(f"   Gravity worked! Dropped ${active_position['expected_drop_usd']:.2f}")
                print(f"   P&L: +{pnl_pct:.1f}% (${pnl_usd:.2f})")
                print(f"   Capital: ${capital:.2f}")

                trades.append({'result': 'win', 'pnl_pct': pnl_pct, 'pnl_usd': pnl_usd})
                active_position = None
                candles_in_trade = 0

            # Check SL
            elif row['high'] >= active_position['stop_loss']:
                pnl_pct = -active_position['sl_distance_pct'] * strategy.leverage
                pnl_usd = capital * (pnl_pct / 100) * 0.92
                capital += pnl_usd

                print(f"\n❌ STOP LOSS at {row['timestamp']} (after {candles_in_trade} candles)")
                print(f"   Momentum recovered - escaped gravity")
                print(f"   P&L: {pnl_pct:.1f}% (${pnl_usd:.2f})")
                print(f"   Capital: ${capital:.2f}")

                trades.append({'result': 'loss', 'pnl_pct': pnl_pct, 'pnl_usd': pnl_usd})
                active_position = None
                candles_in_trade = 0

            # Check TIMEOUT - gravity should work within 2 candles!
            elif candles_in_trade >= 2:
                current_price = row['close']
                pnl_raw = (active_position['entry_price'] - current_price) / active_position['entry_price'] * 100
                pnl_pct = pnl_raw * strategy.leverage
                pnl_usd = capital * (pnl_pct / 100) * 0.92
                capital += pnl_usd

                result = 'win' if pnl_pct > 0 else 'loss'
                emoji = '✅' if pnl_pct > 0 else '❌'

                print(f"\n⏱️ TIMEOUT at {row['timestamp']} (after 2 candles)")
                print(f"   Gravity too slow - exiting")
                print(f"   Exit: ${current_price:.2f}")
                print(f"   P&L: {pnl_pct:+.1f}% (${pnl_usd:.2f})")
                print(f"   Capital: ${capital:.2f}")

                trades.append({'result': result, 'pnl_pct': pnl_pct, 'pnl_usd': pnl_usd})
                active_position = None
                candles_in_trade = 0

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
    Test physics momentum decay strategy
    """
    print("\n🚀 PHYSICS MOMENTUM DECAY - Like a Rocket Running Out of Fuel\n")

    # Test different momentum decay thresholds
    configs = [
        (1.0, 0.5),   # $1 climb, 50% momentum decay
        (1.0, 0.6),   # $1 climb, 60% momentum decay
        (1.5, 0.5),   # $1.50 climb, 50% momentum decay
        (1.5, 0.6),   # $1.50 climb, 60% momentum decay
    ]

    for climb_usd, decay_threshold in configs:
        print(f"\n{'='*80}")
        print(f"TEST: ${climb_usd:.2f} climb, {decay_threshold:.0%} momentum decay threshold")
        print(f"{'='*80}")

        strategy, trades, capital = backtest_physics_momentum(
            'SOL_USDT_1min_7days.csv',
            min_climb_usd=climb_usd,
            momentum_decay_threshold=decay_threshold
        )

        print("\n")


if __name__ == "__main__":
    main()
