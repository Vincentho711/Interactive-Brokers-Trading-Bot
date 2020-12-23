import operator
import numpy as np
import pandas as pd

from typing import Any
from typing import List
from typing import Dict
from typing import Union
from typing import Optional
from typing import Tuple

from robot.stock_frame import StockFrame

class Indicators():
    def __init__(self, price_df: StockFrame) -> None:

        self._stock_frame: StockFrame = price_df
        self._price_groups = self._stock_frame.symbol_groups
        self._current_indicators = {}        #Instead of asking the user to call all the functions again when a new data row comes in, a wrapper is used to update each column
                                             #Indicators that user has assigned to the stock frame
        self._indicator_signals = {}         #A dictionary of all the signals
        self._frame = self._stock_frame.frame

        self._indicators_comp_key = []
        self._indicators_key = []

    def set_indicator_signal(self, indicator:str, buy: float, sell: float, condition_buy: Any, condition_sell: Any, buy_max: float = None, sell_max: float = None
    , condition_buy_max: Any = None, condition_sell_max: Any = None):
        #Each indicator has a buy signal and a sell signal, numeric threshold and operator (e.g. <,>)
        """Used to set an indicator where one indicator crosses above or below a certain numerical threshold.
            Arguments:
            ----
            indicator {str} -- The indicator key, for example `ema` or `sma`.
            buy {float} -- The buy signal threshold for the indicator.
            
            sell {float} -- The sell signal threshold for the indicator.
            condition_buy {str} -- The operator which is used to evaluate the `buy` condition. For example, `">"` would
                represent greater than or from the `operator` module it would represent `operator.gt`.
            
            condition_sell {str} -- The operator which is used to evaluate the `sell` condition. For example, `">"` would
                represent greater than or from the `operator` module it would represent `operator.gt`.
            buy_max {float} -- If the buy threshold has a maximum value that needs to be set, then set the `buy_max` threshold.
                This means if the signal exceeds this amount it WILL NOT PURCHASE THE INSTRUMENT. (defaults to None).
            
            sell_max {float} -- If the sell threshold has a maximum value that needs to be set, then set the `buy_max` threshold.
                This means if the signal exceeds this amount it WILL NOT SELL THE INSTRUMENT. (defaults to None).
            condition_buy_max {str} -- The operator which is used to evaluate the `buy_max` condition. For example, `">"` would
                represent greater than or from the `operator` module it would represent `operator.gt`. (defaults to None).
            
            condition_sell_max {str} -- The operator which is used to evaluate the `sell_max` condition. For example, `">"` would
                represent greater than or from the `operator` module it would represent `operator.gt`. (defaults to None).
            """
        # Add the key if it doesn't exist. If there is no signal for that indicator, set a template.
        if indicator not in self._indicator_signals:
            self._indicator_signals[indicator] = {}
            self._indicators_key.append(indicator)

        # Add the signals.
        self._indicator_signals[indicator]['buy'] = buy     
        self._indicator_signals[indicator]['sell'] = sell
        self._indicator_signals[indicator]['buy_operator'] = condition_buy
        self._indicator_signals[indicator]['sell_operator'] = condition_sell

        # Add the max signals
        self._indicator_signals[indicator]['buy_max'] = buy_max  
        self._indicator_signals[indicator]['sell_max'] = sell_max
        self._indicator_signals[indicator]['buy_operator_max'] = condition_buy_max
        self._indicator_signals[indicator]['sell_operator_max'] = condition_sell_max

    #Another method for creating a signal would be when one indicator crosses above or below another indicator, so we need to compare the 2 here
    def set_indicator_signal_compare(self,indicator_1:str, indicator_2:str, condition_buy: Any, condition_sell: Any) -> None:
        """Used to set an indicator where one indicator is compared to another indicator.
        Overview:
        ----
        Some trading strategies depend on comparing one indicator to another indicator.
        For example, the Simple Moving Average crossing above or below the Exponential
        Moving Average. This will be used to help build those strategies that depend
        on this type of structure.
        Arguments:
        ----
        indicator_1 {str} -- The first indicator key, for example `ema` or `sma`.
        indicator_2 {str} -- The second indicator key, this is the indicator we will compare to. For example,
            is the `sma` greater than the `ema`.
        condition_buy {str} -- The operator which is used to evaluate the `buy` condition. For example, `">"` would
            represent greater than or from the `operator` module it would represent `operator.gt`.
        
        condition_sell {str} -- The operator which is used to evaluate the `sell` condition. For example, `">"` would
            represent greater than or from the `operator` module it would represent `operator.gt`.
        """

        #define the key
        key = "{ind_1}_comp_{ind_2}".format(
            ind_1 = indicator_1,
            ind_2 = indicator_2
        )

        #Add the key if it doesn't exist
        if key not in self._indicator_signals:
            self._indicator_signals[key] = {}
            self._indicators_comp_key.append(key)
        
        #Grab the dicionary
        indicator_dict = self._indicator_signals[key]

        #Add the signals
        indicator_dict['type'] = 'comparison'
        indicator_dict['indicator_1'] = indicator_1
        indicator_dict['indicator_2'] = indicator_2
        indicator_dict['buy_operator'] = condition_buy
        indicator_dict['sell_operator'] = condition_sell

    def get_indicator_signal(self,indicator:str = None) -> Dict:
        """Return the raw Pandas Dataframe Object.
        Arguments:
        ----
        indicator {Optional[str]} -- The indicator key, for example `ema` or `sma`.
        Returns:
        ----
        {dict} -- Either all of the indicators or the specified indicator.
        """
        if indicator and indicator in self._indicator_signals:      #if user passes in indicator and it is in the indicator_signals dictionary
            return self._indicator_signals[indicator]
        else:       #if user does not pass in any indicator, return all of them
            return self._indicator_signals

    @property
    def price_df(self) -> pd.DataFrame:
        return self._frame

    @price_df.setter
    def price_df(self,price_df:pd.DataFrame) -> None:
        self._frame = price_df

    def change_in_price(self) -> pd.DataFrame:
        """Calculates the Change in Price.
        Returns:
        ----
        {pd.DataFrame} -- A data frame with the Change in Price included.
        """
        locals_data = locals()      #Capture information passed through as arguments in a local symbol table, it changes depending where you can it
        del locals_data['self']     #delete the 'self' key as it doesn't matter, we only care about the arguments we pass through besides 'self'

        column_name = 'change_in_price'            #Create an additional column in the dataframe
        self._current_indicators[column_name] = {}      #Create a new dictionary with key 'change_in_price' to be placed in our current indicators dictionary
        self._current_indicators[column_name]['args'] = locals_data      #Create a new dictionary with key 'args' to be placed in our _current_indicators[column_name] dict
                                                                         #The values are the arguments passed to the function, so it saves all our arguments passed to an object
        self._current_indicators[column_name]['func'] = self.change_in_price   #Storing the function so it can be called again

        #Calculating the actual indicator
        self._frame[column_name] = self._frame['close'].transform(
            lambda x: x.diff()      #Calculate the change in price
        )

        return self._frame

    def rsi(self,period:int,method:str='wilders') ->pd.DataFrame:
        locals_data = locals()
        del locals_data['self']

        column_name = 'rsi'
        self._current_indicators[column_name] = {}
        self._current_indicators[column_name]['args'] = locals_data
        self._current_indicators[column_name]['func'] = self.rsi

        #Since RSI indicator require change in price, check whether change in price column exists first, if not, create it by calling change_in_price()
        if 'change_in_price' not in self._frame.columns:
            self.change_in_price()
        
        self._frame['up_day'] = self._price_groups['change_in_price'].transform(
            lambda x: np.where(x>=0,x,0)        #Return elements chosen from x or y depending on condition, if x>=0, x=x, elif x < 0, return 0, only keep positive values
        )

        self._frame['down_day'] = self._price_groups['change_in_price'].transform(
            lambda x: np.where(x<=0,x.abs(),0)        #Return elements chosen from x or y depending on condition, if x<=0, x=x.abs(), elif x > 0, return 0, only keep negative values
        )

        self._frame['ewma_up'] = self._price_groups['up_day'].transform(
            lambda x: x.ewm(span = period).mean()        #Give rolling average on up_day
        )

        self._frame['ewma_down'] = self._price_groups['down_day'].transform(
            lambda x: x.ewm(span = period).mean()        #Give rolling average on up_day
        )
        relative_strength = self._frame['ewma_up']/self._frame['ewma_down']
        relative_strength_index = 100.0 - (100.0/ (1.0 + relative_strength))   #Using RSI formula

        self._frame['rsi'] = np.where(relative_strength_index==0,100, 100 - (100 / (1 + relative_strength_index)))   #Step 2 of the RSI calculation

        # Clean up before sending back. Delete all the unnessary columns and just leave 'rsi' in place
        self._frame.drop(
            labels=['ewma_up', 'ewma_down', 'down_day', 'up_day', 'change_in_price'],
            axis=1,
            inplace=True
        )

        return self._frame

    #Simple moving average
    def sma(self, period:int) -> pd.DataFrame:
        locals_data = locals()
        del locals_data['self']

        column_name = 'sma'
        self._current_indicators[column_name] = {}
        self._current_indicators[column_name]['args'] = locals_data
        self._current_indicators[column_name]['func'] = self.sma

        self._frame[column_name] = self._price_groups['close'].transform(
            lambda x: x.rolling(window=period).mean()
        )

        return self._frame

    def ema(self, period:int, alpha: float = 0.0) -> pd.DataFrame:
        locals_data = locals()
        del locals_data['self']

        column_name = 'ema'
        self._current_indicators[column_name] = {}
        self._current_indicators[column_name]['args'] = locals_data
        self._current_indicators[column_name]['func'] = self.ema

        self._frame[column_name] = self._price_groups['close'].transform(
            lambda x: x.ewm(span=period).mean()
        )

        return self._frame

    #refresh all the indicators every time a new row is added
    def refresh(self):
        #First update the groups
        self._price_groups = self._stock_frame.symbol_groups    #Data related to one symbol is in a symbol_group

        #Loop through all the stored indicators
        for indicator in self._current_indicators:

            indicator_arguments = self._current_indicators[indicator]['args']
            indicator_function = self._current_indicators[indicator]['func']

            #Update the columns
            indicator_function(**indicator_arguments)   # ** is used to unpack the indicator_arguments dictionary for passing them as arguments, google 'python dictionary unpacking' 

    #Check whether the signals have been flagged for the indicators, if there is a buy/sell signal generated , then return the last row of dataframe. If not, return None.
    def check_signals(self) -> Union[pd.DataFrame,None]:    #Union returns either one or the other
        """Checks to see if any signals have been generated.
        Returns:
        ----
        {Union[pd.DataFrame, None]} -- If signals are generated then a pandas.DataFrame
            is returned otherwise nothing is returned.
        """
        signals_df = self._stock_frame._check_signals(
            indicators=self._indicator_signals,
            indicators_comp_key=self._indicators_comp_key,
            indicators_key=self._indicators_key
        )
        return signals_df

    
            


