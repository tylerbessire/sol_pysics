"""
REFINED STRATEGY: Adapted for Daily Timeframes

The confirmation-based entry system, now optimized for daily candles.

Key differences from 1-minute strategy:
1. Wider take profit/stop loss targets (1-3% instead of 0.2-0.5%)
2. Multi-day confirmation windows
3. Lower optimal leverage (20-50x instead of 50-100x)
4. Adjusted momentum exhaustion thresholds
"""

import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt


class DailyMomentumExhaustionDetector:
    """
    Detect momentum exhaustion on daily timeframes
    """

    def __init__(self, window=20):
        self.window = window

    def calculate_momentum_exhaustion(self, df):
        """
        Calculate momentum exhaustion for daily data
        """
        # 1. Daily velocity (price change)
        df['velocity'] = df['Close'].diff()

        # 2. Acceleration
        df['acceleration'] = df['velocity'].diff()

        # 3. Volume-weighted momentum
        df['momentum'] = df['velocity'] * df['Volume']

        # 4. Momentum decay from recent peak
        df['momentum_peak'] = df['momentum'].rolling(self.window).max()
        df['momentum_ratio'] = df['momentum'] / (df['momentum_peak'] + 1e-10)

        # 5. Exhaustion signals (adjusted for daily)
        df['negative_acceleration'] = (df['acceleration'] < 0).astype(float)
        df['momentum_decaying'] = (df['momentum_ratio'] < 0.7).astype(float)  # More conservative for daily
        df['volume_declining'] = (df['Volume'] < df['Volume'].rolling(10).mean()).astype(float)

        # 6. Combined exhaustion score
        df['exhaustion_score'] = (
            df['negative_acceleration'] * 0.35 +
            df['momentum_decaying'] * 0.35 +
            df['volume_declining'] * 0.30
        )

        return df

    def detect_green_candle_exhaustion(self, df):
        """
        Detect when daily green candles are losing strength
        """
        # Green candle metrics
        df['is_green'] = (df['Close'] > df['Open']).astype(float)
        df['candle_body'] = abs(df['Close'] - df['Open'])
        df['candle_body_pct'] = (df['candle_body'] / df['Open']) * 100

        # Compare current green to previous greens
        df['prev_green_body'] = df['candle_body'].shift(1)
        df['green_weakening'] = (
            (df['is_green'] == 1) &
            (df['candle_body'] < df['prev_green_body'] * 0.6)  # More strict for daily
        )

        # Exhaustion detected
        df['exhaustion_detected'] = (
            (df['exhaustion_score'] > 0.6) &
            ((df['green_weakening']) | (df['is_green'].shift(1) == 1))
        )

        return df


class DailyConfirmationEntrySystem:
    """
    Daily timeframe confirmation system
    """

    def __init__(self, min_red_retracement_pct=40, min_volume_drop_pct=15):
        self.min_red_retracement_pct = min_red_retracement_pct
        self.min_volume_drop_pct = min_volume_drop_pct

    def detect_confirmation_candles(self, df):
        """
        Detect daily red candles that confirm reversal
        """
        # Candle characteristics
        df['is_red'] = (df['Close'] < df['Open']).astype(float)
        df['red_body'] = np.where(df['is_red'], df['Open'] - df['Close'], 0)
        df['red_body_pct'] = (df['red_body'] / df['Open']) * 100

        # Previous green candles
        df['prev_candle_body'] = abs(df['Close'].shift(1) - df['Open'].shift(1))
        df['prev_2_candle_body'] = abs(df['Close'].shift(2) - df['Open'].shift(2))
        df['prev_3_candle_body'] = abs(df['Close'].shift(3) - df['Open'].shift(3))
        df['recent_green_avg'] = (df['prev_candle_body'] + df['prev_2_candle_body'] + df['prev_3_candle_body']) / 3

        # Retracement calculation
        df['retracement_ratio'] = df['red_body'] / (df['recent_green_avg'] + 1e-10)

        # Volume confirmation
        df['volume_ma'] = df['Volume'].rolling(10).mean()
        df['volume_drop_pct'] = ((df['volume_ma'] - df['Volume']) / df['volume_ma']) * 100

        # CONFIRMATION SIGNAL (adjusted for daily)
        df['confirmation_signal'] = (
            (df['is_red'] == 1) &
            (df['retracement_ratio'] >= self.min_red_retracement_pct / 100) &
            (df['volume_drop_pct'] >= self.min_volume_drop_pct) &
            (df['exhaustion_score'] > 0.5)  # Slightly lower threshold for daily
        )

        return df

    def calculate_entry_levels(self, df, confirmation_idx, leverage=50,
                               take_profit_pct=2.0, stop_loss_pct=3.0):
        """
        Calculate entry levels for daily timeframe
        """
        confirmation_row = df.loc[confirmation_idx]

        entry_price = confirmation_row['Close']

        # Take profit: Wider targets for daily
        take_profit = entry_price * (1 - take_profit_pct / 100)

        # Stop loss: Above recent high
        recent_high = df.loc[:confirmation_idx]['High'].tail(20).max()
        stop_loss_recent = recent_high * 1.005  # 0.5% above recent high
        stop_loss_percent = entry_price * (1 + stop_loss_pct / 100)

        stop_loss = min(stop_loss_recent, stop_loss_percent)

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


