# Zamanlama, stop ve lot motoru

Tek terminalde seans görüntüsü ve geçmiş karşılaştırma:

```powershell
.\.venv\Scripts\python.exe -X utf8 .\execution_trigger.py --with-backtest
```

Gerçek pozisyon girişi ve bilinen zirve varsa açıkça kaydet:

```powershell
.\.venv\Scripts\python.exe -X utf8 .\execution_trigger.py --entry TUPRS=390 --peak TUPRS=410
```

Bu örnek fiyatlar mevcut pozisyon iddiası değildir. Kayıt `data/market/execution_positions.json` içinde saklanır; sonraki çalıştırmalarda görülen zirve korunur ve stop aşağı indirilmez. Pozisyon kapandıysa `--close-position TUPRS` yerel kaydı kaldırır; aracı kuruma emir göndermez. Kaydedilmiş giriş başka pozisyona taşınmaz.

Pozisyon bildirilmemişse çıktıda gerçek iz süren stop yerine yeni giriş için varsayımsal yüzde 5 stop ve lot kapasitesi gösterilir. AL_AKTİF yoksa teyitli yeni giriş lotu sıfırdır. Varsayılan sermaye 100.000 TL, işlem risk bütçesi yüzde 2, komisyon her işlem tarafında yüzde 0,2'dir. Lot kapasitesi boşluk/kayma zararını sınırlamaz; toplam portföy riski ayrıca yönetilmelidir.

Günlük SMA5 kapanış teyidi gelecekteki günlük kapanışa bağlıdır; seans içi anlık teyit sayılmaz. Sonraki kritik fiyat son dört kapanış ortalamasıdır; önceki kapanış zaten ortalamanın üstündeyse ertesi gün yeni yukarı kesişim mümkün değildir.

Backtestte bugünkü temel hedefler ve ayrı aylık fiyat vekili karşılaştırılır. Fiyat vekili yalnız önceki 63 kapanış ortalamasının 1,05/1,25 katıdır; tarihi bilanço veya adil değer değildir. Temel hedeflerin geçmiş bilgiyle yeniden kurulması `needs_source` kalır. Bugünkü hedefler look-ahead bias taşır. İz süren backtest günlük kapanış zirvesini izler ve stop ihlalini izleyen kapanışta uygular; seans içi emir, likidite ve kayma yoktur.

## Neden Önemli?

Bu parçalar fiyat teyidini, pozisyon riskini ve geçmiş değerlendirmeyi aynı kurallarla izler. Giriş kaydı, zirve ve bilgi kesim tarihleri saklanarak varsayımlar gerçek işlem veya doğrulanmış temel veri gibi sunulmaz.
## Plan geçerliliği ve karar kaydı

Her plan yalnız yazılı işlem gününe aittir; operasyonel son geçerlilik 19:00 İstanbul saati. Seans içinde bugünkü plan, bu kesimden sonra sonraki hafta içi plan hazırlanır. Resmi tatil/özel seans takvimi otomatik doğrulanmadı. Gerekli önceki hafta içi kapanışı yoksa NO_ORDER kalır.

Teknik aday ancak planın fiyat kaydıyla aynı bugünkü tarihe ait olması ve fiyatın tetik–azami limit bandında kalmasıyla AL_AKTİF olabilir. Broker fiyatı ve emir koşulları ayrıca doğrulanmalıdır. Ekrandaki stop, resmi pay fiyat adımına yukarı yuvarlanır; risk hesabı aynı yuvarlanmış seviyeyi kullanır.

`data/market/execution_decision_journal.jsonl` her çalıştırmanın kararını tutar. `reports/execution_runs/` tarihli plan ve JSON görüntülerini saklar. `reports/order_sheet.md` son planı gösterir. Bu kayıtlar yalnız gözlem/plan arşividir; aracı kurum emri veya gerçekleşmiş işlem değildir.
## İleriye dönük kâğıt işlem kaydı

```powershell
.\.venv\Scripts\python.exe -X utf8 .\execution_trigger.py --paper
```

