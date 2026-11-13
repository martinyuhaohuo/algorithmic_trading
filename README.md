# Algorithmic Trading
Class notes and trading robots for the Flex-E-Markets (`fmclient`) platform.

## Setup
```bash
source activate_venv.sh            # activates venvs/algo_trade_venv
pip install -r requirements.txt    # if setting up a fresh environment
```

## Running
```bash
python algo_trading_robots/CAPM_Bot.py              # CAPM bot
python algo_trading_robots/isd_bot.py               # ISD bot
python algo_trading_robots/base_robot_template.py   # market info
```

## CAPM Bot (`CAPM_Bot.py`)

Trades several risky assets so the portfolio scores as high as possible on a mean–variance measure.

**Objective.** Each market's description lists the asset's payoff in every possible state, and all states are equally likely. For a given holding of cash and assets, the bot scores the portfolio as:

```
Performance = E[payoff] − b · Var[payoff]      (b = RISK_PENALTY)
```

**Loop (runs every 1s):**

1. **Take orders.** Try every combination of {buy at best ask, sell at best bid, do nothing} across all markets, one unit each. Skip combinations the bot can't afford in cash or units. If the best combination beats current performance by more than `PROFIT_MARGIN`, send those orders.
2. **Make orders.** After 10 checks in a row with nothing worth taking, look for one limit order to post inside the spread: a buy at `bid + 20% of spread` or a sell at `ask − 20% of spread`. Post it if it clears the same margin.
3. **Manage orders.** Only one batch of orders is active at a time. A resting order that hasn't traded after 3s is cancelled. A fill is detected by comparing holdings before and after.
4. **Relax the threshold.** Every 30s, `PROFIT_MARGIN` drops by `MARGIN_REDUC` (it never goes below 0), so the bot trades more as the session goes on.

## ISD Bot (`isd_bot.py`)

Arbitrages between a **public** market and a **private** market. In the private market, a single counterparty (`TARGET_ID`) posts a bid or an ask, which is the private signal.

**Role.** The private signal decides the bot's role:
- private **bid** present → **BUYER**: buy publicly, then sell privately
- private **ask** present → **SELLER**: sell publicly, then buy privately

**Two trading styles** (`MARKET_PERFORMANCE_BOT_TYPE`):
- **ACTIVE**: posts a public limit order at `private bid − PROFIT_MARGIN` (buyer) or `private ask + PROFIT_MARGIN` (seller), then waits for someone to fill it.
- **REACTIVE**: posts nothing on its own. It only takes an existing public order when the spread against the private price is at least `PROFIT_MARGIN`.

**Completing the trade.** Once the public order fills, the bot immediately sends the offsetting order to the private counterparty, which locks in the margin. Fills are detected through `has_traded`, with a fallback check on net holdings. A rejected private order is resent.