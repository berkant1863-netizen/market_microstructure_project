import requests
import csv
import time
import pandas as pd
import matplotlib.pyplot as plt

from datetime import datetime, timezone

## SETTINGS

COLLECT_NEW_DATA = True
CSV_FILE = "btcusdt_final_test.csv"
SNAPSHOT_COUNT = 2000

QUANTITY = 0.001
FEE_RATE = 0.001

UPPER_THRESHOLD = 0.95
LOWER_THRESHOLD = -0.95
OFI_THRESHOLD = 0.001

## BINANCE API

url = "https://api.binance.com/api/v3/depth"

params = {
    "symbol": "BTCUSDT",
    "limit": 5
}

def get_orderbook():

    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    return {
        "update_id": data["lastUpdateId"],
        "bid_price": float(data["bids"][0][0]),
        "ask_price": float(data["asks"][0][0]),
        "bid_volume": float(data["bids"][0][1]),
        "ask_volume": float(data["asks"][0][1])
    }

##FEATURE CALCULATION
def calculate_features(book):

    bid = book["bid_price"]
    ask = book["ask_price"]

    bid_volume = book["bid_volume"]
    ask_volume = book["ask_volume"]
    spread = ask - bid
    midprice = (bid + ask) / 2
    total_volume = bid_volume + ask_volume

    if total_volume <= 0:
        raise ValueError("Total volume is zero.")

    obi = (
        (bid_volume - ask_volume)
        / total_volume
    )
    microprice = (
        ask * bid_volume
        + bid * ask_volume
    ) / total_volume
    return {
        "spread": spread,
        "midprice": midprice,
        "obi": obi,
        "microprice": microprice
    }

##ORDER FLOW IMBALANCE

def calculate_ofi(old_book, new_book):

    if new_book["bid_price"] > old_book["bid_price"]:
        bid_ofi = new_book["bid_volume"]

    elif new_book["bid_price"] < old_book["bid_price"]:
        bid_ofi = -old_book["bid_volume"]

    else:
        bid_ofi = (
            new_book["bid_volume"]
            - old_book["bid_volume"]
        )

    if new_book["ask_price"] < old_book["ask_price"]:
        ask_ofi = -new_book["ask_volume"]

    elif new_book["ask_price"] > old_book["ask_price"]:
        ask_ofi = old_book["ask_volume"]

    else:
        ask_ofi = (
            old_book["ask_volume"]
            - new_book["ask_volume"]
        )

    return bid_ofi + ask_ofi

##DATA COLLECTION

def collect_data():
    old_book = None

    columns = [
        "timestamp", "update_id",
        "bid_price", "ask_price",
        "bid_volume", "ask_volume",
        "spread", "midprice",
        "obi", "microprice", "ofi"
    ]

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)

        for i in range(SNAPSHOT_COUNT):
            try:
                book = get_orderbook()

                if old_book is not None:
                    if book["update_id"] <= old_book["update_id"]:
                        continue

                features = calculate_features(book)

                if old_book is None:
                    ofi = None
                else:
                    ofi = calculate_ofi(old_book, book)

                writer.writerow([
                    datetime.now(timezone.utc).isoformat(),
                    book["update_id"],
                    book["bid_price"],
                    book["ask_price"],
                    book["bid_volume"],
                    book["ask_volume"],
                    features["spread"],
                    features["midprice"],
                    features["obi"],
                    features["microprice"],
                    ofi
                ])

                file.flush()
                old_book = book

                print("TEST:", i + 1)

            except (
                requests.RequestException,
                ValueError,
                KeyError,
                IndexError
            ) as error:
                print("ERROR:", error)

            finally:
                time.sleep(0.5)

    print("Data collection completed")

##PANDAS DATA ANALYSIS

if COLLECT_NEW_DATA:

    collect_data()


df = pd.read_csv(CSV_FILE)

print("DATASET:")
print(df.head())

##DATA CLEANING

df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    utc=True
)

df = df.sort_values(
    "timestamp"
).reset_index(drop=True)


##MIDPRICE CHANGE ANALYSIS

df["next_midprice"] = (
    df["midprice"].shift(-1)
)

df["midprice_change"] = (
    df["next_midprice"] - df["midprice"]
)

print("MIDPRICE CHANGES:")

print(
    df[[
        "timestamp",
        "midprice",
        "next_midprice",
        "midprice_change"
    ]].head(10)
)

##MICROPRICE SIGNAL

df["microprice_signal"] = (
    df["microprice"] - df["midprice"]
)

##FEATURE CORRELATION ANALYSIS

features = [
    "spread",
    "obi",
    "ofi",
    "microprice_signal"
]