Her çağrı bir güncel görüntü işler; seans boyunca arka plan izleme değildir. `--with-backtest` eklenirse geçmiş karşılaştırma da aynı terminale basılır, fakat kâğıt hesabın içine geçmiş sonuç eklenmez.

Kâğıt hesap `data/market/paper_trading_state.json`, özeti `reports/paper_trading_summary.md` içindedir. Gerçek emir göndermez. İlk uygun gözlem aday kurar; sonraki farklı ve güncel bar şartlar sürerse varsayımsal giriş sağlar. Aynı/eskimiş bar tekrar işlem oluşturmaz. İki hisse ortak örnek sermaye ve risk tavanını paylaşır. Varsayımsal pozisyonlara gözlenen zirve stopu ve girişte sabitlenen kâr al uygulanır; güncel hedef/kod değişirse bekleyen aday iptal edilir.

Bu sürüm temettü, bölünme, seans arasında kaçırılan zirveler, gerçek broker dolumu ve kaymayı modellemez. Kayıt yalnız program çalıştırıldığında alınan gözlemlerin fiyat ve komisyon simülasyonudur; toplam yatırım getirisi veya strateji kârlılığı kanıtı değildir.
## Terminalden seans boyunca izleme

```powershell
.\.venv\Scripts\python.exe -X utf8 .\watch_session.py --watch
```

Varsayılan operasyonel pencere hafta içi 10:05–17:55 İstanbul saati; resmî tatil ve özel seans takvimi değildir. Ana döngü fiyat ve plan görüntüsünü alır; tamamlandıktan sonra 300 saniye bekler. Kâğıt hesaba aktarım için her satırda feed_latency_verified=true gerekir. Mevcut Yahoo akışı bu doğrulamayı sağlamaz; feed_latency_not_verified durumunda fiyat gözlemi sürer, hesap işlenmez. Bu ek kapı watch_session.py içindedir; execution_trigger.py --paper komutunu doğrudan çalıştırmak aynı ek kapıyı uygulamaz. Terminal açık kalmalıdır; Ctrl+C durdurur. Pencere dışında başlatılırsa veri çekmeden çıkar; ertesi gün kendiliğinden başlamaz. Pencere dışında bekleyip sabah uyanan bir görev veya Windows zamanlanmış görev kurulmadı.

Sınırlı gözlem sayısı gerekiyorsa:

```powershell
.\.venv\Scripts\python.exe -X utf8 .\watch_session.py --watch --max-cycles 6
```

Tek gözlem için --watch kullanma. Döngü aralığı --interval ile değiştirilebilir; en az 60 saniye. Gerçek emir gönderilmez. Son durum reports/session_watch_summary.md ve reports/session_watch_status.json içinde tutulur. Üç ardışık çalıştırma hatasında durur; tek süreç kilidi eşzamanlı izleyicileri engeller. Fiyat servisinin gecikmesi veya eski veriyle dönen başarılı komut işlem sinyali garantisi değildir; kâğıt hesap kendi veri denetimini uygular.

Kâğıt mod gerçek pozisyon kayıt seçenekleriyle birlikte kullanılmaz ve execution_positions.json dosyasını değiştirmez. Süresi geçmiş bekleyen kâğıt adaylar yeni bar gelmese bile kayıt zinciri yeniden çalıştırıldığında iptal edilir; program çalışmıyorken otomatik iptal yapıldığı iddia edilmez.
## Risk kontrolleri ve dondurulmuş ileri deney

Risk senaryoları (sentetik veriler; gerçek veya kâğıt hesap değişmez):

```powershell
.\.venv\Scripts\python.exe -X utf8 .\check_risk_rules.py
```

15 kontrol: eski/tekrar/gelecek/zamansız/eksik bar, alım bandı, sıçrama, plan süresi, komisyonlu lot kapasitesi, ortak risk tavanı ve stop davranışı. Son sonuç `reports/risk_checks.md` içindedir. Bunlar risk yardımcı işlevlerini doğrular; broker dolumunu veya tüm entegrasyon/kurumsal işlem durumlarını doğrulamaz.

