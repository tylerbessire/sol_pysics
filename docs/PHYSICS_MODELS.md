# Physics Models Documentation

## Overview

This project applies classical physics principles to cryptocurrency trading, specifically targeting liquidation cascades in high-leverage markets.

## Core Physics Concepts

### 1. Momentum (p = mv)

In physics: **Momentum = Mass × Velocity**

In trading:
- **Mass** = Trading Volume
- **Velocity** = Rate of price change (Δprice/Δtime)
- **Momentum** = Volume × Price Velocity

**Why this works:** Just like in physics, market momentum tells us how much "force" is behind a price movement. High volume + fast price change = strong momentum that's hard to stop.

### 2. Terminal Velocity

In physics: Terminal velocity is when an object stops accelerating because drag force equals gravitational force.

In trading: "Terminal velocity" is when a liquidation cascade reaches maximum momentum and starts decaying - **this is the optimal entry point**.

**Detection criteria:**
- High downward velocity (fast price drop)
- Negative acceleration (velocity decreasing)
- Momentum decaying from peak
- Volume still elevated

### 3. Mean Reversion

In physics: Systems tend to return to equilibrium (rubber band effect).

In trading: Prices that deviate significantly from their mean tend to revert back.

**Why liquidation cascades are perfect for this:**
- Cascades create artificial, physics-driven deviations
- Not driven by fundamentals or market makers
- Pure momentum exhaustion → predictable reversion

## Model Implementations

### Momentum Calculator (`src/models/momentum.py`)

Calculates market momentum and detects exhaustion:

```python
momentum = volume * velocity
exhaustion = momentum < (peak_momentum * threshold)
```

**Signals:**
- Momentum building: Cascade starting
- Momentum peak: Maximum cascade intensity
- Momentum exhaustion: Entry point approaching

### Mean Reversion Detector (`src/models/mean_reversion.py`)

Uses statistical methods to detect reversion opportunities:

```python
zscore = (price - mean) / std_dev
is_extreme = zscore > threshold
reversion_target = mean
```

**Signals:**
- High Z-score: Price far from mean
- Outside Bollinger Bands: Extreme deviation
- High reversion probability: Entry signal

### Terminal Velocity Detector (`src/models/terminal_velocity.py`)

Detects the precise moment to enter trades:

```python
conditions = (
    high_velocity AND
    negative_acceleration AND
    momentum_decaying AND
    volume_elevated
)
```

**Why this is the edge:**
- Everyone sees the cascade
- Most people panic or enter too early
- Terminal velocity = precise mathematical entry point
- Combines momentum decay + mean reversion + volume analysis

## The Complete Strategy

### Phase 1: Detection
- Monitor volume for spikes (2x+ average)
- Detect rapid price movements
- Identify cascade starting

### Phase 2: Tracking
- Calculate momentum continuously
- Track acceleration
- Identify cascade phase (building, accelerating, peak, decelerating)

### Phase 3: Entry Signal
- Wait for terminal velocity conditions
- Momentum peaked and decaying
- Negative acceleration confirmed
- Volume still elevated

### Phase 4: Execution
- Enter short at precise moment
- Take profit: 0.2% (perfect for 500x leverage)
- Stop loss: 0.15% (tight risk management)

## Why 500x Leverage Works Here

**The Math:**
- 0.2% price movement × 500x leverage = 100% return
- 0.15% adverse movement × 500x leverage = 75% loss
- Risk/Reward ratio: 1.33:1 before considering win rate

**With 60% win rate:**
- Expected value = (0.6 × 100%) - (0.4 × 75%) = +30% per trade

**Why it's possible:**
- Physics-based timing provides edge
- Liquidation cascades are predictable
- Terminal velocity detection = precision entry
- Tight take-profit targets are achievable

## Academic vs. Practical

### 2011 Academic Models
- Proven physics concepts
- Tested on traditional markets
- Theoretical edge existed
- BUT: No 500x leverage, no crypto cascades, institutional interference

### 2025 Crypto Implementation
- Same physics principles
- Applied to pure liquidation cascades
- 500x leverage available
- No market makers interfering
- 24/7 markets with constant opportunities

**The difference:** Academic models proved the concept. Crypto markets + high leverage make it profitable.

## Risks and Reality Checks

### This Is Extremely Risky
- 500x leverage can wipe out account instantly
- Model could fail in unprecedented conditions
- Exchange issues (API failures, liquidation engine bugs)
- Black swan events

### Requirements for Success
1. **Discipline:** No emotional trading, follow signals exactly
2. **Risk management:** Never risk more than you can afford to lose
3. **Backtesting:** Extensive testing on historical data
4. **Paper trading:** Prove it works before using real money
5. **Capital:** Start small, compound gradually

### When Models Fail
- Sudden news events (fundamentals override physics)
- Exchange manipulation
- Coordinated whale activity
- Market structure changes

## Further Reading

- Classical Mechanics: Momentum and Energy
- Market Microstructure Theory
- Mean Reversion in Financial Markets
- Liquidation Cascade Dynamics
- High-Frequency Trading Strategies

---

*"In physics, terminal velocity is when falling stops accelerating. In trading, it's when falling becomes profitable."*
