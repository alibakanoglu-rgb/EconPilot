import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

PROJECT_DIR = Path(__file__).resolve().parent
RAW_DIR = PROJECT_DIR / "data" / "kap" / "financials_raw"
CONSTITUENTS_FILE = PROJECT_DIR / "data" / "kap" / "bist100_constituents.csv"
OUTPUT_DIR = PROJECT_DIR / "data" / "kap" / "processed"

FINANCIAL_ITEMS = [
    "Toplam Kaynaklar",
    "Kısa Vadeli Yükümlülükler",
    "Uzun Vadeli Yükümlülükler",
    "Toplam Özkaynaklar",
    "Toplam Varlıklar",
    "Hasılat",
    "Net Dönem Kârı (Zararı)",
    "Finans Sektörü Faaliyetleri Hasılatı",
]

# KAP dosyalarında 2025 dönemindeki eski unvanlarla görünen şirketler.
OLD_NAMES = {
    "KOZA ALTIN İŞLETMELERİ A.Ş.": "TRALT",
    "İPEK DOĞAL ENERJİ KAYNAKLARI ARAŞTIRMA VE ÜRETİM A.Ş.": "TRENJ",
    "KOZA ANADOLU METAL MADENCİLİK İŞLETMELERİ A.Ş.": "TRMET",
    "BATIÇİM BATI ANADOLU ÇİMENTO SANAYİİ A.Ş.": "BTCIM",
}


def clean_name(value):
    return " ".join(str(value).strip().upper().split())


def parse_amount(value, unit):
    if value is None or str(value).strip() == "":
        return ""

    if isinstance(value, (int, float, Decimal)):
        amount = Decimal(str(value))
    else:
        text = str(value).strip().replace(" ", "")
        if text.startswith("(") and text.endswith(")"):
            text = "-" + text[1:-1]
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(".", "")
        try:
            amount = Decimal(text)
        except InvalidOperation:
            return ""

    unit_text = str(unit or "TL").replace(" ", "").upper()
    multiplier = {
        "TL": Decimal("1"),
        "1000TL": Decimal("1000"),
        "1000000TL": Decimal("1000000"),
    }.get(unit_text)

    if multiplier is None:
        return ""

    return str(amount * multiplier)


def main():
    if not CONSTITUENTS_FILE.exists():
        raise FileNotFoundError(f"BIST 100 listesi bulunamadı: {CONSTITUENTS_FILE}")

    with CONSTITUENTS_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        constituents = list(csv.DictReader(file))

    name_to_ticker = {
        clean_name(row["company"]): row["ticker"].strip()
        for row in constituents
    }

    filings = {}

    source_files = sorted(RAW_DIR.glob("*_2025_h1.xlsx"))
    if not source_files:
        raise FileNotFoundError(f"Kaynak Excel dosyası bulunamadı: {RAW_DIR}")

    for source_file in source_files:
        sheet = load_workbook(
            source_file, read_only=True, data_only=True
        ).active
        rows = sheet.iter_rows(values_only=True)
        header = None

        for row in rows:
            if row and row[0] == "Şirket":
                header = list(row)
                break

        if header is None:
            print(f"Başlık satırı bulunamadı, atlandı: {source_file.name}")
            continue

        indexes = {name: header.index(name) for name in FINANCIAL_ITEMS if name in header}

        for row in rows:
            if not row or len(row) < 8:
                continue
            if row[0] is None or not str(row[1]).strip().isdigit():
                continue

            kap_name = str(row[0]).strip()
            normalized_name = clean_name(kap_name)
            ticker = OLD_NAMES.get(normalized_name) or name_to_ticker.get(normalized_name)

            # BIST 100 dışında kalan arama sonuçlarını alma.
            if not ticker:
                continue

            filing_id = str(row[1]).strip()
            filing = {
                "ticker": ticker,
                "company": next(
                    item["company"] for item in constituents
                    if item["ticker"].strip() == ticker
                ),
                "kap_company": kap_name,
                "disclosure_id": filing_id,
                "published_at": str(row[2] or ""),
                "year": str(row[3] or ""),
                "period_code": str(row[4] or ""),
                "consolidation": str(row[5] or ""),
                "unit": str(row[6] or ""),
                "sector_type": str(row[7] or ""),
                "source_file": source_file.name,
                "values": {},
            }

            for item, column in indexes.items():
                raw_value = row[column] if column < len(row) else None
                filing["values"][item] = {
                    "raw": "" if raw_value is None else str(raw_value),
                    "value_tl": parse_amount(raw_value, filing["unit"]),
                }

            filings.setdefault(ticker, {})[filing_id] = filing

    selected = {}
    for ticker, company_filings in filings.items():
        def preference(filing):
            consolidated = filing["consolidation"].strip().lower() == "konsolide"
            try:
                published = datetime.strptime(
                    filing["published_at"], "%d-%m-%Y %H:%M:%S"
                )
            except ValueError:
                published = datetime.min
            return consolidated, published

        selected[ticker] = max(company_filings.values(), key=preference)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    financial_path = OUTPUT_DIR / "bist100_financials_2025_h1.csv"
    coverage_path = OUTPUT_DIR / "bist100_coverage_2025_h1.csv"

    with financial_path.open("w", encoding="utf-8-sig", newline="") as file:
        fields = [
            "ticker", "company", "kap_company", "year", "period_code",
            "consolidation", "sector_type", "item", "raw_value",
            "unit", "value_tl", "disclosure_id", "published_at", "source_file",
        ]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for ticker in sorted(selected):
            filing = selected[ticker]
            for item in FINANCIAL_ITEMS:
                value = filing["values"].get(item, {"raw": "", "value_tl": ""})
                writer.writerow({
                    "ticker": ticker,
                    "company": filing["company"],
                    "kap_company": filing["kap_company"],
                    "year": filing["year"],
                    "period_code": filing["period_code"],
                    "consolidation": filing["consolidation"],
                    "sector_type": filing["sector_type"],
                    "item": item,
                    "raw_value": value["raw"],
                    "unit": filing["unit"],
                    "value_tl": value["value_tl"],
                    "disclosure_id": filing["disclosure_id"],
                    "published_at": filing["published_at"],
                    "source_file": filing["source_file"],
                })

    with coverage_path.open("w", encoding="utf-8-sig", newline="") as file:
        fields = [
            "ticker", "company", "status", "kap_company",
            "consolidation", "disclosure_id", "source_file",
        ]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for company in sorted(constituents, key=lambda item: item["ticker"]):
            ticker = company["ticker"].strip()
            filing = selected.get(ticker)
            writer.writerow({
                "ticker": ticker,
                "company": company["company"],
                "status": "Veri bulundu" if filing else "Bu dosyalarda veri yok",
                "kap_company": filing["kap_company"] if filing else "",
                "consolidation": filing["consolidation"] if filing else "",
                "disclosure_id": filing["disclosure_id"] if filing else "",
                "source_file": filing["source_file"] if filing else "",
            })

    missing = [
        company["ticker"].strip()
        for company in constituents
        if company["ticker"].strip() not in selected
    ]

    print(f"BIST 100 şirketi: {len(constituents)}")
    print(f"Finansal kaydı bulunan şirket: {len(selected)}")
    print(f"Verisi olmayan şirket: {', '.join(missing) if missing else 'yok'}")
    print(f"Finansal veri CSV: {financial_path}")
    print(f"Kapsam kontrol CSV: {coverage_path}")


if __name__ == "__main__":
    main()