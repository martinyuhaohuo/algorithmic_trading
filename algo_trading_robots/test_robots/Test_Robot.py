from fmclient import Agent, Holding, Session, Order

FM_ACCOUNT = "fain-premium"
FM_EMAIL = "trader03@d002"
FM_PASSWORD = "LIPNE"
ROBOT_NAME = "fmClient Installed Test Robot"
FM_MARKETPLACE_ID = 1515


class FMTestRobot(Agent):
    """ A simple agent which tests the connection to Flex-E-Markets
    and installation of the fmClient package.
    """

    def __init__(
        self,
        account: str,
        email: str,
        password: str,
        marketplace_id: int,
        name: str = "FMBot",
    ):
        super().__init__(account, email, password, marketplace_id, name=name)

    def initialised(self):
        self.inform('---------- Test robot successfully ran ----------')
        self.stop_after_wait(2)

    def pre_start_tasks(self):
        pass

    def received_session_info(self, session: Session):
        pass

    def received_holdings(self, holdings: Holding):
        pass

    def received_orders(self, orders: list[Order]):
        pass

    def order_accepted(self, order: Order):
        pass

    def order_rejected(self, info: dict[str, str], order: Order):
        pass


if __name__ == "__main__":
    if not FM_ACCOUNT:
        print("You must populate your FM_ACCOUNT at the top of the FMTestRobot file")
    elif not FM_EMAIL:
        print("You must populate your FM_EMAIL at the top of the FMTestRobot file")
    elif not FM_PASSWORD:
        print("You must populate your FM_PASSWORD at the top of the FMTestRobot file")
    elif not FM_MARKETPLACE_ID:
        print("You must populate the FM_MARKETPLACE_ID at the top of the FMTestRobot file")
    else:
        bot = FMTestRobot(
            account=FM_ACCOUNT,
            email=FM_EMAIL,
            password=FM_PASSWORD,
            marketplace_id=FM_MARKETPLACE_ID,
            name=ROBOT_NAME,
        )
        bot.run()
