import copy
import logging
from itertools import product
from fmclient import (
    Agent, 
    Market, 
    Holding, 
    Session, 
    Order, 
    OrderType, 
    OrderSide
    )

# Trading account details
# ------ These must be set for testing and market performance evaluation ------
# ------ However, must be removed prior to submission -------------------------
FM_ACCOUNT = ""
FM_EMAIL = ""
FM_PASSWORD = ""

# ------ Market ID, risk penalty, min margin, decrease in min margin every 30s-
FM_MARKETPLACE_ID = 1524
RISK_PENALTY = 0.01
PROFIT_MARGIN = 3.5
MARGIN_REDUC = 0.5

#------------------------------------------------------------------------------
# The robot class definition
#------------------------------------------------------------------------------
class CAPMBot(Agent):
    _risk_penalty: float
    _payoffs: dict[int, list[int]]
    _bids: dict[int, int | None]
    _asks: dict[int, int | None]
    _asset: dict[int, int]
    _last_asset: dict[int, int]
    _cash: int
    _best_order_list: list[Order] | None
    _best_performance: float | None
    _standing_order_list: dict[int, Order | None]
    _order_placing: dict[int, bool]
    _session_time: int
    _wait_time: int
    _order_cancelling: dict[int, int]
    _min_margin: float
    _current_performance: float
    _perform_check_time: int
    _session_open: bool
    _margin_reduc: float

#------------------------------------------------------------------------------
# Initialize the bot states
#------------------------------------------------------------------------------
    def __init__(
            self, 
            account: str, 
            email: str, 
            password: str, 
            marketplace_id: int, 
            risk_penalty: float, 
            min_margin: float,
            margin_reduc: float,
            bot_name: str = "CAPMBot"
            ) -> None:
        """
        Initalise the CAPM bot and its internal states
        
        Args:
            account: FM_account name
            email:FM_account email
            password: FM_account password
            marketplace_id: ID of the market place
            risk_penalty: risk-aversion for calculating payoff
            min_margin: minimum imporvement in performance required in trade
            margin_reduc: amount by which min_margin is reduced every 30s
            bot_name: name of the bot
        """
        super().__init__(
            account, 
            email, 
            password, 
            marketplace_id, 
            name=bot_name
            )
        self._risk_penalty = risk_penalty
        self._payoffs = {}
        self._bids = {}
        self._asks = {}
        self._asset = {}
        self._last_asset = {}
        self._cash = 0
        self._best_order_list = None
        self._best_performance = None
        self._standing_order_list = {}
        self._order_placing = {}
        self._session_time = 1
        self._wait_time = 0
        self._order_cancelling = {} 
        self._min_margin = min_margin
        self._current_performance = 0
        self._perform_check_time = 0
        self._session_open = False
        self._margin_reduc = margin_reduc

#------------------------------------------------------------------------------
# Extract payoff distribution and asset ids, update initial bot states
#------------------------------------------------------------------------------
    def initialised(self) -> None:
        """
        Extract payoff distribution and assets ids and update initial states
        """
        for market in self.markets.values():
            asset_id = market.fm_id
            description = market.description
            # Extract payoff distribution for each asset
            self._payoffs[asset_id] = [
                int(payoff) for payoff in description.split(",")
                ]
            # Update inital value of other bot states
            self._bids[asset_id] = None
            self._asks[asset_id] = None
            self._asset[asset_id] = 0
            self._last_asset[asset_id] = 0
            self._standing_order_list[asset_id] = None
            self._order_placing[asset_id] = False
            self._order_cancelling[asset_id] = 0
        self.inform("Bot initialised, I have the payoffs for the states.")

