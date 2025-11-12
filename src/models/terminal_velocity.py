"""
Terminal Velocity Model - Detect optimal entry points during liquidation cascades

In physics, terminal velocity is when an object stops accelerating due to air resistance.
In trading, "terminal velocity" is when a liquidation cascade reaches maximum momentum
and starts decaying - the perfect moment to enter a mean reversion trade.

Key concept: When acceleration turns negative while velocity is still high,
that's the "terminal velocity" signal - momentum has peaked and will soon reverse.
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Tuple
from dataclasses import dataclass


@dataclass
class TerminalVelocitySignal:
    """Data class for terminal velocity signals"""
    timestamp: pd.Timestamp
    price: float
    velocity: float
    acceleration: float
    momentum: float
    signal_strength: float
    is_terminal_velocity: bool
    entry_price: float
    stop_loss: float
    take_profit: float


class TerminalVelocityDetector:
    """
    Detect terminal velocity - the optimal entry point for mean reversion

    Terminal velocity occurs when:
    1. High downward velocity (fast price drop)
    2. Negative acceleration (velocity is decreasing)
    3. Momentum is decaying from peak
    4. Volume is still elevated (liquidations still happening)

    This is the precise moment to enter short positions before the bounce.
    """

    def __init__(self,
                 velocity_window: int = 5,
                 acceleration_threshold: float = -0.5,
                 momentum_decay_threshold: float = 0.8):
        """
        Initialize terminal velocity detector

        Args:
            velocity_window: Window for velocity calculation
            acceleration_threshold: Minimum negative acceleration to signal
            momentum_decay_threshold: Momentum decay ratio from peak (0-1)
        """
        self.velocity_window = velocity_window
        self.acceleration_threshold = acceleration_threshold
        self.momentum_decay_threshold = momentum_decay_threshold

    def detect_terminal_velocity(self,
                                 prices: pd.Series,
                                 volumes: pd.Series,
                                 velocities: pd.Series,
                                 accelerations: pd.Series,
                                 momentum: pd.Series) -> pd.DataFrame:
        """
        Detect terminal velocity points

        Args:
            prices: Price series
            volumes: Volume series
            velocities: Price velocity series
            accelerations: Price acceleration series
            momentum: Market momentum series

        Returns:
            DataFrame with terminal velocity signals
        """
        # Calculate momentum decay from rolling peak
        momentum_peak = momentum.rolling(window=20).max()
        momentum_ratio = momentum / momentum_peak

        # Volume profile (is volume elevated?)
        volume_ma = volumes.rolling(window=20).mean()
        volume_ratio = volumes / volume_ma

        # Detect terminal velocity conditions
        signals = pd.DataFrame({
            'price': prices,
            'velocity': velocities,
            'acceleration': accelerations,
            'momentum': momentum,
            'momentum_ratio': momentum_ratio,
            'volume_ratio': volume_ratio,

            # Core conditions
            'has_high_velocity': np.abs(velocities) > np.abs(velocities.rolling(20).mean()),
            'has_negative_acceleration': accelerations < self.acceleration_threshold,
            'has_momentum_decay': momentum_ratio < self.momentum_decay_threshold,
            'has_elevated_volume': volume_ratio > 1.2,

            # Signal
            'is_terminal_velocity': False,
            'signal_strength': 0.0
        })

        # Combine conditions for terminal velocity signal
        signals['is_terminal_velocity'] = (
            signals['has_high_velocity'] &
            signals['has_negative_acceleration'] &
            signals['has_momentum_decay'] &
            signals['has_elevated_volume']
        )

        # Calculate signal strength (0-1)
        signals['signal_strength'] = np.where(
            signals['is_terminal_velocity'],
            (
                # Stronger signal with more negative acceleration
                np.clip(np.abs(accelerations) / 2.0, 0, 0.4) +
                # Stronger with more momentum decay
                (1 - momentum_ratio) * 0.3 +
                # Stronger with higher volume
                np.clip(volume_ratio / 2.0, 0, 0.3)
            ),
            0
        )

        return signals

    def find_liquidation_cascade_peak(self,
                                     momentum: pd.Series,
                                     window: int = 10) -> pd.Series:
        """
        Find the peak of a liquidation cascade

        The peak is when momentum reaches maximum before starting to decay.

        Args:
            momentum: Momentum series
            window: Window for peak detection

        Returns:
            Boolean series indicating peaks
        """
        # A peak is when momentum is higher than surrounding points
        rolling_max_before = momentum.shift(1).rolling(window=window).max()
        rolling_max_after = momentum.shift(-1).rolling(window=window).max()

        is_peak = (momentum >= rolling_max_before) & (momentum >= rolling_max_after)

        return is_peak

    def calculate_velocity_decay_rate(self,
                                     velocities: pd.Series,
                                     window: int = 5) -> pd.Series:
        """
        Calculate how fast velocity is decaying

        Faster decay = stronger terminal velocity signal

        Args:
            velocities: Velocity series
            window: Window for decay calculation

        Returns:
            Velocity decay rate
        """
        # Rate of change in absolute velocity
        abs_velocity = np.abs(velocities)
        decay_rate = -abs_velocity.diff(window) / window

        return decay_rate

    def predict_bounce_target(self,
                            current_price: float,
                            terminal_velocity_price: float,
                            mean_price: float,
                            cascade_magnitude: float) -> Dict[str, float]:
        """
        Predict the bounce target after terminal velocity

        Args:
            current_price: Current market price
            terminal_velocity_price: Price at terminal velocity
            mean_price: Mean reversion target
            cascade_magnitude: Size of the liquidation cascade

        Returns:
            Dictionary with bounce predictions
        """
        # Typical bounce is 30-50% of the cascade drop
        cascade_drop = terminal_velocity_price - current_price
        expected_bounce = cascade_drop * 0.4  # 40% retracement

        bounce_target = current_price + expected_bounce

        # Conservative and aggressive targets
        conservative_target = current_price + (cascade_drop * 0.2)  # 0.2% move
        aggressive_target = current_price + (cascade_drop * 0.6)

        return {
            'current_price': current_price,
            'expected_bounce_target': bounce_target,
            'conservative_target': conservative_target,
            'aggressive_target': aggressive_target,
            'mean_reversion_target': mean_price,
            'cascade_drop': cascade_drop,
            'expected_bounce_pct': (expected_bounce / current_price) * 100
        }


class TerminalVelocityStrategy:
    """
    Trading strategy based on terminal velocity detection
    """

    def __init__(self,
                 detector: TerminalVelocityDetector,
                 take_profit_pct: float = 0.2,
                 stop_loss_pct: float = 0.15):
        """
        Initialize strategy

        Args:
            detector: TerminalVelocityDetector instance
            take_profit_pct: Take profit percentage (default 0.2% for 500x leverage)
            stop_loss_pct: Stop loss percentage (default 0.15%)
        """
        self.detector = detector
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct

    def generate_entry_signals(self,
                               prices: pd.Series,
                               volumes: pd.Series,
                               velocities: pd.Series,
                               accelerations: pd.Series,
                               momentum: pd.Series,
                               mean_prices: pd.Series) -> pd.DataFrame:
        """
        Generate entry signals based on terminal velocity

        Args:
            prices: Price series
            volumes: Volume series
            velocities: Velocity series
            accelerations: Acceleration series
            momentum: Momentum series
            mean_prices: Mean reversion target prices

        Returns:
            DataFrame with entry signals and levels
        """
        # Detect terminal velocity
        tv_signals = self.detector.detect_terminal_velocity(
            prices, volumes, velocities, accelerations, momentum
        )

        # Calculate decay rates
        decay_rate = self.detector.calculate_velocity_decay_rate(velocities)

        # Generate full signals
        signals = tv_signals.copy()
        signals['decay_rate'] = decay_rate
        signals['mean_price'] = mean_prices

        # Calculate entry/exit levels
        signals['entry_price'] = prices
        signals['stop_loss'] = prices * (1 + self.stop_loss_pct / 100)
        signals['take_profit'] = prices * (1 - self.take_profit_pct / 100)

        # Calculate expected profit/loss
        signals['expected_profit'] = (signals['entry_price'] - signals['take_profit']) * 500  # 500x leverage
        signals['expected_loss'] = (signals['stop_loss'] - signals['entry_price']) * 500
        signals['risk_reward_ratio'] = signals['expected_profit'] / signals['expected_loss']

        # Only signal when terminal velocity is detected and risk/reward is favorable
        signals['final_signal'] = (
            signals['is_terminal_velocity'] &
            (signals['risk_reward_ratio'] > 1.3)  # Minimum 1.3:1 R/R
        )

        return signals

    def create_terminal_velocity_signal(self,
                                       row: pd.Series,
                                       timestamp: pd.Timestamp) -> TerminalVelocitySignal:
        """
        Create a TerminalVelocitySignal object from a DataFrame row

        Args:
            row: Row from signals DataFrame
            timestamp: Timestamp of the signal

        Returns:
            TerminalVelocitySignal object
        """
        return TerminalVelocitySignal(
            timestamp=timestamp,
            price=row['price'],
            velocity=row['velocity'],
            acceleration=row['acceleration'],
            momentum=row['momentum'],
            signal_strength=row['signal_strength'],
            is_terminal_velocity=row['is_terminal_velocity'],
            entry_price=row['entry_price'],
            stop_loss=row['stop_loss'],
            take_profit=row['take_profit']
        )


# Example usage
if __name__ == "__main__":
    # Example with sample liquidation cascade data
    np.random.seed(42)

    # Simulate a liquidation cascade
    dates = pd.date_range('2024-01-01 10:00', periods=100, freq='1s')

    # Create cascade: rapid drop, then slowdown
    cascade_phase = np.concatenate([
        np.linspace(0, -5, 40),  # Accelerating drop
        np.linspace(-5, -6, 30),  # Slowing drop (terminal velocity)
        np.linspace(-6, -5, 30)   # Bounce
    ])
    noise = np.random.randn(100) * 0.1
    prices = pd.Series(100 + cascade_phase + noise, index=dates)

    # Volume spikes during cascade
    volumes = pd.Series(np.concatenate([
        np.random.randint(1000, 5000, 40),
        np.random.randint(5000, 10000, 30),
        np.random.randint(2000, 4000, 30)
    ]), index=dates)

    # Calculate velocity and acceleration
    velocities = prices.diff()
    accelerations = velocities.diff()
    momentum = volumes * velocities

    # Mean reversion target
    mean_prices = prices.rolling(window=50).mean()

    # Create detector and strategy
    detector = TerminalVelocityDetector()
    strategy = TerminalVelocityStrategy(detector)

    # Generate signals
    signals = strategy.generate_entry_signals(
        prices, volumes, velocities, accelerations, momentum, mean_prices
    )

    # Show terminal velocity signals
    tv_signals = signals[signals['final_signal']]

    print("Terminal Velocity Detection Example:")
    print(f"\nTotal data points: {len(signals)}")
    print(f"Terminal velocity signals detected: {tv_signals['final_signal'].sum()}")

    if len(tv_signals) > 0:
        print(f"\nFirst terminal velocity signal:")
        first_signal = tv_signals.iloc[0]
        print(f"  Time: {first_signal.name}")
        print(f"  Price: ${first_signal['price']:.2f}")
        print(f"  Velocity: {first_signal['velocity']:.4f}")
        print(f"  Acceleration: {first_signal['acceleration']:.4f}")
        print(f"  Signal strength: {first_signal['signal_strength']:.2%}")
        print(f"  Entry: ${first_signal['entry_price']:.2f}")
        print(f"  Take profit: ${first_signal['take_profit']:.2f}")
        print(f"  Stop loss: ${first_signal['stop_loss']:.2f}")
        print(f"  Risk/Reward: {first_signal['risk_reward_ratio']:.2f}")
