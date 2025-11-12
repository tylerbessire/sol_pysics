"""
PAPER TRADING SYSTEM

Virtual trading system for testing the refined strategy on testnet
or simulated environment before going live.

Features:
- Real-time signal detection
- Virtual position management
- Performance tracking
- Risk management
- Trade logging
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from live_signal_detector import LiveTradingSystem


class PaperTradingAccount:
    """
    Virtual trading account for paper trading
    """

    def __init__(self, initial_capital=10000, max_position_size_pct=10):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.max_position_size_pct = max_position_size_pct

        self.active_positions = []
        self.closed_trades = []
        self.equity_curve = [initial_capital]
        self.timestamps = [datetime.now()]

        self.stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0,
            'total_loss': 0,
            'max_drawdown': 0,
            'current_drawdown': 0,
            'peak_equity': initial_capital
        }

    def can_open_position(self, signal):
        """
        Check if account can open new position
        """
        # Check capital available
        if self.capital <= 0:
            return False, "Insufficient capital"

        # Check max position size
        position_value = self.capital * (signal['position_size_pct'] / 100)
        max_position_value = self.capital * (self.max_position_size_pct / 100)

        if position_value > max_position_value:
            return False, f"Position size {signal['position_size_pct']:.1f}% exceeds max {self.max_position_size_pct}%"

        # Check if already have active position (only 1 at a time for now)
        if len(self.active_positions) > 0:
            return False, "Already have active position"

        return True, "OK"

    def open_position(self, signal, timestamp):
        """
        Open new position
        """
        can_open, reason = self.can_open_position(signal)

        if not can_open:
            return None, reason

        # Calculate position size
        position_value = self.capital * (signal['position_size_pct'] / 100)
        position_size = position_value * signal['leverage']  # With leverage

        position = {
            'id': len(self.active_positions) + len(self.closed_trades) + 1,
            'type': signal['type'],
            'entry_time': timestamp,
            'entry_price': signal['entry_price'],
            'position_value': position_value,
            'position_size': position_size,
            'leverage': signal['leverage'],
            'take_profit': signal['take_profit'],
            'stop_loss': signal['stop_loss'],
            'tp_distance_pct': signal['tp_distance_pct'],
            'sl_distance_pct': signal['sl_distance_pct'],
            'risk_reward': signal['risk_reward']
        }

        self.active_positions.append(position)

        print(f"\n📈 POSITION OPENED #{position['id']}")
        print(f"   Type: {position['type']}")
        print(f"   Entry: ${position['entry_price']:.2f}")
        print(f"   Size: ${position_size:.2f} ({signal['leverage']}x leverage)")
        print(f"   Capital at risk: ${position_value:.2f}")
        print(f"   TP: ${position['take_profit']:.2f} | SL: ${position['stop_loss']:.2f}")

        return position, "Position opened"

    def check_positions(self, current_price, timestamp):
        """
        Check all active positions for TP/SL
        """
        positions_to_close = []

        for position in self.active_positions:
            # SHORT position
            if position['type'] == 'SHORT':
                # Check TP (price goes down)
                if current_price <= position['take_profit']:
                    positions_to_close.append((position, 'TP', current_price))
                # Check SL (price goes up)
                elif current_price >= position['stop_loss']:
                    positions_to_close.append((position, 'SL', current_price))

            # LONG position
            elif position['type'] == 'LONG':
                # Check TP (price goes up)
                if current_price >= position['take_profit']:
                    positions_to_close.append((position, 'TP', current_price))
                # Check SL (price goes down)
                elif current_price <= position['stop_loss']:
                    positions_to_close.append((position, 'SL', current_price))

        # Close positions
        for position, reason, exit_price in positions_to_close:
            self.close_position(position, exit_price, reason, timestamp)

    def close_position(self, position, exit_price, reason, timestamp):
        """
        Close position and update account
        """
        # Calculate P&L
        if position['type'] == 'SHORT':
            price_move_pct = ((position['entry_price'] - exit_price) / position['entry_price']) * 100
        else:  # LONG
            price_move_pct = ((exit_price - position['entry_price']) / position['entry_price']) * 100

        # Apply leverage
        pnl_pct = price_move_pct * position['leverage']

        # Calculate P&L in USD
        pnl_usd = position['position_value'] * (pnl_pct / 100)

        # Apply fees (0.08% round trip)
        fees = position['position_value'] * 0.0008
        pnl_usd -= fees

        # Update capital
        self.capital += pnl_usd

        # Record trade
        trade = {
            'id': position['id'],
            'type': position['type'],
            'entry_time': position['entry_time'],
            'entry_price': position['entry_price'],
            'exit_time': timestamp,
            'exit_price': exit_price,
            'exit_reason': reason,
            'duration': (timestamp - position['entry_time']).total_seconds() / 60,  # minutes
            'pnl_pct': pnl_pct,
            'pnl_usd': pnl_usd,
            'fees': fees,
            'capital_after': self.capital,
            'result': 'win' if pnl_usd > 0 else 'loss'
        }

        self.closed_trades.append(trade)
        self.active_positions.remove(position)

        # Update stats
        self.stats['total_trades'] += 1
        if trade['result'] == 'win':
            self.stats['winning_trades'] += 1
            self.stats['total_profit'] += pnl_usd
        else:
            self.stats['losing_trades'] += 1
            self.stats['total_loss'] += abs(pnl_usd)

        # Update equity curve
        self.equity_curve.append(self.capital)
        self.timestamps.append(timestamp)

        # Update drawdown
        if self.capital > self.stats['peak_equity']:
            self.stats['peak_equity'] = self.capital
            self.stats['current_drawdown'] = 0
        else:
            self.stats['current_drawdown'] = ((self.stats['peak_equity'] - self.capital) / self.stats['peak_equity']) * 100
            if self.stats['current_drawdown'] > self.stats['max_drawdown']:
                self.stats['max_drawdown'] = self.stats['current_drawdown']

        # Print update
        result_emoji = "✅" if trade['result'] == 'win' else "❌"
        print(f"\n{result_emoji} POSITION CLOSED #{trade['id']} ({reason})")
        print(f"   Entry: ${trade['entry_price']:.2f} → Exit: ${exit_price:.2f}")
        print(f"   P&L: ${pnl_usd:.2f} ({pnl_pct:.2f}%)")
        print(f"   Duration: {trade['duration']:.0f} minutes")
        print(f"   Capital: ${self.capital:.2f}")

        return trade

    def get_performance_summary(self):
        """
        Get account performance summary
        """
        win_rate = self.stats['winning_trades'] / self.stats['total_trades'] if self.stats['total_trades'] > 0 else 0
        profit_factor = self.stats['total_profit'] / self.stats['total_loss'] if self.stats['total_loss'] > 0 else float('inf')
        total_return = ((self.capital - self.initial_capital) / self.initial_capital) * 100

        avg_win = self.stats['total_profit'] / self.stats['winning_trades'] if self.stats['winning_trades'] > 0 else 0
        avg_loss = self.stats['total_loss'] / self.stats['losing_trades'] if self.stats['losing_trades'] > 0 else 0

        return {
            'initial_capital': self.initial_capital,
            'current_capital': self.capital,
            'total_return_pct': total_return,
            'total_return_usd': self.capital - self.initial_capital,
            'total_trades': self.stats['total_trades'],
            'winning_trades': self.stats['winning_trades'],
            'losing_trades': self.stats['losing_trades'],
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_profit': self.stats['total_profit'],
            'total_loss': self.stats['total_loss'],
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': self.stats['max_drawdown'],
            'current_drawdown': self.stats['current_drawdown'],
            'active_positions': len(self.active_positions)
        }


class PaperTradingSystem:
    """
    Complete paper trading system
    """

    def __init__(self, initial_capital=10000, config=None):
        self.account = PaperTradingAccount(initial_capital)
        self.signal_system = LiveTradingSystem(config)

        print("="*80)
        print("PAPER TRADING SYSTEM INITIALIZED")
        print("="*80)
        print(f"Initial Capital: ${initial_capital:,.2f}")
        print(f"Leverage: {config['leverage']}x" if config else "Leverage: 50x")
        print(f"Strategy: Momentum Exhaustion + Confirmation Entry")
        print("="*80)

    def process_candle(self, timestamp, open_price, high, low, close, volume):
        """
        Process new candle - detect signals and manage positions
        """
        # Step 1: Check existing positions
        self.account.check_positions(close, timestamp)

        # Step 2: Detect new signals
        signal = self.signal_system.process_candle(
            timestamp, open_price, high, low, close, volume
        )

        # Step 3: Open new position if signal and no active position
        if signal and len(self.account.active_positions) == 0:
            self.account.open_position(signal, timestamp)

    def run_paper_trading(self, data_file):
        """
        Run paper trading on historical data
        """
        print(f"\nLoading data from {data_file}...")
        df = pd.read_csv(data_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        print(f"Processing {len(df)} candles...\n")

        for idx, row in df.iterrows():
            self.process_candle(
                row['timestamp'],
                row['open'],
                row['high'],
                row['low'],
                row['close'],
                row['volume']
            )

            # Progress update
            if (idx + 1) % 1000 == 0:
                perf = self.account.get_performance_summary()
                print(f"\n--- Progress: {idx+1}/{len(df)} candles ---")
                print(f"Capital: ${perf['current_capital']:.2f} ({perf['total_return_pct']:.1f}%)")
                print(f"Trades: {perf['total_trades']} | Win Rate: {perf['win_rate']*100:.1f}%")

        # Final summary
        self.print_final_summary()

    def print_final_summary(self):
        """
        Print final trading summary
        """
        perf = self.account.get_performance_summary()

        print("\n" + "="*80)
        print("PAPER TRADING RESULTS")
        print("="*80)

        print(f"\n💰 CAPITAL:")
        print(f"   Initial: ${perf['initial_capital']:,.2f}")
        print(f"   Final: ${perf['current_capital']:,.2f}")
        print(f"   Return: ${perf['total_return_usd']:,.2f} ({perf['total_return_pct']:.2f}%)")

        print(f"\n📊 TRADES:")
        print(f"   Total: {perf['total_trades']}")
        print(f"   Wins: {perf['winning_trades']} | Losses: {perf['losing_trades']}")
        print(f"   Win Rate: {perf['win_rate']*100:.1f}%")

        print(f"\n💵 PROFITABILITY:")
        print(f"   Total Profit: ${perf['total_profit']:,.2f}")
        print(f"   Total Loss: ${perf['total_loss']:,.2f}")
        print(f"   Avg Win: ${perf['avg_win']:.2f}")
        print(f"   Avg Loss: ${perf['avg_loss']:.2f}")
        print(f"   Profit Factor: {perf['profit_factor']:.2f}")

        print(f"\n📉 RISK METRICS:")
        print(f"   Max Drawdown: {perf['max_drawdown']:.2f}%")
        print(f"   Current Drawdown: {perf['current_drawdown']:.2f}%")
        print(f"   Active Positions: {perf['active_positions']}")

        # Trade log
        if self.account.closed_trades:
            print(f"\n📝 RECENT TRADES (Last 10):")
            print(f"   {'ID':<5} {'Type':<6} {'Entry':<10} {'Exit':<10} {'P&L':<10} {'Duration'}")
            print(f"   {'-'*60}")
            for trade in self.account.closed_trades[-10:]:
                pnl_str = f"${trade['pnl_usd']:.2f}"
                print(f"   {trade['id']:<5} {trade['type']:<6} ${trade['entry_price']:<9.2f} "
                      f"${trade['exit_price']:<9.2f} {pnl_str:<10} {trade['duration']:.0f}min")

        print("\n" + "="*80)


def main():
    """
    Run paper trading on 7-day real data
    """
    # Configuration
    config = {
        'leverage': 50,
        'take_profit_pct': 0.3,
        'stop_loss_pct': 0.5,
        'exhaustion_threshold': 0.6,
        'min_red_retracement_pct': 50,
        'min_volume_drop_pct': 20
    }

    # Initialize paper trading system
    paper_system = PaperTradingSystem(
        initial_capital=10000,  # Start with $10,000
        config=config
    )

    # Run on 7-day real data
    paper_system.run_paper_trading('SOL_USDT_1min_7days.csv')

    # Save results
    perf = paper_system.account.get_performance_summary()
    with open('paper_trading_results.json', 'w') as f:
        json.dump(perf, f, indent=2)

    print(f"\n✓ Results saved to paper_trading_results.json")


if __name__ == "__main__":
    main()
