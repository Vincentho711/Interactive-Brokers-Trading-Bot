import pandas as pd
import numpy as np
import json
import re
import pathlib

from typing import Tuple
from typing import Dict
from typing import List
from typing import Optional
from typing import Union
from datetime import datetime
from datetime import timezone
from ibw.client import IBClient

class Trade():
    """
    Object Type:
    ----
    `robot.Trade`
    Overview:
    ----
    Reprsents the Trade Object which is used to create new trades,
    add customizations to them, and easily modify existing content.
    """
    def __init__(self):
        """Initalizes a new order."""
        self.account = ""
        self.order_instructions = {}
        self.local_trade_id = ""    #Local trade ID
        self.trade_id = ""      #order_id given by IB
        self.side = ""  #Long/short
        self.side_opposite = "" #Opposite of self.side
        self.quantity = 0.0
        self.total_cost = 0.0
        self.conid = 0
        self.order_status = ""

        self._order_response = {}
        self._triggered_added = False
        self._multi_leg = False
        self._ib_client:IBClient = None

    def create_order(self, account_id:Optional[str], local_trade_id:str, conid:str, ticker:str, security_type:str, order_type: str, side:str, duration:str , 
    price:float = 0.0, quantity:float = 0.0,outsideRTH:bool=False) -> dict:
        """Creates a new Trade object template.
        A trade object is a template that can be used to help build complex trades
        that normally are prone to errors when writing the JSON. Additionally, it
        will help the process of storing trades easier.
        Please note here, sometimes this end-point alone can't make sure you submit the order 
        successfully, you could receive some questions in the response, you have to to answer 
        them in order to submit the order successfully. You can use "/iserver/reply/{replyid}" 
        end-point to answer questions.
        Arguments:
        ----
        account_id {str} -- It is optional. It should be one of the accounts returned by /iserver/accounts. 
            If not passed, the first one in the list is selected.
        local_trade_id {str} -- Optional, if left blank, a unqiue identification code will be automatically generated
        conid {str} -- conid is the identifier of the security you want to trade, you can find the conid with /iserver/secdef/search
        ticker {str} -- Ticker symbol for the asset
        security_type {str} -- The order's security/asset type, can be one of the following
            ['STK','OPT','WAR','IOPT','CFD','BAG']
        order_type {str} -- The type of order you would like to create. Can be
            one of the following: ['MKT', 'LMT', 'STP', 'STP_LIMIT']
        side {str} -- The side the trade will take, can be one of the
            following: ['BUY', 'SELL']
        duration {str} -- The tif/duration of order, can be one of the following: ['DAY','GTC']
        price {float} -- For 'MKT', this is optional. For 'lmt', this is the limit price. For 'STP', 
            this is the stop price 
        quantity {float} -- The quantity of assets to buy
        outsideRTH {bool} -- Execute outside trading hours if True, default is False
        Returns:
        ----
        {dict} -- Returns a dictionary containing 'id' and 'message'.if the message is a question,
             you have to reply to question in order to submit the order successfully. See more in the "/iserver/reply/{replyid}" endpoint.
        """

        #Set the other required parameters for the api call, refer to api manual or inspect source code when placing a order
        isClose = False
        referrer = "QuickTrade"
        useAdaptive = False

        #Check if conid has been passed through as the test will miss it if conid == ''
        if (conid==None or conid==''):
            raise ValueError("Conid is none or has no value")

        #Combine conid and ticker to form 'secType' parameter
        secType = str(conid) + ":" + security_type
        #secType = separator.join([conid,security_type])

        #Build a default cOID based on arguments passed if local_trade_id is None
        if local_trade_id is None:
            current_timestamp = str(int(datetime.now(tz=timezone.utc).timestamp()))
            local_trade_id = ticker + '_' + side + '_' + str(price) + '_' + current_timestamp

        #Convert conid from str to integer as IB requires conid to be integer
        conid=int(conid)
        
        order_dict = {
            'acctId': account_id,
            'cOID': local_trade_id,
            'isClose': isClose,
            #Lisiting exchange is not passed as it is optional, smart routing is used
            'orderType': order_type,
            'outsideRTH': outsideRTH,
            'conid': conid,
            'price': price,
            'quantity': quantity,
            'referrer': referrer,
            'secType':secType,
            'side': side,
            'ticker': ticker,
            'tif': duration,
            'useAdaptive': useAdaptive
        }
        #Check if all values have been filled
        for key,value in order_dict.items():
            if (value == '' or (type(value)!=bool and value == 0.0)):    #Because python evaluates False as 0, check type to prevent False be mistaken as unfilled value
                print(value)
                raise ValueError("order_dict has unfilled values. {key} is not filled, the current value is {value}".format(key=key,value=value))
        
        #Make a reference on all data passed through
        self.symbol = ticker
        self.conid = conid
        self.quantity = quantity
        self.price = price
        self.order_type = order_type
        self.asset_type = security_type
        #Assigned order_dict to a self attribute which can be called to place order
        self.order_instructions = order_dict
        self.local_trade_id = local_trade_id
        self.side = side
        #Set self.side_opposite
        if self.side=='BUY':
            self.side_opposite = 'SELL'
        else:
            self.side_opposite = 'BUY'
        
        return order_dict

    def preview_order(self) -> Dict:
        """Preview an order
        After a order has been created with create_order(), the order can be
        passed to the IB server to check and be reviewed before placing the order.
        Arguments:
        ----

        Returns:
        ----
        {dict} -- A dictionary with keys: 'amount','equity','initial','maintenance','warn','error'
        
        """
        
        #Check if order_instructions exists
        if self.order_instructions:
            #Call place_order_scenario() in IBClient for order preview
            preview_order_dict = self._ib_client.place_order_scenario(account_id=self.account,order=self.order_instructions)
        
            #Using the return from preview to set some attributes
            if preview_order_dict['error'] is not None:
                raise RuntimeError("There is an error in the order. Error: {}".format(preview_order_dict['error']))

            self.order_status = "Not submitted"
            #Remove non numeric value from preview_order_dict['amount']['total'] to store it as string
            total_cost = re.sub(r'[^\d.]+', '', preview_order_dict['amount']['total'])
            print("Total cost of order: {}".format(total_cost))
            self.total_cost = float(total_cost)

            return preview_order_dict
        else:
            raise TypeError("order_dict is not in a form of a dictionary.")

    def place_order(self,ignore_warning=False) -> Dict:
        """Place an order
        Ideally, preview_order() should be called to check that order_instructions has no issues.
        place_order() uses order_instructions dictionary which is an attribute of Trade object to execute the order. 
        Please note here, sometimes this endpoint alone can't make sure you submit the order successfully, 
        you could receive some questions in the response, you have to to answer them in order to 
        submit the order successfully. You can use "/iserver/reply/{replyid}" endpoint to answer questions.
        Arguments:
        ----
        ignore_warning {bool} -- IB will require confirmation to place order if user has no live data subscription.
            Set this to True if you acknowledge the warning and an automatic reply will be sent to IB. It also handles 
            a number of scenarios, check the code in the trades.py for clarification.
        Returns:
        ----
        {dict} -- A dictionary containing the 'id' and 'message'. If the message is a question,
            you have to reply to question in order to submit the order successfully, see more in the 
            "/iserver/reply/{replyid}" endpoint
        """
        #Check if self.order_instructions exist
        if self.order_instructions:
            place_order_dict = self._ib_client.place_order(account_id=self.account,order=self.order_instructions)

            #Sometimes, IB will return with a warning about trading without market data sub and prompt a reply
            if 'message' in place_order_dict[0].keys() and 'o354' in place_order_dict[0]['messageIds']:
                #Check whether the response require a reply by seeing if 'message' is a key of response and 'messageIds' == 'o354'  
                #'o354' is the warning code for trading without real time data
                print("Warning of trading without live data has been ignored!")
                reply_id = place_order_dict[0]['id']
                #Send an automatic reply to authorise trade
                place_order_dict = self._ib_client.place_order_reply(reply_id=reply_id,reply=True)
            
            elif 'message' in place_order_dict[0].keys() and 'o163' in place_order_dict[0]['messageIds']:
                # Sometimes, if an limit order has been submitted and the limit price exceeds the current price by 
                # the percentage constraint of 3%, IB will send an warning with 'messageIds' == 'o163'.
                # This case will also be handled when ignore_warning is False.
                print("Warning of limit price exceeds the current price by more than 3 percent has been ignored!")
                reply_id = place_order_dict[0]['id']
                #Send an automatic reply to authorise trade
                place_order_dict = self._ib_client.place_order_reply(reply_id=reply_id,reply=True)

                
            print(place_order_dict)
            if any(condition in place_order_dict[0]['order_status'] for condition in ['Submitted','PreSubmitted','Filled']):
                #Add data to Trade object if 'order_status' is either 'Submitted', 'Filled' or 'PreSubmitted'

                self.trade_id = place_order_dict[0]['order_id']
                self.order_status = place_order_dict[0]['order_status']

                #Record the trade and log it down to json file
                self.add_to_order_record()
                return place_order_dict
            else:
                message = "Order hasn't been placed and might require additional input."
                raise RuntimeError(message + "Order Status: {}".format(place_order_dict['order_status']))

        else:
            raise TypeError("self.order_instructions is undefined, please create the order first.")

    def add_to_order_record(self) -> None:
        """
        Save the order details onto a json file so orders can be viewed later
        """
        #Establish the location of order_record.json
        record_path = pathlib.Path('order_record/orders.jsonc')
        
        # Convert IB_Client details in self object into strings so they can be read,
        # We can't just dump the IBClient object into a json file
        def default(obj):
            if isinstance(obj,IBClient):
                return str(obj)
        # # Create a directory called 'order_records' in working directory and create a JSON file called 'orders.jsonc'
        # # Initialise the file with empty list
        # with open(file=record_path,mode='w+') as order_file:
        #     json.dump(
        #         obj=[], #Set up empty list
        #         fp=order_file,
        #         indent=4
        #     )
        
        # After a directory is created, open the JSON file and append new data
        with open(file=record_path,mode='a') as order_file_json:
            data = self.__dict__
            order_file_json.write(json.dumps(data,indent=4,default=default))
            order_file_json.close()
    
    def cancel_order(self) -> dict:
        """
        Cancel an open order that has not been filled. Uses the self attribute trade_id to cancel order.

        Returns:
        ----
        {dict} -- A dictionary object that has keys 'order_id', 'msg','conid','account'
        """
        if self.trade_id:
            #Check the order_status to see the status of the order
            if self.order_status=="PreSubmitted":
                #if order is pre-submitted and not filled, then cancel the order
                response = self._ib_client.delete_order(account_id=self.account,customer_order_id=self.trade_id)
                self.order_status = "Cancelled"
                return response
            elif self.order_status == "Filled":
                #if order is filled already, it can't be cancelled
                raise RuntimeError("{} has been filled already so it cannot be cancelled.".format(self.trade_id))
            elif self.order_status == "Cancelled":
                raise RuntimeError("{} has already been cancelled so it cannot be cancelled again.".format(self.trade_id))
            else:
                raise RuntimeError("The order_status of {} is not specidie/is not defined. Please check the status through IB"
            .format(self.trade_id))

        else:
            RuntimeError("self.trade_id is undefined.")
        