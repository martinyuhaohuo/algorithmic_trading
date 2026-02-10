# The Imports

import copy
import logging #used to create all the robot logs

from fmclient import Agent, Market, Holding, Session, Order, OrderType, OrderSide
import pandas as pd
import time
import datetime


# Flex-E-Market credential

FM_ACCOUNT = "fain-premium"
FM_EMAIL = "yh620@d002"
FM_PASSWORD = "yh620"
ROBOT_NAME = "Order Generator"
FM_MARKETPLACE_ID = 1513
widget_market_id = 2681
private_market_id = 2682
target_id = "T103"


# The Base Robot Class definition

class FMRobot(Agent):

    def __init__(self, account: str, email: str, password: str, marketplace_id: int, name: str = 'FMRobot'):
        # Initialise the parent class, Agent
        super().__init__(account, email, password, marketplace_id, name=name)
        self._my_standing_order = pd.DataFrame(columns=["ref", "market", "side", "price", "unit", "order"])
        self.order_num = 0
        self.description = f"This is {name} bot for {email}"

    def initialised(self) -> None:
        # print fm_id, name, description, price tick size of markets in the market place
        for market in self.markets.values():
            self.inform(f"\t with market: {market.name}, fm_id: {market.fm_id}, market description: {market.description}, tick size: {market.price_tick}")

    def pre_start_tasks(self) -> None:
        self._place_order(600, 1, "sell", widget_market_id)
        self._place_order(620, 1, "sell", widget_market_id)
        self._place_order(650, 1, "sell", widget_market_id)
        self._place_order(700, 2, "buy", private_market_id, target = target_id)
        self._place_order(10, 2, "buy", private_market_id, target = target_id)
        self._place_order(5, 1, "buy", private_market_id, target = target_id)
    
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
        new_order.ref = f"{side}_{units}_{price}_{self.order_num}"
        self.order_num += 1
        self.send_order(order = new_order)

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
        pass

    def order_accepted(self, order: Order) -> None:
        self.inform(f"I have {order.order_type.name} order accepted by the book: {order.ref}")

    def order_rejected(self, info: dict[str, str], order: Order) -> None:
        self.inform(f"I have {order.order_type.name} order rejected by the book: {order.ref}, reason: {info}")

# The dunder name equals dunder main
if __name__ == "__main__":
    # Swap your robot
    bot = FMRobot(account=FM_ACCOUNT, email=FM_EMAIL, password=FM_PASSWORD, marketplace_id=FM_MARKETPLACE_ID, name=ROBOT_NAME)    
    bot.run()
