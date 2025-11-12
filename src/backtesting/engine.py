"""
Backtesting Engine

Backtest physics-based trading strategies on historical data.
Tests terminal velocity signals with 500x leverage and tight take-profit targets.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.momentum import MomentumCalculator, MomentumSignals
from models.mean_reversion import MeanReversionDetector, MeanReversionStrategy
from models.terminal_velocity import TerminalVelocityDetector, TerminalVelocityStrategy


@dataclass
class Trade:
    """Single trade record"""
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    side: str = "short"  # 'long' or 'short'
    size: float = 1.0
    leverage: float = 500.0
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    signal_strength: float = 0.0
    status: str = "open"  # 'open', 'win', 'loss'


@dataclass
class BacktestResult:
    """Complete backtest results"""
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    trades: List[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)


class BacktestEngine:
    """
    Backtest trading strategies on historical data
    """

    def __init__(self,
                 initial_capital: float = 1000.0,
                 leverage: float = 500.0,
                 take_profit_pct: float = 0.2,
                 stop_loss_pct: float = 0.15,
                 commission_pct: float = 0.04):  # 0.04% per trade
        """
        Initialize backtesting engine

        Args:
            initial_capital: Starting capital
            leverage: Trading leverage
            take_profit_pct: Take profit percentage
            stop_loss_pct: Stop loss percentage
            commission_pct: Commission per trade
        """
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.commission_pct = commission_pct

        self.capital = initial_capital
        self.trades: List[Trade] = []
        self.equity_history: List[float] = [initial_capital]

    def calculate_position_size(self, capital: float, leverage: float) -> float:
        """
        Calculate position size based on capital and leverage

        Args:
            capital: Available capital
            leverage: Leverage multiplier

        Returns:
            Position size
        """
        return capital * leverage

    def execute_trade(self,
                     entry_time: pd.Timestamp,
                     entry_price: float,
                     signal_strength: float) -> Trade:
        """
        Execute a new trade

        Args:
            entry_time: Entry timestamp
            entry_price: Entry price
            signal_strength: Signal strength (0-1)

        Returns:
            Trade object
        """
        # Calculate take profit and stop loss levels
        take_profit = entry_price * (1 - self.take_profit_pct / 100)
        stop_loss = entry_price * (1 + self.stop_loss_pct / 100)

        trade = Trade(
            entry_time=entry_time,
            entry_price=entry_price,
            side="short",
            size=self.calculate_position_size(self.capital, self.leverage),
            leverage=self.leverage,
            take_profit=take_profit,
            stop_loss=stop_loss,
            signal_strength=signal_strength,
            status="open"
        )

        return trade

    def update_trade(self,
                    trade: Trade,
                    current_time: pd.Timestamp,
                    current_price: float) -> bool:
        """
        Update trade status based on current price

        Args:
            trade: Trade to update
            current_time: Current timestamp
            current_price: Current price

        Returns:
            True if trade closed, False if still open
        """
        if trade.status != "open":
            return True

        # Check take profit
        if current_price <= trade.take_profit:
            trade.exit_time = current_time
            trade.exit_price = trade.take_profit
            trade.status = "win"

            # Calculate PnL
            price_diff = trade.entry_price - trade.exit_price
            trade.pnl_pct = (price_diff / trade.entry_price) * 100 * self.leverage
            commission = self.capital * (self.commission_pct / 100) * 2  # Entry + exit
            trade.pnl = (self.capital * trade.pnl_pct / 100) - commission

            self.capital += trade.pnl
            return True

        # Check stop loss
        if current_price >= trade.stop_loss:
            trade.exit_time = current_time
            trade.exit_price = trade.stop_loss
            trade.status = "loss"

            # Calculate PnL
            price_diff = trade.entry_price - trade.exit_price
            trade.pnl_pct = (price_diff / trade.entry_price) * 100 * self.leverage
            commission = self.capital * (self.commission_pct / 100) * 2
            trade.pnl = (self.capital * trade.pnl_pct / 100) - commission

            self.capital += trade.pnl
            return True

        return False

    def run_backtest(self,
                    prices: pd.Series,
                    volumes: pd.Series,
                    signals: pd.DataFrame) -> BacktestResult:
        """
        Run complete backtest

        Args:
            prices: Price data
            volumes: Volume data
            signals: Trading signals with 'final_signal' and 'signal_strength' columns

        Returns:
            BacktestResult object
        """
        self.capital = self.initial_capital
        self.trades = []
        self.equity_history = [self.initial_capital]

        open_trades: List[Trade] = []

        # Iterate through each time period
        for timestamp, row in signals.iterrows():
            current_price = row['price']

            # Update existing trades
            for trade in open_trades[:]:
                if self.update_trade(trade, timestamp, current_price):
                    self.trades.append(trade)
                    open_trades.remove(trade)

            # Check for new signals
            if row.get('final_signal', False) or row.get('entry_signal', False):
                # Only enter if no existing open trade
                if len(open_trades) == 0:
                    signal_strength = row.get('signal_strength', 0.5)
                    trade = self.execute_trade(timestamp, current_price, signal_strength)
                    open_trades.append(trade)

            # Track equity
            self.equity_history.append(self.capital)

        # Close any remaining open trades at final price
        final_price = prices.iloc[-1]
        final_time = prices.index[-1]
        for trade in open_trades:
            self.update_trade(trade, final_time, final_price)
            self.trades.append(trade)

        # Calculate results
        result = self._calculate_results(prices)

        return result

    def _calculate_results(self, prices: pd.Series) -> BacktestResult:
        """
        Calculate backtest statistics

        Args:
            prices: Price data used in backtest

        Returns:
            BacktestResult object
        """
        if len(self.trades) == 0:
            return BacktestResult(
                start_date=prices.index[0],
                end_date=prices.index[-1],
                initial_capital=self.initial_capital,
                final_capital=self.capital,
                total_return_pct=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                trades=[],
                equity_curve=pd.Series(self.equity_history)
            )

        winning_trades = [t for t in self.trades if t.status == "win"]
        losing_trades = [t for t in self.trades if t.status == "loss"]

        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = abs(sum(t.pnl for t in losing_trades))

        avg_win = total_wins / len(winning_trades) if len(winning_trades) > 0 else 0
        avg_loss = total_losses / len(losing_trades) if len(losing_trades) > 0 else 0

        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        win_rate = len(winning_trades) / len(self.trades) if len(self.trades) > 0 else 0

        # Calculate max drawdown
        equity_curve = pd.Series(self.equity_history)
        running_max = equity_curve.expanding().max()
        drawdown = (equity_curve - running_max) / running_max
        max_drawdown = drawdown.min() * 100

        # Calculate Sharpe ratio (simplified)
        returns = equity_curve.pct_change().dropna()
        if len(returns) > 0 and returns.std() > 0:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)  # Annualized
        else:
            sharpe_ratio = 0.0

        return BacktestResult(
            start_date=prices.index[0],
            end_date=prices.index[-1],
            initial_capital=self.initial_capital,
            final_capital=self.capital,
            total_return_pct=((self.capital - self.initial_capital) / self.initial_capital) * 100,
            total_trades=len(self.trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            trades=self.trades,
            equity_curve=equity_curve
        )


def print_backtest_results(result: BacktestResult):
    """
    Print backtest results in readable format

    Args:
        result: BacktestResult object
    """
    print("\n" + "="*60)
    print("BACKTEST RESULTS")
    print("="*60)

    print(f"\nPeriod: {result.start_date} to {result.end_date}")
    print(f"Initial Capital: ${result.initial_capital:,.2f}")
    print(f"Final Capital: ${result.final_capital:,.2f}")
    print(f"Total Return: {result.total_return_pct:.2f}%")

    print(f"\nTrade Statistics:")
    print(f"  Total Trades: {result.total_trades}")
    print(f"  Winning Trades: {result.winning_trades}")
    print(f"  Losing Trades: {result.losing_trades}")
    print(f"  Win Rate: {result.win_rate * 100:.2f}%")

    print(f"\nProfit/Loss:")
    print(f"  Average Win: ${result.avg_win:.2f}")
    print(f"  Average Loss: ${result.avg_loss:.2f}")
    print(f"  Profit Factor: {result.profit_factor:.2f}")

    print(f"\nRisk Metrics:")
    print(f"  Max Drawdown: {result.max_drawdown:.2f}%")
    print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")

    print("\n" + "="*60)


# Example usage
if __name__ == "__main__":
    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=1000, freq='1min')

    # Simulate price with liquidation cascades
    price_pattern = 100 + np.cumsum(np.random.randn(1000) * 0.1)
    prices = pd.Series(price_pattern, index=dates)

    volume_pattern = np.random.randint(1000, 5000, 1000)
    volumes = pd.Series(volume_pattern, index=dates)

    # Calculate physics metrics
    calc = MomentumCalculator()
    velocities = calc.calculate_velocity(prices)
    accelerations = calc.calculate_acceleration(velocities)
    momentum = calc.calculate_momentum(prices, volumes)

    # Mean reversion
    mean_detector = MeanReversionDetector()
    mean_prices = prices.rolling(20).mean()

    # Terminal velocity strategy
    tv_detector = TerminalVelocityDetector()
    tv_strategy = TerminalVelocityStrategy(tv_detector)

    signals = tv_strategy.generate_entry_signals(
        prices, volumes, velocities, accelerations, momentum, mean_prices
    )

    # Run backtest
    engine = BacktestEngine(initial_capital=1000, leverage=500)
    result = engine.run_backtest(prices, volumes, signals)

    # Print results
    print_backtest_results(result)

    # Show sample trades
    if len(result.trades) > 0:
        print("\nSample Trades (first 5):")
        for i, trade in enumerate(result.trades[:5]):
            print(f"\nTrade {i+1}:")
            print(f"  Entry: {trade.entry_time} @ ${trade.entry_price:.2f}")
            print(f"  Exit: {trade.exit_time} @ ${trade.exit_price:.2f}")
            print(f"  Status: {trade.status}")
            print(f"  PnL: ${trade.pnl:.2f} ({trade.pnl_pct:.2f}%)")
