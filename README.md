# BTCUSDT Market Microstructure Research

## Overview

This project investigates whether Order Book Imbalance and Order Flow Imbalance can predict short term BTCUSDT price movements and generate profitable trading signals after transaction costs.
Using Python and the Binance REST API, 2,000 order book snapshots were collected and analyzed.

## Methodology

Data Collection: Collected BTCUSDT bid/ask prices, volumes, and timestamps.
Feature Engineering: Calculated OBI, OFI, bid ask spread, midprice, and microprice.
Statistical Analysis: Examined correlations between order book features and future price movements.
Signal Decay: Analyzed how predictive relationships change across different time horizons.
Backtesting: Evaluated trading signals using bid ask prices, next snapshot execution, and transaction fees.
Cost Analysis: Examined holding periods, transaction costs, and break even fees.

## Best Case Exit Analysis

To investigate whether poor exit timing was responsible for the strategy's losses, a theoretical best case exit analysis was conducted.
For each trade, the most favorable observed exit price within a 30 snapshot window was selected and compared with a fixed holding period exit.
Even with perfect hindsight, 49 out of 50 trades remained unprofitable after transaction costs.
This suggests that the main limitation was not simply exit timing. The price movements captured by the signals were generally too small to overcome trading costs.

## Key Finding

Statistical predictability does not necessarily translate into economic profitability.
Although order book imbalance showed relationships with short term price movements, these relationships did not produce a profitable strategy under the tested assumptions.

## Limitations

The study uses 2,000 periodic order book snapshots. The backtest does not fully model execution latency, slippage, or market impact.The best case exit analysis uses future information and represents a theoretical upper benchmark, not an executable trading strategy.
## Conclusion

This project demonstrates market microstructure research, statistical signal analysis, and transaction cost aware backtesting, emphasizing realistic evaluation and transparent reporting of negative results.
