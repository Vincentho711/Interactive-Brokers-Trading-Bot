from typing import List
from typing import Dict
from typing import Union
from typing import Optional
from typing import Tuple

from ibw.client import IBClient

import robot.stock_frame as stock_frame
import pandas as pd
import numpy as np


class Portfolio():

    def __init__(self,account_id = Optional[str]):
        """Initalizes a new instance of the Portfolio object.
        Keyword Arguments:
        ----
        account_number {str} -- An accout number to associate with the Portfolio. (default: {None})
        """
        self.account = account_id
        self.positions = {}
        self.positions_count = 0
        
        self._ib_client: IBClient = None
        self._stock_frame : stock_frame.StockFrame = None

        
    #Create an add_position function to add positions to portfolio
    def add_position(self,symbol:str, asset_type:str, purchase_date:Optional[str],order_status: str, quantity: float = 0.0, purchase_price: float = 0.0, ) -> Dict:
        """Adds a single new position to the the portfolio.
        Arguments:
        ----
        symbol {str} -- The Symbol of the Financial Instrument. Example: 'AAPL' or '/ES'

        asset_type {str} -- The type of the financial instrument to be added. For example,
            'STK','OPT','WAR','IOPT','CFD','BAG'.
        purchase_date {str} -- This is optional, must be in ISO format e.g. yyyy-mm-dd
        purchase_price {float} -- The purchase price, default is 0.0
        quantity -- The number of shares bought
        
        Returns:
        ----
        {dict} -- a dictionary object that represents a position in the portfolio
        """
        self.positions[symbol] = {}
        self.positions[symbol]['symbol'] = symbol
        self.positions[symbol]['asset_type'] = asset_type
        self.positions[symbol]['purchase_price'] = purchase_price
        self.positions[symbol]['quantity'] = quantity
        self.positions[symbol]['purchase_date'] = purchase_date
        self.positions[symbol]['order_status'] = order_status
        
        if purchase_date:
            self.positions[symbol]['ownership_status'] = True
        else:
            self.positions[symbol]['ownership_status'] = False

        return self.positions[symbol]
    
    def add_positions(self,positions:List[dict]) -> dict:
        if isinstance(positions,list):
            for position in positions:
                self.add_position(
                    symbol=position['symbol'],
                    asset_type=position['asset_type'],
                    purchase_date=position.get('purchase_date',None),    #If 'puchase_date' is not passed through, set to None
                    purchase_price=position.get('purchase_price',0.0),
                    quantity=position.get('quantity',0.0),
                    order_status=position['order_status']
                )
            return self.positions
        else:
            raise TypeError("Positions must be a list of dictionaries!")
    
    def remove_position(self,symbol:str) -> Tuple[bool,str]:
        if symbol in self.positions:
            del self.positions[symbol]
            return (True,"Symbol {symbol} was successfully removed.".format(symbol=symbol))
        else:
            return (False,"Symbol {symbol} doesn't exist in the portfolio.".format(symbol=symbol))

    def in_portfolio(self,symbol:str) -> bool:
        if symbol in self.positions:
            return True
        else:
            return False

    def is_profitable(self,symbol:str, current_price:float) -> bool:
        if self.in_portfolio(symbol=symbol):
            #Grab the purchase price
            purchase_price = self.positions[symbol]['purchase_price']    #Select the purchase_price for a symbol row
            #Check if symbol is in portfolio
            if current_price > purchase_price:
                return True
            else: 
                return False
        else:
            raise ValueError("Symbol {symbol} is not in the portfolio.".format(symbol=symbol))

    def get_ownership_status(self,symbol:str) -> bool:
        """Gets the ownership status for a position in the portfolio.
        Arguments:
        ----
        symbol {str} -- The symbol you want to grab the ownership status for.
        Returns:
        ----
        {bool} -- `True` if the we own the position, `False` if we do not own it.
        """
        if self.in_portfolio(symbol=symbol) and self.positions[symbol]['ownership_status']:
            return self.positions[symbol]['ownership_status']
        else:
            return False

    def set_ownership_status(self, symbol: str, ownership: bool) -> None:
        """Sets the ownership status for a position in the portfolio.
        Arguments:
        ----
        symbol {str} -- The symbol you want to change the ownership status for.
        ownership {bool} -- The ownership status you want the symbol to have. Can either
            be `True` or `False`.
        Raises:
        ----
        KeyError: If the symbol does not exist in the portfolio it will return an error.
        """

        if self.in_portfolio(symbol=symbol):
            self.positions[symbol]['ownership_status'] = ownership
        else:
            raise KeyError(
                "Can't set ownership status, as you do not have the symbol in your portfolio."
            )

    def total_allocation(self):
        pass

    def risk_exposure(self):
        pass

    def total_market_value(self):
        pass