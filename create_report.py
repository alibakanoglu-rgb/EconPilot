from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

CSV_PATH = DATA / "monthly_macro_comparison.csv"
CPI_CHART = DATA / "tufe_yillik_enflasyon.png"
FX_CHART = DATA / "usdtry_gunluk.png"
COMPARE_CHART = DATA / "tufe_usdtry_indexed.png"
OUTPUT = REPORTS / "econpilot_genel_rapor.docx"

df = pd.read_csv(CSV_PATH, parse_dates=["month"]).sort_values("month")
df = df.dropna(subset=["cpi", "usd_try_monthly_avg"])

if len(df) < 13:
    raise ValueError("Yıllık değişimleri karşılaştırmak için en az 13 aylık veri gerekli.")

first = df.iloc[0]
last = df.iloc[-1]
start_label = first["month"].strftime("%Y-%m")
end_label = last["month"].strftime("%Y-%m")
count = len(df)

cpi_change = (last["cpi"] / first["cpi"] - 1) * 100
fx_change = (
    last["usd_try_monthly_avg"] / first["usd_try_monthly_avg"] - 1
) * 100

cpi_yoy = df.dropna(subset=["cpi_yoy_pct"])
fx_yoy = df.dropna(subset=["usd_try_yoy_pct"])

cpi_yoy_first = cpi_yoy.iloc[0]
cpi_yoy_last = cpi_yoy.iloc[-1]
fx_yoy_first = fx_yoy.iloc[0]
fx_yoy_last = fx_yoy.iloc[-1]

fx_min = fx_yoy["usd_try_yoy_pct"].min()
fx_max = fx_yoy["usd_try_yoy_pct"].max()


