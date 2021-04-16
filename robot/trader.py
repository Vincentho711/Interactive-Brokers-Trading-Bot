import json
import time as time_true
import pprint
import pathlib
import pandas as pd

from datetime import time
from datetime import datetime
from datetime import timezone
from datetime import timedelta

from typing import List
from typing import Dict
from typing import Union
from typing import Optional
from ibw.client import IBClient
from configparser import ConfigParser

from robot.stock_frame import StockFrame
from robot.trades import Trade
from robot.portfolio import Portfolio


#gateway_path = pathlib.Path('clientportal.gw').resolve() #Added this line to redirect clientportal.gw away from resoruces/clientportal.beta.gw

class Trader():

    def __init__(self, username: str, account: str , client_gateway_path: str = None, is_server_running: bool = True):
        """
            USAGE:
            Specify the paper and regular account details and gateway path before creating an object
            e.g.
                # Grab configuration values.
                config = ConfigParser()
                file_path = pathlib.Path('config/config.ini').resolve()
                config.read(file_path)

                # Load the details.
                paper_account = config.get('main', 'PAPER_ACCOUNT')
                paper_username = config.get('main', 'PAPER_USERNAME')
                regular_account = config.get('main','REGULAR_ACCOUNT')
                regular_username = config.get('main','REGULAR_USERNAME')

                #Specify path
                gateway_path = pathlib.Path('clientportal.gw').resolve()

                >>> ib_paper_session = IBClient(
                username='paper_username',
                account='paper_account',
            )
        """
        #Change username and account to go from paper account to regular account
        self.username = username
        self.account = account
        #self.client_gateway_path = client_gateway_path
        self.is_paper_trading = True                            #Remember to change it when switch to regular account
        self.session: IBClient = self._create_session()         ### self.seesion = ib_client ### 
        self._account_data:pd.DataFrame = self._get_account_data()      #Get account data
        self.historical_prices = {}                             #A historical prices dictionary for all interested stocks
        self.stock_frame:StockFrame = None
        self.portfolio:Portfolio = None
        self.trades = {}                                        # A dictionary of all the trades that belongs to the trader
    
    @property
    def account_data(self) -> pd.DataFrame:
        return self._account_data

    def _create_session(self) -> IBClient:
        """Start a new session. Go to initiate an IBClient object and the session will be passed onto trader object
        Creates a new session with the IB Client  API and logs the user into
        the new session.
        Returns:
        ----
        IBClient -- A IBClient object with an authenticated sessions.
        """
        ib_client = IBClient(
            username = self.username,
            account = self.account,
            is_server_running=True
        )

        #Start a new session
        ib_client.create_session()
        
        return ib_client
    

    def _get_account_data(self) -> pd.DataFrame:
        #Has to call /iserver/accounts before anything, make a request with ib_client.portfolio_accounts()
        portfolio_accounts = self.session.portfolio_accounts()

        portfolio_ledger = self.session.portfolio_account_ledger(account_id=self.account)

        column_names = ['account number','currency','cash balance','stock value','net liquidation value','realised PnL','unrealised PnL',]
        #create a pandas df with columns stated by column_names

        account_df = pd.DataFrame(columns=column_names)
        
        for item in portfolio_ledger:
            #Parse the timestamp
            time_stamp = pd.to_datetime(
                portfolio_ledger[item]['timestamp'],        #timestamp from IB in epoch format, see IB Client Portal API docs /portal/iserver/marketdata/snapshot for data return of price request
                unit='s',
                origin='unix'   
            )

            #Define currency
            currency = portfolio_ledger[item]['currency']
            #Define our index
            row_id = (time_stamp,currency)       #Tuple with 2 elements, time_stamp and currency which is fixed

            row_values = [
                portfolio_ledger[item]['acctcode'],
                portfolio_ledger[item]['currency'],
                portfolio_ledger[item]['cashbalance'],
                portfolio_ledger[item]['stockmarketvalue'],
                portfolio_ledger[item]['netliquidationvalue'],
                portfolio_ledger[item]['realizedpnl'],
                portfolio_ledger[item]['unrealizedpnl']
            ]

            #New row
            new_row = pd.Series(data=row_values,index=account_df.columns,name=row_id)

            #Add row
            account_df = account_df.append(new_row)
        
        #return dataframe
        return account_df

    def contract_details_by_symbols(self,symbols:List[str]=None) -> pd.DataFrame:
        #Search for the conid for a symnbol and get basic info about the instruments
        #With /portal/iserver/secdef/search

        column_names = ['symbol','company','company header','conid','exchange','security type']
        #Create a pandas df with column names staed in column_names
        symbol_to_conid_df = pd.DataFrame(columns=column_names)

        for symbol in symbols:
            symbol_results = self.session.symbol_search(symbol=symbol)
            for item in symbol_results:
                #Obtain the 'secType' in 'sections' by normalising it making it into a list
                normalized_sectype_list = pd.json_normalize(item['sections'])
                normalized_sectype_list = normalized_sectype_list['secType'].tolist()

                row_values=[
                    item['symbol'],
                    item['companyName'],
                    item['companyHeader'],      #str(Company Name - Exchange) 
                    item['conid'],
                    item['description'],        #Exchange
                    normalized_sectype_list     #List containing all securities type
                ]
                
                #Define our index
                row_id = (item['symbol'],item['description'])      #Tuple with 2 elements, symbol and exchange which is fixed

                #New row
                new_row = pd.Series(data=row_values,index=symbol_to_conid_df.columns,name=row_id)
                #Add row
                symbol_to_conid_df = symbol_to_conid_df.append(new_row)
                
        return symbol_to_conid_df
    
    def symbol_to_conid(self,symbol:str,exchange:List[str]) -> str:
        """Use this to find the conid of a symbol. It will return the conid for a specified symbol.
        Keep the list of exchange as short as possible as this function aims to return one conid for a symbol.
        Arguments:
        ----
        symbol {str} -- The symbol/ticker that you wish to look up

        exchange {list[str]} -- The list of exchanges that you wish to trade in. The exchanges can be
            `NASDAQ`,`NYSE`,`MEXI` but there are many more. 
            It is a good practive to keep the list of exchange to the primary exchanges 
            you trade in to prevent conflicts. E.g. if you put in both `NASDAQ` and `MEXI` in the list of exchange for `AAPL`,
            it will return the first conid found even though Apple is listed on both exchanges. 
            
            
        Returns:
        ----
        {str} -- The conid for the specified symbol
        """
        symbol_results = self.session.symbol_search(symbol=symbol)
        for item in symbol_results:
            if item['description'] in exchange:
                return item['conid']
        
        #If nothing is returned by this point, it means the symbol is not in the exchanges provided.
        raise ValueError("{} is not in the list of exchanges you provided".format(symbol))
    
    def get_current_quotes(self,conids:List[str]=None) -> Dict:
        #Get the current price for a list of conids
        """
            After querying symbol_to_conid and have a dataframe returned,
            select the 'conid' column of the specific row id with symbol, exchange
            then pass them to a list to get the current qoutes for them
        """
        quote_fields = ['55','31']      #qoute_feilds to indicate information wanted,'55' is symbol,'31' is last price
        current_quotes = self.session.market_data(
            conids=conids,
            since='0',
            fields=quote_fields

        )

        current_quotes_dict = dict()
        for item in current_quotes:
            if '31' in item.keys():     # Check if the last price exists for a symbol
                current_quotes_dict.update({item['55']:item['31']})
            else:
                current_quotes_dict.update({item['55']:None})

        return current_quotes_dict
        

    def get_historical_prices(self,period:str,bar:str,conids:List[str]=None) -> List[Dict]:
        #Get historical prices for a list of conids
        """
            Get history of market Data for the given conid, length of data is controlled by period and 
            bar. e.g. 1y period with bar=1w returns 52 data points.

            NAME: conids
            DESC: The contract ID for a given instrument. You can pass it a list of conids for all the interesetd stocks
            TYPE: List

            NAME: period
            DESC: Specifies the period of look back. For example 1y means looking back 1 year from today.
                  Possible values are ['1d','1w','1m','1y']
            TYPE: String

            NAME: bar
            DESC: Specifies granularity of data. For example, if bar = '1h' the data will be at an hourly level.
                  Possible values are ['1min','5min','1h','1w']
            TYPE: String

        """
        #List of new_prices for each symbol
        new_prices = []
        
        for conid in conids:
            historical_prices = self.session.market_data_history(
                conid=conid,
                period=period,
                bar=bar
            )

            #Obtain symbol for each query
            symbol = historical_prices['symbol']
            self.historical_prices[symbol]= {}      #Create a dictionary which will be a propety of trader object
            self.historical_prices[symbol]['candles'] = historical_prices['data']

            
            #Extract candle data from historical_prices['data']
            for candle in historical_prices['data']:
                #Parse the timestamp
                # time_stamp = pd.to_datetime(
                #     candle['t'],        #timestamp from IB in epoch format, see IB Client Portal API docs /portal/iserver/marketdata/snapshot for data return of price request
                #     unit='ms',
                #     origin='unix'   
                # )
                new_price_dict = {}     #This is a mini dictionary for every candle, refer to /portal/iserver/marketdata/history
                new_price_dict['symbol'] = symbol
                new_price_dict['datetime'] = candle['t']        #Parse it to datetime timestamp later in stockframe
                new_price_dict['open'] = candle['o']
                new_price_dict['close'] = candle['c']
                new_price_dict['high'] = candle['h']
                new_price_dict['low'] = candle['l']
                new_price_dict['volume'] = candle['v']
                new_prices.append(new_price_dict)

        self.historical_prices['aggregated'] = new_prices

        return self.historical_prices
    #Get latest candle
    def get_latest_candle(self,bar='1min',conids=List[str]) -> List[Dict]:
        """
            Get latest candle of a list of stocks, the default bar is '1min'

            NAME: bar
            DESC: Specifies granularity of data. For example, if bar = '1h' the data will be at an hourly level. Default is '1min'.
                  Possible values are ['1min','5min','1h','1w']
            TYPE: String

            NAME: conids
            DESC: A list of conids of interested stock
            TYPE: List of strings

        """
        #define period based on bar, since we will be extracting final candle in historical_prices, out only constraint is period > bar
        if 'min' in bar:
            period = '1h'
        elif 'h' in bar:
            period = '1d'
        elif 'w' in bar:
            period = '1m'
        else:
            raise ValueError('Bar parameter does not contain min,h or w strings.')
        latest_prices = []
        
        for conid in conids:
            try:
                historical_prices = self.session.market_data_history(
                conid=conid,
                period=period,
                bar=bar
            )
            except:
                #Sleep for 1sec then retry
                time_true.sleep(1)
                historical_prices = self.session.market_data_history(
                conid=conid,
                period=period,
                bar=bar
            )
            #Obtain symbol for each query
            symbol = historical_prices['symbol']
            
            for candle in historical_prices['data'][-1:]:
                new_price_dict = {}     #This is a mini dictionary for every candle, refer to /portal/iserver/marketdata/history
                new_price_dict['symbol'] = symbol
                new_price_dict['datetime'] = candle['t']        #Parse it to datetime timestamp later in stockframe
                new_price_dict['open'] = candle['o']
                new_price_dict['close'] = candle['c']
                new_price_dict['high'] = candle['h']
                new_price_dict['low'] = candle['l']
                new_price_dict['volume'] = candle['v']
                latest_prices.append(new_price_dict)

        return latest_prices

    def wait_till_next_candle(self,last_bar_timestamp:pd.DatetimeIndex) -> None:
        last_bar_time = last_bar_timestamp.to_pydatetime()[0].replace(tzinfo=timezone.utc)     #Convert it into a python datetime format and make sure it is in utc time zone
        #Because data doesn't come out at 0s at the minute, it will take another 30s for the data to arrive, set refresh at 30s
        last_bar_time = last_bar_time + timedelta(seconds=30.0)

        next_bar_time = last_bar_time + timedelta(seconds=60.0)
        curr_bar_time = datetime.now(tz=timezone.utc)

        #Because IB only offers delayed data by 15 mins without market subscription, delayed_time takes care off this by
        #shifting curr_bar_time forward by 15 mins to take of the delayed data, this variable is named delayed_curr_bar_time
        delayed_time = -timedelta(minutes=15)
        delayed_curr_bar_time = curr_bar_time + delayed_time

        last_bar_timestamp = int(last_bar_time.timestamp())
        next_bar_timestamp = int(next_bar_time.timestamp())
        #curr_bar_timestamp = int(curr_bar_time.timestamp())    #Not used because delayed_curr_bar_timestamp is used instead
        delayed_curr_bar_timestamp = int(delayed_curr_bar_time.timestamp())
        
        #time_to_wait_now = next_bar_timestamp - curr_bar_timestamp
        time_to_wait_now = next_bar_timestamp - delayed_curr_bar_timestamp

        if time_to_wait_now < 0:
            time_to_wait_now = 0

        print("=" * 80)
        print("Pausing for the next bar")
        print("-" * 80)
        print("Curr Time: {time_curr}".format(
            time_curr=curr_bar_time.strftime("%Y-%m-%d %H:%M:%S")
        )
        )
        print("Delayed Curr Time: {delayed_time_curr}".format(
            delayed_time_curr=delayed_curr_bar_time.strftime("%Y-%m-%d %H:%M:%S")
        )
        )
        print("Next Time: {time_next}".format(
            time_next=next_bar_time.strftime("%Y-%m-%d %H:%M:%S")
        )
        )
        print("Sleep Time: {seconds}".format(seconds=time_to_wait_now))
        print("-" * 80)
        print('')

        time_true.sleep(time_to_wait_now)
        
    #Create a stock frame for trader class
    def create_stock_frame(self,data: List[Dict]) -> StockFrame:
        """Generates a new stock frame object
        Arguments:
        ----
        data{List[dict]} -- The data to add to the StockFrame object, it can be the results obtained from get_historical_prices(), e.g. self.historical_prices['aggregated']

        Returns:
        ----
        StockFrame -- A multi-index pandas data frame built for trading.
        """

        #Create the frame
        self.stock_frame = StockFrame(data=data)
        return self.stock_frame

    #Obtain account positions data which will then be passed to the portfolio object to generate a portfolio dataframe
    def load_positions(self) -> List[Dict]:
        """Load all the existing positions from IB to the Portfolio object
        Arguments:
        ----
        None

        Returns:
        ----
        data{List[dict]} -- List of Dictionary containing information about every positions the account holds

        Usage:
        ----
            >>> trader = Trader(
                username=paper_username,
                account=paper_account,
                client_gateway_path=gateway_path
            )
            >>> trader_portfolio = trader.create_portfolio()
            >>> trader.load_positions()

        """
        account_positions = self.session.portfolio_account_positions(
            account_id=self.account,
            page_id=0
        )
        for position in account_positions:

            # Sometimes there isn't the key 'ticker' in the position dictionary, in which case \
            # use 'contractDesc' instead
            if 'ticker' not in position:
                position['ticker'] = position['contractDesc']
            
            self.portfolio.add_position(
                symbol=position['ticker'],
                asset_type=position['assetClass'],
                purchase_date="Unknown",
                order_status="Filled",      #If it is in the positions list, it is filled
                quantity=position['position'],
                purchase_price=position['mktPrice']
            )

        # Set the ownership_status to True as not providing date has set it to False originally
        self.portfolio.set_ownership_status(symbol=position['ticker'],ownership=True)

        return account_positions

    def create_portfolio(self) -> Portfolio:
        """Creates a new portfoliio

        Creates a Portfolio Object to help store and organise positions as they are added or removed.
        
        Usage:
        ----
        trader = Trader(
            username=paper_username,                      
            account=paper_account,               
            is_server_running=True
        )
        
        trader_portfolio = trader.create_portfolio()
        """
        self.portfolio = Portfolio(account_id=self.account)
        
        #Assign the client
        self.portfolio._ib_client = self.session

        return self.portfolio


    def create_trade(self,account_id:Optional[str], local_trade_id:str, conid:str, ticker:str, security_type:str, order_type: str, side:str, duration:str , 
    price:float = 0.0, quantity:float = 0.0,outsideRTH:bool=False) -> Trade:
        """Initalizes a new instance of a Trade Object.
        This helps simplify the process of building an order by using pre-built templates that can be
        easily modified to incorporate more complex strategies.
        Keyword Arguments:
        ----
        account_id {str} -- It is optional. It should be one of the accounts returned 
            by /iserver/accounts. If not passed, the first one in the list is selected.
        
        trade_id {str} -- Optional, if left blank, a unqiue identification code will be automatically generated

        conid {str} -- conid is the identifier of the security you want to trade, you can find 
            the conid with /iserver/secdef/search

        ticker {str} -- Ticker symbol for the asset

        security_type {str} -- The order's security/asset type, can be one of the following
            [`STK`,`OPT`,`WAR`,`IOPT`,`CFD`,`BAG`]

        order_type {str} -- The type of order you would like to create. Can be
            one of the following: [`MKT`, `LMT`, `STP`, `STP_LIMIT`]

        side {str} -- The side the trade will take, can be one of the
            following: [`BUY`, `SELL`]
        duration {str} -- The tif/duration of order, can be one of the following: [`DAY`,`GTC`]

        price {float} -- For `MKT`, this is optional. For `LMT`, this is the limit price. For `STP`, 
            this is the stop price 

        quantity {float} -- The quantity of assets to buy

        outsideRTH {bool} -- Execute outside trading hours if True, default is False

        Usage:
        ----
            >>> trader = Trader(
                username=paper_username,
                account=paper_account,
                client_gateway_path=gateway_path
            )
            >>> new_trade = trader.create_trade(
                account_id=paper_account,
                trade_id=None,
                conid='',  
                ticker='',
                security_type='STK',
                order_type='LMT',
                side='BUY',
                duration='DAY',
                price=0.0,
                quantity=0.0
            )
            >>> new_trade
        
        Returns:
        ----
        Trade -- A pyrobot.Trade object with the specified template.
        """

        #Initialise a Trade object
        trade = Trade()

        #Create a new order
        trade.create_order(
            account_id=account_id,
            local_trade_id=local_trade_id,
            conid=conid,
            ticker=ticker,
            security_type=security_type,
            order_type=order_type,
            side=side,
            duration=duration,
            price=price,
            quantity=quantity
        )

        #Set the Client
        trade.account = self.account
        trade._ib_client = self.session

        local_trade_id = trade.local_trade_id
        self.trades[local_trade_id] = trade

        return trade

    def process_signal(self,signals:pd.Series,exchange:list,order_type:str = 'MKT') -> List[dict]:
        """ Process the signal after we have obtained the signal through indicator.check_sigals()
        It will create establish the Trade Objects and create orders for buy and sell signals

        Arguments:
        ----
        signals {pd.Dataframe} -- The signals returned by Indicator object's check_signals()

        exchange {list[str]} -- The list of exchanges that you wish to trade in. The exchanges can be
            `NASDAQ`,`NYSE`,`MEXI` but there are many more. 
            It is a good practive to keep the list of exchange to the primary exchanges 
            you trade in to prevent conflicts. E.g. if you put in both `NASDAQ` and `MEXI` in the list of exchange for `AAPL`,
            it will return the first conid found even though Apple is listed on both exchanges.

        order_type {str} -- The order type of executing signal, `MKT` or `LMT`, the default is
            `MKT` and support for `LMT` is not added yet

        Returns:
        ----
        {list[dict]} -- A list of order responses will be returned
        """

        # Extract buys and sells signal from signals
        buys:pd.Series = signals['buys']
        sells:pd.Series = signals['sells']

        # Establish order_response list
        order_responses = []

        # Check if we have buy signals
        if not buys.empty:
            # Grab the buy symbols
            symbol_list = buys.index.get_level_values(0).to_list()

            #Loop through each symbol in buy signals
            for symbol in symbol_list:
                # Obtain the conid for the symbol
                conid = self.symbol_to_conid(symbol=symbol,exchange=exchange)

                # Check if position already exists in Portfolio object, only proceed buy signal if it is not in portfolio
                if self.portfolio.in_portfolio(symbol) is False:
                    #Create a Trade object for symbol that doesn't exist in Portfolio.positions
                    trade_obj: Trade = self.create_trade(
                        account_id=self.account,
                        local_trade_id=None,
                        conid=conid,
                        ticker=symbol,
                        security_type='STK',
                        order_type=order_type,
                        side='BUY',
                        duration='DAY',
                        price=None,
                        quantity=1.0
                    )

                    # Preview the order
                    preview_order_response = trade_obj.preview_order()

                    # Execute the order
                    execute_order_response = trade_obj.place_order(ignore_warning=True)

                    # Save the exexcute_order_response into a dictionary
                    order_response = {
                        'symbol': symbol,
                        'local_trade_id':execute_order_response[0]['local_order_id'],
                        'trade_id':execute_order_response[0]['order_id'],
                        'message':execute_order_response[0]['text'],
                        'order_status':execute_order_response[0]['order_status'],
                        'warning_message':execute_order_response[0]['warning_message']
                    }

                    # Sleep for 0.1 seconds to make sure order is executed on IB server
                    time_true.sleep(0.1)

                    # Query order to find out market order, price and other info
                    order_status_response = self.session.get_order_status(trade_id=execute_order_response[0]['order_id'])
                    order_price = float(order_status_response['exit_strategy_display_price'])
                    order_quantity = float(order_status_response['size'])
                    order_status = order_status_response['order_status']
                    order_asset_type = order_status_response['sec_type']
                    
                    # Obtain the time now
                    time_now = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
                    
                    # Add this position onto our Portfolio Object with the data obtained from order_status_response
                    portfolio_position_dict = self.portfolio.add_position(
                        symbol=symbol,
                        asset_type=order_asset_type,
                        purchase_date=time_now,
                        purchase_price=order_price,
                        quantity=order_quantity,
                        order_status=order_status
                        # Ownership_status is automatically set to when purchase_date is supplied
                        )

                    # IMPLEMENT WAIT UNTIL ORDER IS FILLED? #


                    # Append the order_response above to the main order_responses list
                    order_responses.append(order_response)

        # Check if we have any sells signals
        elif not sells.empty:
            
            # Grab the sell symbols
            symbol_list = buys.index.get_level_values(0).to_list()
            
            #Loop through each symbol in sell signals
            for symbol in symbol_list:
                # Obtain the conid for the symbol
                conid = self.symbol_to_conid(symbol=symbol,exchange=exchange)
                
                # Check if position already exists in Portfolio object, only proceed sell signal if it is in portfolio
                if self.portfolio.in_portfolio(symbol):
                    
                    #Check if we own the position in portfolio
                    if self.portfolio.positions[symbol]['ownership_status']:
                        # Set ownership_status to False as we are selling it
                        self.portfolio.set_ownership_status(symbol=symbol,ownership=False)

                        # Create a trade_obj to sell it
                        trade_obj: Trade = self.create_trade(
                            account_id=self.account,
                            local_trade_id=None,
                            conid=conid,
                            ticker=symbol,
                            security_type='STK',
                            order_type=order_type,
                            side='SELL',
                            duration='DAY',
                            price=None,
                            quantity=self.portfolio.positions[symbol]['quantity']
                        )

                        # Preview the order
                        preview_order_response = trade_obj.preview_order()

                        # Execute the order
                        execute_order_response = trade_obj.place_order(ignore_warning=True)

                        # Save the exexcute_order_response into a dictionary
                        order_response = {
                            'symbol': symbol,
                            'local_trade_id':execute_order_response[0]['local_order_id'],
                            'trade_id':execute_order_response[0]['order_id'],
                            'order_status':execute_order_response[0]['order_status'],
                        }


                        # Sleep for 0.1 seconds to make sure order is executed on IB server
                        time_true.sleep(0.1)

                        # Set positions[symbol]['quantity] to 0 and update order_status
                        self.portfolio.positions[symbol]['quantity'] = 0
                        self.portfolio.positions[symbol]['order_status'] = execute_order_response[0]['order_status']

                        order_responses.append(order_response)
        
        return order_responses
    
    # A function similar to process_signal() used to process ticker specific signals
    def process_ticker_signal(self,ticker_signals:Dict,exchange:List,order_type:str='MKT') -> List[dict]:
        
        # Extract buys and sells signal from signals
        buys:dict = ticker_signals['buys']
        sells:dict = ticker_signals['sells']

        # Establish order_response list
        order_responses = []

        # Check if there are any buys signals
        if buys:
            # Loop through each key value pair in dict
            for ticker,buy_cash_quantity in buys.items():
                # Obtain the conid for the symbol
                conid = self.symbol_to_conid(symbol=ticker,exchange=exchange)

                # Check if position already exists in Portfolio object, only proceed buy signal if it is not in portfolio
                if self.portfolio.in_portfolio(ticker) is False:
                    
                    quantity = 0.0
                    quantity = self.calculate_buy_quantity(ticker=ticker,conid=conid,buy_cash_quantity=buy_cash_quantity)
                    
                    # Check if a quantity has been calculated
                    if quantity != 0.0:
                        # Create a Trade object for symbol that doesn't exist in Portfolio.positions
                        # Purchase with the quantity calculated
                        trade_obj: Trade = self.create_trade(
                            account_id=self.account,
                            local_trade_id=None,
                            conid=conid,
                            ticker=ticker,
                            security_type='STK',
                            order_type=order_type,
                            side='BUY',
                            duration='DAY',
                            price=None,
                            quantity=quantity
                        )

                        # Preview the order
                        preview_order_response = trade_obj.preview_order()

                        # Execute the order
                        execute_order_response = trade_obj.place_order(ignore_warning=True)

                        # Save the exexcute_order_response into a dictionary
                        order_response = {
                            'symbol': symbol,
                            'local_trade_id':execute_order_response[0]['local_order_id'],
                            'trade_id':execute_order_response[0]['order_id'],
                            'message':execute_order_response[0]['text'],
                            'order_status':execute_order_response[0]['order_status'],
                            'warning_message':execute_order_response[0]['warning_message']
                        }

                        # Sleep for 0.1 seconds to make sure order is executed on IB server
                        time_true.sleep(0.1)

                        # Query order to find out market order, price and other info
                        order_status_response = self.session.get_order_status(trade_id=execute_order_response[0]['order_id'])
                        order_price = float(order_status_response['exit_strategy_display_price'])
                        order_quantity = float(order_status_response['size'])
                        order_status = order_status_response['order_status']
                        order_asset_type = order_status_response['sec_type']
                        
                        # Obtain the time now
                        time_now = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
                        
                        # Add this position onto our Portfolio Object with the data obtained from order_status_response
                        portfolio_position_dict = self.portfolio.add_position(
                            symbol=ticker,
                            asset_type=order_asset_type,
                            purchase_date=time_now,
                            purchase_price=order_price,
                            quantity=order_quantity,
                            order_status=order_status
                            # Ownership_status is automatically set to when purchase_date is supplied
                        )

                        # IMPLEMENT WAIT UNTIL ORDER IS FILLED? #


                        # Append the order_response above to the main order_responses list
                        order_responses.append(order_response)
                    else:
                        pprint(f"Current quote for {ticker} is {quantity} which means it cannot be obtained,\
                             no order has been placed as a result.")

        # Check if we have any sells signals
        elif sells:
            # Loop through each key value pair in dict
            for ticker,close_position_when_sell in sells.items():
                # Obtain the conid for the symbol
                conid = self.symbol_to_conid(symbol=ticker,exchange=exchange)

                # Check if position already exists in Portfolio object, only proceed sell signal if it is in portfolio
                if self.portfolio.in_portfolio(ticker):
                    
                    #Check if we own the position in portfolio
                    if self.portfolio.positions[ticker]['ownership_status']:
                        # Set ownership_status to False as we are selling it
                        self.portfolio.set_ownership_status(symbol=ticker,ownership=False)

                        # Check if we want to close the position when selling 
                        # Logic needs to be implemented when close_position_when_sell == False
                        if close_position_when_sell:
                            quantity = self.portfolio.positions[ticker]['quantity']
                        else:
                            # Not yet implemented, simply sell position even when it results to False for now
                            quantity = self.portfolio.positions[ticker]['quantity']
                        
                        # Create a trade_obj to sell it
                        trade_obj: Trade = self.create_trade(
                            account_id=self.account,
                            local_trade_id=None,
                            conid=conid,
                            ticker=ticker,
                            security_type='STK',
                            order_type=order_type,
                            side='SELL',
                            duration='DAY',
                            price=None,     # price can be None when selling with market order
                            quantity=quantity
                        )

                        # Preview the order
                        preview_order_response = trade_obj.preview_order()

                        # Execute the order
                        execute_order_response = trade_obj.place_order(ignore_warning=True)

                        # Save the exexcute_order_response into a dictionary
                        order_response = {
                            'symbol': ticker,
                            'local_trade_id':execute_order_response[0]['local_order_id'],
                            'trade_id':execute_order_response[0]['order_id'],
                            'order_status':execute_order_response[0]['order_status'],
                        }


                        # Sleep for 0.1 seconds to make sure order is executed on IB server
                        time_true.sleep(0.1)

                        # Set positions[symbol]['quantity] to 0 and update order_status
                        self.portfolio.positions[symbol]['quantity'] = 0
                        self.portfolio.positions[symbol]['order_status'] = execute_order_response[0]['order_status']

                        order_responses.append(order_response)

        return order_responses


    def calculate_buy_quantity(self,ticker:str,conid:str,buy_cash_quantity:float) -> Union[float,None]:
        """Calculate the quantity of stock to buy based on the latest quote and the total buy cash.

        Args:
            ticker (str): Ticker
            conid (str): The conid for the ticker
            buy_cash_quantity (float): Total cash allocation for this purchase

        Returns:
            Union[float,None]: Depending on whether current quote can be obtained, it returns the quantity \
                or None
        """
        # First query the latest quote
        quotes_dict = self.get_current_quotes(conids=[conid])
        
        # Check if the dict contains latest quote data 
        if quotes_dict.get(ticker):
            # Convert the price to a float
            current_price = float(quotes_dict.get(ticker))
            # Calculate quantity
            quantity = buy_cash_quantity/current_price
            # Round it to 2 d.p
            return round(quantity,2)
        else:
            return None


    def update_order_status(self) -> Dict:
        """Query and update all the live orders on IB.
        The end-point is meant to be used in polling mode, e.g. requesting every 
        x seconds. The response will contain two objects, one is notification, the 
        other is orders. Orders is the list of orders (cancelled, filled, submitted) 
        with activity in the current day. Notifications contains information about 
        execute orders as they happen, see status field.

        Returns:
        {dict} -- A dictionary containing all the live orders
        """
        live_order_response = self.session.get_live_orders()

        # Check if live_order_response contains any data to update
        if live_order_response['snapshot'] is True:
            # Loop through all the live orders
            for order in live_order_response['orders']:
                print(order)
                symbol = order['ticker']
                # Check if the order is in portfolio position
                if self.portfolio.in_portfolio(symbol=symbol):
                    # Check if the order has order_status 'Submitted' ir 'PreSubmitted'
                    if self.portfolio.positions[symbol]['order_status'] is 'Submitted' or 'PreSubmitted':
                        self.portfolio.positions[symbol]['order_status'] = order['status']

        return live_order_response