analysis_df = df.dropna(
    subset=features + ["midprice_change"]
).copy()

print("/nFEATURE CORRELATIONS:")

for feature in features:
    correlation = analysis_df[feature].corr(
        analysis_df["midprice_change"]
    )

    print(feature, "correlation:", correlation)


##DESCRIPTIVE STATISTICS

print("/nTOTAL OBSERVATIONS:")
print(len(analysis_df))

print("DESCRIPTIVE STATISTICS:")

print(
    analysis_df[
        features + ["midprice_change"]
    ].describe()
)

##MULTI-FEATURE SIGNAL GENERATION

analysis_df["signal"] = 0

analysis_df.loc[
    (analysis_df["obi"] > UPPER_THRESHOLD)
    & (analysis_df["ofi"] > OFI_THRESHOLD),
    "signal"
] = 1

analysis_df.loc[
    (analysis_df["obi"] < LOWER_THRESHOLD)
    & (analysis_df["ofi"] < -OFI_THRESHOLD),
    "signal"
] = -1

print("TRADING SIGNALS")
print(analysis_df["signal"].value_counts())

##MULTIPLE TRADES BACKTEST

trades = []

signals = analysis_df["signal"].reindex(
    df.index,
    fill_value=0
)

split_index = int(len(df) * 0.70)
i = split_index

while i < len(df) - 2:

    signal = signals.iloc[i]

    if signal == 0:

        i = i + 1
        continue

    entry = df.iloc[i + 1]
    exit_book = df.iloc[i + 2]

    if signal == 1:

        entry_price = entry["ask_price"]
        exit_price = exit_book["bid_price"]

        gross_pnl = (
            exit_price - entry_price
        ) * QUANTITY

    elif signal == -1:

        entry_price = entry["bid_price"]
        exit_price = exit_book["ask_price"]

        gross_pnl = (
            entry_price - exit_price
        ) * QUANTITY


    entry_fee = (
        entry_price * QUANTITY * FEE_RATE
    )

    exit_fee = (
        exit_price * QUANTITY * FEE_RATE
    )

    total_fee = entry_fee + exit_fee
    net_pnl = gross_pnl - total_fee

    trades.append({
        "signal_time": df.iloc[i]["timestamp"],
        "entry_time": entry["timestamp"],
        "exit_time": exit_book["timestamp"],
        "direction": "LONG" if signal == 1 else "SHORT",
        "entry_price": entry_price,
        "exit_price": exit_price,
        "quantity": QUANTITY,
        "gross_pnl": gross_pnl,
        "total_fee": total_fee,
        "net_pnl": net_pnl
    })

    i = i + 2

##BACKTEST RESULTS

trades_df = pd.DataFrame(trades)

if not trades_df.empty:

    total_trades = len(trades_df)
    winning_trades = (
        trades_df["net_pnl"] > 0
    ).sum()
    losing_trades = (
        trades_df["net_pnl"] < 0
    ).sum()
    total_gross_pnl = (
        trades_df["gross_pnl"].sum()
    )
    total_fees = (
        trades_df["total_fee"].sum()
    )
    total_net_pnl = (
        trades_df["net_pnl"].sum()
    )
    win_rate = (
        winning_trades / total_trades * 100
    )

    print("BACKTEST RESULTS")
    print("Total Trades:", total_trades)
    print("Winning Trades:", winning_trades)
    print("Losing Trades:", losing_trades)
    print("Win Rate:", win_rate, "%")
    print(
        "Gross PnL:",
        total_gross_pnl,
        "USDT"
    )
    print(
        "Total Fees:",
        total_fees,
        "USDT"
    )
    print(
        "Net PnL:",
        total_net_pnl,
        "USDT"
    )

else:
    print("No trades found for backtesting.")

##TRANSACTION COST SENSITIVITY

if not trades_df.empty:

    fee_rates = [0, 0.0001, 0.001]

    print("/nFEE SENSITIVITY")

    for fee_rate in fee_rates:

        fees = (
            trades_df["entry_price"]
            + trades_df["exit_price"]
        ) * QUANTITY * fee_rate

        net_pnls = trades_df["gross_pnl"] - fees

        total_net_pnl = net_pnls.sum()

        print("Fee:", fee_rate * 100, "%")
        print("Net PnL:", total_net_pnl, "USDT")

##BREAK-EVEN ANALYSIS

