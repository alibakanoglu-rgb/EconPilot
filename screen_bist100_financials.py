from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data" / "kap" / "processed"
INPUT_FILE = DATA_DIR / "bist100_financials_2025_h1.csv"
COVERAGE_FILE = DATA_DIR / "bist100_coverage_2025_h1.csv"
OUTPUT_FILE = DATA_DIR / "bist100_basic_metrics_2025_h1.csv"
REPORT_FILE = PROJECT_DIR / "reports" / "bist100_financial_screen_2025_h1.md"

ITEM_COLUMNS = {
    "Toplam Varlıklar": "assets_tl",
    "Toplam Özkaynaklar": "equity_tl",
    "Hasılat": "business_revenue_tl",
    "Finans Sektörü Faaliyetleri Hasılatı": "financial_revenue_tl",
    "Net Dönem Kârı (Zararı)": "net_income_tl",
}


def main():
    if not INPUT_FILE.exists() or not COVERAGE_FILE.exists():
        raise FileNotFoundError(
            "Birleştirilmiş finansal CSV veya kapsam CSV dosyası bulunamadı."
        )

    data = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")
    coverage = pd.read_csv(COVERAGE_FILE, encoding="utf-8-sig")

    selected_items = data[data["item"].isin(ITEM_COLUMNS)].copy()
    values = selected_items.pivot_table(
        index="ticker",
        columns="item",
        values="value_tl",
        aggfunc="first",
    ).rename(columns=ITEM_COLUMNS)

    for column in ITEM_COLUMNS.values():
        if column not in values.columns:
            values[column] = pd.NA

    values = values.reset_index()
    values["ticker"] = values["ticker"].astype(str)

    metadata = (
        data[["ticker", "sector_type", "consolidation", "kap_company"]]
        .drop_duplicates(subset="ticker")
        .copy()
    )
    metadata["ticker"] = metadata["ticker"].astype(str)

    screen = coverage.merge(metadata, on="ticker", how="left")
    screen = screen.merge(values, on="ticker", how="left")

    numeric_columns = [
        "assets_tl",
        "equity_tl",
        "business_revenue_tl",
        "financial_revenue_tl",
        "net_income_tl",
    ]
    for column in numeric_columns:
        screen[column] = pd.to_numeric(screen[column], errors="coerce")

    financial_sectors = screen["sector_type"].isin(
        ["banks", "par-banks", "insurance"]
    )

    screen["revenue_basis_tl"] = screen["business_revenue_tl"]
    use_financial_revenue = (
        financial_sectors & screen["financial_revenue_tl"].notna()
    )
    screen.loc[use_financial_revenue, "revenue_basis_tl"] = screen.loc[
        use_financial_revenue, "financial_revenue_tl"
    ]

    screen["revenue_basis"] = "Hasılat"
    screen.loc[use_financial_revenue, "revenue_basis"] = (
        "Finans Sektörü Faaliyetleri Hasılatı"
    )

    screen["net_margin_pct"] = (
        screen["net_income_tl"] / screen["revenue_basis_tl"] * 100
    )
    screen.loc[screen["revenue_basis_tl"] == 0, "net_margin_pct"] = pd.NA

    # Bu oran yalnızca genel sektör şirketleri için betimleyici olarak hesaplanır.
    nonfinancial_general = screen["sector_type"] == "general"
    screen["equity_to_assets_pct"] = pd.NA
    valid_assets = nonfinancial_general & screen["assets_tl"].gt(0)
    screen.loc[valid_assets, "equity_to_assets_pct"] = (
        screen.loc[valid_assets, "equity_tl"]
        / screen.loc[valid_assets, "assets_tl"]
        * 100
    )

    screen["net_margin_pct"] = screen["net_margin_pct"].round(2)
    screen["equity_to_assets_pct"] = pd.to_numeric(screen["equity_to_assets_pct"], errors="coerce").round(2)

    output_columns = [
        "ticker",
        "company",
        "status",
        "sector_type",
        "consolidation",
        "kap_company",
        "business_revenue_tl",
        "financial_revenue_tl",
        "revenue_basis",
        "revenue_basis_tl",
        "net_income_tl",
        "net_margin_pct",
        "assets_tl",
        "equity_tl",
        "equity_to_assets_pct",
        "source_file",
    ]
    output_columns = [column for column in output_columns if column in screen.columns]
    screen = screen[output_columns].sort_values(["sector_type", "ticker"])
    screen.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    available_margins = int(screen["net_margin_pct"].notna().sum())
    available_equity_ratios = int(screen["equity_to_assets_pct"].notna().sum())

    sector_summary = (
        screen.dropna(subset=["sector_type"])
        .groupby("sector_type")
        .agg(
            şirket_sayısı=("ticker", "count"),
            marj_verisi=("net_margin_pct", "count"),
            medyan_net_marj_pct=("net_margin_pct", "median"),
        )
        .reset_index()
        .sort_values("sector_type")
    )

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# BIST 100 | Temel finansal tarama",
        "",
        "**Dönem:** 2025 ilk yarı (KAP periyot 2)",
        "**Kapsam:** KAP dosyalarında kaydı bulunan şirketler; PAHOL için bu dönemde kayıt bulunamadı.",
        "",
        "## Bu tarama neyi gösteriyor?",
        "",
        f"- {len(screen)} şirket için kapsam satırı oluşturuldu.",
        f"- {available_margins} şirkette gelir ve net kâr üzerinden net marj hesaplanabildi.",
        f"- {available_equity_ratios} genel sektör şirketinde özkaynak / varlık oranı hesaplandı.",
        "- Banka ve sigorta şirketlerinde, mevcutsa finans sektörü faaliyet hasılatı gelir temeli olarak kullanıldı.",
        "",
        "## Sektör özeti",
        "",
        "| Sektör türü | Şirket sayısı | Net marjı hesaplanan | Medyan net marj (%) |",
        "|---|---:|---:|---:|",
    ]

    for _, row in sector_summary.iterrows():
        median = (
            "—"
            if pd.isna(row["medyan_net_marj_pct"])
            else f'{row["medyan_net_marj_pct"]:.2f}'
        )
        lines.append(
            f'| {row["sector_type"]} | {int(row["şirket_sayısı"])} '
            f'| {int(row["marj_verisi"])} | {median} |'
        )

    lines.extend([
        "",
        "## Yöntem ve sınırlar",
        "",
        "- Net marj = net dönem kârı / uygun gelir kalemi. Finans kuruluşlarında gelir kaleminin kapsamı farklı olabilir; sektörler arasında doğrudan kıyaslanmamalıdır.",
        "- Özkaynak / varlık oranı yalnızca KAP tablosunda `general` olarak sınıflanan şirketler için hesaplandı.",
        "- Veriler 2025 ilk yarısına aittir; tek dönem şirketlerin büyüme eğilimini göstermez.",
        "- Güncel hisse fiyatı, piyasa değeri ve nakit akışı bu veri setinde yoktur. Bu nedenle değerleme veya al/sat sonucu üretmez.",
        "- Bu çıktı genel bilgilendirme amaçlı bir finansal taramadır; yatırım tavsiyesi değildir.",
        "",
        f"Detaylı CSV: `{OUTPUT_FILE.relative_to(PROJECT_DIR)}`",
    ])
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Şirket satırı: {len(screen)}")
    print(f"Net marjı hesaplanan şirket: {available_margins}")
    print(f"CSV: {OUTPUT_FILE}")
    print(f"Rapor: {REPORT_FILE}")


if __name__ == "__main__":
    main()