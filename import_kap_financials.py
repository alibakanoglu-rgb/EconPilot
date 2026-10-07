from io import StringIO
from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "kap" / "TUPRS_ozet_finansallar.xls"
OUTPUT = ROOT / "data" / "kap" / "TUPRS_ozet_finansallar.csv"

if not SOURCE.exists():
    raise FileNotFoundError(f"KAP dosyası bulunamadı: {SOURCE}")

html = SOURCE.read_text(encoding="utf-8", errors="replace")
tables = pd.read_html(StringIO(html))

records = []
all_periods = set()


def find_metadata(table, label, period):
    labels = table.iloc[:, 0].astype(str).str.strip()
    matches = table.loc[labels.str.casefold() == label.casefold()]
    if matches.empty:
        return ""
    return str(matches.iloc[0][period]).strip()


def parse_number(value):
    if pd.isna(value):
        return None

    text = str(value).strip().replace("\xa0", "").replace(" ", "")
    if text in {"", "-", "—", "nan", "None"}:
        return None

    # KAP dışa aktarımındaki Türkçe sayı biçimi: 1.234.567,89
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


for table in tables:
    if table.empty or len(table.columns) < 2:
        continue

    periods = [
        column
        for column in table.columns[1:]
        if re.fullmatch(r"\d{4}/\d{2}", str(column).strip())
    ]
    if not periods:
        continue

    statement = str(table.columns[0]).strip()
    all_periods.update(str(period) for period in periods)

    for period in periods:
        unit = find_metadata(table, "Sunum Para Birimi", period)
        table_nature = find_metadata(table, "Finansal Tablo Niteliği", period)

        for _, row in table.iterrows():
            item = str(row.iloc[0]).strip()
            if item.casefold() in {
                "",
                "nan",
                "sunum para birimi",
                "finansal tablo niteliği",
            }:
                continue

            value = parse_number(row[period])
            if value is None:
                continue

            records.append(
                {
                    "ticker": "TUPRS",
                    "statement": statement,
                    "item": item,
                    "period": str(period),
                    "unit": unit,
                    "table_nature": table_nature,
                    "value": value,
                    "source_file": SOURCE.name,
                }
            )

if not records:
    raise ValueError(
        "Finansal tablo bulunamadı. KAP dosyasının biçimi beklenenden farklı olabilir."
    )

result = pd.DataFrame(records)
result.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

print(f"İşlenen finansal tablo satırı: {len(result)}")
print(f"Dönemler: {', '.join(sorted(all_periods))}")
print(f"Tablo türleri: {', '.join(result['statement'].drop_duplicates())}")
print(f"CSV: {OUTPUT}")