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