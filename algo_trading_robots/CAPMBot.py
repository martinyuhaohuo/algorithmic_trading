"""
This is a template for Trading Task 2 (Diversification - CAPM)
"""

import copy
import logging
from fmclient import Agent, Market, Holding, Session, Order, OrderType, OrderSide


# Trading account details
# ------ These must be set for testing and market performance evaluation -----
# ------ However, must be removed prior to submission -----
FM_ACCOUNT = ""
FM_EMAIL = ""
FM_PASSWORD = ""
FM_MARKETPLACE_ID = -1

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
        self._cash = None

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
        expected_cash = self._cash
        
        for order in orders:
            if order.order_side == OrderSide.BUY:
                expected_cash -= order.price * order.units
                expected_asset[asset_id] += order.units
            elif order.order_side == OrderSide.SELL:
                expected_cash += order.price * order.units
                expected_asset[asset_id] -= order.units

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
            (payoff_w - expected_payoff)^2 
            + (payoff_x - expected_payoff)^2 
            + (payoff_y - expected_payoff)^2 
            + (payoff_z - expected_payoff)^2 
            )/4
        performance = expected_payoff - variance*self._risk_penalty

        return performance

    def is_portfolio_optimal(self) -> bool:
        """
        Returns true if the current holdings are optimal (as per the performance formula) based on each of
        the current best standing prices in the market, and false otherwise.
        :return: performance is optimal (bool)
        """
        payoff_w = self._asset[2714]*10 + self._asset[2715]*0 + self._asset[2716]*0 + self._asset[2717]*5 + self._cash
        payoff_x = self._asset[2714]*0 + self._asset[2715]*2.5 + self._asset[2716]*7.5 + self._asset[2717]*5 + self._cash
        payoff_y = self._asset[2714]*7.5 + self._asset[2715]*7.5 + self._asset[2716]*2.5 + self._asset[2717]*5 + self._cash
        payoff_z = self._asset[2714]*2.5 + self._asset[2715]*10 + self._asset[2716]*10 + self._asset[2717]*5 + self._cash
        expected_payoff = (payoff_w + payoff_x + payoff_y + payoff_z)/4
        variance = (
            (payoff_w - expected_payoff)^2 
            + (payoff_x - expected_payoff)^2 
            + (payoff_y - expected_payoff)^2 
            + (payoff_z - expected_payoff)^2 
            )/4
        current_performance = expected_payoff - variance*self._risk_penalty
        


    def _place_order(self, price: int, units: int, side: str, market_id: int) -> None:
        # Place an order in given market, at given side, price, units
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
        new_order.ref = (
            f"Market: {market}, Order Type: {new_order.order_type}, " 
            + f"Side: {new_order.order_side}, Unit: {new_order.units}, " 
            + f"Price: {new_order.price}")
        self.send_order(order = new_order)
        self.inform(f"Placed order: {new_order}", ws = False)

    def pre_start_tasks(self):
        pass

    def received_session_info(self, session: Session):
        pass

    def received_holdings(self, holdings: Holding):
        pass

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
        pass

    def order_rejected(self, info: dict[str, str], order: Order):
        pass


if __name__ == "__main__":
    capm_bot = CAPMBot(FM_ACCOUNT, FM_EMAIL, FM_PASSWORD, FM_MARKETPLACE_ID, RISK_PENALTY)
    capm_bot.run()
