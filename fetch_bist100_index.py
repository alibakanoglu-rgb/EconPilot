from pathlib import Path

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "market" / "bist100_index_daily.csv"

index = yf.Ticker("XU100.IS").history(
    period="5y",
    interval="1d",
    auto_adjust=False,
)

if index.empty or "Close" not in index.columns:
    raise RuntimeError("XU100.IS endeks verisi indirilemedi.")

adjusted_close = index["Adj Close"] if "Adj Close" in index.columns else index["Close"]

result = pd.DataFrame(
    {
        "date": pd.to_datetime(index.index).strftime("%Y-%m-%d"),
        "close": index["Close"].to_numpy(),
        "adj_close": adjusted_close.to_numpy(),
        "source": "Yahoo Finance via yfinance",
    }
)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
result.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

print(f"İndirilen gözlem: {len(result)}")
print(f"İlk tarih: {result['date'].min()}")
print(f"Son tarih: {result['date'].max()}")
print(f"CSV: {OUTPUT}")