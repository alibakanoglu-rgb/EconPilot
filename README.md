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