`data/market/paper_strategy_baseline.json` ileri deneyin hedef eşiklerini, sermayesini, risk ve komisyon parametrelerini, kural kodu özetlerini sabitler. Bunlardan biri değişirse aynı kâğıt deney sessizce devam etmez. Eski hesap ve başlangıç dosyası silinmez; yeni deney ayrı ve açık biçimde tanımlanmalıdır. Sonuçlara bakarak en iyi kural otomatik seçilmez.

Backtest artık yalnız pullback ile pullback veya üç kapanış kırılımını, iki stop ve iki hedef modeli altında karşılaştırır: iki hisse toplam 16 sonuç. Günlük kapanış modeli canlı beş dakikalık limit bandı ve ortak yüzde 2 riskli portföyün tam karşılığı değildir. Sinyal hedefi girişte sabitlenir; sonraki gün alım bölgesi dışına sıçrarsa giriş iptal edilir. Önceki rapor/tablolar reports/backtest_runs/ altında güncelleme öncesi arşivlenmiştir.
## İleri gözlem değerlendirmesi

`reports/forward_review.md` kaç benzersiz güncel bar, kaç gözlem günü ve kaç kapanan kâğıt işlem olduğunu gösterir. Seans izleyicisi başarılı gözlemden sonra ve ana run.ps1 zinciri kâğıt hesaptan sonra günceller. Tek başına şu komutla da üretilebilir:

```powershell
.\.venv\Scripts\python.exe -X utf8 .\build_forward_review.py
```

Raporda 20 gün/20 kapanan işlem yalnız örnek betimleyici inceleme eşiğidir; istatistiksel güven veya kârlılık onayı değildir. Dondurma öncesi görüntüler hariç tutulur, tekrar barlar yeni gözlem sayılmaz. Bu rapor stratejiyi ve hesabı değiştirmez. Dondurulmuş çekirdek kod bu aşamada değiştirilmedi; yalnız ayrı okuma/raporlama katmanı ve onu çağıran çalıştırıcılar güncellendi.

## 98 hisselik arka plan tarayıcısı

`watch_bist100_session.py --watch` kayıtlı BIST evreninden TUPRS ve CCOLA'yı çıkarır. Ayrı süreç ve kilitle, 900 saniyede bir en fazla iki eşzamanlı indirmeyle onarlı grupları tarar. yfinance toplu çağrısı sağlayıcı tarafında tek HTTP isteği anlamına gelmez. Önceki günlük kapanışlar gün başına önbelleğe alınır. Pencere 10:05–17:55'tir; terminal/bilgisayar kapandıktan sonra kendiliğinden başlamaz.

Son tarama `data/market/bist100_session_latest.csv` dosyasına UTF-8 BOM, virgül ayracı, nokta ondalık ayracı ve indeks olmadan yazılır. Sütun sırası kesin olarak:

```csv
symbol,price,change_pct,volume,timestamp
```

- symbol: BIST kısa kodu.
- price: son tamamlanmış beş dakikalık barın fiyatı.
- change_pct: Yahoo önceki mevcut günlük kapanışına göre yüzde değişim.
- volume: son veri gününün indirilen tamamlanmış barlarının toplam hacmi; eksiksiz seans hacmi garanti edilmez.
- timestamp: fiyat barının İstanbul saat dilimli zamanı; sorgu zamanı değildir.

Eksik veriler boş kalır. Ayrıntılı veri zamanı, durum, hata ve referans kapanış alanları `data/market/session_observations/bist100_YYYY-MM-DD.jsonl` içinde korunur. Tekrarlanan barlar ayrı gözlem kaydıdır; yeni fiyat barı veya işlem sayılmaz. Tarayıcı hedef değer, emir ya da kâğıt hesap işlemi oluşturmaz.

Tek seferlik tarama için `--watch` kullanmayın. Çalışan tarayıcıyla çakışan süreç kilit nedeniyle reddedilir. `--initial-delay 900`, tek seferlik tarama sonrasında yeniden başlatılan izleyicinin hemen ikinci ağ çağrısını yapmasını önler.

Bu CSV'nin sabit şeması, PowerShell ve diğer okuyucuların alanları aynı isimlerle bulmasını sağlar. Ayrıntılı günlük log, son tablo yenilense de gözlem geçmişini korur.