#------------------------------------------------------------------------------
# Get expected performance for a given list of orders
#------------------------------------------------------------------------------
    def get_potential_performance(self, orders: list[Order]) -> float:
        """
        Returns the portfolio performance if all the given list of orders is 
        executed based on your current holdings.
        The performance as per the following formula:
        Performance = ExpectedPayoff - b * PayoffVariance, where b is the 
        penalty for risk.

        Args:
            orders: list of orders to evaluate
        Returns: 
            performance (float)
        """
        # Initalize expected asset as current asset, expected cash as 
        # current cash
        expected_asset = {}
        for market in self.markets.values():
            asset_id = market.fm_id
            expected_asset[asset_id] = self._asset[asset_id]
        expected_cash = self._cash/100
        
        # Adjust expected asset and cash based on input order list
        for order in orders:
            if order.order_side == OrderSide.BUY:
                expected_cash -= (order.price * order.units)/100
                expected_asset[order.market.fm_id] += order.units
            elif order.order_side == OrderSide.SELL:
                expected_cash += (order.price * order.units)/100
                expected_asset[order.market.fm_id] -= order.units

        # Compute payoff at each state
        payoff_list = []
        state_num = len(list(self._payoffs.values())[0])
        for state in range(state_num):
            payoff = 0
            for market in self.markets.values():
                asset_id = market.fm_id
                payoff += expected_asset[asset_id]*(
                    self._payoffs[asset_id][state]/100
                    )
            payoff += expected_cash
            payoff_list.append(payoff)
        
        # Compute expected payoff
        expected_payoff = 0
        for payoff in payoff_list:
            expected_payoff += payoff
        expected_payoff = expected_payoff/len(payoff_list)

        # Compute variance
        variance = 0
        for payoff in payoff_list:
            variance += (payoff - expected_payoff)**2
        variance = variance/len(payoff_list)

        # Compute performance
        performance = expected_payoff - variance*self._risk_penalty
        return performance

#------------------------------------------------------------------------------
# Check if current performance is optimal, suggest optimal improvement
#------------------------------------------------------------------------------
    def is_portfolio_optimal(self) -> bool:
        """
        Returns true if the current holdings are optimal (as per the 
        performance formula) based on each of the current best standing prices 
        in the market, and false otherwise.
        
        Returns: 
            performance is optimal (bool)
        """
        # Compute payoff of current holdings at each state
        cash = self._cash/100
        payoff_list = []
        state_num = len(list(self._payoffs.values())[0])
        for state in range(state_num):
            payoff = 0
            for market in self.markets.values():
                asset_id = market.fm_id
                payoff += self._asset[asset_id]*(
                    self._payoffs[asset_id][state]/100
                    )
            payoff += cash
            payoff_list.append(payoff)
        
        # Compute expected payoff
        expected_payoff = 0
        for payoff in payoff_list:
            expected_payoff += payoff
        expected_payoff = expected_payoff/len(payoff_list)

        # Compute variance
        variance = 0
        for payoff in payoff_list:
            variance += (payoff - expected_payoff)**2
        variance = variance/len(payoff_list)

        # Compute current performance
        current_performance = expected_payoff - variance*self._risk_penalty
        self.inform(f"current performance is: {current_performance}")
        self._current_performance = current_performance

        # Check if there exist profit opportunity
        self._best_performance = None
        self._best_order_list = None
        signal = True
        market_num = len(self.markets.values())
        sides = [0, 1, -1]

        # Iterate through each combination of possible order
        for side_list in product(sides, repeat = market_num):
            order_list = []
            net_cost = 0
            asset_enough = True
            for market, side in zip(self.markets.values(), side_list):
                asset_id = market.fm_id
                order = self._set_order(side, asset_id)
                if order is not None:
                    # Update cost of this order combination
                    net_cost += side*order.price
                    order_list.append(order)
                    # Check if asset is enough
                    if self._asset[asset_id] + side < 0:
                        asset_enough = False
            if (
                # Check if cash is enough
                (self._cash - net_cost >= 0)
                and (asset_enough == True)
                and (len(order_list) != 0)
                ):
                # Check expected perfomance of this order combination
                performance = self.get_potential_performance(order_list)
                # Find best performanced order list
                if performance > current_performance + self._min_margin:
                    if (
                        (self._best_performance is None) 
                        or(performance > self._best_performance)
                        ):
                        self._best_performance = performance
                        self._best_order_list = order_list

        # If performance > current_performance, set 
        # current_performance_optimal signal to False
        if self._best_performance is not None:
            signal = False
            self.inform(
                "current performance is not optimal, profit-making order list:"
                )
            for order in self._best_order_list:
                self.inform(
                    f"\t Market: {order.market.fm_id}, " 
                    + f"Side: {order.order_side}, Unit: {order.units}, " 
                    + f"Price: {order.price}"
                    )
            self.inform(f"expected performance: {self._best_performance}")
        return signal

