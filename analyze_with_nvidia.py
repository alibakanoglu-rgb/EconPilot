from pathlib import Path
import os

import pandas as pd
import requests
from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
REPORT_DIR = PROJECT_DIR / "reports"

load_dotenv(PROJECT_DIR / ".env")
api_key = os.getenv("NVIDIA_API_KEY")

if not api_key:
    raise RuntimeError(".env içinde NVIDIA_API_KEY bulunamadı.")

df = pd.read_csv(
    DATA_DIR / "monthly_macro_comparison.csv",
    parse_dates=["month"],
)

if df.empty:
    raise RuntimeError("Karşılaştırma CSV dosyasında veri bulunamadı.")

first_row = df.iloc[0]
last_row = df.iloc[-1]
cpi_yoy = df.dropna(subset=["cpi_yoy_pct"])
usd_yoy = df.dropna(subset=["usd_try_yoy_pct"])

if cpi_yoy.empty or usd_yoy.empty:
    raise RuntimeError("Yıllık değişim için yeterli veri bulunamadı.")

first_month = first_row["month"].strftime("%Y-%m")
last_month = last_row["month"].strftime("%Y-%m")

cpi_change = (
    last_row["cpi_index_100"] / first_row["cpi_index_100"] - 1
) * 100
usd_change = (
    last_row["usd_try_index_100"] / first_row["usd_try_index_100"] - 1
) * 100

summary = f"""
Dönem: {first_month} - {last_month}
Aylık gözlem sayısı: {len(df)}
İlk ortak ayda her iki endeks de 100'e eşitlenmiştir.
Dönem boyunca TÜFE endeksindeki değişim: %{cpi_change:.2f}
Dönem boyunca USD/TRY endeksindeki değişim: %{usd_change:.2f}
TÜFE yıllık değişimi: {cpi_yoy.iloc[0]['month']:%Y-%m} ayında
%{cpi_yoy.iloc[0]['cpi_yoy_pct']:.2f};
{cpi_yoy.iloc[-1]['month']:%Y-%m} ayında
%{cpi_yoy.iloc[-1]['cpi_yoy_pct']:.2f}.
USD/TRY yıllık değişimi: {usd_yoy.iloc[0]['month']:%Y-%m} ayında
%{usd_yoy.iloc[0]['usd_try_yoy_pct']:.2f};
{usd_yoy.iloc[-1]['month']:%Y-%m} ayında
%{usd_yoy.iloc[-1]['usd_try_yoy_pct']:.2f}.
USD/TRY yıllık değişiminin gözlenen aralığı:
%{usd_yoy['usd_try_yoy_pct'].min():.2f} - %{usd_yoy['usd_try_yoy_pct'].max():.2f}.
Yıllık değişim değerleri ilk 12 ay için mevcut değildir; bu değerler sıfır değildir.
""".strip()

columns = [
    "month",
    "cpi_yoy_pct",
    "usd_try_yoy_pct",
    "cpi_index_100",
    "usd_try_index_100",
]
data_table = df[columns].to_string(
    index=False,
    float_format=lambda value: f"{value:.2f}",
)

system_prompt = """
EconPilot için kısa, Türkçe bir ekonomik veri notu yaz.
Yalnızca kullanıcı mesajındaki sayısal özete ve tabloya dayan.
Verilmeyen sayıları hesaplama veya uydurma.
Korelasyon ölçülmedi; korelasyon iddiasında bulunma.
Nedensellik, güncel olay veya tahmin çıkarımı yapma.
Önce 3-4 kısa bulgu maddesi, sonra kısa bir sınırlılıklar bölümü ver.
İç analizini, planını veya düşünme taslağını gösterme.
""".strip()

user_prompt = f"""
Aşağıdaki sayısal özet Python ile EVDS verilerinden hesaplandı.
Yüzdeleri aynen kullan; özellikle yıllık değişimin ilk 12 ayda
bulunmadığını sıfır olmadığını dikkate al.

Özet:
{summary}

Aylık tablo:
{data_table}

Yalnızca bu veri kümesi için kısa bir veri notu yaz.
""".strip()

payload = {
    "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    "temperature": 0.2,
    "max_tokens": 1000,
    "stream": False,
    "chat_template_kwargs": {"enable_thinking": False},
}

response = requests.post(
    "https://integrate.api.nvidia.com/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    },
    json=payload,
    timeout=120,
)
response.raise_for_status()

analysis = response.json()["choices"][0]["message"]["content"]

REPORT_DIR.mkdir(exist_ok=True)
report_path = REPORT_DIR / "macro_brief.md"
draft_path = REPORT_DIR / "ai_draft_for_review.md"

report_text = f"""# EconPilot — Aylık makro veri notu

**Dönem:** {first_month} – {last_month}  
**Gözlem sayısı:** {len(df)}

## Hesaplanan bulgular

- TÜFE endeksi dönem boyunca %{cpi_change:.2f} değişti.
- USD/TRY endeksi dönem boyunca %{usd_change:.2f} değişti.
- TÜFE yıllık değişimi {cpi_yoy.iloc[0]['month']:%Y-%m} ayında %{cpi_yoy.iloc[0]['cpi_yoy_pct']:.2f}, {cpi_yoy.iloc[-1]['month']:%Y-%m} ayında %{cpi_yoy.iloc[-1]['cpi_yoy_pct']:.2f} oldu.
- USD/TRY yıllık değişimi aynı gözlem aralığında %{usd_yoy.iloc[0]['usd_try_yoy_pct']:.2f} değerinden %{usd_yoy.iloc[-1]['usd_try_yoy_pct']:.2f} değerine değişti. Gözlenen aralık %{usd_yoy['usd_try_yoy_pct'].min():.2f} – %{usd_yoy['usd_try_yoy_pct'].max():.2f} oldu.

## Sınırlılıklar

- Karşılaştırma 25 aylık ortak dönemi kapsıyor.
- İlk 12 ay için yıllık değişim hesaplanamadığından bu gözlemler sıfır olarak yorumlanmamalı.
- Bu betimleyici karşılaştırma tek başına korelasyon veya nedensellik kanıtlamaz.

*Bu not yatırım tavsiyesi değildir.*
"""

report_path.write_text(report_text, encoding="utf-8")
draft_path.write_text(
    "# NVIDIA taslağı — doğrulanmadı; rapor olarak kullanmadan önce kontrol et\n\n"
    + analysis,
    encoding="utf-8",
)

print(f"Veriye dayalı rapor: {report_path}")
print(f"Kontrol edilecek NVIDIA taslağı: {draft_path}")	