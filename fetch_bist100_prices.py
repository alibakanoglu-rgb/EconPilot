from pathlib import Path
import time

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "data" / "kap" / "bist100_constituents.csv"
OUTPUT_DIR = ROOT / "data" / "market"
PRICES_OUTPUT = OUTPUT_DIR / "bist100_daily_prices.csv"
COVERAGE_OUTPUT = OUTPUT_DIR / "bist100_price_coverage.csv"

companies = pd.read_csv(INPUT, dtype={"ticker": str})
companies["ticker"] = companies["ticker"].str.strip().str.upper()
companies = companies.dropna(subset=["ticker"]).drop_duplicates("ticker")

price_rows = []
coverage_rows = []
batch_size = 10


def value_or_none(row, column):
    if column not in row.index or pd.isna(row[column]):
        return None
    return float(row[column])


for start in range(0, len(companies), batch_size):
    batch = companies.iloc[start : start + batch_size]
    symbols = [f"{ticker}.IS" for ticker in batch["ticker"]]

    print(f"İndiriliyor: {start + 1}-{start + len(batch)} / {len(companies)}")

    try:
        downloaded = yf.download(
            tickers=symbols,
            period="5y",
            interval="1d",
            auto_adjust=False,
            actions=True,
            group_by="ticker",
            threads=False,
            progress=False,
            multi_level_index=True,
            timeout=30,
        )
    except Exception as exc:
        for _, company in batch.iterrows():
            coverage_rows.append(
                {
                    "ticker": company["ticker"],
                    "company": company.get("company", ""),
                    "yahoo_symbol": f"{company['ticker']}.IS",
                    "status": "error",
                    "rows": 0,
                    "first_date": "",
                    "last_date": "",
                    "error": str(exc)[:250],
                }
            )
        time.sleep(2)
        continue

    for _, company in batch.iterrows():
        ticker = company["ticker"]
        symbol = f"{ticker}.IS"

        try:
            if isinstance(downloaded.columns, pd.MultiIndex):
                frame = None
                for level in range(downloaded.columns.nlevels):
                    if symbol in downloaded.columns.get_level_values(level):
                        frame = downloaded.xs(symbol, axis=1, level=level)
                        break
                if frame is None:
                    raise ValueError("Sembol sonuç sütunlarında bulunamadı.")
            else:
                frame = downloaded

            frame.columns = [str(column) for column in frame.columns]
            if "Close" not in frame.columns:
                raise ValueError("Kapanış fiyatı sütunu yok.")

            frame = frame.dropna(subset=["Close"])
            if frame.empty:
                raise ValueError("Fiyat verisi dönmedi.")

            dates = pd.to_datetime(frame.index)
            for date, row in zip(dates, frame.itertuples(index=False, name=None)):
                row_values = pd.Series(row, index=frame.columns)
                price_rows.append(
                    {
                        "ticker": ticker,
                        "date": date.strftime("%Y-%m-%d"),
                        "open": value_or_none(row_values, "Open"),
                        "high": value_or_none(row_values, "High"),
                        "low": value_or_none(row_values, "Low"),
                        "close": value_or_none(row_values, "Close"),
                        "adj_close": value_or_none(row_values, "Adj Close"),
                        "volume": value_or_none(row_values, "Volume"),
                        "dividends": value_or_none(row_values, "Dividends"),
                        "stock_splits": value_or_none(row_values, "Stock Splits"),
                        "source": "Yahoo Finance via yfinance",
                    }
                )

            coverage_rows.append(
                {
                    "ticker": ticker,
                    "company": company.get("company", ""),
                    "yahoo_symbol": symbol,
                    "status": "downloaded",
                    "rows": len(frame),
                    "first_date": dates.min().strftime("%Y-%m-%d"),
                    "last_date": dates.max().strftime("%Y-%m-%d"),
                    "error": "",
                }
            )
        except Exception as exc:
            coverage_rows.append(
                {
                    "ticker": ticker,
                    "company": company.get("company", ""),
                    "yahoo_symbol": symbol,
                    "status": "no_data_or_error",
                    "rows": 0,
                    "first_date": "",
                    "last_date": "",
                    "error": str(exc)[:250],
                }
            )

    time.sleep(2)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

pd.DataFrame(price_rows).to_csv(
    PRICES_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)
pd.DataFrame(coverage_rows).to_csv(
    COVERAGE_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)

coverage = pd.DataFrame(coverage_rows)
downloaded_count = (
    int((coverage["status"] == "downloaded").sum()) if not coverage.empty else 0
)

print(f"Şirket sayısı: {len(companies)}")
print(f"Fiyatı indirilen şirket: {downloaded_count}")
print(f"Fiyat CSV: {PRICES_OUTPUT}")
print(f"Kapsam CSV: {COVERAGE_OUTPUT}")