#------------------------------------------------------------------------------
# Initalize an Order with one unit based on provided market and side
#------------------------------------------------------------------------------
    def _set_order(self, side: int, market_id: int) -> Order | None:
        """
        Creates a limit order of one unit based on input side 
        with price = best bid/ask depending on side

        Args:
            side: trading direction, 1, 0, -1
            market_id: ID of the market the order may be placed
        Returns: 
            one unit limit order (Order)
        """
        # Initalize an order in given market at given side
        market = Market.get_by_id(market_id)
        new_order = Order.create_new(market = market)
        new_order.order_type = OrderType.LIMIT
        new_order.mine = True

        # If side is 1, it is a buy order
        # set unit to 1, price to best ask
        if side == 1:
            new_order.order_side = OrderSide.BUY
            new_order.units = 1
            if self._asks[market_id] is not None:
                new_order.price = self._asks[market_id]
            elif self._asks[market_id] is None:
                new_order = None
        
        # If side is -1, it is a sell order
        # set unit to 1, price to best bid
        elif side == -1:
            new_order.order_side = OrderSide.SELL
            new_order.units = 1
            if self._bids[market_id] is not None:
                new_order.price = self._bids[market_id]
            elif self._bids[market_id] is None:
                new_order = None
        
        # If side is 0, no order, set order to None
        elif side == 0:
            new_order = None
        
        # If order is not None, add order ref
        if new_order is not None:
            new_order.ref = (
                f"Market: {market}, Order Type: {new_order.order_type}, " 
                + f"Side: {new_order.order_side}, Unit: {new_order.units}, " 
                + f"Price: {new_order.price}")
        
        return new_order

#------------------------------------------------------------------------------
# Check if there exist any profitable opportunity to place limit order
#------------------------------------------------------------------------------
    def _placing_opportunity(self) -> bool:
        """
        Check if placing a new limit order could improve performance
        """
        best_performance = None
        self._best_order_list = None
        signal = False

        # Different from order-taking opportunity, 
        # this methods considers one market each time
        for side in [1, -1]:
            for market in self.markets.values():
                asset_id = market.fm_id
                best_bid = self._bids[asset_id]
                best_ask = self._asks[asset_id]
                price = None

                # Consider placing order only in market with both bid and ask
                if best_bid is not None and best_ask is not None:
                    bid_ask_spread = best_ask - best_bid
                    cut = int(bid_ask_spread*0.2)
                    # Set price of an intended buy order to best ask 
                    # + 20% of bid-ask spread
                    if side == 1:
                        price = best_bid + cut
                    # Set price of an intended sell order to best ask 
                    # - 20% of bid-ask spread
                    elif side == -1:
                        price = best_ask - cut
                    market = Market.get_by_id(asset_id)
                    new_order = Order.create_new(market = market)
                    new_order.order_type = OrderType.LIMIT
                    new_order.mine = True
                    if side == 1:
                        new_order.order_side = OrderSide.BUY
                    elif side == -1:
                        new_order.order_side = OrderSide.SELL
                    new_order.units = 1
                    new_order.price = price

                    # Check performance of each intended limit order
                    if (
                        (self._cash - side * price >= 0) 
                        and (self._asset[asset_id] + side >= 0)
                        ):
                        order_list = [new_order]
                        performance = self.get_potential_performance(
                            order_list
                            )
                        # Check if performance > current performance 
                        # + min margin
                        if (
                            performance 
                            > self._current_performance + self._min_margin
                            ):
                            # Find the order leading to best improvement
                            if (
                                (best_performance is None) 
                                or (performance > best_performance)
                                ):
                                best_performance = performance
                                self._best_order_list = order_list
        
        # Return the signal as True if found order placing opportunity
        if best_performance is not None:
            signal = True
            self.inform(f"Detected order placing opportunity:")
            for order in self._best_order_list:
                self.inform(
                    f"\t Market: {order.market.fm_id}, " 
                    + f"Side: {order.order_side}, Unit: {order.units}, " 
                    + f"Price: {order.price}"
                    )
            self.inform(f"expected performance: {best_performance}")
        
        return signal

