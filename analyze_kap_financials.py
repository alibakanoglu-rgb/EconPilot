from pathlib import Path
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "kap" / "TUPRS_ozet_finansallar.csv"
OUTPUT = ROOT / "reports" / "TUPRS_finansal_ozet.md"

if not SOURCE.exists():
    raise FileNotFoundError(f"CSV bulunamadı: {SOURCE}")

df = pd.read_csv(SOURCE)
periods = ["2023/12", "2024/12", "2025/12", "2026/06"]


def normalize(text):
    text = str(text).casefold().translate(
        str.maketrans("çğıöşüâ", "cgiosua")
    )
    return "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def value(period, item_name):
    wanted = normalize(item_name)
    rows = df[
        (df["period"] == period)
        & (df["item"].map(normalize) == wanted)
    ]
    if rows.empty:
        raise ValueError(f"Kalem bulunamadı: {item_name} / {period}")
    return float(rows.iloc[0]["value"])


def money_bn(value_1000tl):
    # Kaynak birimi 1000 TL; sonuç milyar TL olarak gösterilir.
    text = f"{value_1000tl / 1_000_000:,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def percent(value):
    if value is None:
        return "hesaplanmadı"
    return f"%{value:.1f}".replace(".", ",")


def yoy_change(previous, current):
    # Önceki dönem sıfır veya zarardaysa yüzde değişim yanıltıcı olabilir.
    if previous is None or current is None or previous <= 0:
        return None
    return (current / previous - 1) * 100

lines = [
    "# TUPRS | KAP finansal özet",
    "",
    f"**Kaynak dosya:** `{SOURCE.name}`  ",
    "**Tablo niteliği:** Konsolide  •  **Sunum birimi:** 1000 TL",
    "",
    "## Yıllık dönemler",
    "",
    "| Dönem | Hasılat (milyar TL) | Brüt kâr (milyar TL) | Esas faaliyet kârı (milyar TL) | Net dönem kârı (milyar TL) |",
    "|---|---:|---:|---:|---:|",
]

for period in periods[:3]:
    revenue = value(period, "Hasılat")
    gross = value(period, "Brüt Kâr (Zarar)")
    operating = value(period, "Esas Faaliyet Kârı (Zararı)")
    net = value(period, "Net Dönem Kârı (Zararı)")
    lines.append(
        f"| {period} | {money_bn(revenue)} | {money_bn(gross)} "
        f"| {money_bn(operating)} | {money_bn(net)} |"
    )

lines += [
    "",
    "## Yıllık değişim",
    "",
]

for previous_period, current_period in [
    ("2023/12", "2024/12"),
    ("2024/12", "2025/12"),
]:
    revenue_growth = yoy_change(
        value(previous_period, "Hasılat"),
        value(current_period, "Hasılat"),
    )
    profit_growth = yoy_change(
        value(previous_period, "Net Dönem Kârı (Zararı)"),
        value(current_period, "Net Dönem Kârı (Zararı)"),
    )
    lines.append(
        f"- {previous_period} → {current_period}: hasılat "
        f"{percent(revenue_growth)}, net dönem kârı {percent(profit_growth)}."
    )

lines += [
    "",
    "## 2026 ilk altı ay",
    "",
]

period = "2026/06"
revenue = value(period, "Hasılat")
gross = value(period, "Brüt Kâr (Zarar)")
operating = value(period, "Esas Faaliyet Kârı (Zararı)")
net = value(period, "Net Dönem Kârı (Zararı)")

current_assets = value(period, "Dönen Varlıklar")
current_liabilities = value(period, "Kısa Vadeli Yükümlülükler")
assets = value(period, "Toplam Varlıklar")
liabilities = value(period, "Toplam Yükümlülükler")

lines += [
    f"- Hasılat: {money_bn(revenue)} milyar TL; brüt kâr marjı: "
    f"{percent(gross / revenue * 100)}.",
    f"- Esas faaliyet kâr marjı: {percent(operating / revenue * 100)}; "
    f"net dönem kâr marjı: {percent(net / revenue * 100)}.",
    f"- Cari oran (dönen varlıklar / kısa vadeli yükümlülükler): "
    f"{current_assets / current_liabilities:.2f}".replace(".", ","),
    f"- Toplam yükümlülükler / toplam varlıklar: "
    f"{percent(liabilities / assets * 100)}.",
    "",
    "## Kapsam ve dikkat noktaları",
    "",
    "- 2026/06 altı aylık dönemdir; 2025/12 tam yılıyla doğrudan büyüme karşılaştırması yapılmadı.",
    "- Kaynak dosya özet bilanço ile kâr/zarar tablolarını içeriyor; nakit akış tablosu ve dipnotlar bu analizde yok.",
    "- Hisse fiyatı bulunmadığı için fiyat/kazanç, piyasa değeri veya ucuzluk değerlendirmesi hesaplanmadı.",
    "- Bu çıktı finansal verilerin betimleyici özetidir; tek başına alım veya satım kararı oluşturmaz.",
    "",
]

OUTPUT.parent.mkdir(exist_ok=True)
OUTPUT.write_text("\n".join(lines), encoding="utf-8")
print(f"Finansal özet oluşturuldu: {OUTPUT}")