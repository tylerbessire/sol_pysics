"""
Order Book Analysis

Analyze order book depth and structure to:
1. Identify buy/sell walls (large orders)
2. Detect imbalances that precede liquidations
3. Visualize order book as gravitational field

Large orders act as "gravity wells" that attract price movement.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class OrderBookLevel:
    """Single order book price level"""
    price: float
    size: float
    side: str  # 'bid' or 'ask'
    orders: int  # Number of orders at this level


@dataclass
class OrderBookSnapshot:
    """Complete order book snapshot"""
    timestamp: pd.Timestamp
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    mid_price: float
    spread: float


class OrderBookAnalyzer:
    """
    Analyze order book structure and imbalances
    """

    def __init__(self, depth_levels: int = 20):
        """
        Initialize order book analyzer

        Args:
            depth_levels: Number of price levels to analyze on each side
        """
        self.depth_levels = depth_levels

    def calculate_order_book_imbalance(self,
                                      bids: pd.DataFrame,
                                      asks: pd.DataFrame) -> float:
        """
        Calculate order book imbalance

        Imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
        Range: -1 (all asks) to +1 (all bids)

        Args:
            bids: DataFrame with bid orders (price, size)
            asks: DataFrame with ask orders (price, size)

        Returns:
            Imbalance ratio (-1 to 1)
        """
        total_bid_volume = bids['size'].sum()
        total_ask_volume = asks['size'].sum()

        if total_bid_volume + total_ask_volume == 0:
            return 0.0

        imbalance = (total_bid_volume - total_ask_volume) / (total_bid_volume + total_ask_volume)

        return imbalance

    def find_order_walls(self,
                        orders: pd.DataFrame,
                        threshold_multiplier: float = 3.0) -> pd.DataFrame:
        """
        Find large "walls" in the order book

        Walls are orders significantly larger than average

        Args:
            orders: DataFrame with orders (price, size)
            threshold_multiplier: How many times average size to count as wall

        Returns:
            DataFrame with walls
        """
        avg_size = orders['size'].mean()
        threshold = avg_size * threshold_multiplier

        walls = orders[orders['size'] >= threshold].copy()
        walls['size_multiple'] = walls['size'] / avg_size

        return walls.sort_values('size', ascending=False)

    def calculate_depth_pressure(self,
                                 bids: pd.DataFrame,
                                 asks: pd.DataFrame,
                                 distance_levels: int = 10) -> Dict[str, float]:
        """
        Calculate buying/selling pressure at different depths

        Args:
            bids: DataFrame with bid orders
            asks: DataFrame with ask orders
            distance_levels: Number of levels to analyze

        Returns:
            Dictionary with pressure metrics
        """
        # Take top N levels
        top_bids = bids.nlargest(distance_levels, 'price')
        top_asks = asks.nsmallest(distance_levels, 'price')

        near_bid_pressure = top_bids.head(5)['size'].sum()
        far_bid_pressure = top_bids.tail(5)['size'].sum()

        near_ask_pressure = top_asks.head(5)['size'].sum()
        far_ask_pressure = top_asks.tail(5)['size'].sum()

        return {
            'near_bid_pressure': near_bid_pressure,
            'far_bid_pressure': far_bid_pressure,
            'near_ask_pressure': near_ask_pressure,
            'far_ask_pressure': far_ask_pressure,
            'bid_depth_ratio': near_bid_pressure / (far_bid_pressure + 1),
            'ask_depth_ratio': near_ask_pressure / (far_ask_pressure + 1),
            'total_bid_pressure': near_bid_pressure + far_bid_pressure,
            'total_ask_pressure': near_ask_pressure + far_ask_pressure
        }

    def detect_spoofing(self,
                       order_book_history: List[OrderBookSnapshot],
                       wall_threshold: float = 3.0,
                       cancel_time_threshold: int = 30) -> List[Dict]:
        """
        Detect potential spoofing (fake walls that get cancelled)

        Args:
            order_book_history: Historical order book snapshots
            wall_threshold: Size multiple to count as wall
            cancel_time_threshold: Seconds before considering wall as spoofing

        Returns:
            List of potential spoofing events
        """
        spoofing_events = []

        # Track walls that appear and disappear quickly
        # (Implementation would track walls across snapshots)

        return spoofing_events

    def calculate_gravity_field(self,
                               bids: pd.DataFrame,
                               asks: pd.DataFrame,
                               current_price: float) -> pd.DataFrame:
        """
        Model order book as gravitational field

        Large orders = massive objects creating gravity wells
        Price attracted to large orders

        Args:
            bids: DataFrame with bid orders
            asks: DataFrame with ask orders
            current_price: Current market price

        Returns:
            DataFrame with gravity field strength at each price level
        """
        # Combine all orders
        all_orders = pd.concat([bids, asks])

        # Calculate "gravitational force" from each order
        # F = G * (m1 * m2) / r^2
        # Here: F = order_size / distance^2

        all_orders['distance'] = np.abs(all_orders['price'] - current_price)
        all_orders['gravity_strength'] = all_orders['size'] / (all_orders['distance'] ** 2 + 0.01)

        # Group by price level
        gravity_field = all_orders.groupby('price').agg({
            'size': 'sum',
            'gravity_strength': 'sum',
            'distance': 'first'
        }).reset_index()

        gravity_field = gravity_field.sort_values('gravity_strength', ascending=False)

        return gravity_field

    def predict_support_resistance(self,
                                   bids: pd.DataFrame,
                                   asks: pd.DataFrame,
                                   current_price: float) -> Dict[str, float]:
        """
        Predict support and resistance levels from order book

        Support = large bid walls below price
        Resistance = large ask walls above price

        Args:
            bids: DataFrame with bid orders
            asks: DataFrame with ask orders
            current_price: Current market price

        Returns:
            Dictionary with support/resistance levels
        """
        # Find walls
        bid_walls = self.find_order_walls(bids)
        ask_walls = self.find_order_walls(asks)

        # Support = strongest bid wall below current price
        support_walls = bid_walls[bid_walls['price'] < current_price]
        if len(support_walls) > 0:
            strongest_support = support_walls.iloc[0]
            support_price = strongest_support['price']
            support_strength = strongest_support['size']
        else:
            support_price = current_price * 0.99
            support_strength = 0

        # Resistance = strongest ask wall above current price
        resistance_walls = ask_walls[ask_walls['price'] > current_price]
        if len(resistance_walls) > 0:
            strongest_resistance = resistance_walls.iloc[0]
            resistance_price = strongest_resistance['price']
            resistance_strength = strongest_resistance['size']
        else:
            resistance_price = current_price * 1.01
            resistance_strength = 0

        return {
            'support_price': support_price,
            'support_strength': support_strength,
            'support_distance_pct': ((current_price - support_price) / current_price) * 100,
            'resistance_price': resistance_price,
            'resistance_strength': resistance_strength,
            'resistance_distance_pct': ((resistance_price - current_price) / current_price) * 100
        }


class OrderBookVisualizationData:
    """
    Prepare order book data for visualization
    """

    @staticmethod
    def prepare_3d_order_book(bids: pd.DataFrame,
                              asks: pd.DataFrame,
                              depth: int = 20) -> Dict:
        """
        Prepare data for 3D order book visualization

        Args:
            bids: DataFrame with bid orders
            asks: DataFrame with ask orders
            depth: Number of levels to include

        Returns:
            Dictionary with visualization data
        """
        top_bids = bids.nlargest(depth, 'price')
        top_asks = asks.nsmallest(depth, 'price')

        return {
            'bid_prices': top_bids['price'].tolist(),
            'bid_sizes': top_bids['size'].tolist(),
            'ask_prices': top_asks['price'].tolist(),
            'ask_sizes': top_asks['size'].tolist(),
            'mid_price': (top_bids['price'].iloc[0] + top_asks['price'].iloc[0]) / 2
        }

    @staticmethod
    def prepare_heatmap_data(order_book_history: List[OrderBookSnapshot],
                            price_levels: int = 50) -> pd.DataFrame:
        """
        Prepare order book heatmap data (time vs price vs volume)

        Args:
            order_book_history: Historical order book snapshots
            price_levels: Number of price levels for heatmap

        Returns:
            DataFrame with heatmap data
        """
        # Create price bins
        all_prices = []
        for snapshot in order_book_history:
            all_prices.extend([b.price for b in snapshot.bids])
            all_prices.extend([a.price for a in snapshot.asks])

        price_min = min(all_prices)
        price_max = max(all_prices)
        price_bins = np.linspace(price_min, price_max, price_levels)

        # Build heatmap matrix
        heatmap_data = []
        for snapshot in order_book_history:
            # Aggregate orders into price bins
            row = {'timestamp': snapshot.timestamp}

            # (Simplified - would need full implementation to bin orders)
            for price_bin in price_bins:
                row[f'price_{price_bin:.2f}'] = 0  # Volume at this price level

            heatmap_data.append(row)

        return pd.DataFrame(heatmap_data)


# Example usage
if __name__ == "__main__":
    # Example order book data
    np.random.seed(42)

    current_price = 100.0

    # Generate sample order book
    bid_prices = np.linspace(99.5, 99.9, 20)
    bid_sizes = np.random.randint(100, 1000, 20)
    bids = pd.DataFrame({'price': bid_prices, 'size': bid_sizes})

    # Add a large buy wall
    bids = pd.concat([bids, pd.DataFrame({'price': [99.0], 'size': [5000]})], ignore_index=True)

    ask_prices = np.linspace(100.1, 100.5, 20)
    ask_sizes = np.random.randint(100, 1000, 20)
    asks = pd.DataFrame({'price': ask_prices, 'size': ask_sizes})

    # Add a large sell wall
    asks = pd.concat([asks, pd.DataFrame({'price': [101.0], 'size': [6000]})], ignore_index=True)

    # Analyze
    analyzer = OrderBookAnalyzer()

    imbalance = analyzer.calculate_order_book_imbalance(bids, asks)
    bid_walls = analyzer.find_order_walls(bids)
    ask_walls = analyzer.find_order_walls(asks)
    pressure = analyzer.calculate_depth_pressure(bids, asks)
    support_resistance = analyzer.predict_support_resistance(bids, asks, current_price)
    gravity_field = analyzer.calculate_gravity_field(bids, asks, current_price)

    print("Order Book Analysis Example:")
    print(f"\nCurrent price: ${current_price:.2f}")
    print(f"Order book imbalance: {imbalance:.3f}")
    print(f"\nBid walls found: {len(bid_walls)}")
    if len(bid_walls) > 0:
        print(f"  Largest: ${bid_walls.iloc[0]['price']:.2f} - {bid_walls.iloc[0]['size']:.0f} units")
    print(f"\nAsk walls found: {len(ask_walls)}")
    if len(ask_walls) > 0:
        print(f"  Largest: ${ask_walls.iloc[0]['price']:.2f} - {ask_walls.iloc[0]['size']:.0f} units")

    print(f"\nSupport/Resistance:")
    print(f"  Support: ${support_resistance['support_price']:.2f} ({support_resistance['support_distance_pct']:.2f}% away)")
    print(f"  Resistance: ${support_resistance['resistance_price']:.2f} ({support_resistance['resistance_distance_pct']:.2f}% away)")

    print(f"\nTop 3 gravity wells:")
    print(gravity_field.head(3)[['price', 'size', 'gravity_strength']])
