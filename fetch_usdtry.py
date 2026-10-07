from pathlib import Path
import os

import matplotlib.pyplot as plt
import pandas as pd
import requests
from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"

load_dotenv(PROJECT_DIR / ".env")
api_key = os.getenv("EVDS_API_KEY")

if not api_key:
    raise RuntimeError(".env içinde EVDS_API_KEY bulunamadı.")

url = (
    "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
    "series=TP.DK.USD.A.YTL&startDate=01-01-2024"
    "&endDate=31-12-2026&type=json"
)

response = requests.get(url, headers={"key": api_key}, timeout=30)
response.raise_for_status()

items = response.json().get("items", [])
if not items:
    raise RuntimeError("EVDS yanıtında USD/TRY verisi bulunamadı.")

df = pd.DataFrame(items)
df = df.rename(
    columns={
        "Tarih": "date",
        "TP_DK_USD_A_YTL": "usd_try_buying",
    }
)
df = df[["date", "usd_try_buying"]].copy()
df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
df["usd_try_buying"] = pd.to_numeric(
    df["usd_try_buying"],
    errors="coerce",
)
df = df.dropna().sort_values("date")

DATA_DIR.mkdir(exist_ok=True)
csv_path = DATA_DIR / "usdtry.csv"
chart_path = DATA_DIR / "usdtry_gunluk.png"

df.to_csv(csv_path, index=False, encoding="utf-8-sig")

plt.figure(figsize=(11, 6))
plt.plot(df["date"], df["usd_try_buying"], color="navy")
plt.title("USD/TRY — Günlük Döviz Alış Kuru")
plt.xlabel("Tarih")
plt.ylabel("TL / USD")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(chart_path, dpi=150)

print(f"İndirilen gözlem: {len(df)}")
print(f"CSV: {csv_path}")
print(f"Grafik: {chart_path}")