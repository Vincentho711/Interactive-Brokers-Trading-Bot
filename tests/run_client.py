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

# First, the script setup.py has to be run once to configure the libraries when you use this library \
# for the first time.
# Before running the run_client.py script, ensure that there is a config.ini file with the correct account info.
# If you don't have this yet. Enter your credentials in wirte_config.py and run it.
# A clientportal.gw will be created within the parent directory when it is run the first time.
# Running it the first time will result in an error code as a local server has not been set up.
# Kill the script, then head to the clientportal.gw in file explorer, run the command \
# "bin/run.bat" "root/conf.yaml" in Git Bash to start the local server.
# Go to "localhost:5000" in your preferred browser and log in with the same credentials provided \
# in config.ini.
# Keep the browser opened.
# After the browser displays "client login succeeds", you can run the following script and the bot \
# take control of the operation.
# See https://interactivebrokers.github.io/cpwebapi/ for the detail setup, java has to be installed on \
# your local machine to run properly.

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


# Grabbing contract detials with symbols()
query_symbols = ['AAPL','MSFT','SCHW']
pprint("Contract details by symbols: ")
pprint("-"*80)
pprint(trader.contract_details_by_symbols(query_symbols))
pprint("="*80)

# Grabbing the conid for a specific symbol
# List the exchanges you trade in, best to keep it concise to prevent errors
exchange_list = ['NASDAQ','NYSE']
query_symbol = 'TSLA'
pprint("Symbol to conid: ")
pprint("-"*80)
response = trader.symbol_to_conid(symbol=query_symbol,exchange=exchange_list)
pprint("The conid for {} is {}".format(query_symbol,response))
pprint("="*80)

# Grab a current qoute
query_symbol = 'TSLA'
quote_response = trader.get_current_quotes(conids=trader.symbol_to_conid(query_symbol,exchange_list))
pprint("Current quote for {}: ".format(query_symbol))
pprint("-"*80)
pprint(quote_response)
pprint("="*80)
# Alternatively, the function supports passing in a list of conids
# Sometimes, there will be an error here, kill and rerun the script and the problem should go away
# If the problem persists after a few times, try chanching the query_conids to something else
query_conids = ['265598','15124833']
pprint("Current quote for {}: ".format(query_conids))
pprint("-"*80)
quote_response_dict = trader.get_current_quotes(conids=query_conids)
pprint(quote_response_dict)
pprint("="*80)

# Grab historical price for a list of stocks
query_conids = ['265598','272093']
pprint("Historical price for {}: ".format(query_conids))
pprint("-"*80)
historical_price_response = trader.get_historical_prices(
    period='30d',
    bar='1d',
    conids=query_conids
)
pprint(historical_price_response)
pprint("="*80)

# The functions above are utility functions that can be queried in any part of the loop to obtain info.
# Below is the main code required to run the bot
# ----------------------------------------------------------------------------------------------------
# Example of how to use the trading bot
# 1. Idenify the stocks of interest and the exhanges they are in, pass the conids for those stocks in\
#    a list and their relevant exchanges
# 2. Create a trader object which we did in the beginning
# 3. Query historical prices of the a list of stocks you would like your trading bot to trade
# 4. Create a stock frame object which will include the historical data you just queried 
# 5. Create a indicator object which will check for buy and sell signals
# 6. Add the relevant indicators your wish to check for
# 7. Create a portfolio object which holds all the positions and check whether trades have been executed
# 8. Add buy and sell signals for the choosen indicators
# 9. Load all the exisiting positions from IB that has not been sold 
# 10.In a loop, keep querying the latest bar of the stocks of interested when it comes out \
#    and it will calculate the newest value for your indicators automatically
# 11.Add the latest bar to the stock frame
# 12.Refresh the stock frame so all the indicators get calcualted
# 13.Check signals in indicators to see if they have met the predefined buy and sell signals
# 14.Process the signal if there is any stocks that has met the buy and sell signals, this will \
#    execute the traes as well
# 15.Query the order status from IB and update the status in portfolio
# 16.Grab the latest timestamp and store it as a variable so a sleep function can be initiated
# 17.Put bot into sleep unitl the next bar comes out and run from 9. again. Currently, the bot refreshes\
#    every minute.
#---------------------------------------------------------------------------------------------------------
# Main code
# 1. Identify stocks of interest, use trader.symbol_to_conid() to find the conid associated with a ticker if\
#    needed
conids_list = ['265598','272093']
exchange_list = ['NYSE','NASDAQ']

