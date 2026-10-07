\# EconPilot



EconPilot'un ilk sürümü, TCMB EVDS'den Türkiye TÜFE endeksini ve USD/TRY alış kurunu indirir. TÜFE için yıllık değişimi hesaplar; verileri CSV ve grafikleri PNG olarak kaydeder.



\## Gereksinimler



\- Python 3.14

\- EVDS API anahtarı



\## Kurulum



Sanal ortamı oluştur: `py -3.14 -m venv .venv`



Paketleri yükle: `.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt`



Proje klasöründe `.env` dosyası oluştur ve içine `EVDS\_API\_KEY=anahtarını\_buraya\_yaz` satırını ekle. API anahtarını GitHub'a gönderme.



\## TÜFE verisini indirme



`.\\.venv\\Scripts\\python.exe .\\fetch\_evds.py`



CSV dosyası `data/tufe.csv`, grafik `data/tufe\_yillik\_enflasyon.png` konumuna kaydedilir.



\## USD/TRY alış kurunu indirme



`.\\.venv\\Scripts\\python.exe .\\fetch\_usdtry.py`



CSV dosyası `data/usdtry.csv`, grafik `data/usdtry\_gunluk.png` konumuna kaydedilir.
## TÜFE ve USD/TRY karşılaştırması



`analyze\_macro.py`, günlük USD/TRY alış kurunu aylık ortalamaya çevirir ve TÜFE ile ortak aylar üzerinden karşılaştırır. Grafikte her seri ortak dönemin ilk ayında 100 olacak şekilde endekslenir. Bu grafik birlikte hareketi gösterir; tek başına nedensellik kanıtlamaz.



Çalıştırma: `.\\.venv\\Scripts\\python.exe .\\analyze\_macro.py`



Çıktılar `data/monthly\_macro\_comparison.csv` ve `data/tufe\_usdtry\_indexed.png` dosyalarına kaydedilir.
## Tüm veri hattını tek komutla çalıştırma

`run_pipeline.py`, TÜFE ve USD/TRY verilerini indirir, ardından aylık karşılaştırmayı üretir.

Çalıştırma: `.\.venv\Scripts\python.exe .\run_pipeline.py`