#------------------------------------------------------------------------------
# Place the order
#------------------------------------------------------------------------------
    def _place_order(self, order: Order) -> None:
        """
        Submit an order to the marketplace

        Args:
            order: the order to send
        """
        self.send_order(order = order)
        self.inform(f"Placed order: {order}", ws = False)

#------------------------------------------------------------------------------
# Cancel the order
#------------------------------------------------------------------------------
    def _cancel_order(self, order: Order) -> None:
        """
        Cancel an order from the marketplace

        Args:
            order: the order to cancel
        """
        cancel_order = copy.copy(order)
        cancel_order.order_type = OrderType.CANCEL
        self.send_order(order = cancel_order)
        self.inform(f"\t Cancelling order: {order}")

#------------------------------------------------------------------------------
# Check if there is order placing / taking opportunities
#------------------------------------------------------------------------------
    def _check_market(self) -> None:
        """
        Inspect the market for order taking / placing opportunities 
        and respond to these opportunities
        """
        # Check placing/taking opportunity only if:
        # 1. there is no order placing now
        # 2. there is no order standing
        # 3. there is no order cancelling now
        is_order_placing = False
        for value in self._order_placing.values():
            if value is True:
                is_order_placing = True
        is_standing_order = False
        for order in self._standing_order_list.values():
            if order is not None:
                is_standing_order = True
        is_cancelling_order = False
        for value in self._order_cancelling.values():
            if value != 0:
                is_cancelling_order = True

        # Check if there is order taking opportunity first
        if (
            (is_order_placing is False) 
            and (is_standing_order is False) 
            and (is_cancelling_order is False) 
            and (self._session_open is True)
            ):
            self._wait_time  = 0
            is_profitable = False
            # Check if current performance is optimal
            is_optimal = self.is_portfolio_optimal()
            # If not optimal, 
            # does the potential improvement > min margin
            if (
                (is_optimal == False) 
                and (
                    self._best_performance > 
                    self._current_performance + self._min_margin
                    )
                ):
                is_profitable = True

            # If not optimal and improvement > min margin, place best order
            if is_profitable:
                for order in self._best_order_list:
                    self._place_order(order)
                    self._order_placing[order.market.fm_id] = True
                self._perform_check_time = 0
            
            # If not optimal or improvement < min margin
            # check order placing opportunity
            elif not is_profitable:
                self._perform_check_time += 1
                if self._perform_check_time >= 10:
                    is_placing_opportunity = self._placing_opportunity()
                    if is_placing_opportunity:
                        for order in self._best_order_list:
                            self._place_order(order)
                            self._order_placing[order.market.fm_id] = True
                        self._perform_check_time = 0

        # If a limit order is placed for more than 3s and not taken, cancel it
        elif (
            (is_order_placing is False) 
            and (is_standing_order is True) 
            and (is_cancelling_order is False) 
            and (self._session_open is True)
            ):
            self._wait_time += 1
            if self._wait_time >= 3:
                self.inform("Wait time > 3s, cancel standing orders")
                for market, order in self._standing_order_list.items():
                    if order is not None:
                        self._cancel_order(order)
                        self._order_cancelling[market] = 1
        
        # Record session time, reduce min margin requirment gradually 
        # over time
        if self._session_open is True:
            self._session_time += 1
            if self._session_time % 30 == 0:
                if self._min_margin - self._margin_reduc >= 0:
                    self._min_margin -= self._margin_reduc

#------------------------------------------------------------------------------
# Periodically check and respond to order taking / placing opportunities
#------------------------------------------------------------------------------
    def pre_start_tasks(self) -> None:
        """
        Periodically check the market and respond to opportunities
        """
        self.execute_periodically(self._check_market, 1)

#------------------------------------------------------------------------------
# Update session info
#------------------------------------------------------------------------------
    def received_session_info(self, session: Session) -> None:
        """
        Inform session start, closed, or paused and update session_open state

        Args:
            session: the Session object
        """
        if session.is_open:
            self.inform(f"Session id: {session.fm_id}, your are able to trade")
            self._session_open = True
        elif session.is_closed:
            self.inform(f"Session id: {session.fm_id}, the session is closed")
            self._session_open = False
        elif session.is_paused:
            self.inform(f"Session id: {session.fm_id}, the session is paused")
            self._session_open = False

