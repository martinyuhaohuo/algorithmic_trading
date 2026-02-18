import copy
from enum import Enum
from fmclient import Agent, Market, Holding, Order, OrderSide, OrderType, Session

# Trading account details
# ------ These must be set for testing and market performance evaluation -----
# ------ However, must be removed prior to submission -----
FM_ACCOUNT = "fain-premium"
FM_EMAIL = "trader03@d002"
FM_PASSWORD = "LIPNE"

# Trading market ids and private market target
FM_MARKETPLACE_ID = 1513
PUBLIC_MARKET_ID = 2681
PRIVATE_MARKET_ID = 2682
TARGET_ID = "yh" 
# TARGET_ID = "M000"

# ------ Add a variable called PROFIT_MARGIN -----
PROFIT_MARGIN = 15

# A new variable timing denoting maximum second for trading after receiving a private signal
TIMING = 50

# Enum for the roles of the bot
class Role(Enum):
    BUYER = 0
    SELLER = 1

# Enum for the trading style of the bot
class BotType(Enum):
    ACTIVE = 0
    REACTIVE = 1

# ------ Add a variable called MARKET_PERFORMANCE_BOT_TYPE ----
MARKET_PERFORMANCE_BOT_TYPE = BotType.ACTIVE


class IDSBot(Agent):
    _public_market_id: int
    _private_market_id: int
    _target_id: int
    _margin: int
    _timing: int
    _role: Role | None
    _P_PB: int | None
    _P_PA: int | None
    _last_P_PB: int | None
    _last_P_PA: int | None
    _widget_buy_signal: bool
    _widget_sell_signal: bool
    _order_placing_signal: bool
    _current_standing_order: Order | None
    _widget_asset: int
    _private_asset: int

    # ------ Add an extra parameter bot_type to the constructor -----
    def __init__(self, account: str, email: str, password: str, marketplace_id: int, bot_type: BotType, bot_name: str = "FMBot"):
        super().__init__(account, email, password, marketplace_id, name=bot_name)
        self._public_market_id = PUBLIC_MARKET_ID
        self._private_market_id = PRIVATE_MARKET_ID
        self._target_id = TARGET_ID
        self._margin = PROFIT_MARGIN
        self._timing = 0
        self._role = None
        self._P_PB = None
        self._P_PA = None
        self._last_P_PB = None
        self._last_P_PA = None
        self._widget_buy_signal = False
        self._widget_sell_signal = False
        self._order_placing_signal = False
        self._current_standing_order = None
        self._widget_asset = 0
        self._private_asset = 0
        # ------ Add new class attribute _bot_type to store the type of the bot
        self._bot_type = bot_type

    def initialised(self):
        # Print fm_id, name, description, price tick size of markets in the market place
        for market in self.markets.values():
            self.inform(f"\t with market: {market.name}, fm_id: {market.fm_id}, market description: {market.description}, tick size: {market.price_tick}")

    def pre_start_tasks(self):
        # Periodic functions: check if there is private signal -> place widget ask / bid order -> check if widget order is taken -> place private bid / ask order
        self.execute_periodically(self._check_private_market, 1)
        self.execute_periodically(self._place_widget_order, 1)
        self.execute_periodically_conditionally(self._check_trade_success, 1, condition=lambda: self._current_standing_order is not None)

    def _place_order(self, price, units, side, market_id, target = None):
        # Place an order in given market, at given side, price, units, and with optional target
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
        new_order.ref = f"Market: {market}, Order Type: {new_order.order_type}, Side: {new_order.order_side}, Unit: {new_order.units}, Price: {new_order.price}"
        self.send_order(order = new_order)
        self.inform(f"Placed order: {new_order}")
    
    def received_session_info(self, session: Session):
        # Inform session start, closed, or paused
        if session.is_open:
            self.inform(f"Session id: {session.fm_id}, your are able to trade")
        elif session.is_closed:
            self.inform(f"Session id: {session.fm_id}, the session is closed")
        elif session.is_paused:
            self.inform(f"Session id: {session.fm_id}, the session is paused")

    def received_holdings(self, holdings: Holding):
        # Inform current asset and cash
        self.inform(f"settled cash: {holdings.cash}, avaliable cash: {holdings.cash_available}")
        for market, asset in holdings.assets.items():
            self.inform(f"\t asset in market {market.name} : {asset.units}")
            if market.fm_id == self._public_market_id:
                self._widget_asset = asset.units
            elif market.fm_id == self._private_market_id:
                self._private_asset = asset.units

    def received_orders(self, orders: list[Order]):
        # Update best bid and ask price in private market each time when orders are updated 
        self._P_PB = None
        self._P_PA = None
        for order in Order.current().values():
            if order.order_type is OrderType.LIMIT:
                if not order.mine:
                    if order.market.fm_id == self._private_market_id:
                        if order.order_side is OrderSide.SELL:
                            # update best ask price in private market
                            if self._P_PA is None or self._P_PA > order.price:
                                self._P_PA = order.price
                        elif order.order_side is OrderSide.BUY:
                            # update best bid price in private market
                            if self._P_PB is None or self._P_PB < order.price:
                                self._P_PB = order.price
    
    def _check_private_market(self):
        # Count the time that private signal has remained unchanged
        if self._last_P_PB is not None and self._P_PB is not None and self._last_P_PB == self._P_PB:
            self._timing += 1
        elif self._last_P_PA is not None and self._P_PA is not None and self._last_P_PA == self._P_PA:
            self._timing += 1
        else:
            self._timing = 0
        # Check best bid and ask in private market, determine whether buy or sell in the widget market
        if self._P_PB is not None:
            self._role = Role.BUYER
            self._widget_buy_signal = True
            self._widget_sell_signal = False
            self._last_P_PB = self._P_PB
            self._last_P_PA = None
        elif self._P_PA is not None:
            self._role = Role.SELLER
            self._widget_buy_signal = False
            self._widget_sell_signal = True
            self._last_P_PA = self._P_PA
            self._last_P_PB = None
        else:
            self._role = None
            self._widget_sell_signal = False
            self._widget_buy_signal = False
            self._last_P_PB = None
            self._last_P_PA = None
        # If the private signal remain unchanged for > pre-specified time, cancel standing order in widget market, wait for next private signal
        if self._timing > TIMING:
            self._widget_sell_signal = False
            self._widget_buy_signal = False
            if self._current_standing_order is not None:
                if self._current_standing_order.market.fm_id == self._public_market_id:
                    self._cancel_order(self._current_standing_order)
        
        # After cancelling widget order, if holding is unbalanced, place private order to balance it
        if self._timing > TIMING + 5:
            if self._widget_asset + self._private_asset > 0:
                self.inform(f"The holding is unbalanced at the time of cancelling all order, place private order to balance the holding")
                self._place_order(self._P_PB, 1, "sell", self._private_market_id, target = self._target_id)
                self._current_standing_order = None
                self._order_placing_signal = True
            elif self._widget_asset + self._private_asset < 0:
                self.inform(f"The holding is unbalanced at the time of cancelling all order, place private order to balance the holding")
                self._place_order(self._P_PA, 1, "buy", self._private_market_id, target = self._target_id)
                self._current_standing_order = None
                self._order_placing_signal = True
            else:
                self.inform(f"The holding is balanced")

    def _cancel_order(self, order):
        # Cancel a specified order
        cancel_order = copy.copy(order)
        cancel_order.order_type = OrderType.CANCEL
        self.send_order(order = cancel_order)
        self.inform(f"Cancel order sent, order: {self._current_standing_order}")
    
    def _place_widget_order(self):
        # Check the signal of buy / sell widget, conduct instructed action (send bid order / sell order in widget market)
        if self._widget_buy_signal is True and self._widget_sell_signal is False:
            if self._order_placing_signal is False and self._current_standing_order is None:
                self._place_order(self._P_PB - self._margin, 1, "buy", self._public_market_id)
                self._order_placing_signal = True
        elif self._widget_buy_signal is False and self._widget_sell_signal is True:
            if self._order_placing_signal is False and self._current_standing_order is None:
                self._place_order(self._P_PA + self._margin, 1, "sell", self._public_market_id)
                self._order_placing_signal = True
    
    def _check_trade_success(self):
        self.inform(f"Current standing order: {self._current_standing_order}, traded: {self._current_standing_order.has_traded}")
        # Check if the standing order is traded
        if self._current_standing_order.has_traded is True:
            self.inform(f"I have order traded: {self._current_standing_order.ref}")
            # If the traded standing order is in widget market, pose bid/ask order in privte market to earn margin
            if self._current_standing_order.market.fm_id == self._public_market_id:
                if self._current_standing_order.order_side is OrderSide.BUY:
                    self._place_order(self._P_PB, 1, "sell", self._private_market_id, target = self._target_id)
                    self._current_standing_order = None
                    self._order_placing_signal = True
                elif self._current_standing_order.order_side is OrderSide.SELL:
                    self._place_order(self._P_PA, 1, "buy", self._private_market_id, target = self._target_id)
                    self._current_standing_order = None
                    self._order_placing_signal = True
            # If the traded standing order is in private market, just set current standing order back to None, socan pose order in widget market in future
            elif self._current_standing_order.market.fm_id == self._private_market_id:
                self._current_standing_order = None
        # It might be the case that widget order traded but the attribute not updated, in such case, using current holding to determine whether order is taken
        elif self._widget_asset + self._private_asset > 0:
            self.inform(f"I have order traded: {self._current_standing_order.ref}")
            self._place_order(self._P_PB, 1, "sell", self._private_market_id, target = self._target_id)
            self._current_standing_order = None
            self._order_placing_signal = True
        elif self._widget_asset + self._private_asset < 0:
            self.inform(f"I have order traded: {self._current_standing_order.ref}")
            self._place_order(self._P_PA, 1, "buy", self._private_market_id, target = self._target_id)
            self._current_standing_order = None
            self._order_placing_signal = True

    def order_accepted(self, order: Order):
        # If order accepted, set current standing order to the approved order, set order placing signal to false
        self.inform(f"I have {order.order_type} order accepted by the book: {order.ref}")
        if order.order_type is OrderType.LIMIT:
            self._current_standing_order = order
            self._order_placing_signal = False
        elif order.order_type is OrderType.CANCEL:
            self._current_standing_order = None

    def order_rejected(self, info: dict[str, str], order: Order):
        # If order rejected, action depends on the market
        self.inform(f"I have order rejected by the book: {order.ref}, reason: {info}")
        if order.order_type is OrderType.LIMIT:
            # For widget market order, just set current standing order to None and order placing signal to False
            # If best bid/ask still exist in private market, the robot will place order again through _place_widget_order function
            if order.market.fm_id == self._public_market_id:
                self._current_standing_order = None
                self._order_placing_signal = False
            # For private market order, if rejected, place it again directly
            elif order.market.fm_id == self._private_market_id:
                if order.order_side is OrderSide.SELL:
                    self._place_order(self._P_PB, 1, "sell", self._private_market_id, target = self._target_id)
                    self._current_standing_order = None
                    self._order_placing_signal = True
                elif order.order_side is OrderSide.BUY:
                    self._place_order(self._P_PA, 1, "buy", self._private_market_id, target = self._target_id)
                    self._current_standing_order = None
                    self._order_placing_signal = True


if __name__ == "__main__":
    # ------ Add an extra argument for bot_type to the initalisation -----
    ids_bot = IDSBot(FM_ACCOUNT, FM_EMAIL, FM_PASSWORD, FM_MARKETPLACE_ID, MARKET_PERFORMANCE_BOT_TYPE)
    ids_bot.run()