if not trades_df.empty:

    avg_gross_pnl = trades_df["gross_pnl"].mean()

    avg_net_pnl = trades_df["net_pnl"].mean()

    total_turnover = (
        (trades_df["entry_price"] + trades_df["exit_price"])
        * trades_df["quantity"]
    ).sum()

    breakeven_fee = (
        trades_df["gross_pnl"].sum()
        / total_turnover
    )

    print("\nBREAK-EVEN ANALYSIS ")
    print("Average Gross PnL:", avg_gross_pnl)
    print("Average Net PnL:", avg_net_pnl)
    print("Break-Even Fee (%):", breakeven_fee)
    print("Break-Even Fee (bps):", breakeven_fee)

##SIGNAL DECAY ANALYSIS

lags = [
    0, 1, 2, 3, 5,
    10, 20, 30, 40, 50,
    75, 100, 125, 150,
    175, 200
]

obi_correlations = []
ofi_correlations = []

for lag in lags:

    price_start = df["midprice"].shift(-lag)
    price_end = df["midprice"].shift(-(lag + 1))
    future_change = price_end - price_start
    obi_corr = df["obi"].corr(future_change)
    ofi_corr = df["ofi"].corr(future_change)
    obi_correlations.append(obi_corr)
    ofi_correlations.append(ofi_corr)

    print("Lag:", lag, "OBI:", obi_corr, "OFI:", ofi_corr)

##HOLDING PERIOD ANALYSIS

def holding_period_backtest(holding_period):

    results = []

    i = 0

    while i + 1 + holding_period < len(df):

        signal = signals.iloc[i]

        if signal == 0:
            i += 1
            continue

        entry = df.iloc[i + 1]
        exit_book = df.iloc[i + 1 + holding_period]

        if signal == 1:
            entry_price = entry["ask_price"]
            exit_price = exit_book["bid_price"]

            gross_pnl = (
                exit_price - entry_price
            ) * QUANTITY

        else:
            entry_price = entry["bid_price"]
            exit_price = exit_book["ask_price"]

            gross_pnl = (
                entry_price - exit_price
            ) * QUANTITY

        fee = (
            entry_price + exit_price
        ) * QUANTITY * FEE_RATE

        net_pnl = gross_pnl - fee

        results.append({
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl
        })

        i += holding_period + 1

    return pd.DataFrame(results)

##COMPARE HOLDING PERIODS

holding_periods = [1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 35, 40, 50, 60,70, 80, 90, 100, 150, 200, 250]
print("\nHOLDING PERIOD ANALYSIS ")

for period in holding_periods:

    result = holding_period_backtest(period)

    if result.empty:
        print("Period:", period, "No trades")
        continue

    print("Period:", period)
    print("Trades:", len(result))
    print("Gross PnL:", result["gross_pnl"].sum())
    print("Net PnL:", result["net_pnl"].sum())
    print("Average Net PnL:", result["net_pnl"].mean())
    print()

##STRONG OBI PRICE MOVEMENT ANALYSIS

OBI_ENTRY_THRESHOLD = 0.90

future_periods = [10, 30, 50, 100]

print("\nSTRONG OBI PRICE MOVEMENT")

for period in future_periods:

    gross_results = []
    net_results = []
    price_movements = []
    fees = []

    for i in range(len(df) - period - 1):

        obi_now = df.iloc[i]["obi"]

        if obi_now > OBI_ENTRY_THRESHOLD:
            direction = 1

        elif obi_now < -OBI_ENTRY_THRESHOLD:
            direction = -1

        else:
            continue

        entry_row = df.iloc[i + 1]

        exit_row = df.iloc[i + 1 + period]

        if direction == 1:
            entry_price = entry_row["ask_price"]
            exit_price = exit_row["bid_price"]

            price_move = exit_price - entry_price

        else:
            entry_price = entry_row["bid_price"]
            exit_price = exit_row["ask_price"]

            price_move = entry_price - exit_price

        gross_pnl = price_move * QUANTITY

        total_fee = (
            entry_price + exit_price
        ) * QUANTITY * FEE_RATE

        net_pnl = gross_pnl - total_fee

        price_movements.append(price_move)
        gross_results.append(gross_pnl)
        fees.append(total_fee)
        net_results.append(net_pnl)

    if len(net_results) == 0:
        print(f"Period {period}: No signals")
        continue

    total_signals = len(net_results)

    avg_price_move = sum(price_movements) / total_signals
    avg_gross = sum(gross_results) / total_signals
    avg_fee = sum(fees) / total_signals
    avg_net = sum(net_results) / total_signals

    profitable_signals = sum(
        1 for pnl in net_results if pnl > 0
    )

    profitable_rate = (
        profitable_signals / total_signals
    ) * 100

    print("Period:", period)
    print("Signals:", total_signals)
    print("Average Price Move:", avg_price_move, "USDT")
    print("Average Gross PnL:", avg_gross, "USDT")
    print("Average Fee:", avg_fee, "USDT")
    print("Average Net PnL:", avg_net, "USDT")
    print("Net Profitable Signals:", profitable_rate, "%")
    print()

