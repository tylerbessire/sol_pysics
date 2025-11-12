# Quick Start Guide

## Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd sol_pysics
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Activate on Linux/Mac:
source venv/bin/activate

# Activate on Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Running the Dashboard

Launch the real-time trading dashboard:

```bash
python src/dashboard/app.py
```

Open your browser to: http://localhost:8050

**Dashboard Features:**
- 💥 Real-time liquidation bubble visualization
- ⚡ Physics gauges (momentum, acceleration, terminal velocity)
- 📊 Order book depth analysis
- 🔥 Energy flow heatmap
- 🎯 Active trading signals

## Running Backtests

Test the strategy on historical data:

```bash
python src/backtesting/engine.py
```

This will:
1. Load sample historical data
2. Calculate physics metrics
3. Generate trading signals
4. Simulate trades with 500x leverage
5. Display performance statistics

## Using the Models

### Calculate Momentum

```python
from src.models.momentum import MomentumCalculator
import pandas as pd

# Your price and volume data
prices = pd.Series([...])  # Your price data
volumes = pd.Series([...])  # Your volume data

# Calculate momentum
calc = MomentumCalculator(window=20)
momentum = calc.calculate_momentum(prices, volumes)
exhaustion = calc.detect_momentum_exhaustion(momentum)

print(f"Current momentum: {momentum.iloc[-1]}")
print(f"Exhaustion detected: {exhaustion.iloc[-1]}")
```

### Detect Mean Reversion

```python
from src.models.mean_reversion import MeanReversionDetector, MeanReversionStrategy

# Create detector
detector = MeanReversionDetector(window=20, num_std=2.0)
strategy = MeanReversionStrategy(detector, min_zscore=2.0)

# Generate signals
signals = strategy.generate_short_signals(prices)

# Check for entry signals
latest_signal = signals.iloc[-1]
if latest_signal['signal']:
    print(f"Entry signal detected!")
    print(f"Expected move: {latest_signal['expected_move_pct']:.2f}%")
```

### Detect Terminal Velocity

```python
from src.models.terminal_velocity import TerminalVelocityDetector, TerminalVelocityStrategy
from src.models.momentum import MomentumCalculator

# Calculate required metrics
calc = MomentumCalculator()
velocities = calc.calculate_velocity(prices)
accelerations = calc.calculate_acceleration(velocities)
momentum = calc.calculate_momentum(prices, volumes)
mean_prices = prices.rolling(20).mean()

# Create detector and strategy
tv_detector = TerminalVelocityDetector()
tv_strategy = TerminalVelocityStrategy(tv_detector)

# Generate signals
signals = tv_strategy.generate_entry_signals(
    prices, volumes, velocities, accelerations, momentum, mean_prices
)

# Check for terminal velocity
tv_signals = signals[signals['final_signal']]
if len(tv_signals) > 0:
    latest = tv_signals.iloc[-1]
    print(f"Terminal velocity detected!")
    print(f"Entry: ${latest['entry_price']:.2f}")
    print(f"Take profit: ${latest['take_profit']:.2f}")
    print(f"Stop loss: ${latest['stop_loss']:.2f}")
```

### Detect Liquidation Cascades

```python
from src.analysis.liquidations import LiquidationDetector, CascadeSignalGenerator

# Create detector
detector = LiquidationDetector()
signal_gen = CascadeSignalGenerator(detector)

# Generate cascade signals
signals = signal_gen.generate_cascade_signals(prices, volumes, momentum, accelerations)

# Check cascade phase
current_phase = signals['cascade_phase'].iloc[-1]
print(f"Current cascade phase: {current_phase}")

# Check for entry signals
if signals['entry_signal'].iloc[-1]:
    print(f"Cascade entry signal detected!")
    print(f"Signal strength: {signals['signal_strength'].iloc[-1]:.2%}")
```

## Configuration

Edit `config/trading_config.yaml` to customize:

- Leverage settings
- Take profit / stop loss percentages
- Physics model parameters
- Risk management rules

## Next Steps

### 1. Backtest Thoroughly

Before live trading, backtest extensively on historical data:

```bash
# Run backtests for different periods
python src/backtesting/engine.py --start-date 2024-01-01 --end-date 2024-12-31
```

Analyze:
- Win rate
- Profit factor
- Maximum drawdown
- Sharpe ratio

### 2. Paper Trade

Test with paper trading on testnet exchanges:

1. Set up testnet API credentials
2. Update `config/trading_config.yaml` (set `testnet: true`)
3. Run the trading bot in paper mode
4. Monitor for at least 100 trades

### 3. Start Small

If backtests and paper trading are successful:

1. Start with minimal capital (only what you can afford to lose)
2. Use lower leverage initially (50x-100x, not 500x)
3. Monitor every trade closely
4. Gradually increase size as confidence builds

## Important Warnings

⚠️ **HIGH RISK WARNING**

- 500x leverage can liquidate your entire account in seconds
- Past performance does not guarantee future results
- Cryptocurrency markets are extremely volatile
- Only trade with money you can afford to lose completely

⚠️ **TECHNICAL RISKS**

- API failures can prevent closing positions
- Exchange bugs can cause unexpected liquidations
- Internet connectivity issues can be catastrophic with high leverage

⚠️ **MODEL RISKS**

- Physics models work until they don't
- Market conditions change
- Unprecedented events can break models
- No trading strategy has a guaranteed edge

## Getting Help

- Read the full documentation in `/docs/`
- Study the physics models in `docs/PHYSICS_MODELS.md`
- Review example code in each module's `if __name__ == "__main__"` section
- Test extensively on historical data before live trading

## Resources

- Exchange APIs: https://docs.ccxt.com/
- Binance Testnet: https://testnet.binance.vision/
- Technical Analysis: https://github.com/bukosabino/ta

---

**Remember:** This is experimental trading research. The intersection of physics models and 500x leverage is extremely high risk. Use responsibly.