class DailyBacktester:
    """
    Backtest on daily timeframes
    """

    def __init__(self, initial_capital=1000, leverage=50,
                 take_profit_pct=2.0, stop_loss_pct=3.0):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.capital = initial_capital
        self.trades = []

    def run_backtest(self, df, signals):
        """
        Run backtest on daily data
        """
        self.capital = self.initial_capital
        self.trades = []

        confirmation_times = signals[signals['confirmation_signal']].index

        print(f"\nFound {len(confirmation_times)} confirmation signals")

        entry_system = DailyConfirmationEntrySystem()

        for conf_time in confirmation_times:
            if self.capital <= 10:  # Stop if capital too low
                break

            levels = entry_system.calculate_entry_levels(
                signals, conf_time,
                leverage=self.leverage,
                take_profit_pct=self.take_profit_pct,
                stop_loss_pct=self.stop_loss_pct
            )

            # Skip if risk/reward is poor
            if levels['risk_reward_ratio'] < 0.5:
                continue

            trade_result = self.execute_trade(df, conf_time, levels)

            if trade_result:
                self.trades.append(trade_result)

                # Update capital
                if trade_result['result'] == 'win':
                    profit = self.capital * (self.take_profit_pct / 100) * self.leverage
                    self.capital += profit * 0.92  # After fees
                elif trade_result['result'] == 'loss':
                    loss = self.capital * (levels['sl_distance_pct'] / 100) * self.leverage
                    self.capital -= loss

                # Log equity progression
                trade_result['capital_after'] = self.capital

        return self.calculate_statistics()

    def execute_trade(self, df, entry_time, levels):
        """
        Simulate daily trade execution
        """
        entry_price = levels['entry_price']
        take_profit = levels['take_profit']
        stop_loss = levels['stop_loss']

        entry_loc = df.index.get_loc(entry_time)

        if entry_loc >= len(df) - 5:
            return None

        # Look at next 30 days
        future = df.iloc[entry_loc + 1:entry_loc + 31]

        if len(future) == 0:
            return None

        # Check for TP or SL hit
        hit_tp = (future['Low'] <= take_profit).any()
        hit_sl = (future['High'] >= stop_loss).any()

        if hit_tp and hit_sl:
            # Both hit - which came first?
            tp_idx = future[future['Low'] <= take_profit].index[0]
            sl_idx = future[future['High'] >= stop_loss].index[0]

            if tp_idx < sl_idx:
                hit_sl = False
            else:
                hit_tp = False

        if hit_tp:
            tp_time = future[future['Low'] <= take_profit].index[0]
            result = 'win'
            exit_price = take_profit
            exit_time = tp_time
        elif hit_sl:
            sl_time = future[future['High'] >= stop_loss].index[0]
            result = 'loss'
            exit_price = stop_loss
            exit_time = sl_time
        else:
            result = 'timeout'
            exit_price = future['Close'].iloc[-1]
            exit_time = future.index[-1]

        # Calculate P&L
        price_move_pct = ((entry_price - exit_price) / entry_price) * 100
        pnl_pct = price_move_pct * self.leverage
        pnl_usd = (self.capital * pnl_pct / 100) * 0.92

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
            'duration_days': (exit_time - entry_time).days
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

        # Calculate max drawdown
        equity_curve = [self.initial_capital]
        for trade in self.trades:
            equity_curve.append(trade['capital_after'])

        running_max = pd.Series(equity_curve).expanding().max()
        drawdown = (pd.Series(equity_curve) - running_max) / running_max * 100
        max_drawdown = drawdown.min()

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
            'max_drawdown_pct': max_drawdown,
            'trades': self.trades
        }