##BEST-CASE EXIT ANALYSIS

BEST_CASE_THRESHOLD = 0.95
BEST_CASE_HOLDING = 30

best_case_trades = []

i = 1

while i + 1 + BEST_CASE_HOLDING < len(df):

    previous_obi = df.iloc[i - 1]["obi"]
    current_obi = df.iloc[i]["obi"]
    if (
        previous_obi <= BEST_CASE_THRESHOLD
        and current_obi > BEST_CASE_THRESHOLD
    ):
        direction = 1  
    elif (
        previous_obi >= -BEST_CASE_THRESHOLD
        and current_obi < -BEST_CASE_THRESHOLD
    ):
        direction = -1 
    else:
        i += 1
        continue

    entry_idx = i + 1
    exit_idx = entry_idx + BEST_CASE_HOLDING

    entry_row = df.iloc[entry_idx]
    fixed_exit_row = df.iloc[exit_idx]

    future_quotes = df.iloc[
        entry_idx + 1 : exit_idx + 1
    ]

    if direction == 1:
        entry_price = entry_row["ask_price"]
        fixed_exit_price = fixed_exit_row["bid_price"]
        best_exit_price = future_quotes["bid_price"].max()
        fixed_move = fixed_exit_price - entry_price
        best_move = best_exit_price - entry_price

    else:
        entry_price = entry_row["bid_price"]
        fixed_exit_price = fixed_exit_row["ask_price"]
        best_exit_price = future_quotes["ask_price"].min()
        fixed_move = entry_price - fixed_exit_price
        best_move = entry_price - best_exit_price

    fixed_gross = fixed_move * QUANTITY
    best_gross = best_move * QUANTITY

    fixed_fee = (
        entry_price + fixed_exit_price
    ) * QUANTITY * FEE_RATE

    best_fee = (
        entry_price + best_exit_price
    ) * QUANTITY * FEE_RATE

    fixed_net = fixed_gross - fixed_fee
    best_net = best_gross - best_fee

    best_case_trades.append({
        "direction": "LONG" if direction == 1 else "SHORT",
        "fixed_move": fixed_move,
        "best_move": best_move,
        "fixed_gross": fixed_gross,
        "best_gross": best_gross,
        "fixed_fee": fixed_fee,
        "best_fee": best_fee,
        "fixed_net": fixed_net,
        "best_net": best_net
    })

    i = exit_idx

best_case_df = pd.DataFrame(best_case_trades)

# BEST-CASE EXIT ANALYSIS

print("/nBEST-CASE EXIT ANALYSIS")

if best_case_df.empty:
    print("No entry events found.")

else:
    print("Trades:", len(best_case_df))

    print("Average Fixed Price Move:", best_case_df["fixed_move"].mean())
    print("Average Best Price Move:", best_case_df["best_move"].mean())

    print("Average Fixed Net PnL:", best_case_df["fixed_net"].mean())
    print("Average Best-Case Net PnL:", best_case_df["best_net"].mean())

    profitable_rate = (best_case_df["best_net"] > 0).mean() * 100
    unprofitable_trades = (best_case_df["best_net"] <= 0).sum()

    print("Best-Case Profitable Rate:", profitable_rate, "%")
    print("Best-Case Unprofitable Trades:", unprofitable_trades)
    print("Total Best-Case Net PnL:", best_case_df["best_net"].sum())

##DATA QUALITY CHECK

print("DATA QUALITY CHECK")

timestamps = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")

intervals = timestamps.diff().dt.total_seconds()

print("Total Snapshots:", len(df))
print("First Timestamp:", timestamps.min())
print("Last Timestamp:", timestamps.max())

print("Snapshot Intervals:")
print(intervals.describe())

print("Missing Timestamps:", timestamps.isna().sum())
print("Duplicate Update IDs:", df["update_id"].duplicated().sum())
print("Non-increasing Update IDs:", (df["update_id"].diff() <= 0).sum())

## BACKTEST VALIDATION

print("/nBACKTEST VALIDATION")

if best_case_df.empty:
    print("No trades to validate.")

else:
    print("Best-Case Trades:", len(best_case_df))

    invalid_exits = (
    best_case_df["best_net"] < best_case_df["fixed_net"]
).sum()

    print("Best-Case Worse Than Fixed:", invalid_exits)

    pnl_errors = (
        best_case_df["best_gross"]
        - best_case_df["best_fee"]
        - best_case_df["best_net"]
    ).abs()

    print(
        "Maximum PnL Calculation Error:",
        pnl_errors.max()
    )






