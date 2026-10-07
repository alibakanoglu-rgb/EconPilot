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
    "series=TP.FG.J0&startDate=01-01-2005"
    "&endDate=31-12-2026&type=json"
)

response = requests.get(
    url,
    headers={"key": api_key},
    timeout=30,
)
response.raise_for_status()

items = response.json().get("items", [])
if not items:
    raise RuntimeError("EVDS yanıtında veri bulunamadı.")

df = pd.DataFrame(items)
df = df.rename(columns={"Tarih": "date", "TP_FG_J0": "cpi"})
df = df[["date", "cpi"]].copy()
df["date"] = pd.to_datetime(df["date"], format="mixed")
df["cpi"] = pd.to_numeric(df["cpi"], errors="coerce")
df = df.dropna().sort_values("date")
df["annual_inflation_pct"] = df["cpi"].pct_change(12) * 100

DATA_DIR.mkdir(exist_ok=True)
csv_path = DATA_DIR / "tufe.csv"
chart_path = DATA_DIR / "tufe_yillik_enflasyon.png"

df.to_csv(csv_path, index=False, encoding="utf-8-sig")

chart_data = df.dropna(subset=["annual_inflation_pct"])
plt.figure(figsize=(11, 6))
plt.plot(
    chart_data["date"],
    chart_data["annual_inflation_pct"],
    color="darkred",
)
plt.title("Türkiye TÜFE — Yıllık Değişim")
plt.xlabel("Tarih")
plt.ylabel("Yıllık değişim (%)")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(chart_path, dpi=150)

print(f"İndirilen gözlem: {len(df)}")
print(f"CSV: {csv_path}")
print(f"Grafik: {chart_path}")