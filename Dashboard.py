import warnings
import datetime
import numpy as np
import time
from tenacity import retry, wait_exponential, stop_after_attempt
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, html, dcc, Input, Output
from functools import lru_cache

warnings.filterwarnings("ignore", category=FutureWarning)

# Custom styles
styles = {
    'background': '#111111',
    'text': '#ffffff',
    'buttonBg': '#ff6600',
    'buttonText': '#ffffff',
    'buttonHover': '#cc5200',
}

# Retry decorator with exponential backoff and a maximum of 5 attempts
@retry(wait=wait_exponential(multiplier=1, min=4, max=60), stop=stop_after_attempt(5))
def fetch_data(symbol, period="1y", interval="1d"):
    data = yf.download(symbol, period=period, interval=interval)
    return data

# LRU cache decorator for caching data
@lru_cache(maxsize=128)
def get_cached_data(symbol, period, interval):
    return fetch_data(symbol, period, interval)

# Let's make a reusable function to create the price indicator for different symbols
def price_indicator(symbol):
    ticker = yf.Ticker(symbol)
    info = ticker.info

    # Check if the 'regularMarketPrice' key exists
    if 'regularMarketPrice' in info:
        open_price = info["regularMarketOpen"]
        current_price = info["regularMarketPrice"]
    else:
        # If the key is not available, use the current price from the fetched data
        data = get_cached_data(symbol, period="1d", interval="1d")
        open_price = data.iloc[0]['Open']
        current_price = data.iloc[-1]['Close']

    delta_fig = go.Figure(layout={
        'plot_bgcolor': styles['background'],
        'paper_bgcolor': styles['background'],
        'font': {'color': styles['text']}
    })

    delta_fig.add_trace(go.Indicator(
                    title={"text": f"{symbol.upper()} Current Price"},
                    delta={'reference': open_price, "valueformat": ".2f"},
                    mode="number+delta",
                    value=current_price,
                    number={"prefix": "$", "valueformat": ".2f"}))
    return delta_fig

# Another function to create charts for different tickers
def candlestick_chart(symbol, period="1y", interval="1d", prediction_days=10):
    data = get_cached_data(symbol, period, interval)
    data = data.reset_index()

    fig = make_subplots(rows=2, cols=1,
                        shared_xaxes=True,
                        subplot_titles=(f'{symbol.upper()} OHLC', 'Volume'),
                        row_heights=[0.7, 0.3],
                        x_title=None
                        )

    fig.add_trace(go.Candlestick(x=data['Date'],
                                  open=data['Open'],
                                  high=data['High'],
                                  low=data['Low'],
                                  close=data['Close'],
                                  showlegend=False),
                   row=1, col=1,
                   )

    fig.add_trace(go.Scatter(x=data['Date'], y=data['Volume'], mode='lines', showlegend=False), row=2, col=1)

    fig.update(layout_xaxis_rangeslider_visible=False)

    # Update layout with custom styles
    fig.update_layout(
        plot_bgcolor=styles['background'],
        paper_bgcolor=styles['background'],
        font_color=styles['text']
    )

    return fig

# Function to create a prediction chart
def prediction_chart(symbol, prediction_days=10):
    data = get_cached_data(symbol, period="1y", interval="1d")
    current_date = data.index[-1]
    prediction_dates = [current_date + datetime.timedelta(days=i) for i in range(1, prediction_days + 1)]  # Get dates for prediction

    # Perform your prediction logic here
    # For demonstration, let's create some dummy predicted prices
    predicted_prices = [data['Close'].iloc[-1] + i for i in range(1, prediction_days + 1)]

    fig = go.Figure()

    # Add a scatter plot for actual prices
    fig.add_trace(go.Scatter(x=data.index, y=data['Close'], mode='lines', name='Actual Prices', line=dict(color='blue')))

    # Add a line plot for predicted prices
    fig.add_trace(go.Scatter(x=prediction_dates, y=predicted_prices, mode='lines', name='Predicted Prices', line=dict(color='green')))

    fig.update_layout(title=f'{symbol.upper()} Price Prediction for Next {prediction_days} Days',
                      xaxis_title='Date',
                      yaxis_title='Price',
                      plot_bgcolor=styles['background'],
                      paper_bgcolor=styles['background'],
                      font_color=styles['text']
                      )

    return fig

# Build App
app = Dash(__name__)

# Initialize with default values
symbol = "aapl"
price_chart = candlestick_chart(symbol, "1y", "1d")
price_metric = price_indicator(symbol)
prediction_days = 10
prediction_fig = prediction_chart(symbol, prediction_days)

# Update the layout to include an input field for prediction days
app.layout = html.Div(
    style={'backgroundColor': styles['background'], 'color': styles['text'], 'padding': '20px'},
    children=[
        html.Header(
            [
                html.H1(children="Stock Dashboard"),
                html.Span([
                    dcc.Input(id='my-input', type='text', value=symbol, placeholder="input ticker symbol", className="form-control",
                              style={'backgroundColor': styles['background'], 'color': styles['text'], 'border': '1px solid #555555', 'fontSize': '16px', 'padding': '10px'}),
                    dcc.Input(id='prediction-days', type='number', value=prediction_days, placeholder="input number of days", className="form-control",
                              style={'backgroundColor': styles['background'], 'color': styles['text'], 'border': '1px solid #555555', 'fontSize': '16px', 'padding': '10px', 'marginLeft': '10px'}),
                    html.Button(id='submit-button-state', n_clicks=0, children='Submit', className="btn",
                                 style={'backgroundColor': styles['buttonBg'], 'color': styles['buttonText'], 'borderColor': styles['buttonBg'], 'marginLeft': '10px', 'padding': '5px 10px', 'fontSize': '14px', 'borderRadius': '5px'}),
                ],
                className="d-flex align-items-center"
             )
            ],
            className="navbar"
        ),
        html.P("This dashboard displays metrics about your favorite stock tickers", style={'marginBottom': '20px'}),
        html.Div([
            dcc.Graph(id='price-metric', figure=price_metric),
        ], id="first-data"),
        html.Div([
            dcc.Graph(id='price-history', figure=price_chart),
            dcc.Graph(id='prediction-chart', figure=prediction_fig)
        ], id="second-data")
    ]
)

# Update the callback to include prediction days input
@app.callback(
    [Output('price-metric', 'figure'),
     Output('price-history', 'figure'),
     Output('prediction-chart', 'figure')],
    [Input('my-input', 'value'),
     Input('prediction-days', 'value')]
)
def update_charts(symbol, prediction_days):
    try:
        prediction_days = int(prediction_days)  # Convert input to integer
        price_metric = price_indicator(symbol)
        price_chart = candlestick_chart(symbol, "1y", "1d")
        prediction_fig = prediction_chart(symbol, prediction_days)
        return price_metric, price_chart, prediction_fig
    except Exception as e:
        return go.Figure(), go.Figure(), go.Figure()

if __name__ == '__main__':
    app.run_server(debug=True)
