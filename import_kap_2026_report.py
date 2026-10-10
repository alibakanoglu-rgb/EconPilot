from io import StringIO
from pathlib import Path
import re
from numbers import Number

import pandas as pd


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "kap" / "TUPRS_2026_6aylik_finansal_rapor.xls"
OUTPUT = ROOT / "data" / "kap" / "processed" / "TUPRS_financials_2026_h1_full.csv"

STATEMENTS = {
    "Finansal Durum Tablosu": "Bilanço",
    "Kar veya Zarar Tablosu": "Kâr veya Zarar",
    "Diğer Kapsamlı Gelir Tablosu": "Diğer Kapsamlı Gelir",
    "Nakit Akış Tablosu": "Nakit Akış",
}


def parse_number(value):
    if pd.isna(value):
        return None

    if isinstance(value, Number):
        return float(value)

    text = str(value).strip().replace("\xa0", "").replace(" ", "")
    if text in {"", "-", "—", "nan", "None"}:
        return None

    # KAP Türkçe sayı biçimi: 1.234.567,89
    text = text.replace(".", "").replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


def statement_name(table):
    preview = " ".join(
        str(value)
        for value in table.head(6).to_numpy().flatten()
        if pd.notna(value)
    )

    for marker, name in STATEMENTS.items():
        if marker.casefold() in preview.casefold():
            return name

    return None


def period_from_header(header):
    text = str(header).strip()
    date_matches = re.findall(r"(\d{2})\.(\d{2})\.(\d{4})", text)

    if not date_matches:
        return None

    # Dönem, başlıktaki bitiş tarihinden alınır.
    day, month, year = date_matches[-1]
    period = f"{year}/{month}"

    if "3 Aylık" in text:
        basis = "quarter"
    elif len(date_matches) > 1:
        basis = "year_to_date"
    else:
        basis = "point_in_time"

    return period, basis


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Rapor dosyası bulunamadı: {SOURCE}")

    html = SOURCE.read_text(encoding="utf-8", errors="replace")
    tables = pd.read_html(StringIO(html))

    records = []
    unit = "1.000 TL"
    consolidation = "Konsolide"

    for table in tables:
        if table.empty or len(table) < 20 or len(table.columns) < 5:
            continue

        statement = statement_name(table)
        if statement is None:
            continue

        # İlk satırdaki sütun başlıklarından dönem sütunlarını bul.
        period_columns = {}
        for column_index in range(3, len(table.columns)):
            period_info = period_from_header(table.iloc[0, column_index])
            if period_info:
                period_columns[column_index] = period_info

        if not period_columns:
            continue

        for _, row in table.iterrows():
            item = str(row.iloc[1]).strip() if len(row) > 1 else ""
            if item.casefold() in {"", "nan", "none"}:
                continue

            item_code = str(row.iloc[2]).strip() if len(row) > 2 else ""
            if item_code.casefold() in {"nan", "none"}:
                item_code = ""

            for column_index, (period, basis) in period_columns.items():
                value = parse_number(row.iloc[column_index])
                if value is None:
                    continue

                records.append(
                    {
                        "ticker": "TUPRS",
                        "statement": statement,
                        "item": item,
                        "item_code": item_code,
                        "period": period,
                        "period_basis": basis,
                        "unit": unit,
                        "consolidation": consolidation,
                        "value": value,
                        "source_file": SOURCE.name,
                    }
                )

    if not records:
        raise ValueError(
            "Finansal tablo satırı bulunamadı. Rapor biçimini kontrol etmek gerekiyor."
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result = pd.DataFrame(records)
    result.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

    print(f"İşlenen finansal veri satırı: {len(result)}")
    print("Tablolar:", ", ".join(sorted(result["statement"].unique())))
    print("Dönemler:", ", ".join(sorted(result["period"].unique())))
    print(f"CSV: {OUTPUT}")


if __name__ == "__main__":
    main()