#------------------------------------------------------------------------------
# Update cash and assets in each market
#------------------------------------------------------------------------------
    def received_holdings(self, holdings: Holding) -> None:
        """
        Update cash and asset holdings, and check if a standing order is 
        traded based on asset change

        Args:
            holdings: the Holding object
        """
        # Update settled cash
        self._cash = holdings.cash
        # Update settled asset
        for market, asset in holdings.assets.items():
            self.inform(f"\t asset in market {market.name} : {asset.units}")
            self._asset[market.fm_id] = asset.units
        
        # Check if trade is success based on asset from last holding update
        for market, current_asset in self._asset.items():
            last_asset = self._last_asset[market]
            standing_order = self._standing_order_list[market]
            unit = 0
            if standing_order is not None:
                if standing_order.order_side == OrderSide.SELL:
                    unit = -1
                elif standing_order.order_side == OrderSide.BUY:
                    unit = 1
                if (
                    (current_asset != last_asset) 
                    and (last_asset + unit == current_asset)
                    ):
                    self.inform(
                        f"Trade success: {self._standing_order_list[market]}"
                        )
                    self._standing_order_list[market] = None
        
        # Update asset from last asset holding update
        for market, asset in self._asset.items():
            self._last_asset[market] = asset

#------------------------------------------------------------------------------
# Update best bid and ask price in each market
#------------------------------------------------------------------------------
    def received_orders(self, orders: list[Order]) -> None:
        """
        Update current best bid and ask prices

        Args:
            orders: list of market orders
        """
        # Set best bid and ask in each market as None
        for market in self.markets.values():
            asset_id = market.fm_id
            self._asks[asset_id] = None
            self._bids[asset_id] = None

            # Iterate through current orders
            for order in Order.current().values():
                if order.order_type is OrderType.LIMIT:
                    if not order.mine:
                        if order.market.fm_id == asset_id:
                            # Find best ask
                            if order.order_side is OrderSide.SELL:
                                if (
                                    (self._asks[asset_id] is None)
                                    or (self._asks[asset_id] > order.price)
                                    ):
                                    self._asks[asset_id] = order.price
                            
                            # Find best bid
                            elif order.order_side is OrderSide.BUY:
                                if (
                                    (self._bids[asset_id] is None) 
                                    or (self._bids[asset_id] < order.price)
                                    ):
                                    self._bids[asset_id] = order.price

#------------------------------------------------------------------------------
# Handle accepted order and update standing order
#------------------------------------------------------------------------------
    def order_accepted(self, order: Order) -> None:
        """
        Inform accpeted order and add accepted order to standing_order 

        Args:
            order: the accepted order
        """
        self.inform(
            f"I have {order.order_type} order accepted by book: {order.ref}"
            )
        if order.order_type is OrderType.LIMIT:
            # If limit order, update standing order
            self._standing_order_list[order.market.fm_id] = order
            self._order_placing[order.market.fm_id] = False
        elif order.order_type is OrderType.CANCEL:
            # If cancel order, remove standing order
            self._order_cancelling[order.market.fm_id] = 0
            self._standing_order_list[order.market.fm_id] = None

#------------------------------------------------------------------------------
# Handle rejected orders
#------------------------------------------------------------------------------
    def order_rejected(self, info: dict[str, str], order: Order) -> None:
        """
        Inform rejected order and check if it is caused by session close

        Args:
            order: the rejected order
        """
        self.inform(
            f"I have {order.order_type} order rejected by book: {order.ref}"
            )
        # If order rejected because session close, inform it
        if order.order_type is OrderType.LIMIT:
            self._order_placing[order.market.fm_id] = False
        elif order.order_type is OrderType.CANCEL:
            self._order_cancelling[order.market.fm_id] = 0
        if self._session_open is False:
            self.inform(f"Order rejected as session paused / closed")

#------------------------------------------------------------------------------
# Activate the robot
#------------------------------------------------------------------------------
if __name__ == "__main__":
    capm_bot = CAPMBot(
        FM_ACCOUNT, 
        FM_EMAIL, 
        FM_PASSWORD, 
        FM_MARKETPLACE_ID, 
        RISK_PENALTY,
        PROFIT_MARGIN,
        MARGIN_REDUC
        )
    capm_bot.run()