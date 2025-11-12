"""
Mean Reversion Model - Statistical mean reversion detection

Identifies when price has deviated from mean and is likely to revert.
Used in conjunction with momentum models to time precise entries.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional
from scipy import stats


class MeanReversionDetector:
    """
    Detect mean reversion opportunities using statistical methods

    Combines:
    - Z-score analysis (standard deviations from mean)
    - Bollinger Band analysis
    - Price extremes detection
    """

    def __init__(self, window: int = 20, num_std: float = 2.0):
        """
        Initialize mean reversion detector

        Args:
            window: Lookback window for mean calculation
            num_std: Number of standard deviations for extremes
        """
        self.window = window
        self.num_std = num_std

    def calculate_zscore(self, prices: pd.Series) -> pd.Series:
        """
        Calculate Z-score (standard deviations from mean)

        Z = (X - μ) / σ

        Args:
            prices: Series of price data

        Returns:
            Series of Z-scores
        """
        rolling_mean = prices.rolling(window=self.window).mean()
        rolling_std = prices.rolling(window=self.window).std()

        zscore = (prices - rolling_mean) / rolling_std

        return zscore

    def calculate_bollinger_bands(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands

        Args:
            prices: Series of price data

        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        middle_band = prices.rolling(window=self.window).mean()
        rolling_std = prices.rolling(window=self.window).std()

        upper_band = middle_band + (rolling_std * self.num_std)
        lower_band = middle_band - (rolling_std * self.num_std)

        return upper_band, middle_band, lower_band

    def detect_extremes(self, prices: pd.Series) -> pd.DataFrame:
        """
        Detect price extremes (potential reversal points)

        Args:
            prices: Series of price data

        Returns:
            DataFrame with extreme signals and distance from mean
        """
        zscore = self.calculate_zscore(prices)
        upper_band, middle_band, lower_band = self.calculate_bollinger_bands(prices)

        # Calculate position relative to bands
        band_width = upper_band - lower_band
        band_position = (prices - lower_band) / band_width  # 0 = lower, 1 = upper

        extremes = pd.DataFrame({
            'price': prices,
            'zscore': zscore,
            'middle_band': middle_band,
            'upper_band': upper_band,
            'lower_band': lower_band,
            'band_position': band_position,
            'is_overbought': prices > upper_band,
            'is_oversold': prices < lower_band,
            'distance_from_mean': prices - middle_band,
            'distance_pct': ((prices - middle_band) / middle_band) * 100
        })

        return extremes

    def reversion_probability(self, prices: pd.Series) -> pd.Series:
        """
        Calculate probability of mean reversion (0-1)

        Higher probability when:
        - Price far from mean (high Z-score)
        - Price outside Bollinger Bands
        - Recent momentum exhausted (would need momentum data)

        Args:
            prices: Series of price data

        Returns:
            Series of reversion probabilities (0-1)
        """
        extremes = self.detect_extremes(prices)

        # Base probability on Z-score magnitude
        zscore_prob = np.abs(extremes['zscore']) / 3.0  # Normalize to ~0-1
        zscore_prob = np.clip(zscore_prob, 0, 1)

        # Boost probability if outside bands
        outside_bands = (extremes['is_overbought'] | extremes['is_oversold']).astype(float) * 0.3

        # Combined probability
        reversion_prob = np.clip(zscore_prob + outside_bands, 0, 1)

        return reversion_prob

    def calculate_expected_reversion_target(self, prices: pd.Series) -> pd.DataFrame:
        """
        Calculate expected mean reversion target and distance

        Args:
            prices: Series of price data

        Returns:
            DataFrame with reversion targets and expected % moves
        """
        extremes = self.detect_extremes(prices)

        # Target is typically the middle band (mean)
        reversion_target = extremes['middle_band']

        # Calculate expected move %
        expected_move_pct = ((reversion_target - prices) / prices) * 100

        targets = pd.DataFrame({
            'current_price': prices,
            'reversion_target': reversion_target,
            'expected_move': reversion_target - prices,
            'expected_move_pct': expected_move_pct,
            'risk_reward_ratio': np.abs(expected_move_pct) / 0.15  # Assume 0.15% stop loss
        })

        return targets


class MeanReversionStrategy:
    """
    Generate trading signals for mean reversion trades
    """

    def __init__(self, detector: MeanReversionDetector, min_zscore: float = 2.0):
        """
        Initialize strategy

        Args:
            detector: MeanReversionDetector instance
            min_zscore: Minimum Z-score to trigger signal
        """
        self.detector = detector
        self.min_zscore = min_zscore

    def generate_short_signals(self, prices: pd.Series) -> pd.DataFrame:
        """
        Generate short signals for mean reversion

        Signal triggers when:
        1. Price is significantly above mean (Z-score > threshold)
        2. Price is outside upper Bollinger Band
        3. High reversion probability

        Args:
            prices: Series of price data

        Returns:
            DataFrame with signals and expected targets
        """
        extremes = self.detector.detect_extremes(prices)
        reversion_prob = self.detector.reversion_probability(prices)
        targets = self.detector.calculate_expected_reversion_target(prices)

        signals = pd.DataFrame({
            'price': prices,
            'zscore': extremes['zscore'],
            'is_overbought': extremes['is_overbought'],
            'reversion_probability': reversion_prob,
            'reversion_target': targets['reversion_target'],
            'expected_move_pct': targets['expected_move_pct'],
            'risk_reward_ratio': targets['risk_reward_ratio'],
            'signal': False
        })

        # Generate signal
        signals['signal'] = (
            (signals['zscore'] > self.min_zscore) &  # Significantly above mean
            (signals['is_overbought']) &  # Outside upper band
            (signals['reversion_probability'] > 0.7)  # High reversion probability
        )

        # Signal strength (0-1)
        signals['signal_strength'] = np.where(
            signals['signal'],
            np.clip(signals['reversion_probability'], 0, 1),
            0
        )

        return signals

    def calculate_entry_exit_levels(self,
                                    current_price: float,
                                    reversion_target: float,
                                    take_profit_pct: float = 0.2,
                                    stop_loss_pct: float = 0.15) -> dict:
        """
        Calculate exact entry, take-profit, and stop-loss levels

        Args:
            current_price: Current market price
            reversion_target: Expected reversion target
            take_profit_pct: Take profit percentage (default 0.2%)
            stop_loss_pct: Stop loss percentage (default 0.15%)

        Returns:
            Dictionary with entry/exit levels
        """
        # For shorts
        take_profit_price = current_price * (1 - take_profit_pct / 100)
        stop_loss_price = current_price * (1 + stop_loss_pct / 100)

        # Calculate risk/reward
        potential_profit = current_price - take_profit_price
        potential_loss = stop_loss_price - current_price
        risk_reward = potential_profit / potential_loss if potential_loss > 0 else 0

        return {
            'entry_price': current_price,
            'take_profit': take_profit_price,
            'stop_loss': stop_loss_price,
            'potential_profit_pct': take_profit_pct,
            'potential_loss_pct': stop_loss_pct,
            'risk_reward_ratio': risk_reward,
            'reversion_target': reversion_target
        }


# Example usage
if __name__ == "__main__":
    # Example with sample data
    np.random.seed(42)

    # Simulate price movement with mean reversion
    dates = pd.date_range('2024-01-01', periods=200, freq='1min')

    # Create prices that deviate and revert
    trend = np.sin(np.linspace(0, 4 * np.pi, 200)) * 5
    noise = np.random.randn(200) * 0.5
    prices = pd.Series(100 + trend + noise, index=dates)

    # Create detector
    detector = MeanReversionDetector(window=20, num_std=2.0)
    strategy = MeanReversionStrategy(detector, min_zscore=2.0)

    # Generate signals
    signals = strategy.generate_short_signals(prices)

    # Show recent signals
    recent_signals = signals[signals['signal']].tail(5)

    print("Mean Reversion Analysis Example:")
    print(f"\nCurrent price: ${prices.iloc[-1]:.2f}")
    print(f"Current Z-score: {signals['zscore'].iloc[-1]:.2f}")
    print(f"Reversion probability: {signals['reversion_probability'].iloc[-1]:.2%}")
    print(f"\nRecent signals:")
    print(recent_signals[['price', 'zscore', 'expected_move_pct', 'signal_strength']])

    # Calculate entry/exit for latest signal
    if len(recent_signals) > 0:
        latest = recent_signals.iloc[-1]
        levels = strategy.calculate_entry_exit_levels(
            current_price=latest['price'],
            reversion_target=latest['reversion_target']
        )
        print(f"\nEntry/Exit Levels:")
        for key, value in levels.items():
            if 'price' in key or 'profit' in key or 'loss' in key or 'target' in key:
                print(f"  {key}: ${value:.2f}")
            else:
                print(f"  {key}: {value:.2f}")
