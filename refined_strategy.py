"""
REFINED STRATEGY: Momentum Exhaustion + Confirmation Entry

Key Insight: DON'T predict the exact peak. Instead:
1. Physics detects momentum exhaustion (green candles losing steam)
2. Wait for red candle confirmation (>50% of previous green + volume drop)
3. Enter on confirmed downward momentum
4. Ride the mean reversion down

This gives us the precision we need for high leverage without trying
to predict the unpredictable exact top.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt


class MomentumExhaustionDetector:
    """
    Detect when upward momentum is exhausting using physics
    """

    def __init__(self, window=10):
        self.window = window

    def calculate_momentum_exhaustion(self, df):
        """
        Calculate momentum exhaustion score (0-1)

        High score = momentum is exhausting (setup for reversal)
        """
        # 1. Velocity (price change rate)
        df['velocity'] = df['close'].diff()

        # 2. Acceleration (velocity change rate)
        df['acceleration'] = df['velocity'].diff()

        # 3. Volume-weighted momentum
        df['momentum'] = df['velocity'] * df['volume']

        # 4. Momentum decay from recent peak
        df['momentum_peak'] = df['momentum'].rolling(self.window).max()
        df['momentum_ratio'] = df['momentum'] / (df['momentum_peak'] + 1e-10)

        # 5. Exhaustion signals
        df['negative_acceleration'] = (df['acceleration'] < 0).astype(float)
        df['momentum_decaying'] = (df['momentum_ratio'] < 0.8).astype(float)
        df['volume_declining'] = (df['volume'] < df['volume'].rolling(5).mean()).astype(float)

        # 6. Combined exhaustion score (0-1)
        df['exhaustion_score'] = (
            df['negative_acceleration'] * 0.35 +
            df['momentum_decaying'] * 0.35 +
            df['volume_declining'] * 0.30
        )

        return df

    def detect_green_candle_exhaustion(self, df):
        """
        Detect when green candles are losing strength

        Returns timestamps where exhaustion is detected
        """
        # Green candle metrics
        df['is_green'] = (df['close'] > df['open']).astype(float)
        df['candle_body'] = abs(df['close'] - df['open'])
        df['candle_body_pct'] = (df['candle_body'] / df['open']) * 100

        # Compare current green to previous green
        df['prev_green_body'] = df['candle_body'].shift(1)
        df['green_weakening'] = (
            (df['is_green'] == 1) &
            (df['candle_body'] < df['prev_green_body'] * 0.7)  # Current green < 70% of previous
        )

        # Exhaustion detected when:
        # - Physics shows exhaustion (high score)
        # - Green candles getting weaker
        # - Still in uptrend (currently green or just turned red)
        df['exhaustion_detected'] = (
            (df['exhaustion_score'] > 0.6) &
            ((df['green_weakening']) | (df['is_green'].shift(1) == 1))
        )

        return df


class ConfirmationEntrySystem:
    """
    Wait for confirmation before entering trade
    """

    def __init__(self, min_red_retracement_pct=50, min_volume_drop_pct=20):
        """
        Args:
            min_red_retracement_pct: Red candle must retrace at least X% of previous greens
            min_volume_drop_pct: Volume must drop by at least X%
        """
        self.min_red_retracement_pct = min_red_retracement_pct
        self.min_volume_drop_pct = min_volume_drop_pct

    def detect_confirmation_candles(self, df):
        """
        Detect red candles that confirm reversal

        Confirmation criteria:
        1. Red candle (close < open)
        2. Red body is >50% of previous green body
        3. Volume is dropping from recent average
        4. Physics shows momentum exhaustion
        """
        # Candle characteristics
        df['is_red'] = (df['close'] < df['open']).astype(float)
        df['red_body'] = np.where(df['is_red'], df['open'] - df['close'], 0)
        df['red_body_pct'] = (df['red_body'] / df['open']) * 100

        # Previous green candle(s) body
        df['prev_candle_body'] = abs(df['close'].shift(1) - df['open'].shift(1))
        df['prev_2_candle_body'] = abs(df['close'].shift(2) - df['open'].shift(2))
        df['recent_green_avg'] = (df['prev_candle_body'] + df['prev_2_candle_body']) / 2

        # Retracement calculation
        df['retracement_ratio'] = df['red_body'] / (df['recent_green_avg'] + 1e-10)

        # Volume confirmation
        df['volume_ma'] = df['volume'].rolling(5).mean()
        df['volume_drop_pct'] = ((df['volume_ma'] - df['volume']) / df['volume_ma']) * 100

        # CONFIRMATION SIGNAL
        df['confirmation_signal'] = (
            (df['is_red'] == 1) &  # Red candle
            (df['retracement_ratio'] >= self.min_red_retracement_pct / 100) &  # Retraces >50% of recent greens
            (df['volume_drop_pct'] >= self.min_volume_drop_pct) &  # Volume dropping
            (df['exhaustion_score'] > 0.6)  # Physics confirms exhaustion
        )

        return df

    def calculate_entry_levels(self, df, confirmation_idx, leverage=100,
                               take_profit_pct=0.3, stop_loss_pct=0.5):
        """
        Calculate entry, TP, and SL for confirmed signal

        Entry: Close of confirmation candle (or next candle open)
        TP: Percentage move down
        SL: Above recent high
        """
        confirmation_row = df.loc[confirmation_idx]

        entry_price = confirmation_row['close']

        # Take profit: X% down from entry
        take_profit = entry_price * (1 - take_profit_pct / 100)

        # Stop loss: Above recent high (or % above entry)
        recent_high = df.loc[:confirmation_idx]['high'].tail(10).max()
        stop_loss_recent = recent_high * 1.001  # 0.1% above recent high
        stop_loss_percent = entry_price * (1 + stop_loss_pct / 100)

        # Use whichever is tighter
        stop_loss = min(stop_loss_recent, stop_loss_percent)

        # Calculate liquidation distance for reference
        liquidation_distance_pct = ((stop_loss - entry_price) / entry_price) * 100

        return {
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'tp_distance_pct': take_profit_pct,
            'sl_distance_pct': ((stop_loss - entry_price) / entry_price) * 100,
            'liquidation_distance_pct': liquidation_distance_pct,
            'risk_reward_ratio': take_profit_pct / liquidation_distance_pct if liquidation_distance_pct > 0 else 0,
            'leverage': leverage,
            'confirmation_time': confirmation_idx
        }


class RefinedBacktester:
    """
    Backtest the refined strategy
    """

    def __init__(self, initial_capital=1000, leverage=100,
                 take_profit_pct=0.3, stop_loss_pct=0.5):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.capital = initial_capital
        self.trades = []

    def run_backtest(self, df, signals):
        """
        Run backtest with confirmation-based entries
        """
        self.capital = self.initial_capital
        self.trades = []

        # Get confirmation signals
        confirmation_times = signals[signals['confirmation_signal']].index

        print(f"\nFound {len(confirmation_times)} confirmation signals")

        entry_system = ConfirmationEntrySystem()

        for conf_time in confirmation_times:
            # Calculate entry levels
            levels = entry_system.calculate_entry_levels(
                signals, conf_time,
                leverage=self.leverage,
                take_profit_pct=self.take_profit_pct,
                stop_loss_pct=self.stop_loss_pct
            )

            # Skip if risk/reward is poor
            if levels['risk_reward_ratio'] < 0.5:
                continue

            # Simulate trade execution
            trade_result = self.execute_trade(df, conf_time, levels)

            if trade_result:
                self.trades.append(trade_result)

                # Update capital
                if trade_result['result'] == 'win':
                    profit = self.capital * (self.take_profit_pct / 100) * self.leverage
                    self.capital += profit * 0.92  # After fees (0.08% round trip)
                elif trade_result['result'] == 'loss':
                    loss = self.capital * (levels['sl_distance_pct'] / 100) * self.leverage
                    self.capital -= loss

        # Calculate statistics
        return self.calculate_statistics()

    def execute_trade(self, df, entry_time, levels):
        """
        Simulate trade execution and outcome
        """
        entry_price = levels['entry_price']
        take_profit = levels['take_profit']
        stop_loss = levels['stop_loss']

        # Get future prices after entry
        entry_loc = df.index.get_loc(entry_time)

        if entry_loc >= len(df) - 5:
            return None  # Not enough future data

        future = df.iloc[entry_loc + 1:entry_loc + 50]  # Next 50 candles

        if len(future) == 0:
            return None

        # Check for TP or SL hit
        hit_tp = (future['low'] <= take_profit).any()
        hit_sl = (future['high'] >= stop_loss).any()

        if hit_tp:
            # Find when TP was hit
            tp_time = future[future['low'] <= take_profit].index[0]
            result = 'win'
            exit_price = take_profit
            exit_time = tp_time
        elif hit_sl:
            # Find when SL was hit
            sl_time = future[future['high'] >= stop_loss].index[0]
            result = 'loss'
            exit_price = stop_loss
            exit_time = sl_time
        else:
            # Neither hit in time window
            result = 'timeout'
            exit_price = future['close'].iloc[-1]
            exit_time = future.index[-1]

        # Calculate P&L
        price_move_pct = ((entry_price - exit_price) / entry_price) * 100
        pnl_pct = price_move_pct * self.leverage
        pnl_usd = (self.capital * pnl_pct / 100) * 0.92  # After fees

        return {
            'entry_time': entry_time,
            'entry_price': entry_price,
            'exit_time': exit_time,
            'exit_price': exit_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'result': result,
            'pnl_pct': pnl_pct,
            'pnl_usd': pnl_usd,
            'duration_minutes': (exit_time - entry_time).total_seconds() / 60
        }

    def calculate_statistics(self):
        """
        Calculate backtest statistics
        """
        if len(self.trades) == 0:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_return': 0,
                'final_capital': self.initial_capital
            }

        wins = [t for t in self.trades if t['result'] == 'win']
        losses = [t for t in self.trades if t['result'] == 'loss']

        win_rate = len(wins) / len(self.trades) if self.trades else 0

        avg_win = np.mean([t['pnl_usd'] for t in wins]) if wins else 0
        avg_loss = np.mean([abs(t['pnl_usd']) for t in losses]) if losses else 0

        profit_factor = (len(wins) * avg_win) / (len(losses) * avg_loss) if losses else float('inf')

        total_return_pct = ((self.capital - self.initial_capital) / self.initial_capital) * 100

        return {
            'total_trades': len(self.trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'total_return_pct': total_return_pct,
            'final_capital': self.capital,
            'trades': self.trades
        }


def main():
    """
    Test refined strategy on 1-minute data
    """
    print("\n" + "="*80)
    print("REFINED STRATEGY: Momentum Exhaustion + Confirmation Entry")
    print("="*80)

    # Load data
    df = pd.read_csv('SOL_USDT_1min_24h_realistic.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    print(f"\nLoaded {len(df)} candles")
    print(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

    # Step 1: Detect momentum exhaustion
    print("\n" + "="*80)
    print("STEP 1: Detecting Momentum Exhaustion")
    print("="*80)

    detector = MomentumExhaustionDetector(window=10)
    df = detector.calculate_momentum_exhaustion(df)
    df = detector.detect_green_candle_exhaustion(df)

    exhaustion_count = df['exhaustion_detected'].sum()
    print(f"Exhaustion signals detected: {exhaustion_count}")

    # Step 2: Wait for confirmation
    print("\n" + "="*80)
    print("STEP 2: Waiting for Confirmation Candles")
    print("="*80)

    entry_system = ConfirmationEntrySystem(min_red_retracement_pct=50, min_volume_drop_pct=20)
    df = entry_system.detect_confirmation_candles(df)

    confirmation_count = df['confirmation_signal'].sum()
    print(f"Confirmation signals detected: {confirmation_count}")

    # Step 3: Backtest
    print("\n" + "="*80)
    print("STEP 3: Backtesting with Different Leverage Levels")
    print("="*80)

    for leverage in [50, 100, 200]:
        print(f"\n--- {leverage}x Leverage ---")

        backtester = RefinedBacktester(
            initial_capital=1000,
            leverage=leverage,
            take_profit_pct=0.3,
            stop_loss_pct=0.5
        )

        results = backtester.run_backtest(df, df)

        print(f"Total Trades: {results['total_trades']}")
        print(f"Winning Trades: {results['winning_trades']}")
        print(f"Losing Trades: {results['losing_trades']}")
        print(f"Win Rate: {results['win_rate'] * 100:.1f}%")

        if results['total_trades'] > 0:
            print(f"Average Win: ${results['avg_win']:.2f}")
            print(f"Average Loss: ${results['avg_loss']:.2f}")
            print(f"Profit Factor: {results['profit_factor']:.2f}")
            print(f"Total Return: {results['total_return_pct']:.2f}%")
            print(f"Final Capital: ${results['final_capital']:.2f}")

    print("\n" + "="*80)
    print("STRATEGY SUMMARY")
    print("="*80)
    print("\nKey Improvements:")
    print("✓ Physics detects momentum exhaustion (not predicting exact peak)")
    print("✓ Waits for confirmation (red candle >50% of recent greens)")
    print("✓ Volume must drop (buying exhaustion confirmed)")
    print("✓ Enters on confirmed downward momentum")
    print("✓ Risk/reward calculated before entry")

    print("\nThis approach should dramatically reduce liquidations")
    print("by not trying to catch the exact top!")


if __name__ == "__main__":
    main()
