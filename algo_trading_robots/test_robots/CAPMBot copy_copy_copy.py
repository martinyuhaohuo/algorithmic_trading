"""
This is a template for Trading Task 2 (Diversification - CAPM)
"""

import copy
import logging
from itertools import product
from fmclient import Agent, Market, Holding, Session, Order, OrderType, OrderSide


# Trading account details
# ------ These must be set for testing and market performance evaluation -----
# ------ However, must be removed prior to submission -----
FM_ACCOUNT = "fain-premium"
FM_EMAIL = "yh620@d002"
FM_PASSWORD = "yh620"
FM_MARKETPLACE_ID = 1524

RISK_PENALTY = 0.01


class CAPMBot(Agent):
    _risk_penalty: float
    _payoffs: dict[int, list[int]]

    def __init__(self, account: str, email: str, password: str, marketplace_id: int, risk_penalty: float, bot_name: str = "CAPMBot"):
        super().__init__(account, email, password, marketplace_id, name=bot_name)
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
        #1: Cancel order placed, 2: Cancel order accepted, 0: Cancel order succeed / no cancel order
        self._min_margin = 5 #test: 3
        self._current_performance = 0
        self._perform_check_time = 0


    def initialised(self):
        # extract payoff distribution for each asset
        for market in self.markets.values():
            asset_id = market.fm_id
            description = market.description
            self._payoffs[asset_id] = [int(payoff) for payoff in description.split(",")]
            # update inital value of other attributes
            self._bids[asset_id] = None
            self._asks[asset_id] = None
            self._asset[asset_id] = 0
            self._last_asset[asset_id] = 0
            self._standing_order_list[asset_id] = None
            self._order_placing[asset_id] = False
            self._order_cancelling[asset_id] = 0

        self.inform("Bot initialised, I have the payoffs for the states.")

    def get_potential_performance(self, orders: list[Order]) -> float:
        """
        Returns the portfolio performance if all the given list of orders is executed based on your current holdings.
        The performance as per the following formula:
        Performance = ExpectedPayoff - b * PayoffVariance, where b is the penalty for risk.

        See the manual assignment brief for this task for examples of how to calculate performance.

        :param orders: list of orders
        :return: performance (float)
        """
        # initalize expected asset as current asset, expected cash as current cash
        expected_asset = {}
        for market in self.markets.values():
            asset_id = market.fm_id
            expected_asset[asset_id] = self._asset[asset_id]
        expected_cash = self._cash/100
        
        # adjust expected asset and cash based on input order list
        for order in orders:
            if order.order_side == OrderSide.BUY:
                expected_cash -= (order.price * order.units)/100
                expected_asset[order.market.fm_id] += order.units
            elif order.order_side == OrderSide.SELL:
                expected_cash += (order.price * order.units)/100
                expected_asset[order.market.fm_id] -= order.units

        # compute payoff at each state
        payoff_list = []
        state_num = len(list(self._payoffs.values())[0])
        for state in range(state_num):
            payoff = 0
            for market in self.markets.values():
                asset_id = market.fm_id
                payoff += expected_asset[asset_id]*(self._payoffs[asset_id][state]/100)
            payoff += expected_cash
            payoff_list.append(payoff)
        
        # compute expected payoff
        expected_payoff = 0
        for payoff in payoff_list:
            expected_payoff += payoff
        expected_payoff = expected_payoff/len(payoff_list)

        # compute variance
        variance = 0
        for payoff in payoff_list:
            variance += (payoff - expected_payoff)**2
        variance = variance/len(payoff_list)

        # compute performance
        performance = expected_payoff - variance*self._risk_penalty
        return performance

    def is_portfolio_optimal(self) -> bool:
        """
        Returns true if the current holdings are optimal (as per the performance formula) based on each of
        the current best standing prices in the market, and false otherwise.
        :return: performance is optimal (bool)
        """
        # compute payoff of current holdings at each state
        cash = self._cash/100
        payoff_list = []
        state_num = len(list(self._payoffs.values())[0])
        # self.inform(f"{state_num}")
        for state in range(state_num):
            payoff = 0
            for market in self.markets.values():
                asset_id = market.fm_id
                payoff += self._asset[asset_id]*(self._payoffs[asset_id][state]/100)
                # self.inform(f"{self._asset[asset_id]*self._payoffs[asset_id][state]}")
            payoff += cash
            payoff_list.append(payoff)
        
        # compute expected payoff
        expected_payoff = 0
        for payoff in payoff_list:
            expected_payoff += payoff
        expected_payoff = expected_payoff/len(payoff_list)

        # compute variance
        variance = 0
        for payoff in payoff_list:
            variance += (payoff - expected_payoff)**2
        variance = variance/len(payoff_list)

        # compute current performance
        current_performance = expected_payoff - variance*self._risk_penalty
        self.inform(f"current performance is: {current_performance}")
        self._current_performance = current_performance

        # check if there exist profit opportunity
        self._best_performance = None
        self._best_order_list = None
        signal = True
        market_num = len(self.markets.values())
        sides = [0, 1, -1]
        # iterate through each combination of possible order
        for side_list in product(sides, repeat = market_num):
            order_list = []
            net_cost = 0
            asset_enough = True
            for market, side in zip(self.markets.values(), side_list):
                asset_id = market.fm_id
                order = self._set_order(side, asset_id)
                if order is not None:
                    # update cost of this order combination
                    net_cost += side*order.price
                    order_list.append(order)
                    # check if asset is enough
                    if self._asset[asset_id] + side < 0:
                        asset_enough = False
            if (
                (self._cash - net_cost >= 0) # check if cash is enough
                and (asset_enough == True)
                and (len(order_list) != 0)
                ):
                # check expected perfomance of this order combination
                performance = self.get_potential_performance(order_list)
                # find order 
                if performance > current_performance + self._min_margin:
                    if self._best_performance is None or performance > self._best_performance:
                        self._best_performance = performance
                        self._best_order_list = order_list

        # if performance > current_performance, set current_performance_optimal signal to False
        if self._best_performance is not None:
            signal = False
            self.inform(f"current performance is not optimal, profit-making order list:")
            for order in self._best_order_list:
                self.inform(f"\t Market: {order.market.fm_id}, Side: {order.order_side}, Unit: {order.units}, Price: {order.price}")
            self.inform(f"expected performance: {self._best_performance}")
        return signal

    def _set_order(self, side: int, market_id: int) -> None:
        # Initalize an order in given market, at given side, price, units
        market = Market.get_by_id(market_id)
        new_order = Order.create_new(market = market)
        new_order.order_type = OrderType.LIMIT
        new_order.mine = True
        if side == 1:
            new_order.order_side = OrderSide.BUY
            new_order.units = 1
            if self._asks[market_id] is not None:
                new_order.price = self._asks[market_id]
            elif self._asks[market_id] is None:
                new_order = None
        elif side == -1:
            new_order.order_side = OrderSide.SELL
            new_order.units = 1
            if self._bids[market_id] is not None:
                new_order.price = self._bids[market_id]
            elif self._bids[market_id] is None:
                new_order = None
        elif side == 0:
            new_order = None
        if new_order is not None:
            new_order.ref = (
                f"Market: {market}, Order Type: {new_order.order_type}, " 
                + f"Side: {new_order.order_side}, Unit: {new_order.units}, " 
                + f"Price: {new_order.price}")
        return new_order
    
    def _placing_opportunity(self):
        best_performance = None
        self._best_order_list = None
        signal = False
        for side in [1, -1]:
            for market in self.markets.values():
                asset_id = market.fm_id
                best_bid = self._bids[asset_id]
                best_ask = self._asks[asset_id]
                price = None
                if best_bid is not None and best_ask is not None:
                    bid_ask_spread = best_ask - best_bid
                    cut = int(bid_ask_spread*0.2)
                    if side == 1:
                        price = best_bid + cut
                        # self.inform(f"Price: {price}")
                    elif side == -1:
                        price = best_ask - cut
                        # self.inform(f"Price: {price}")
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
                    # check performance of this intended limit order
                    if (self._cash - side * price >= 0) and (self._asset[asset_id] + side >= 0):
                        order_list = [new_order]
                        performance = self.get_potential_performance(order_list)
                        if performance > self._current_performance + self._min_margin:
                            if best_performance is None or performance > best_performance:
                                best_performance = performance
                                self._best_order_list = order_list
        if best_performance is not None:
            signal = True
            self.inform(f"Detected order placing opportunity:")
            for order in self._best_order_list:
                self.inform(f"\t Market: {order.market.fm_id}, Side: {order.order_side}, Unit: {order.units}, Price: {order.price}")
            self.inform(f"expected performance: {best_performance}")
        return signal

    
    def _place_order(self, order) -> None:
        self.send_order(order = order)
        self.inform(f"Placed order: {order}", ws = False)
    
    def _cancel_order(self, order: Order) -> None:
        cancel_order = copy.copy(order)
        cancel_order.order_type = OrderType.CANCEL
        self.send_order(order = cancel_order)
        self.inform(f"\t Cancelling order: {order}")
    
    def _check_market(self):
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

        if is_order_placing is False and is_standing_order is False and is_cancelling_order is False:
            self._wait_time  = 0
            is_profitable = False
            is_optimal = self.is_portfolio_optimal()
            if (
                (is_optimal == False) 
                and (self._best_performance > self._current_performance + self._min_margin)
                ):
                is_profitable = True

            if is_profitable:
                for order in self._best_order_list:
                    self._place_order(order)
                    self._order_placing[order.market.fm_id] = True
                self._perform_check_time = 0
            
            elif not is_profitable:
                self._perform_check_time += 1
                if self._perform_check_time >= 10:
                    is_placing_opportunity = self._placing_opportunity()
                    if is_placing_opportunity:
                        for order in self._best_order_list:
                            self._place_order(order)
                            self._order_placing[order.market.fm_id] = True
                        self._perform_check_time = 0

        elif is_order_placing is False and is_standing_order is True and is_cancelling_order is False:
            self._wait_time += 1
            if self._wait_time >= 5:
                self.inform("Wait time > 5s, cancel standing orders")
                for market, order in self._standing_order_list.items():
                    if order is not None:
                        self._cancel_order(order)
                        self._order_cancelling[market] = 1
        
        self._session_time += 1
        if self._session_time % 30 == 0:
            if self._min_margin - 0.5 >= 0:
                self._min_margin -= 0.5


    def pre_start_tasks(self):
        self.execute_periodically(self._check_market, 1)

    def received_session_info(self, session: Session):
        # Inform session start, closed, or paused
        if session.is_open:
            self.inform(f"Session id: {session.fm_id}, your are able to trade")
        elif session.is_closed:
            self.inform(f"Session id: {session.fm_id}, the session is closed")
        elif session.is_paused:
            self.inform(f"Session id: {session.fm_id}, the session is paused")

    def received_holdings(self, holdings: Holding):
        # Update settled cash
        self._cash = holdings.cash
        # Update settled asset
        for market, asset in holdings.assets.items():
            self.inform(f"\t asset in market {market.name} : {asset.units}")
            self._asset[market.fm_id] = asset.units
        # Check if trade is success based on asset from last asset holding update
        for market, current_asset in self._asset.items():
            last_asset = self._last_asset[market]
            standing_order = self._standing_order_list[market]
            unit = 0
            if standing_order is not None:
                if standing_order.order_side == OrderSide.SELL:
                    unit = -1
                elif standing_order.order_side == OrderSide.BUY:
                    unit = 1
            # Modification made
            if (current_asset != last_asset) and (last_asset + unit == current_asset):
                self.inform(f"Trade success: {self._standing_order_list[market]}")
                self._standing_order_list[market] = None
                if self._order_cancelling[market] == 2:
                    self.inform(f"Order cancel fail, the order is traded: {standing_order}")
                    self._order_cancelling[market] = 0
            elif self._order_cancelling[market] == 2 and current_asset == last_asset:
                self.inform(f"Order successfully cancelled: {standing_order}")
                self._standing_order_list[market] = None
                self._order_cancelling[market] = 0
        # Update asset from last asset holding update
        for market, asset in self._asset.items():
            self._last_asset[market] = asset

    def received_orders(self, orders: list[Order]):
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
                            # Set best ask
                            if order.order_side is OrderSide.SELL:
                                if (self._asks[asset_id] is None or self._asks[asset_id] > order.price):
                                    self._asks[asset_id] = order.price
                            # Set best bid
                            elif order.order_side is OrderSide.BUY:
                                if (self._bids[asset_id] is None  or self._bids[asset_id] < order.price):
                                    self._bids[asset_id] = order.price

    def order_accepted(self, order: Order):
        self.inform(f"I have {order.order_type} order accepted by book: {order.ref}")
        if order.order_type is OrderType.LIMIT:
            self._standing_order_list[order.market.fm_id] = order
            self._order_placing[order.market.fm_id] = False
        elif order.order_type is OrderType.CANCEL:
            self._order_cancelling[order.market.fm_id] = 2

    def order_rejected(self, info: dict[str, str], order: Order):
        self.inform(f"I have {order.order_type} order rejected by book: {order.ref}")


if __name__ == "__main__":
    capm_bot = CAPMBot(FM_ACCOUNT, FM_EMAIL, FM_PASSWORD, FM_MARKETPLACE_ID, RISK_PENALTY)
    capm_bot.run()