def test_on_daily_data(filepath, leverage_levels=[30, 50, 75],
                       take_profit_pct=2.0, stop_loss_pct=3.0):
    """
    Test refined strategy on daily data
    """
    print("\n" + "="*80)
    print("REFINED STRATEGY: Testing on Daily Timeframes")
    print("="*80)

    # Load data
    df = pd.read_csv(filepath)

    # Standardize column names
    df = df.rename(columns={
        'time': 'timestamp',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume'
    })

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    # Need proper case for the detector
    df['Open'] = df['open']
    df['High'] = df['high']
    df['Low'] = df['low']
    df['Close'] = df['close']
    df['Volume'] = df['volume']

    print(f"\nLoaded {len(df)} daily candles")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    print(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

    # Calculate momentum exhaustion
    print("\n" + "="*80)
    print("STEP 1: Detecting Momentum Exhaustion")
    print("="*80)

    detector = DailyMomentumExhaustionDetector(window=20)
    df = detector.calculate_momentum_exhaustion(df)
    df = detector.detect_green_candle_exhaustion(df)

    exhaustion_count = df['exhaustion_detected'].sum()
    print(f"Exhaustion signals detected: {exhaustion_count}")

    # Wait for confirmation
    print("\n" + "="*80)
    print("STEP 2: Waiting for Confirmation Candles")
    print("="*80)

    entry_system = DailyConfirmationEntrySystem(min_red_retracement_pct=40, min_volume_drop_pct=15)
    df = entry_system.detect_confirmation_candles(df)

    confirmation_count = df['confirmation_signal'].sum()
    print(f"Confirmation signals detected: {confirmation_count}")

    # Backtest with different leverage levels
    print("\n" + "="*80)
    print("STEP 3: Backtesting Across Multiple Leverage Levels")
    print("="*80)

    results = {}

    for leverage in leverage_levels:
        print(f"\n--- {leverage}x Leverage ---")

        backtester = DailyBacktester(
            initial_capital=1000,
            leverage=leverage,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct
        )

        result = backtester.run_backtest(df, df)
        results[leverage] = result

        print(f"Total Trades: {result['total_trades']}")
        print(f"Winning Trades: {result['winning_trades']}")
        print(f"Losing Trades: {result['losing_trades']}")
        print(f"Win Rate: {result['win_rate'] * 100:.1f}%")

        if result['total_trades'] > 0:
            print(f"Average Win: ${result['avg_win']:.2f}")
            print(f"Average Loss: ${result['avg_loss']:.2f}")
            print(f"Profit Factor: {result['profit_factor']:.2f}")
            print(f"Total Return: {result['total_return_pct']:.2f}%")
            print(f"Final Capital: ${result['final_capital']:.2f}")
            print(f"Max Drawdown: {result['max_drawdown_pct']:.2f}%")

    return results, df


def analyze_market_regimes(df, results):
    """
    Analyze performance across different market conditions
    """
    print("\n" + "="*80)
    print("MARKET REGIME ANALYSIS")
    print("="*80)

    # Identify bull vs bear markets
    df['sma_200'] = df['close'].rolling(200).mean()
    df['regime'] = np.where(df['close'] > df['sma_200'], 'bull', 'bear')

    # Analyze by regime
    for regime in ['bull', 'bear']:
        regime_days = (df['regime'] == regime).sum()
        regime_pct = regime_days / len(df) * 100
        print(f"\n{regime.upper()} Market: {regime_days} days ({regime_pct:.1f}%)")

    # Volatility analysis
    df['returns'] = df['close'].pct_change()
    df['volatility_20d'] = df['returns'].rolling(20).std() * np.sqrt(365) * 100

    print(f"\nVolatility Statistics:")
    print(f"  Average: {df['volatility_20d'].mean():.2f}%")
    print(f"  Max: {df['volatility_20d'].max():.2f}%")
    print(f"  Min: {df['volatility_20d'].min():.2f}%")

    return df


def main():
    """
    Main function - test on 4-year daily data
    """
    filepath = 'Solana_daily_data_2018_2024.csv'

    # Test with different parameter sets
    print("\n" + "="*80)
    print("TEST 1: Standard Parameters (2% TP, 3% SL)")
    print("="*80)

    results1, df = test_on_daily_data(
        filepath,
        leverage_levels=[30, 50, 75],
        take_profit_pct=2.0,
        stop_loss_pct=3.0
    )

    # Test with wider targets
    print("\n\n" + "="*80)
    print("TEST 2: Wider Targets (3% TP, 4% SL)")
    print("="*80)

    results2, _ = test_on_daily_data(
        filepath,
        leverage_levels=[30, 50, 75],
        take_profit_pct=3.0,
        stop_loss_pct=4.0
    )

    # Analyze market regimes
    df_analyzed = analyze_market_regimes(df, results1)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY: 4-Year Daily Backtest Results")
    print("="*80)

    print("\nStandard Parameters (2% TP, 3% SL):")
    for leverage, result in results1.items():
        if result['total_trades'] > 0:
            print(f"  {leverage}x: {result['win_rate']*100:.1f}% WR, PF {result['profit_factor']:.2f}, "
                  f"{result['total_return_pct']:.1f}% return")

    print("\nWider Targets (3% TP, 4% SL):")
    for leverage, result in results2.items():
        if result['total_trades'] > 0:
            print(f"  {leverage}x: {result['win_rate']*100:.1f}% WR, PF {result['profit_factor']:.2f}, "
                  f"{result['total_return_pct']:.1f}% return")


if __name__ == "__main__":
    main()
