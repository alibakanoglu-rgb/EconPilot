from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_FILE = PROJECT_DIR / "data" / "kap" / "Endeksler.xlsx"
OUTPUT_FILE = PROJECT_DIR / "data" / "kap" / "bist100_constituents.csv"
SHEET_NAME = "Endeksler Listesi"


def main() -> None:
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"Kaynak Excel dosyası bulunamadı: {SOURCE_FILE}")

    workbook = load_workbook(SOURCE_FILE, read_only=True, data_only=True)
    if SHEET_NAME not in workbook.sheetnames:
        raise ValueError(f"'{SHEET_NAME}' sayfası bulunamadı.")

    sheet = workbook[SHEET_NAME]
    header_row = None

    for row_number, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        if any(
            isinstance(value, str) and value.strip().upper() == "BIST 100"
            for value in row
        ):
            header_row = row_number
            break

    if header_row is None:
        raise ValueError("Excel dosyasında BIST 100 başlığı bulunamadı.")

    companies = []
    for row in sheet.iter_rows(
        min_row=header_row + 1,
        max_col=3,
        values_only=True,
    ):
        rank, ticker, company = row

        # Sonraki endeks başlığına gelince BIST 100 bölümünü bitir.
        if isinstance(rank, str) and rank.strip().upper().startswith("BIST "):
            break

        if rank is None or ticker is None or company is None:
            continue

        try:
            rank = int(rank)
        except (TypeError, ValueError):
            continue

        companies.append(
            {
                "rank": rank,
                "ticker": str(ticker).strip(),
                "company": str(company).strip(),
                "index": "BIST 100",
                "source_file": SOURCE_FILE.name,
                "downloaded_at": datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
            }
        )

    if len(companies) != 100:
        raise ValueError(
            f"BIST 100 bölümünde 100 şirket bekleniyordu; "
            f"{len(companies)} şirket bulundu. Kaynak dosyayı kontrol et."
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=companies[0].keys())
        writer.writeheader()
        writer.writerows(companies)

    print(f"Çıkarılan şirket sayısı: {len(companies)}")
    print(f"CSV: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()