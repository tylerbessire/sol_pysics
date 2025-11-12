"""
Liquidation Cascade Detector

Detects and analyzes liquidation cascades in leveraged cryptocurrency markets.

A liquidation cascade occurs when:
1. Large leveraged positions get liquidated
2. Liquidations cause price to move against other leveraged positions
3. Those positions get liquidated, creating a chain reaction
4. The cascade continues until momentum exhausts (terminal velocity)

This is the most predictable pattern in crypto because it's purely physics-driven.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class CascadePhase(Enum):
    """Phases of a liquidation cascade"""
    BUILDING = "building"  # Liquidations starting
    ACCELERATING = "accelerating"  # Cascade gaining momentum
    PEAK = "peak"  # Maximum momentum
    DECELERATING = "decelerating"  # Terminal velocity phase
    EXHAUSTED = "exhausted"  # Cascade complete


@dataclass
class LiquidationEvent:
    """Single liquidation event"""
    timestamp: pd.Timestamp
    price: float
    size: float  # Size of liquidation
    side: str  # 'long' or 'short'
    leverage: Optional[float] = None


@dataclass
class LiquidationCascade:
    """Complete liquidation cascade data"""
    start_time: pd.Timestamp
    end_time: Optional[pd.Timestamp]
    start_price: float
    low_price: float
    total_liquidations: int
    total_volume: float
    max_momentum: float
    phase: CascadePhase
    liquidation_events: List[LiquidationEvent]


class LiquidationDetector:
    """
    Detect and track liquidation cascades in real-time
    """

    def __init__(self,
                 volume_spike_threshold: float = 2.0,
                 cascade_timeout: int = 300,  # 5 minutes
                 min_cascade_size: int = 5):  # Minimum liquidations to count as cascade
        """
        Initialize liquidation detector

        Args:
            volume_spike_threshold: Volume multiple to detect unusual activity
            cascade_timeout: Seconds before considering cascade complete
            min_cascade_size: Minimum number of liquidations to count as cascade
        """
        self.volume_spike_threshold = volume_spike_threshold
        self.cascade_timeout = cascade_timeout
        self.min_cascade_size = min_cascade_size
        self.active_cascades: List[LiquidationCascade] = []

    def detect_volume_spike(self,
                           volumes: pd.Series,
                           window: int = 20) -> pd.Series:
        """
        Detect abnormal volume spikes (potential liquidations)

        Args:
            volumes: Volume series
            window: Window for average calculation

        Returns:
            Boolean series indicating volume spikes
        """
        volume_ma = volumes.rolling(window=window).mean()
        volume_ratio = volumes / volume_ma

        is_spike = volume_ratio > self.volume_spike_threshold

        return is_spike

    def detect_price_velocity_spike(self,
                                    prices: pd.Series,
                                    threshold_pct: float = 0.5) -> pd.Series:
        """
        Detect rapid price movements (liquidation cascades)

        Args:
            prices: Price series
            threshold_pct: Minimum price movement % to detect

        Returns:
            Boolean series indicating velocity spikes
        """
        # Price change percentage
        price_change_pct = (prices.diff() / prices) * 100

        # Spike when price moves more than threshold
        is_velocity_spike = np.abs(price_change_pct) > threshold_pct

        return is_velocity_spike

    def identify_cascade_start(self,
                               prices: pd.Series,
                               volumes: pd.Series,
                               window: int = 20) -> pd.Series:
        """
        Identify the start of potential liquidation cascades

        Cascade starts when:
        - Volume spike occurs
        - Price velocity spike occurs
        - Both happen simultaneously

        Args:
            prices: Price series
            volumes: Volume series
            window: Window for detection

        Returns:
            Boolean series indicating cascade starts
        """
        volume_spike = self.detect_volume_spike(volumes, window)
        velocity_spike = self.detect_price_velocity_spike(prices)

        # Cascade starts when both conditions are met
        cascade_start = volume_spike & velocity_spike

        return cascade_start

    def track_cascade_phase(self,
                           momentum: pd.Series,
                           acceleration: pd.Series,
                           window: int = 10) -> pd.Series:
        """
        Track which phase of the cascade we're in

        Args:
            momentum: Momentum series
            acceleration: Acceleration series
            window: Window for phase detection

        Returns:
            Series with cascade phase labels
        """
        phases = pd.Series(CascadePhase.BUILDING.value, index=momentum.index)

        # Calculate momentum changes
        momentum_change = momentum.diff()
        momentum_peak = momentum.rolling(window=window).max()
        momentum_ratio = momentum / momentum_peak

        # Phase detection
        accelerating = (acceleration < 0) & (momentum_change < 0)  # Getting faster
        at_peak = (acceleration > -0.1) & (acceleration < 0.1) & (np.abs(momentum) > momentum.rolling(50).mean())
        decelerating = (acceleration > 0) & (momentum_ratio < 0.8)  # Slowing down
        exhausted = momentum_ratio < 0.3

        phases[accelerating] = CascadePhase.ACCELERATING.value
        phases[at_peak] = CascadePhase.PEAK.value
        phases[decelerating] = CascadePhase.DECELERATING.value
        phases[exhausted] = CascadePhase.EXHAUSTED.value

        return phases

    def estimate_liquidation_levels(self,
                                   current_price: float,
                                   open_interest: pd.Series,
                                   leverage_distribution: Dict[int, float]) -> pd.DataFrame:
        """
        Estimate where liquidation levels are (where cascades might trigger)

        Args:
            current_price: Current market price
            open_interest: Open interest at each price level
            leverage_distribution: Distribution of leverage levels (e.g., {10: 0.2, 50: 0.3, 100: 0.5})

        Returns:
            DataFrame with estimated liquidation levels
        """
        liquidation_levels = []

        for leverage, weight in leverage_distribution.items():
            # For longs: liquidation when price drops by ~100/leverage %
            # For 100x leverage: liquidation at ~1% drop
            liquidation_distance_pct = 90 / leverage  # Conservative estimate

            long_liquidation_price = current_price * (1 - liquidation_distance_pct / 100)
            short_liquidation_price = current_price * (1 + liquidation_distance_pct / 100)

            liquidation_levels.append({
                'leverage': leverage,
                'weight': weight,
                'long_liquidation_price': long_liquidation_price,
                'short_liquidation_price': short_liquidation_price,
                'distance_pct': liquidation_distance_pct
            })

        df = pd.DataFrame(liquidation_levels)
        df = df.sort_values('long_liquidation_price')

        return df

    def calculate_cascade_momentum(self,
                                  liquidation_events: List[LiquidationEvent],
                                  time_window: int = 60) -> float:
        """
        Calculate the momentum of a liquidation cascade

        Momentum = total liquidation volume / time

        Args:
            liquidation_events: List of liquidation events
            time_window: Time window in seconds

        Returns:
            Cascade momentum value
        """
        if len(liquidation_events) == 0:
            return 0.0

        # Total volume liquidated
        total_volume = sum(event.size for event in liquidation_events)

        # Time span
        if len(liquidation_events) == 1:
            time_span = 1
        else:
            time_span = (liquidation_events[-1].timestamp - liquidation_events[0].timestamp).total_seconds()
            time_span = max(time_span, 1)  # Avoid division by zero

        # Momentum = volume / time
        momentum = total_volume / time_span

        return momentum

    def predict_cascade_target(self,
                              cascade: LiquidationCascade,
                              liquidation_levels: pd.DataFrame) -> Dict[str, float]:
        """
        Predict how far the cascade might go

        Args:
            cascade: Current liquidation cascade
            liquidation_levels: Estimated liquidation levels

        Returns:
            Dictionary with cascade predictions
        """
        current_price = cascade.low_price

        # Find next major liquidation clusters
        nearby_liquidations = liquidation_levels[
            liquidation_levels['long_liquidation_price'] < current_price
        ].sort_values('long_liquidation_price', ascending=False)

        if len(nearby_liquidations) > 0:
            next_target = nearby_liquidations.iloc[0]['long_liquidation_price']
            total_risk = ((current_price - next_target) / current_price) * 100
        else:
            next_target = current_price * 0.98  # Default 2% drop
            total_risk = 2.0

        return {
            'current_price': current_price,
            'predicted_target': next_target,
            'distance_pct': total_risk,
            'estimated_time_sec': cascade.total_liquidations * 2,  # Rough estimate
            'confidence': min(len(nearby_liquidations) / 3, 1.0)  # Confidence based on data
        }


class CascadeSignalGenerator:
    """
    Generate trading signals from liquidation cascade analysis
    """

    def __init__(self, detector: LiquidationDetector):
        self.detector = detector

    def generate_cascade_signals(self,
                                 prices: pd.Series,
                                 volumes: pd.Series,
                                 momentum: pd.Series,
                                 acceleration: pd.Series) -> pd.DataFrame:
        """
        Generate trading signals based on cascade analysis

        Signal strength increases in DECELERATING phase (terminal velocity)

        Args:
            prices: Price series
            volumes: Volume series
            momentum: Momentum series
            acceleration: Acceleration series

        Returns:
            DataFrame with cascade signals
        """
        # Detect cascade phases
        cascade_phase = self.detector.track_cascade_phase(momentum, acceleration)

        # Detect cascade starts
        cascade_starts = self.detector.identify_cascade_start(prices, volumes)

        signals = pd.DataFrame({
            'price': prices,
            'volume': volumes,
            'momentum': momentum,
            'acceleration': acceleration,
            'cascade_phase': cascade_phase,
            'cascade_start': cascade_starts,
            'is_decelerating': cascade_phase == CascadePhase.DECELERATING.value,
            'is_exhausted': cascade_phase == CascadePhase.EXHAUSTED.value,
            'signal_strength': 0.0,
            'entry_signal': False
        })

        # Generate entry signals in DECELERATING phase
        signals['signal_strength'] = np.where(
            signals['is_decelerating'],
            0.8,  # Strong signal during deceleration
            np.where(
                signals['is_exhausted'],
                0.5,  # Medium signal when exhausted
                0.0
            )
        )

        signals['entry_signal'] = signals['signal_strength'] > 0.7

        return signals


# Example usage
if __name__ == "__main__":
    # Example with sample cascade data
    np.random.seed(42)

    # Simulate liquidation cascade
    dates = pd.date_range('2024-01-01 10:00', periods=200, freq='1s')

    # Cascade pattern: normal -> spike -> cascade -> recovery
    price_pattern = np.concatenate([
        100 + np.random.randn(50) * 0.2,  # Normal
        100 + np.linspace(0, -3, 50),  # Start cascade
        97 + np.linspace(0, -2, 50),  # Deep cascade
        95 + np.linspace(0, 1, 50)  # Recovery
    ])
    prices = pd.Series(price_pattern, index=dates)

    volume_pattern = np.concatenate([
        np.random.randint(1000, 2000, 50),  # Normal
        np.random.randint(5000, 10000, 50),  # Cascade volume
        np.random.randint(8000, 15000, 50),  # Peak volume
        np.random.randint(2000, 4000, 50)  # Recovery
    ])
    volumes = pd.Series(volume_pattern, index=dates)

    # Calculate momentum and acceleration
    velocities = prices.diff()
    accelerations = velocities.diff()
    momentum = volumes * velocities

    # Create detector
    detector = LiquidationDetector()
    signal_gen = CascadeSignalGenerator(detector)

    # Generate signals
    signals = signal_gen.generate_cascade_signals(prices, volumes, momentum, accelerations)

    # Show results
    print("Liquidation Cascade Analysis Example:")
    print(f"\nTotal periods: {len(signals)}")
    print(f"Cascade starts detected: {signals['cascade_start'].sum()}")
    print(f"Entry signals generated: {signals['entry_signal'].sum()}")

    # Show cascade phases distribution
    print(f"\nCascade phase distribution:")
    print(signals['cascade_phase'].value_counts())

    # Show entry signals
    entry_signals = signals[signals['entry_signal']]
    if len(entry_signals) > 0:
        print(f"\nFirst entry signal:")
        first_signal = entry_signals.iloc[0]
        print(f"  Time: {first_signal.name}")
        print(f"  Price: ${first_signal['price']:.2f}")
        print(f"  Phase: {first_signal['cascade_phase']}")
        print(f"  Signal strength: {first_signal['signal_strength']:.2%}")