def pct(value):
    return f"%{value:.1f}".replace(".", ",")


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run("EconPilot  •  ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    paragraph._p.append(field)


def style_run(run, size=10, bold=False, color=None):
    run.font.name = "Aptos"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Aptos")
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def paragraph(doc, text, size=10, bold=False, color=None, after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.08
    r = p.add_run(text)
    style_run(r, size=size, bold=bold, color=color)
    return p


def heading(doc, text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(5)
    r = p.add_run(text)
    style_run(
        r,
        size=17 if level == 1 else 12,
        bold=True,
        color=(24, 62, 94),
    )
    return p


def add_chart(doc, path, caption):
    if not path.exists():
        paragraph(doc, f"Grafik bulunamadı: {path.name}", color=(150, 60, 50))
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Inches(6.15))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(7)
    style_run(cap.add_run(caption), size=8, color=(90, 90, 90))


doc = Document()
section = doc.sections[0]
section.top_margin = Inches(0.62)
section.bottom_margin = Inches(0.62)
section.left_margin = Inches(0.72)
section.right_margin = Inches(0.72)

normal = doc.styles["Normal"]
normal.font.name = "Aptos"
normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Aptos")
normal.font.size = Pt(10)

footer = section.footer.paragraphs[0]
add_page_number(footer)

# Sayfa 1: Genel bakış
p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(3)
style_run(p.add_run("EconPilot | Ekonomiye genel bakış"), size=22, bold=True,
          color=(24, 62, 94))

paragraph(doc, f"TÜFE ve USD/TRY incelemesi  •  {start_label} – {end_label}",
          size=11, color=(85, 85, 85), after=12)

heading(doc, "Bu rapor neye bakıyor?")
paragraph(
    doc,
    f"Bu rapor, TCMB EVDS’den alınan aylık Türkiye TÜFE endeksi ile günlük "
    f"USD/TRY alış kuru verilerinin aylık ortalamalarını ortak dönem olan "
    f"{start_label}–{end_label} aralığında inceler. Veri setinde {count} "
    f"aylık ortak gözlem bulunuyor. Amaç, iki göstergenin nasıl değiştiğini "
    f"genel okuyucu için anlaşılır biçimde özetlemektir."
)

heading(doc, "Öne çıkan bulgular")
for item in [
    f"Ortak dönemde TÜFE endeksi başlangıca göre {pct(cpi_change)} yükseldi.",
    f"Aynı dönemde aylık ortalama USD/TRY kuru {pct(fx_change)} yükseldi.",
    f"TÜFE yıllık değişimi {cpi_yoy_first['month']:%Y-%m} dönemindeki "
    f"{pct(cpi_yoy_first['cpi_yoy_pct'])} değerinden "
    f"{cpi_yoy_last['month']:%Y-%m} döneminde "
    f"{pct(cpi_yoy_last['cpi_yoy_pct'])} değerine geldi.",
    f"USD/TRY yıllık değişimi son gözlemde "
    f"{pct(fx_yoy_last['usd_try_yoy_pct'])} oldu; gözlenen aralık "
    f"{pct(fx_min)}–{pct(fx_max)} olarak hesaplandı.",
]:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(4)
    style_run(p.add_run(item), size=10)

heading(doc, "Bu bulgular nasıl okunmalı?")
paragraph(
    doc,
    "Endeks düzeyindeki artış, ilgili göstergenin dönem içindeki nominal "
    "değişimini anlatır. TÜFE endeksindeki yükseliş tüketici fiyat düzeyinin "
    "arttığını; USD/TRY kurundaki yükseliş ise bir ABD dolarının daha fazla "
    "Türk lirası karşılığı olduğunu gösterir. Bu iki seri birlikte hareket "
    "edebilir, ancak aynı yönde hareket etmeleri tek başına birinin diğerine "
    "neden olduğunu kanıtlamaz."
)
paragraph(
    doc,
    "Rapor, yalnızca mevcut EVDS serilerini kullanır. Güncel haberleri, şirket "
    "bilançolarını, faiz oranlarını veya yatırımcının kişisel koşullarını "
    "içermediğinden belirli bir hisse için alım ya da satım önerisi sunmaz.",
    size=9, color=(90, 90, 90)
)

# Sayfa 2: TÜFE
doc.add_page_break()
heading(doc, "1. TÜFE: fiyat düzeyindeki değişim")
paragraph(
    doc,
    f"TÜFE endeksi {start_label} ayında {first['cpi']:,.2f} iken "
    f"{end_label} ayında {last['cpi']:,.2f} oldu. Bu, ortak dönem boyunca "
    f"{pct(cpi_change)} artış anlamına geliyor. Endeks, fiyatların belirli "
    f"bir baz döneme göre değişimini izler; tek tek ürünlerin fiyatını "
    f"veya her hanenin yaşadığı enflasyonu doğrudan göstermez."
)
add_chart(doc, CPI_CHART, "Şekil 1. TÜFE yıllık değişimi (EVDS serisi: TP.FG.J0).")
paragraph(
    doc,
    f"Yıllık TÜFE değişimi, bir ayın endeksini 12 ay önceki aynı ayla "
    f"karşılaştırır. Veride bu oran {cpi_yoy_first['month']:%Y-%m} için "
    f"{pct(cpi_yoy_first['cpi_yoy_pct'])}, son gözlem olan "
    f"{cpi_yoy_last['month']:%Y-%m} için "
    f"{pct(cpi_yoy_last['cpi_yoy_pct'])} olarak hesaplandı. Yıllık oranın "
    f"düşmesi, fiyatların genel düzeyinin düştüğü anlamına gelmez; fiyat "
    f"artış hızının önceki yılın aynı ayına kıyasla yavaşlamış olabileceğini "
    f"gösterir."
)
heading(doc, "Gündelik hayata bağlantısı", level=2)
paragraph(
    doc,
    "Endeksin yükselmesi, aynı miktar parayla zaman içinde daha az mal ve "
    "hizmet alınabilmesiyle ilişkilidir. Bunun hane bütçesine etkisi; gelir "
    "artışına, tüketim sepetine ve kişisel harcama kalıplarına göre değişir. "
    "Bu nedenle genel TÜFE oranı, her bireyin kişisel enflasyon oranıyla "
    "birebir aynı olmayabilir."
)

# Sayfa 3: Kur
doc.add_page_break()
heading(doc, "2. USD/TRY: kurdaki değişim")
paragraph(
    doc,
    f"EVDS günlük USD/TRY alış kuru gözlemlerinin aylık ortalaması "
    f"{start_label} ayında {first['usd_try_monthly_avg']:.2f}, "
    f"{end_label} ayında {last['usd_try_monthly_avg']:.2f} oldu. Bu ölçüme "
    f"göre kur ortak dönemde {pct(fx_change)} yükseldi. Kurun yükselmesi, "
    f"doların Türk lirası cinsinden fiyatının arttığını ifade eder."
)
add_chart(doc, FX_CHART, "Şekil 2. EVDS günlük USD/TRY alış kuru.")
paragraph(
    doc,
    f"Yıllık kur değişimi, aylık ortalama kurun 12 ay önceki değerine göre "
    f"değişimini gösterir. Hesaplanan oran {fx_yoy_first['month']:%Y-%m} "
    f"ayında {pct(fx_yoy_first['usd_try_yoy_pct'])}, "
    f"{fx_yoy_last['month']:%Y-%m} ayında "
    f"{pct(fx_yoy_last['usd_try_yoy_pct'])} oldu. Dönem içindeki yıllık "
    f"değişim oranları {pct(fx_min)} ile {pct(fx_max)} arasında seyretti."
)
heading(doc, "Kur artışı neden izlenir?", level=2)
paragraph(
    doc,
    "Döviz kuru; ithal ürünlerin, enerji ve ara mallarının TL maliyetini "
    "etkileyebilecek göstergelerden biridir. Ancak kur hareketlerinin "
    "tüketici fiyatlarına ne ölçüde ve ne hızla yansıyacağı; şirketlerin "
    "maliyet yapısı, fiyatlama davranışı, talep koşulları ve diğer ekonomik "
    "etkenlere bağlıdır. Bu rapor bu aktarımın büyüklüğünü ölçmüyor."
)

# Sayfa 4: Birlikte değerlendirme
doc.add_page_break()
heading(doc, "3. İki göstergeyi birlikte değerlendirmek")
paragraph(
    doc,
    f"Başlangıç ayı 100 kabul edilerek hazırlanan karşılaştırma grafiği, "
    f"TÜFE ve kurun ortak dönemdeki göreli hareketini gösterir. Dönem sonunda "
    f"TÜFE endeksi başlangıca kıyasla {pct(cpi_change)}, aylık ortalama "
    f"USD/TRY ise {pct(fx_change)} daha yüksek seviyedeydi."
)
add_chart(doc, COMPARE_CHART, "Şekil 3. TÜFE ve USD/TRY, ortak dönemin ilk ayı = 100.")
paragraph(
    doc,
    "Bu karşılaştırma tanımlayıcıdır. İki seri aynı dönemde yükselse bile "
    "bu durum nedensellik kanıtı değildir. Enflasyon ve kur; para politikası, "
    "beklentiler, üretim maliyetleri, dış ticaret ve küresel koşullar gibi "
    "bu raporda incelenmeyen değişkenlerle de bağlantılı olabilir."
)
heading(doc, "Borsa açısından genel çerçeve", level=2)
paragraph(
    doc,
    "Yüksek enflasyon ve kur oynaklığı, şirketleri değerlendirirken maliyet "
    "yapısı, fiyatlama gücü, borçların para birimi, döviz gelirleri ve işletme "
    "sermayesi gibi başlıkların önemini artırabilir. Etki şirketten şirkete "
    "değişir: döviz geliri olan bir işletme ile döviz cinsi borcu yüksek bir "
    "işletme aynı kur hareketinden aynı şekilde etkilenmeyebilir."
)
paragraph(
    doc,
    "Bu veri seti tek başına borsanın yönünü veya belirli bir hissenin "
    "getirisini tahmin etmeye yetmez. Şirket finansalları, değerleme, faiz "
    "oranları, piyasa fiyatları ve yatırımcının risk profili incelenmeden "
    "alım-satım kararı çıkarılmamalıdır. Buradaki değerlendirme genel "
    "bilgilendirme amaçlıdır; yatırım tavsiyesi değildir.",
    size=9, color=(90, 90, 90)
)
heading(doc, "Yöntem, kaynak ve sınırlılıklar", level=2)
paragraph(
    doc,
    "Kaynak: Türkiye Cumhuriyet Merkez Bankası Elektronik Veri Dağıtım "
    "Sistemi (EVDS). TÜFE serisi TP.FG.J0; kur serisi TP.DK.USD.A.YTL "
    "günlük alış kuru. Kur, ortak karşılaştırma için aylık ortalamaya "
    "dönüştürülmüştür. Endeksli grafik, iki serinin ortak döneminin ilk "
    "ayını 100 kabul eder."
)
paragraph(
    doc,
    f"Analiz {start_label}–{end_label} dönemindeki {count} aylık ortak "
    f"gözlemle sınırlıdır. Yıllık değişim için ilk 12 ayda karşılaştırma "
    f"gözlemi bulunmaz. Veriler sonradan revize edilebilir. Çalışma, "
    f"korelasyon veya nedensellik testi yapmaz; geleceğe yönelik tahmin "
    f"üretmez."
)

doc.save(OUTPUT)
print(f"Word raporu oluşturuldu: {OUTPUT}")