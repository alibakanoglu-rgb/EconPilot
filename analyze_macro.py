from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"

cpi = pd.read_csv(DATA_DIR / "tufe_2025base.csv", parse_dates=["date"])
usd = pd.read_csv(DATA_DIR / "usdtry.csv", parse_dates=["date"])

cpi["month"] = cpi["date"].dt.to_period("M")
usd["month"] = usd["date"].dt.to_period("M")

usd_monthly = (
    usd.groupby("month")["usd_try_buying"]
    .mean()
    .rename("usd_try_monthly_avg")
    .reset_index()
)

comparison = cpi[["month", "cpi"]].merge(
    usd_monthly,
    on="month",
    how="inner",
)
comparison = comparison.sort_values("month").reset_index(drop=True)

if comparison.empty:
    raise RuntimeError("TÜFE ve USD/TRY için ortak dönem bulunamadı.")

comparison["cpi_yoy_pct"] = comparison["cpi"].pct_change(12) * 100
comparison["usd_try_yoy_pct"] = (
    comparison["usd_try_monthly_avg"].pct_change(12) * 100
)

comparison["cpi_index_100"] = (
    comparison["cpi"] / comparison["cpi"].iloc[0] * 100
)
comparison["usd_try_index_100"] = (
    comparison["usd_try_monthly_avg"]
    / comparison["usd_try_monthly_avg"].iloc[0]
    * 100
)

comparison["month"] = comparison["month"].dt.to_timestamp()

csv_path = DATA_DIR / "monthly_macro_comparison.csv"
chart_path = DATA_DIR / "tufe_usdtry_indexed.png"

comparison.to_csv(csv_path, index=False, encoding="utf-8-sig")

plt.figure(figsize=(11, 6))
plt.plot(
    comparison["month"],
    comparison["cpi_index_100"],
    label="TÜFE endeksi (2025 bazlı)",
)
plt.plot(
    comparison["month"],
    comparison["usd_try_index_100"],
    label="USD/TRY aylık ortalaması",
)
plt.title("TÜFE ve USD/TRY — Ortak başlangıç ayı 100")
plt.xlabel("Tarih")
plt.ylabel("Endeks (başlangıç ayı = 100)")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(chart_path, dpi=150)

print(f"Ortak aylık gözlem: {len(comparison)}")
print(f"İlk ay: {comparison['month'].min():%Y-%m}")
print(f"Son ay: {comparison['month'].max():%Y-%m}")
print(f"CSV: {csv_path}")
print(f"Grafik: {chart_path}")