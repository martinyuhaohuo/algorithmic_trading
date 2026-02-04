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
        
        self._my_standing_sell_order = None
        
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
        market_id = 2686
        market = Market.get_by_id(market_id)

        new_order = Order.create_new(market = market)
        new_order.order_type = OrderType.LIMIT
        new_order.order_side = OrderSide.BUY
        new_order.price = 50 #50 cents = 0.5 dollar
        new_order.units = 1
        new_order.mine = True
        new_order.ref = f"My order number: {1}"

        self.send_order(order = new_order)
        self.inform(f"I have sent a new order: {new_order}")

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

    def _cancel_my_standing_order(self):
        if self._my_standing_sell_order is None:
            self.inform("There is no standing order to cancell")
            return
        
        cancel_order = copy.copy(self._my_standing_sell_order)
        cancel_order.order_type = OrderType.CANCEL
        self.send_order(order = cancel_order)
        self.inform(f"I have cancelled an order: {cancel_order}")

    def received_orders(self, orders: list[Order]) -> None:

        market_id = 2686
        best_standing_sell_order = None

        for order in Order.current().values():
            if order.order_type is OrderType.LIMIT:
                if order.order_side is OrderSide.SELL:
                    if order.market.fm_id == market_id:
                        if order.mine:
                            self._my_standing_sell_order = order
                        else:
                            if best_standing_sell_order is None or best_standing_sell_order.price > order.price:
                                best_standing_sell_order = order
        
        self.inform(f"best standing sell order : {best_standing_sell_order.fm_id}, this is a {best_standing_sell_order.order_type.name} order for {best_standing_sell_order.market.name} to {best_standing_sell_order.order_side.name} {best_standing_sell_order.units} units at price {best_standing_sell_order.price}")

        if self._my_standing_sell_order is not None:
            self._cancel_my_standing_order()


    def order_accepted(self, order: Order) -> None:
        self.inform(f"I have {order.order_type.name} order accepted by the book: {order.ref}")
        if order.order_type is OrderType.LIMIT:
            self._my_standing_sell_order = order
        elif order.order_type is OrderType.CANCEL:
            self._my_standing_sell_order = None

    def order_rejected(self, info: dict[str, str], order: Order) -> None:
        self.inform(f"I have {order.order_type.name} order rejected by the book: {order.ref}, reason: {info}")
        self._my_standing_sell_order = None
    

# The dunder name equals dunder main

if __name__ == "__main__":
    # Swap your robot
    bot = FMRobot(account=FM_ACCOUNT, email=FM_EMAIL, password=FM_PASSWORD, marketplace_id=FM_MARKETPLACE_ID, name=ROBOT_NAME)    
    bot.run()
