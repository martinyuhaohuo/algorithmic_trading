"""
This is a template for Trading Task 2 (Diversification - CAPM)
"""

import copy
import logging
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
        self._bids = {2714:0, 2715:0,  2716:0,  2717:0}
        self._asks = {2714:20, 2715:20,  2716:20,  2717:20}
        self._asset = {2714:0, 2715:0,  2716:0,  2717:0}
        self._last_asset = {2714:0, 2715:0,  2716:0,  2717:0}
        self._cash = 0
        self._best_order_list = None
        self._standing_order_list = {2714:None, 2715:None,  2716:None,  2717:None}
        self._order_placing = {2714:False, 2715:False,  2716:False,  2717:False}
        self._session_time = 1
        self._wait_time = 0
        self._order_cancelling = {2714:0, 2715:0,  2716:0,  2717:0} 
        #1: Cancel order placed, 2: Cancel order accepted, 0: Cancel order succeed / no cancel order
        self._min_margin = 3
        self._current_performance = 0
        self._perform_check_time = 0


    def initialised(self):
        # Extract payoff distribution for each asset
        for market in self.markets.values():
            asset_id = market.fm_id
            description = market.description
            self._payoffs[asset_id] = [int(payoff) for payoff in description.split(",")]

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
        expected_asset = {}
        for market in self.markets.values():
            asset_id = market.fm_id
            expected_asset[asset_id] = self._asset[asset_id]
        expected_cash = self._cash/100
                    
        for order in orders:
            if order.order_side == OrderSide.BUY:
                expected_cash -= (order.price * order.units)/100
                expected_asset[order.market.fm_id] += order.units
            elif order.order_side == OrderSide.SELL:
                expected_cash += (order.price * order.units)/100
                expected_asset[order.market.fm_id] -= order.units

        # Asset A, fm_id: 2714
        # Asset B, fm_id: 2715
        # Asset C, fm_id: 2716
        # Note, fm_id: 2717
        payoff_w = expected_asset[2714]*10 + expected_asset[2715]*0 + expected_asset[2716]*0 + expected_asset[2717]*5 + expected_cash
        payoff_x = expected_asset[2714]*0 + expected_asset[2715]*2.5 + expected_asset[2716]*7.5 + expected_asset[2717]*5 + expected_cash
        payoff_y = expected_asset[2714]*7.5 + expected_asset[2715]*7.5 + expected_asset[2716]*2.5 + expected_asset[2717]*5 + expected_cash
        payoff_z = expected_asset[2714]*2.5 + expected_asset[2715]*10 + expected_asset[2716]*10 + expected_asset[2717]*5 + expected_cash
        expected_payoff = (payoff_w + payoff_x + payoff_y + payoff_z)/4

        variance = (
            (payoff_w - expected_payoff)**2 
            + (payoff_x - expected_payoff)**2 
            + (payoff_y - expected_payoff)**2 
            + (payoff_z - expected_payoff)**2 
            )/4

        performance = expected_payoff - variance*self._risk_penalty

        return performance

    def is_portfolio_optimal(self) -> bool:
        """
        Returns true if the current holdings are optimal (as per the performance formula) based on each of
        the current best standing prices in the market, and false otherwise.
        :return: performance is optimal (bool)
        """
        cash = self._cash/100
        payoff_w = self._asset[2714]*10 + self._asset[2715]*0 + self._asset[2716]*0 + self._asset[2717]*5 + cash
        payoff_x = self._asset[2714]*0 + self._asset[2715]*2.5 + self._asset[2716]*7.5 + self._asset[2717]*5 + cash
        payoff_y = self._asset[2714]*7.5 + self._asset[2715]*7.5 + self._asset[2716]*2.5 + self._asset[2717]*5 + cash
        payoff_z = self._asset[2714]*2.5 + self._asset[2715]*10 + self._asset[2716]*10 + self._asset[2717]*5 + cash
        expected_payoff = (payoff_w + payoff_x + payoff_y + payoff_z)/4
        variance = (
            (payoff_w - expected_payoff)**2 
            + (payoff_x - expected_payoff)**2 
            + (payoff_y - expected_payoff)**2 
            + (payoff_z - expected_payoff)**2 
            )/4
        current_performance = expected_payoff - variance*self._risk_penalty
        self.inform(f"current performance is: {current_performance}")
        self._current_performance = current_performance
        best_performance = None
        self._best_order_list = None
        signal = True
        for A_side in [0, 1, -1]:
            for B_side in [0, 1, -1]:
                for C_side in [0, 1, -1]:
                    for N_side in [0, 1, -1]:
                        order_A = self._set_order(A_side, 2714)
                        order_B = self._set_order(B_side, 2715)
                        order_C = self._set_order(C_side, 2716)
                        order_N = self._set_order(N_side, 2717)
                        net_cost = 0
                        if order_A is not None:
                            net_cost += A_side*order_A.price
                        if order_B is not None:
                            net_cost += B_side*order_B.price
                        if order_C is not None:
                            net_cost += C_side*order_C.price
                        if order_N is not None:
                            net_cost += N_side*order_N.price
                        if (
                            (self._cash - net_cost >= 0)
                            and
                            (self._asset[2714] + A_side >= 0)
                            and
                            (self._asset[2715] + B_side >= 0)
                            and
                            (self._asset[2716] + C_side >= 0)
                            and
                            (self._asset[2717] + N_side >= -20)
                            ):
                            order_list = []
                            for order in [order_A, order_B, order_C, order_N]:
                                if order is not None:
                                    order_list.append(order)
                            if len(order_list) != 0:
                                performance = self.get_potential_performance(order_list)
                                if performance > current_performance + self._min_margin:
                                    if best_performance is None or performance > best_performance:
                                        best_performance = performance
                                        self._best_order_list = order_list
        if best_performance is not None:
            signal = False
            self.inform(f"current performance is not optimal, profit-making order list:")
            for order in self._best_order_list:
                self.inform(f"\t Market: {order.market.fm_id}, Side: {order.order_side}, Unit: {order.units}, Price: {order.price}")
            self.inform(f"expected performance: {best_performance}")
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
            for market_id in [2714, 2715, 2716, 2717]:
                best_bid = self._bids[market_id]
                best_ask = self._asks[market_id]
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
                    market = Market.get_by_id(market_id)
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
                    if (self._cash - side * price >= 0) and (self._asset[market_id] + side >= 0):
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
            is_optimal = self.is_portfolio_optimal()
            if not is_optimal:
                for order in self._best_order_list:
                    self._place_order(order)
                    self._order_placing[order.market.fm_id] = True
                self._perform_check_time = 0
            elif is_optimal:
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