# 2. Create  a trader object
trader = Trader(
    username=paper_username,
    account=paper_account
)

# 3. Query historical prices of stocks of interest
historical_prices_list = trader.get_historical_prices(
    period='30d',
    bar='1d',
    conids=conids_list
)

# 4. Create a stock frame object
stock_frame_client = trader.create_stock_frame(trader.historical_prices['aggregated'])

# 5. Create a indicator object and populate it historical prices
indicator_client = Indicators(
    price_df= stock_frame_client
)



# 6. Add any indicators, in here, we will add the RSI indicator
indicator_client.rsi(period=14)

# 7. Add the buy and sell signal for the indicator
indicator_client.set_indicator_signal(
    indicator='rsi',
    buy=30.0,   # Buy when RSI drops below 30
    sell=70.0,  # Sell when RSI climbs above 70
    condition_buy=operator.ge,   # Greater or equal to operator
    condition_sell=operator.le
)

# You can see a list of the signals set using indicator_client._indicators_key and \
# indicator_client._indicators_signals
pprint("Indicators key: ")
pprint("-"*80)
pprint(indicator_client._indicators_key)
pprint("="*80)
pprint("Indicators signals: ")
pprint("-"*80)
pprint(indicator_client._indicator_signals)
pprint("="*80)

# You can also query the indicator's stock frame:
pprint("Indicator's stock frame: ")
pprint("-"*80)
pprint(indicator_client._frame.tail(20))
pprint("="*80)

# 8. Create a portfolio object
trader.create_portfolio()

# 9. Load all the existing positions from IB
positions_list = trader.load_positions()
pprint("Positions List: ")
pprint("-"*80)
pprint(positions_list)
pprint("="*80)

# 10. Main Loop
while (True):

    # 11. Grab the latest bar
    latest_candle = trader.get_latest_candle(
        bar='1min',
        conids=conids_list
    )

    # 11. Add the latest bar to the stock frame
    stock_frame_client.add_rows(data=latest_candle)

    # 12. Refresh the indicator object so that all indicators values get calculated
    indicator_client.refresh()

    # 13. Check signals in indicators to see whether any signals have been met by the latest candle
    signals = indicator_client.check_signals()
    buys = signals['buys'].to_list()
    sells = signals['sells'].to_list()
    pprint("Buy signals: {} ".format(buys))
    pprint("Sells signals: {} ".format(sells))

    # 14. Process the signals if there are any buys or sells signals
    # The default method of trade will be using market order and any errors will be suppreseed.
    # It may still require user input to overide any warnings, see the function itself for more info
    process_signal_response = trader.process_signal(signals=signals,exchange=exchange_list)
    pprint(process_signal_response)

    # 15. Update the orders status of any orders that have been placed but not filled in the portfolio object
    update_order_status = trader.update_order_status()
    pprint(update_order_status)

    # You can choose to display all exsisting positions here
    pprint("-"*80)
    pprint("Positions:")
    pprint("="*50)
    pprint(trader.portfolio.positions)

    # 16. Grab the latest timestamp in the stock frame
    latest_candle_timestamp = trader.stock_frame.frame.tail(1).index.get_level_values(1)
    pprint("-"*80)
    pprint("Latest timestamp:")
    pprint("="*50)
    pprint(latest_candle_timestamp)

    # 17. Put bot into sleep until next candle comes out
    trader.wait_till_next_candle(last_bar_timestamp=latest_candle_timestamp)

    # END OF LOOP



