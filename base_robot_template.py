# The Imports

import copy
import logging #used to create all the robot logs

from fmclient import Agent, Market, Holding, Session, Order, OrderType, OrderSide


# Flex-E-Market credential

FM_ACCOUNT = "fain-premium"
FM_EMAIL = "trader03@d002"
FM_PASSWORD = "LIPNE"
ROBOT_NAME = "fmClient Installed Test Robot"
FM_MARKETPLACE_ID = 1516


# The Base Robot Class definition

class FMRobot(Agent):
    """ A agent template that ...
    """
    def __init__(self, account: str, email: str, password: str, marketplace_id: int, name: str = 'FMRobot'):
        # Initialise the parent class, Agent
        super().__init__(account, email, password, marketplace_id, name=name)
        
        # Set the logger to DEBUG to record all events or INFO for key events.
        # logging.getLogger('agent').setLevel(logging.DEBUG)

        self.description = f"This is {name} bot for {email}!"

    def initialised(self) -> None:

        # print fm_id, name, description of market place
        self.inform(f"market place: {self.marketplace.name}, marketplace id: {self.marketplace.fm_id}, marketplace description: {self.marketplace.description}")

        # print fm_id, name, description, price tick size of markets in the market place
        for market in self.markets.values():
            self.inform(f"\t with market: {market.name}, fm_id: {market.fm_id}, market description: {market.description}, tick size: {market.price_tick}")

    def pre_start_tasks(self) -> None:
        pass

    def received_session_info(self, session: Session) -> None:
        if session.is_open:
            self.inform(f"Session id: {session.fm_id}, your are able to trade")
        elif session.is_closed:
            self.inform(f"Session id: {session.fm_id}, the session is closed")
        elif session.is_paused:
            self.inform(f"Session id: {session.fm_id}, the session is paused")

    def received_holdings(self, holdings: Holding) -> None:
        self.inform(f"my current settled cash is {holdings.cash}, my current avaliable cash is {holdings.cash_available}")
        for market, asset in holdings.assets.items():
            self.inform(f"\t holdings of asset in market {market.name} : {asset.units}")

    def received_orders(self, orders: list[Order]) -> None:
        for order in orders:
            self.inform(f"we have a new order : {order.fm_id}, this is a {order.order_type.name} order for {order.market.name} to {order.order_side.name} {order.units} units at price {order.price}")
            if order.mine:
                self.inform(f"\t this order is mine")

    def order_accepted(self, order: Order) -> None:
        pass

    def order_rejected(self, info: dict[str, str], order: Order) -> None:
        pass


# The dunder name equals dunder main

if __name__ == "__main__":
    # Swap your robot
    bot = FMRobot(account=FM_ACCOUNT, email=FM_EMAIL, password=FM_PASSWORD, marketplace_id=FM_MARKETPLACE_ID, name=ROBOT_NAME)    
    bot.run()
