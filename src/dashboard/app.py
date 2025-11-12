"""
Real-Time Trading Dashboard

Visualizes:
- Liquidation bubbles in real-time
- Physics gauges (momentum, acceleration, terminal velocity)
- 3D order book visualization
- Energy heat maps
- Entry/exit signals

Run with: python src/dashboard/app.py
"""

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.momentum import MomentumCalculator
from models.terminal_velocity import TerminalVelocityDetector
from analysis.liquidations import LiquidationDetector


# Initialize Dash app with dark theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
app.title = "Perfect Timing Analysis - Physics Trading Dashboard"


# Layout
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("⚛️ Perfect Timing Analysis", className="text-center mb-4"),
            html.H5("Physics-Based Liquidation Cascade Trading", className="text-center text-muted mb-4")
        ])
    ]),

    # Status Row
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Current Price", className="card-subtitle"),
                    html.H3(id="current-price", children="$0.00", className="text-success")
                ])
            ])
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Momentum", className="card-subtitle"),
                    html.H3(id="momentum-value", children="0.00", className="text-info")
                ])
            ])
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Cascade Phase", className="card-subtitle"),
                    html.H3(id="cascade-phase", children="Normal", className="text-warning")
                ])
            ])
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Signal Strength", className="card-subtitle"),
                    html.H3(id="signal-strength", children="0%", className="text-danger")
                ])
            ])
        ], width=3),
    ], className="mb-4"),

    # Main Charts Row
    dbc.Row([
        # Price Chart with Liquidation Bubbles
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("💥 Price & Liquidation Bubbles"),
                dbc.CardBody([
                    dcc.Graph(id="price-liquidation-chart", style={'height': '400px'})
                ])
            ])
        ], width=8),

        # Physics Gauges
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("⚡ Physics Gauges"),
                dbc.CardBody([
                    dcc.Graph(id="momentum-gauge", style={'height': '120px'}),
                    dcc.Graph(id="acceleration-gauge", style={'height': '120px'}),
                    dcc.Graph(id="terminal-velocity-gauge", style={'height': '120px'})
                ])
            ])
        ], width=4),
    ], className="mb-4"),

    # Order Book and Energy Row
    dbc.Row([
        # 3D Order Book
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📊 Order Book Depth"),
                dbc.CardBody([
                    dcc.Graph(id="order-book-chart", style={'height': '300px'})
                ])
            ])
        ], width=6),

        # Energy Heat Map
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🔥 Energy Flow Map"),
                dbc.CardBody([
                    dcc.Graph(id="energy-heatmap", style={'height': '300px'})
                ])
            ])
        ], width=6),
    ], className="mb-4"),

    # Trading Signals Row
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🎯 Active Signals"),
                dbc.CardBody([
                    html.Div(id="active-signals", children=[
                        html.P("Waiting for terminal velocity signal...", className="text-muted")
                    ])
                ])
            ])
        ], width=12),
    ], className="mb-4"),

    # Update interval
    dcc.Interval(
        id='interval-component',
        interval=1*1000,  # Update every 1 second
        n_intervals=0
    ),

    # Store for historical data
    dcc.Store(id='historical-data')

], fluid=True, className="p-4")


# Callback functions
@app.callback(
    [
        Output("current-price", "children"),
        Output("momentum-value", "children"),
        Output("cascade-phase", "children"),
        Output("signal-strength", "children"),
        Output("price-liquidation-chart", "figure"),
        Output("momentum-gauge", "figure"),
        Output("acceleration-gauge", "figure"),
        Output("terminal-velocity-gauge", "figure"),
        Output("order-book-chart", "figure"),
        Output("energy-heatmap", "figure"),
        Output("active-signals", "children"),
    ],
    [Input("interval-component", "n_intervals")]
)
def update_dashboard(n):
    """
    Update all dashboard components

    In production, this would fetch real-time data from exchange APIs.
    For now, we'll generate sample data for demonstration.
    """

    # Generate sample data (replace with real exchange data)
    np.random.seed(n)

    # Sample price data
    dates = pd.date_range(datetime.now() - timedelta(minutes=100), periods=100, freq='1min')
    prices = pd.Series(100 + np.cumsum(np.random.randn(100) * 0.2), index=dates)
    volumes = pd.Series(np.random.randint(1000, 5000, 100), index=dates)

    # Calculate physics metrics
    calc = MomentumCalculator()
    velocities = calc.calculate_velocity(prices)
    accelerations = calc.calculate_acceleration(velocities)
    momentum = calc.calculate_momentum(prices, volumes)

    current_price = prices.iloc[-1]
    current_momentum = momentum.iloc[-1] if not pd.isna(momentum.iloc[-1]) else 0
    current_acceleration = accelerations.iloc[-1] if not pd.isna(accelerations.iloc[-1]) else 0

    # Determine cascade phase
    if abs(current_momentum) > abs(momentum.mean()) * 2:
        cascade_phase = "⚠️ CASCADE"
        phase_color = "text-danger"
    elif abs(current_acceleration) < 0.1:
        cascade_phase = "🎯 TERMINAL V"
        phase_color = "text-success"
    else:
        cascade_phase = "📊 Normal"
        phase_color = "text-muted"

    # Signal strength
    signal_strength = min(abs(current_momentum) / (abs(momentum.mean()) * 2), 1.0)
    signal_pct = f"{signal_strength * 100:.0f}%"

    # Price chart with liquidation bubbles
    price_chart = create_price_liquidation_chart(prices, volumes, momentum)

    # Physics gauges
    momentum_gauge = create_gauge("Momentum", current_momentum, -100, 100)
    acceleration_gauge = create_gauge("Acceleration", current_acceleration, -2, 2)
    terminal_v_gauge = create_gauge("Terminal V", signal_strength, 0, 1)

    # Order book chart
    order_book_chart = create_order_book_chart(current_price)

    # Energy heatmap
    energy_heatmap = create_energy_heatmap(momentum)

    # Active signals
    active_signals = create_signal_list(signal_strength, current_price)

    return (
        f"${current_price:.2f}",
        f"{current_momentum:.2f}",
        cascade_phase,
        signal_pct,
        price_chart,
        momentum_gauge,
        acceleration_gauge,
        terminal_v_gauge,
        order_book_chart,
        energy_heatmap,
        active_signals
    )


