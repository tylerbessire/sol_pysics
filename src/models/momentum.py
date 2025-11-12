"""
Momentum Model - Physics-based momentum calculation for trading

Treats market movements using classical physics:
- Volume as mass (m)
- Price velocity as velocity (v)
- Momentum = mass × velocity (p = mv)
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple


class MomentumCalculator:
    """
    Calculate market momentum using physics principles

    Momentum (p) = Volume (mass) × Price Velocity

    This helps identify when buying/selling pressure is building or dissipating.
    """

    def __init__(self, window: int = 20):
        """
        Initialize momentum calculator

        Args:
            window: Number of periods for velocity calculation
        """
        self.window = window

    def calculate_velocity(self, prices: pd.Series, time_delta: float = 1.0) -> pd.Series:
        """
        Calculate price velocity (rate of price change)

        Args:
            prices: Series of price data
            time_delta: Time between measurements (default 1.0 for single periods)

        Returns:
            Series of velocity values (price change per unit time)
        """
        # v = Δp / Δt
        velocity = prices.diff() / time_delta
        return velocity

    def calculate_acceleration(self, velocity: pd.Series, time_delta: float = 1.0) -> pd.Series:
        """
        Calculate price acceleration (rate of velocity change)

        Args:
            velocity: Series of velocity values
            time_delta: Time between measurements

        Returns:
            Series of acceleration values
        """
        # a = Δv / Δt
        acceleration = velocity.diff() / time_delta
        return acceleration

    def calculate_momentum(self,
                          prices: pd.Series,
                          volumes: pd.Series,
                          time_delta: float = 1.0) -> pd.Series:
        """
        Calculate market momentum (volume × velocity)

        Args:
            prices: Series of price data
            volumes: Series of volume data (represents "mass")
            time_delta: Time between measurements

        Returns:
            Series of momentum values
        """
        velocity = self.calculate_velocity(prices, time_delta)

        # p = m × v (momentum = mass × velocity)
        momentum = volumes * velocity

        return momentum

    def calculate_force(self,
                       prices: pd.Series,
                       volumes: pd.Series,
                       time_delta: float = 1.0) -> pd.Series:
        """
        Calculate market "force" (rate of momentum change)

        F = Δp/Δt = m × a

        Args:
            prices: Series of price data
            volumes: Series of volume data
            time_delta: Time between measurements

        Returns:
            Series of force values
        """
        velocity = self.calculate_velocity(prices, time_delta)
        acceleration = self.calculate_acceleration(velocity, time_delta)

        # F = m × a
        force = volumes * acceleration

        return force

    def detect_momentum_exhaustion(self,
                                   momentum: pd.Series,
                                   threshold: float = 0.8) -> pd.Series:
        """
        Detect when momentum is exhausting (slowing down)

        This is a key signal for mean reversion entry points.

        Args:
            momentum: Series of momentum values
            threshold: Percentage of momentum decay to trigger signal (0-1)

        Returns:
            Boolean series indicating exhaustion points
        """
        # Calculate rolling max momentum
        rolling_max = momentum.rolling(window=self.window).max()

        # Current momentum as percentage of recent max
        momentum_ratio = momentum / rolling_max

        # Exhaustion when momentum has dropped below threshold of recent max
        exhaustion = momentum_ratio < threshold

        return exhaustion

    def momentum_divergence(self,
                           prices: pd.Series,
                           momentum: pd.Series) -> pd.Series:
        """
        Detect divergence between price and momentum

        When price continues moving but momentum decreases = exhaustion signal

        Args:
            prices: Series of price data
            momentum: Series of momentum values

        Returns:
            Series of divergence scores (positive = bearish divergence)
        """
        # Normalize both series to compare trends
        price_normalized = (prices - prices.rolling(self.window).mean()) / prices.rolling(self.window).std()
        momentum_normalized = (momentum - momentum.rolling(self.window).mean()) / momentum.rolling(self.window).std()

        # Divergence = difference in normalized trends
        divergence = price_normalized - momentum_normalized

        return divergence


class MomentumSignals:
    """
    Generate trading signals from momentum analysis
    """

    def __init__(self, calculator: MomentumCalculator):
        self.calculator = calculator

    def generate_short_signals(self,
                               prices: pd.Series,
                               volumes: pd.Series,
                               exhaustion_threshold: float = 0.7) -> pd.DataFrame:
        """
        Generate short entry signals based on momentum exhaustion

        Signal strength increases when:
        1. Momentum is exhausting
        2. Price-momentum divergence is high
        3. Acceleration is negative

        Args:
            prices: Series of price data
            volumes: Series of volume data
            exhaustion_threshold: Threshold for momentum exhaustion

        Returns:
            DataFrame with signal strength and components
        """
        # Calculate physics metrics
        velocity = self.calculator.calculate_velocity(prices)
        acceleration = self.calculator.calculate_acceleration(velocity)
        momentum = self.calculator.calculate_momentum(prices, volumes)

        # Detect exhaustion
        exhaustion = self.calculator.detect_momentum_exhaustion(momentum, exhaustion_threshold)

        # Detect divergence
        divergence = self.calculator.momentum_divergence(prices, momentum)

        # Combine signals
        signals = pd.DataFrame({
            'velocity': velocity,
            'acceleration': acceleration,
            'momentum': momentum,
            'exhaustion': exhaustion.astype(int),
            'divergence': divergence,
            'signal_strength': 0.0
        })

        # Calculate signal strength (0-1)
        # Strong signal when: exhaustion + bearish divergence + negative acceleration
        signals['signal_strength'] = (
            signals['exhaustion'] * 0.4 +
            (signals['divergence'] > 0).astype(int) * 0.3 +
            (signals['acceleration'] < 0).astype(int) * 0.3
        )

        return signals


# Example usage
if __name__ == "__main__":
    # Example with sample data
    np.random.seed(42)

    # Simulate a liquidation cascade (price drops with high volume)
    dates = pd.date_range('2024-01-01', periods=100, freq='1min')
    prices = pd.Series(100 + np.cumsum(np.random.randn(100) * 0.5), index=dates)
    volumes = pd.Series(np.random.randint(1000, 10000, 100), index=dates)

    # Create momentum calculator
    calc = MomentumCalculator(window=20)

    # Calculate metrics
    momentum = calc.calculate_momentum(prices, volumes)
    exhaustion = calc.detect_momentum_exhaustion(momentum)

    print("Momentum Analysis Example:")
    print(f"Current price: ${prices.iloc[-1]:.2f}")
    print(f"Current momentum: {momentum.iloc[-1]:.2f}")
    print(f"Exhaustion detected: {exhaustion.iloc[-1]}")
