from datetime import datetime, time, timezone

from typing import List
from typing import Dict
from typing import Union

import numpy as np
import pandas as pd
from pandas.core.groupby import DataFrameGroupBy
from pandas.core.window import RollingGroupby


class StockFrame():

    def __init__(self, data: List[Dict]) -> None:
        """Initalizes the Stock Data Frame Object.
        Arguments:
        ----
        data {List[Dict]} -- The data to convert to a frame. Normally, this is 
            returned from the historical prices endpoint.
        """
        self._data = data
        self._frame: pd.DataFrame = self.create_frame()
        self._symbol_groups: DataFrameGroupBy = None
        self._symbol_rolling_groups: RollingGroupby = None

    @property
    def frame(self) -> pd.DataFrame:
        return self._frame
    
    @property
    def symbol_groups(self) -> DataFrameGroupBy:
        self._symbol_groups = self._frame.groupby(
            by='symbol',
            as_index=False,
            sort=True
        )

        return self._symbol_groups

    def symbol_rolling_groups(self,size:int) -> RollingGroupby:
        #"size specifies the window size"
        
        if not self._symbol_groups:     #if there is no _symbol_groups object
            self.symbol_groups

        self._symbol_rolling_groups = self._symbol_groups.rolling(size)
        
        return self._symbol_rolling_groups

    def create_frame(self) -> pd.DataFrame:             #Initialise dataframe
        #Create a dataframe
        price_df  = pd.DataFrame(data=self._data)
        price_df = self._parse_datatime_column(price_df=price_df)       #Take timestamp column of every row, make it a pandas
        price_df = self._set_multi_index(price_df=price_df)

        return price_df

    def _parse_datatime_column(self,price_df:pd.DataFrame) -> pd.DataFrame:
        price_df['datetime'] = pd.to_datetime(price_df['datetime'], unit = 'ms', origin = 'unix')       #Parse unix epoch timestamp to date time
        return price_df

    def _set_multi_index(self, price_df:pd.DataFrame) -> pd.DataFrame:
        price_df = price_df.set_index(keys=['symbol','datetime'])
        return price_df

    def add_rows(self, data:dict) -> None:      #Add qoute from results of get_historical_prices() to dataframe
        """Adds a new row to our StockFrame.
        Arguments:
        ----
        data {Dict} -- A list of quotes.
        Usage:
        ----
            >>> # Create a StockFrame object.
            >>> stock_frame = trading_robot.create_stock_frame(
                data=historical_prices['aggregated']
            )
            >>> fake_data = {
                "datetime": 1586390396750,
                "symbol": "MSFT",
                "close": 165.7,
                "open": 165.67,
                "high": 166.67,
                "low": 163.5,
                "volume": 48318234
            }
            >>> # Add to the Stock Frame.
            >>> stock_frame.add_rows(data=fake_data)
        """
        column_names = ['open','close','high','low','volume']       #Headers of the columns in stock dataframe

        for quote in data:
            #Parse the timestamp
            time_stamp = pd.to_datetime(
                quote['datetime'],        #timestamp from IB in epoch format, see IB Client Portal API docs /portal/iserver/marketdata/snapshot for data return of price request
                unit='ms',
                origin='unix'   
            )
            symbol = quote['symbol']
            #Define our index
            row_id = (symbol,time_stamp)       #Tuple with 2 elements, symbols and time_stamp which is fixed

            #Define our values, see IB Client Portal API docs /portal/iserver/marketdata/snapshot for data return of price request
            ######### NEED TO CHANGE IT TO HISTORICAL MARKET PRICE RATHER THAN CURRENT PRICE
            row_values = [
                quote['open'],            
                quote['close'],     
                quote['high'],    
                quote['low'],     
                quote['volume'], 
            ]

            #New row
            new_row = pd.Series(data=row_values)

            #Add row
            self.frame.loc[row_id,column_names] = new_row.values
            self.frame.sort_index(inplace=True)

    #Check whehter an indicator exists in the stock frame dataframe
    def do_indicator_exist(self, column_names: List[str]) -> bool:
        """Checks to see if the indicator columns specified exist.
        Overview:
        ----
        The user can add multiple indicator columns to their StockFrame object
        and in some cases we will need to modify those columns before making trades.
        In those situations, this method, will help us check if those columns exist
        before proceeding on in the code.
        Arguments:
        ----
        column_names {List[str]} -- A list of column names that will be checked.
        Raises:
        ----
        KeyError: If a column is not found in the StockFrame, a KeyError will be raised.
        Returns:
        ----
        bool -- `True` if all the columns exist.
        """

        if set(column_names).issubset(self._frame.columns):
            return True
        else:
            raise KeyError("The following indicator columns are missing from the StockFrame: {missing_columns}".format(
                missing_columns=set(column_names).difference(
                    self._frame.columns)
            ))


    #Check whether the conditions for the indicators are met. If it's met, it will return the last row for each symbol in the StockFrame and compare the indicator column
    #values with the conditions specidied
    def _check_signals(self, indicators:Dict,indicators_comp_key:List[str],indicators_key: List[str]) -> Union[pd.DataFrame,None]:
        """Returns the last row of the StockFrame if conditions are met.
        Overview:
        ----
        Before a trade is executed, we must check to make sure if the
        conditions that warrant a `buy` or `sell` signal are met. This
        method will take last row for each symbol in the StockFrame and
        compare the indicator column values with the conditions specified
        by the user.
        If the conditions are met the row will be returned back to the user.
        Arguments:
        ----
        indicators {dict} -- A dictionary containing all the indicators to be checked
            along with their buy and sell criteria.
        indicators_comp_key List[str] -- A list of the indicators where we are comparing
            one indicator to another indicator.
        indicators_key List[str] -- A list of the indicators where we are comparing
            one indicator to a numerical value.
        Returns:
        ----
        {Union[pd.DataFrame, None]} -- If signals are generated then, a pandas.DataFrame object
            will be returned. If no signals are found then nothing will be returned.
        """

        #Get the last row of every symbol_groups
        last_rows = self._symbol_groups.tail(1)

        #Define a dictionary of conditions 
        conditions = {}

        #Check to see if all the columns for the indicators specified exists
        if self.do_indicator_exist(column_names=indicators_key):

            #Loop through every indicator using its key
            for indicator in indicators_key:

                #Define new column which is the value in the last row of indicator
                column = last_rows[indicator]

                #Grab the buy and sell condition of an indicator from the indicators arguments, e.g. self._indicator_signals:Dict in Indicator class
                buy_condition_target = indicators[indicator]['buy']
                sell_condition_target = indicators[indicator]['sell']

                buy_condition_operator = indicators[indicator]['buy_operator']
                sell_condition_operator = indicators[indicator]['sell_operator']

                #Set up conditions for buy and sell, i.e. one conditiona would be value in 'column' compared
                condition_1: pd.Series = buy_condition_operator(
                    column, buy_condition_target    #compare the value of last role against the buy_conditiona_target
                )
                condition_2: pd.Series = sell_condition_operator(
                    column, sell_condition_target
                )

                condition_1 = condition_1.where(lambda x: x==True).dropna()     #Keep the columns when condition_1 is met, i.e. when column is (buy_condition_operator) than buy_condition_target
                condition_2 = condition_2.where(lambda x: x==True).dropna()

                conditions['buys'] = condition_1        #Store the value of the indicator in a dictionary when the condition is met, it will later be returned 
                conditions['sells'] = condition_2
            
        #Store the indicators in a list
        check_indicators = []

        #Check whether the indicator exists in indicators_comp_key
        for indicator in indicators_comp_key:
            #Split the indicators into 2 parts by '_comp_' so we can check if both exist
            parts = indicator.split('_comp_')
            check_indicators+= parts
        
        if self.do_indicator_exist(column_names=check_indicators):
            for indicator in indicators_comp_key:
                # Split the indicators.
                parts = indicator.split('_comp_')

                #Grab the indicators that need to be compared
                indicator_1 = last_rows[parts[0]]
                indicator_2 = last_rows[parts[1]]

                #If we have a buy operator, grab it
                if indicators['indicator']['buy_operator']:
                    buy_condition_operator = indicators['indicator']['buy_operator']

                    #Grab the condition
                    condition_1 : pd.Series = buy_condition_operator(
                        indicator_1, indicator_2
                    )
                    # Keep the one's that aren't null.
                    condition_1 = condition_1.where(lambda x: x == True).dropna()

                    #Add it as a buy signal
                    conditions['buy'] = condition_1

                #If we have a sell operator, grab it
                if indicators['indicator']['sell_operator']:
                    buy_condition_operator = indicators['indicator']['sell_operator']

                    #Grab the condition
                    condition_2 : pd.Series = sell_condition_operator(
                        indicator_1, indicator_2
                    )
                    # Keep the one's that aren't null.
                    condition_2 = condition_2.where(lambda x: x == True).dropna()

                    #Add it as a buy signal
                    conditions['sell'] = condition_2
        return conditions

    # Check whether the conditions for the indicators associated with ticker has been met. If it's met, it will \
    # return the last row for each symbol in the StockFrame and compare the indicator column values with the conditions specidied. 
    def _check_ticker_signals(self, ticker_indicators:Dict, ticker_indicators_key:List[tuple]) -> Union[pd.DataFrame,None]:
        
        #Define a dictionary of conditions 
        conditions = {}

        # First, form a list with all the indicator names from the 2nd element in ticker_indicators_key:List
        # Check to see if all the indicator columns exist
        if self.do_indicator_exist(column_names=[pair[1] for pair in ticker_indicators_key]):

            #Loop through every tuple in ticker_indicators_key which is a list
            for ticker_indicator in ticker_indicators_key:
                # The first element of tuple is the ticker and the second element of tuple contains the name of indicator 
                ticker = ticker_indicator[0]
                indicator = ticker_indicator[1]
                
                # Get the last row of the specified ticker group
                last_row = self._symbol_groups.get_group(ticker).tail(1)

                # Select the indicator cell as target for comparison later
                target_cell = last_row[indicator]

                #Grab the buy and sell condition of an ticker_indicator from the function arguments, e.g. self._ticker_indicator_signals:Dict in Indicator class
                buy_condition_target = ticker_indicators[ticker][indicator]['buy']
                sell_condition_target = ticker_indicators[ticker][indicator]['sell']

                buy_condition_operator = ticker_indicators[ticker][indicator]['buy_operator']
                sell_condition_operator = ticker_indicators[ticker][indicator]['sell_operator']

                if buy_condition_operator(target_cell, buy_condition_target):
                    # If the buy condition has been met, append key-value pair to conditions['buys']
                    # The key would be the ticker and the value would be the buy_cash_quantity which can be used to calculate quantity in process_signal()
                    conditions['buys'].update({ticker:ticker_indicators[ticker][indicator]['buy_cash_quantity']})

                if sell_condition_operator(target_cell, sell_condition_target):
                    # If the sell condition has been met, append key-value pair to conditions['sells']
                    # The key would be the ticker and the value would be close_position_when_sold:bool, this will be passed onto process_signal()
                    conditions['sells'].update({ticker:ticker_indicators[ticker][indicator]['close_position_when_sell']})
        
        return conditions





