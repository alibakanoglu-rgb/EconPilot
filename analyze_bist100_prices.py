from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "market"
INPUT = DATA_DIR / "bist100_daily_prices.csv"
INDEX_INPUT = DATA_DIR / "bist100_index_daily.csv"
OUTPUT = DATA_DIR / "bist100_price_metrics.csv"

prices = pd.read_csv(INPUT, parse_dates=["date"])
benchmark = pd.read_csv(INDEX_INPUT, parse_dates=["date"])

for column in ["close", "adj_close"]:
    prices[column] = pd.to_numeric(prices[column], errors="coerce")
    benchmark[column] = pd.to_numeric(benchmark[column], errors="coerce")

prices = prices.dropna(subset=["ticker", "date", "adj_close"])
benchmark = benchmark.dropna(subset=["date", "adj_close"])
benchmark = benchmark[["date", "adj_close"]].rename(
    columns={"adj_close": "benchmark_adj_close"}
)

prices = prices.sort_values(["ticker", "date"])


def trailing_return(series, trading_days):
    if len(series) <= trading_days:
        return np.nan
    return (series.iloc[-1] / series.iloc[-trading_days - 1] - 1) * 100


def relative_return(stock_return, benchmark_return):
    if pd.isna(stock_return) or pd.isna(benchmark_return):
        return np.nan
    return ((1 + stock_return / 100) / (1 + benchmark_return / 100) - 1) * 100


records = []

for ticker, group in prices.groupby("ticker"):
    group = group.sort_values("date")
    common = group[["date", "close", "adj_close"]].merge(
        benchmark,
        on="date",
        how="inner",
    ).sort_values("date")

    if common.empty:
        continue

    stock_prices = common["adj_close"]
    index_prices = common["benchmark_adj_close"]

    stock_returns = {
        "1m": trailing_return(stock_prices, 21),
        "3m": trailing_return(stock_prices, 63),
        "6m": trailing_return(stock_prices, 126),
        "12m": trailing_return(stock_prices, 252),
    }
    index_returns = {
        "1m": trailing_return(index_prices, 21),
        "3m": trailing_return(index_prices, 63),
        "6m": trailing_return(index_prices, 126),
        "12m": trailing_return(index_prices, 252),
    }

    daily_returns = stock_prices.pct_change().dropna().tail(252)
    last_year_prices = stock_prices.tail(253)
    drawdowns = last_year_prices / last_year_prices.cummax() - 1

    record = {
        "ticker": ticker,
        "last_date": common["date"].max().strftime("%Y-%m-%d"),
        "last_close": common["close"].iloc[-1],
        "price_observations": len(group),
        "common_observations": len(common),
        "volatility_1y_pct": (
            daily_returns.std(ddof=1) * np.sqrt(252) * 100
            if len(daily_returns) > 1
            else np.nan
        ),
        "max_drawdown_1y_pct": (
            drawdowns.min() * 100 if not drawdowns.empty else np.nan
        ),
        "source": "Yahoo Finance via yfinance",
    }

    for window in ["1m", "3m", "6m", "12m"]:
        stock_return = stock_returns[window]
        index_return = index_returns[window]
        record[f"return_{window}_pct"] = stock_return
        record[f"bist100_return_{window}_pct"] = index_return
        record[f"relative_return_{window}_pct"] = relative_return(
            stock_return,
            index_return,
        )

    records.append(record)

result = pd.DataFrame(records).sort_values("ticker")
result.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

print(f"Göstergesi hesaplanan şirket: {len(result)}")
print(f"Ortak son tarih: {result['last_date'].max()}")
print(f"CSV: {OUTPUT}")