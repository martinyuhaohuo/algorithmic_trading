# The Imports

import copy
import logging

from fmclient import Agent, Market, Holding, Session, Order, OrderType, OrderSide


# Flex-E-Market credential

FM_ACCOUNT = ""
FM_EMAIL = ""
FM_PASSWORD = ""
ROBOT_NAME = ""
FM_MARKETPLACE_ID = -1


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
        pass

    def pre_start_tasks(self) -> None:
        pass

    def received_session_info(self, session: Session) -> None:
        pass

    def received_holdings(self, holdings: Holding) -> None:
        pass

    def received_orders(self, orders: list[Order]) -> None:
        pass

    def order_accepted(self, order: Order) -> None:
        pass

    def order_rejected(self, info: dict[str, str], order: Order) -> None:
        pass


# The dunder name equals dunder main

if __name__ == "__main__":
    # Swap your robot
    bot = FMRobot(account=FM_ACCOUNT, email=FM_EMAIL, password=FM_PASSWORD, marketplace_id=FM_MARKETPLACE_ID, name=ROBOT_NAME)    
    bot.run()