def create_price_liquidation_chart(prices, volumes, momentum):
    """Create price chart with liquidation bubbles"""

    # Detect liquidation events (volume spikes)
    volume_threshold = volumes.mean() * 2
    liquidations = volumes > volume_threshold

    fig = go.Figure()

    # Price line
    fig.add_trace(go.Scatter(
        x=prices.index,
        y=prices.values,
        mode='lines',
        name='Price',
        line=dict(color='#00ff00', width=2)
    ))

    # Liquidation bubbles
    liq_times = prices.index[liquidations]
    liq_prices = prices.values[liquidations]
    liq_sizes = volumes.values[liquidations] / 100  # Scale for visibility

    fig.add_trace(go.Scatter(
        x=liq_times,
        y=liq_prices,
        mode='markers',
        name='Liquidations',
        marker=dict(
            size=liq_sizes,
            color='red',
            opacity=0.6,
            line=dict(color='white', width=1)
        )
    ))

    fig.update_layout(
        template='plotly_dark',
        showlegend=True,
        margin=dict(l=40, r=40, t=20, b=40),
        xaxis_title="Time",
        yaxis_title="Price ($)",
        hovermode='x unified'
    )

    return fig


def create_gauge(title, value, min_val, max_val):
    """Create a gauge chart"""

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={'text': title, 'font': {'size': 14}},
        gauge={
            'axis': {'range': [min_val, max_val]},
            'bar': {'color': "#00ff00"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [min_val, min_val + (max_val - min_val) * 0.33], 'color': '#1e1e1e'},
                {'range': [min_val + (max_val - min_val) * 0.33, min_val + (max_val - min_val) * 0.66], 'color': '#2a2a2a'},
                {'range': [min_val + (max_val - min_val) * 0.66, max_val], 'color': '#363636'}
            ],
        }
    ))

    fig.update_layout(
        template='plotly_dark',
        height=120,
        margin=dict(l=20, r=20, t=30, b=10)
    )

    return fig


def create_order_book_chart(current_price):
    """Create order book depth chart"""

    # Sample order book data
    bid_prices = np.linspace(current_price - 2, current_price - 0.1, 20)
    bid_sizes = np.random.randint(100, 1000, 20)

    ask_prices = np.linspace(current_price + 0.1, current_price + 2, 20)
    ask_sizes = np.random.randint(100, 1000, 20)

    fig = go.Figure()

    # Bids (green)
    fig.add_trace(go.Bar(
        x=bid_sizes,
        y=bid_prices,
        orientation='h',
        name='Bids',
        marker=dict(color='green'),
        opacity=0.7
    ))

    # Asks (red)
    fig.add_trace(go.Bar(
        x=ask_sizes,
        y=ask_prices,
        orientation='h',
        name='Asks',
        marker=dict(color='red'),
        opacity=0.7
    ))

    # Current price line
    fig.add_hline(y=current_price, line_dash="dash", line_color="yellow", annotation_text="Current Price")

    fig.update_layout(
        template='plotly_dark',
        showlegend=True,
        margin=dict(l=40, r=40, t=20, b=40),
        xaxis_title="Size",
        yaxis_title="Price ($)",
        barmode='overlay'
    )

    return fig


def create_energy_heatmap(momentum):
    """Create energy flow heatmap"""

    # Create rolling window heatmap
    window_size = 20
    data = []
    for i in range(len(momentum) - window_size):
        data.append(momentum.iloc[i:i+window_size].values)

    fig = go.Figure(data=go.Heatmap(
        z=data,
        colorscale='RdYlGn_r',
        showscale=True
    ))

    fig.update_layout(
        template='plotly_dark',
        margin=dict(l=40, r=40, t=20, b=40),
        xaxis_title="Time Window",
        yaxis_title="Period"
    )

    return fig


def create_signal_list(signal_strength, current_price):
    """Create active signals list"""

    if signal_strength > 0.7:
        return html.Div([
            dbc.Alert([
                html.H5("🎯 TERMINAL VELOCITY DETECTED", className="alert-heading"),
                html.P(f"Entry Price: ${current_price:.2f}"),
                html.P(f"Take Profit: ${current_price * 0.998:.2f} (0.2%)"),
                html.P(f"Stop Loss: ${current_price * 1.0015:.2f} (0.15%)"),
                html.P(f"Signal Strength: {signal_strength * 100:.0f}%"),
            ], color="success")
        ])
    elif signal_strength > 0.4:
        return html.Div([
            dbc.Alert([
                html.P("⚠️ Potential cascade building..."),
                html.P(f"Signal Strength: {signal_strength * 100:.0f}%"),
            ], color="warning")
        ])
    else:
        return html.P("Waiting for terminal velocity signal...", className="text-muted")


if __name__ == '__main__':
    print("Starting Perfect Timing Analysis Dashboard...")
    print("Open your browser to: http://localhost:8050")
    app.run_server(debug=True, host='0.0.0.0', port=8050)
