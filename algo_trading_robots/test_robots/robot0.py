# The Imports

import copy
import logging #used to create all the robot logs

from fmclient import Agent, Market, Holding, Session, Order, OrderType, OrderSide
import pandas as pd
import time
from datetime import datetime


# Flex-E-Market credential

FM_ACCOUNT = "fain-premium"
FM_EMAIL = "trader03@d002"
FM_PASSWORD = "LIPNE"
ROBOT_NAME = "fmClient Installed Test Robot"
FM_MARKETPLACE_ID = 1513
widget_market_id = 2681
private_market_id = 2682
target_id = "T004"


# The Base Robot Class definition

class FMRobot(Agent):

    def __init__(self, account: str, email: str, password: str, marketplace_id: int, name: str = 'FMRobot'):
        # Initialise the parent class, Agent
        super().__init__(account, email, password, marketplace_id, name=name)
        # self._my_standing_order = pd.DataFrame(columns=["ref", "market", "side", "price", "unit", "order"])
        self._my_standing_order = dict()
        self._best_standing_order = {
            "private": {"buy":None, "sell":None},
            "widget": {"buy":None, "sell":None}
            }
        self.order_num = 1
        self.widget_price_1 = None
        self.widget_price_2 = None
        self.private_price_1 = None
        self.private_price_2 = None
        self.description = f"This is {name} bot for {email}"

    def initialised(self) -> None:
        # print fm_id, name, description, price tick size of markets in the market place
        for market in self.markets.values():
            self.inform(f"\t with market: {market.name}, fm_id: {market.fm_id}, market description: {market.description}, tick size: {market.price_tick}")

    def pre_start_tasks(self) -> None:
        self.execute_periodically(self._buy_at_low, sleep_time = 1)
    
    def _place_order(self, price, units, side, market_id, target = None) -> None:
        market = Market.get_by_id(market_id)
        new_order = Order.create_new(market = market)
        new_order.order_type = OrderType.LIMIT
        if side == "buy":
            new_order.order_side = OrderSide.BUY
        elif side == "sell":
            new_order.order_side = OrderSide.SELL
        new_order.price = price
        new_order.units = units
        new_order.mine = True
        if target:
            new_order.owner_or_target = target
        new_order.ref = f"{datetime.now()}_{self.order_num}"
        self.order_num += 1
        self.send_order(order = new_order)
    
    def _cancel_order(self, ref):
        cancel_order = copy.copy(
            self._my_standing_order[ref]["order"]
        )
        cancel_order.order_type = OrderType.CANCEL
        self.send_order(order = cancel_order)

    def received_session_info(self, session: Session) -> None:
        if session.is_open:
            self.inform(f"Session id: {session.fm_id}, your are able to trade")
        elif session.is_closed:
            self.inform(f"Session id: {session.fm_id}, the session is closed")
        elif session.is_paused:
            self.inform(f"Session id: {session.fm_id}, the session is paused")

    def received_holdings(self, holdings: Holding) -> None:
        pass
        
    def received_orders(self, orders: list[Order]) -> None:
        for order in Order.current().values():
            if order.order_type is OrderType.LIMIT:
                if order.mine:
                    if order.ref not in self._my_standing_order.keys():
                        self._my_standing_order[order.ref] = {
                            "market": order.market.fm_id, 
                            "side": order.order_side, 
                            "price": order.price, 
                            "unit" : order.units, 
                            "order": order
                        }
                else:
                    if order.market.fm_id == private_market_id:
                        if order.order_side is OrderSide.SELL:
                            best_sell_order = self._best_standing_order["private"]["sell"]
                            if best_sell_order is None or best_sell_order.price > order.price:
                                self._best_standing_order["private"]["sell"] = order
                        elif order.order_side is OrderSide.BUY:
                            best_buy_order = self._best_standing_order["private"]["buy"]
                            if best_buy_order is None or best_buy_order.price < order.price:
                                self._best_standing_order["private"]["buy"] = order
                    
                    elif order.market.fm_id == widget_market_id:
                        if order.order_side is OrderSide.SELL:
                            best_sell_order = self._best_standing_order["widget"]["sell"]
                            if best_sell_order is None or best_sell_order.price > order.price:
                                self._best_standing_order["widget"]["sell"] = order
                        elif order.order_side is OrderSide.BUY:
                            best_buy_order = self._best_standing_order["widget"]["buy"]
                            if best_buy_order is None or best_buy_order.price < order.price:
                                self._best_standing_order["widget"]["buy"] = order
    
    def _check_signal_widget_buy(self):
        signal = False
        best_private_buy = self._best_standing_order["private"]["buy"]
        best_widget_sell = self._best_standing_order["widget"]["sell"]
        if (best_private_buy is not None) & (best_widget_sell is not None):
            if best_private_buy.price >= best_widget_sell.price + 20:
                signal = True
                self.widget_price_1 = best_widget_sell.price
                self.private_price_1 = best_private_buy.price
        return signal
    
    def _check_signal_private_buy(self):
        signal = False

    def _check_signal_widget_sell(self):
        signal = False
        best_private_sell = self._best_standing_order["private"]["sell"]
        best_widget_buy = self._best_standing_order["widget"]["buy"]
        if (best_private_sell is not None) & (best_widget_buy is not None):
            if best_private_sell.price <= best_widget_buy.price - 20:
                signal = True
                self.widget_price_2 = best_widget_buy.price
                self.private_price_2 = best_private_sell.price
        return signal

    def _widget_buy(self):
        self._place_order(self.widget_price_1, 1, "buy", widget_market_id)
    
    def _private_sell(self):
        self._place_order(self.private_price_1, 1, "sell", private_market_id, target = target_id)
        
    def _widget_sell(self):
        self._place_order(self.widget_price_2, 1, "sell", widget_market_id)
    
    def _private_buy(self):
        self._place_order(self.private_price_2, 1, "buy", private_market_id, target = target_id)

    def order_accepted(self, order: Order) -> None:
        self.inform(f"I have {order.order_type.name} order accepted by the book: {order.ref}")
        if order.order_type is OrderType.LIMIT:
            self._my_standing_order[order.ref] = {
                "market": order.market.fm_id, 
                "side": order.order_side, 
                "price": order.price, 
                "unit" : order.units, 
                "order": order
            }
        elif order.order_type is OrderType.CANCEL:
            value = self._my_standing_order.pop(order.ref, None)

    def order_rejected(self, info: dict[str, str], order: Order) -> None:
        self.inform(f"I have {order.order_type.name} order rejected by the book: {order.ref}, reason: {info}")

# The dunder name equals dunder main
if __name__ == "__main__":
    # Swap your robot
    bot = FMRobot(account=FM_ACCOUNT, email=FM_EMAIL, password=FM_PASSWORD, marketplace_id=FM_MARKETPLACE_ID, name=ROBOT_NAME)    
    bot.run()
