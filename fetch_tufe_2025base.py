from pathlib import Path
import os

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
    "series=TP.TUKFIY2025.GENEL&startDate=01-01-2025"
    "&endDate=31-12-2026&type=json"
)

response = requests.get(url, headers={"key": api_key}, timeout=30)
response.raise_for_status()

items = response.json().get("items", [])
if not items:
    raise RuntimeError("EVDS yanıtında veri bulunamadı.")

df = pd.DataFrame(items)
value_column = "TP_TUKFIY2025_GENEL"

if "Tarih" not in df.columns or value_column not in df.columns:
    raise RuntimeError(f"EVDS yanıtındaki sütunlar beklenenden farklı: {list(df.columns)}")

df = df.rename(columns={"Tarih": "date", value_column: "cpi"})
df = df[["date", "cpi"]].copy()
df["date"] = pd.to_datetime(df["date"], format="mixed")
df["cpi"] = pd.to_numeric(df["cpi"], errors="coerce")
df = df.dropna().sort_values("date")
df["annual_inflation_pct"] = df["cpi"].pct_change(12) * 100

DATA_DIR.mkdir(exist_ok=True)
csv_path = DATA_DIR / "tufe_2025base.csv"
df.to_csv(csv_path, index=False, encoding="utf-8-sig")

print(f"İndirilen gözlem: {len(df)}")
print(f"İlk tarih: {df['date'].min():%Y-%m}")
print(f"Son tarih: {df['date'].max():%Y-%m}")
print(f"CSV: {csv_path}")