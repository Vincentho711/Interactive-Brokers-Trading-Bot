import pathlib
import pandas as pd
import json
import pathlib
import operator
import time as time_true

from pprint import pprint
from datetime import time
from datetime import datetime
from datetime import timezone
from configparser import ConfigParser

from ibw.client import IBClient
from robot.trader import Trader
from robot.stock_frame import StockFrame
from robot.indicator import Indicators
from robot.portfolio import Portfolio
from robot.trades import Trade


# This script is used to test the newly implemented functions associated to ticker indicators

# Grab configuration values.
config = ConfigParser()
file_path = pathlib.Path('config/config.ini').resolve()
config.read(file_path)

# Load the details.
paper_account = config.get('main', 'PAPER_ACCOUNT')
paper_username = config.get('main', 'PAPER_USERNAME')
regular_account = config.get('main','REGULAR_ACCOUNT')
regular_username = config.get('main','REGULAR_USERNAME')

# Create a new trader object
trader = Trader(
    username=paper_username,
    account=paper_account
)

# Grabbing account data
pprint("Account details: ")
pprint("-"*80)
pprint(trader._account_data)
pprint("="*80)

# '2665586' = 'AAPL', '272093' = 'MSFT'
conids_list = ['265598','272093']
exchange_list = ['NYSE','NASDAQ']

# Query historical prices for stocks of interest
historical_prices_list = trader.get_historical_prices(
    period='30d',
    bar='1d',
    conids=conids_list
)

# Create a stock frame object
stock_frame_client = trader.create_stock_frame(trader.historical_prices['aggregated'])

# Create a indicator object
indicator_client = Indicators(
    price_df=stock_frame_client
)

# Add an indicator
indicator_client.rsi(period=14)

# Associate rsi indicator to the ticker 'AAPL'
indicator_client.set_ticker_indicator_signal(
    ticker='AAPL',
    indicator='rsi',
    buy_cash_quantity=50.0,
    close_position_when_sell=True,
    buy=30.0,
    sell=70.0,
    condition_buy=operator.ge,
    condition_sell=operator.le,
)

# Add a MACD indicator
indicator_client.macd(fast_period=12,slow_period=26)

# Associate macd indicator to the ticker 'AAPL'
indicator_client.set_ticker_indicator_signal(
    ticker='AAPL',
    indicator='macd',
    buy_cash_quantity=100.0,
    close_position_when_sell=True,
    
) 
# Check indicators 
pprint("Ticker indicators key: ")
pprint("-"*80)
pprint(indicator_client._ticker_indicators_key)
pprint("="*80)

# Print every indicator associated with every ticker
for ticker in indicator_client._ticker_indicator_signals:
    pprint(f"Indicators for {ticker}:")
    pprint("-"*80)
    for count, indicator in enumerate(indicator_client._ticker_indicator_signals[ticker],start=1):
        pprint(f"{count}: {str(indicator)}")
        pprint(indicator_client._ticker_indicator_signals[ticker][indicator])
        pprint("="*80)
        pprint("")






