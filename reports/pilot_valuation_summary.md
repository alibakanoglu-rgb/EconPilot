# EconPilot — TUPRS ve CCOLA hisse başına değerleme aralıkları

**Bu rapor varsayımsal değerleme bandıdır; doğrulanmış adil değer, hedef fiyat tahmini veya beklenen getiri değildir.**
Yeni veri kaynağı kullanılmadı. 45 açık kaynak kaydı değişmedi; sayısı azalmadı. Mevcut H2 kâr/finansman duyarlılıkları alt–üst bant olarak donduruldu; eksik nakit takvimine rakam uydurulmadı.

## Üç senaryo — kâr çarpanı yöntemi

| Şirket | Senaryo | Son kayıtlı fiyat / tarih | Alt değer | Referans değer | Üst değer | Alt–üst fiyat farkı | Referans fiyat farkı | Referans güvenlik marjı |
|---|---|---|---:|---:|---:|---:|---:|---:|
| TUPRS | Baskı | 386.25 TL / 2026-10-09 | 286.82 TL | 463.77 TL | 772.95 TL | %-25.7 – %100.1 | %20.1 | %16.7 |
| TUPRS | Referans | 386.25 TL / 2026-10-09 | 398.41 TL | 631.16 TL | 1051.93 TL | %3.1 – %172.3 | %63.4 | %38.8 |
| TUPRS | İyileşme | 386.25 TL / 2026-10-09 | 426.30 TL | 672.99 TL | 1121.65 TL | %10.4 – %190.4 | %74.2 | %42.6 |
| CCOLA | Baskı | 83.75 TL / 2026-10-09 | 50.02 TL | 80.67 TL | 165.55 TL | %-40.3 – %97.7 | %-3.7 | %-3.8 |
| CCOLA | Referans | 83.75 TL / 2026-10-09 | 61.66 TL | 98.13 TL | 194.66 TL | %-26.4 – %132.4 | %17.2 | %14.7 |
| CCOLA | İyileşme | 83.75 TL / 2026-10-09 | 63.34 TL | 100.66 TL | 198.87 TL | %-24.4 – %137.5 | %20.2 | %16.8 |

### Formüller ve kapsam

- H2 ana ortaklık kârı yaklaşımı = H2 grup duyarlılığı × H1 ana ortaklık/grup kâr oranı. Bu oran gelecek dönem için doğrulanmadı.
- Yıllık ana ortaklık kârı yaklaşımı = gerçekleşen H1 ana ortaklık kârı + koşullu H2 yaklaşımı. Sürdürülebilir ileri 12 aylık kâr değildir.
- Hisse değeri = yıllık kâr yaklaşımı × F/K ÷ çıkarılmış hisse adedi. Alt F/K 8, referans 12, üst 20; mevcut örnek politika kullanıldı, sektör çarpanı olarak doğrulanmadı.
- Alt/üst H2 grup kârı: mevcut üç finansman/parasal durum ile üç borç faiz şokunun en düşük/en yüksek sonucu. Referans: parasal etkisi çıkarılan durum. Bunlar bütün riskleri sınırlayan istatistiksel bantlar değildir.
- Fiyat farkı / upside = (model değeri ÷ piyasa fiyatı − 1) × 100.
- Güvenlik marjı / iskonto = (1 − piyasa fiyatı ÷ model değeri) × 100. İki yüzdenin paydaları farklıdır; aynı gösterge değildir.
- Haziran para bazı Eylül TÜFE ile 1.05569659 katsayısıyla taşındı. Ekim kayıtlı fiyatıyla aynı satın alma gücü tarihi değildir; Ekim enflasyonu varsayılmadı.
- Fiyatlar dosyadaki son kapanışlardır; anlık veri çekilmedi. Çıkarılmış sermaye / 1 TL lot eşdeğeri kullanıldı; geri alınmış payların dışarıdaki adet etkisi doğrulanmadı.

## Net borç düşülen firma değeri yöntemi — ayrı duyarlılık

| Şirket | Senaryo | Alt değer | Referans değer | Üst değer |
|---|---|---:|---:|---:|
| TUPRS | Baskı | 226.28 TL | 405.65 TL | 494.85 TL |
| TUPRS | Referans | 338.83 TL | 555.71 TL | 682.42 TL |
| TUPRS | İyileşme | 366.95 TL | 593.21 TL | 729.29 TL |
| CCOLA | Baskı | 40.35 TL | 73.26 TL | 95.64 TL |
| CCOLA | Referans | 52.15 TL | 88.99 TL | 115.30 TL |
| CCOLA | İyileşme | 53.85 TL | 91.27 TL | 118.14 TL |

Firma değeri = (H1 faaliyet kârı + koşullu H2 faaliyet kârı) × örnek FD/Faaliyet kârı çarpanı. Hisse değeri = (firma değeri − net borç − azınlık payı yaklaşımı) ÷ çıkarılmış hisse adedi; ardından Eylül para bazına taşıma.
Çarpanlar 6/8/10 açık örnek varsayımdır; mevcut F/K çarpanıyla aynı ölçü değildir. Net borç bandında nakit kredisi sıfır ile nakit akışı kapanış bakiyesi arasında değişir. Azınlık payına H1 defter özkaynağı yaklaşımı uygulanır; piyasa değeri değildir. Kiralama borcu toplam borçta yer alır; işletme kârı/kiralama yöntemi tam kalibre edilmedi.
F/K yöntemi doğrudan özkaynak değeri üretir; oradan net borç tekrar düşülmez. Firma değeri ve F/K yöntemleri harmanlanıp tek kesin değer sayılmaz.

## Nakit risk bandı

| Şirket | H1 ticari borç katkısı duyarlılığında CFO − seçili yatırım, alt–üst | H2 tam serbest nakit |
|---|---:|---|
| TUPRS | 35.367 – 120.508 milyar TL | needs_source |
| CCOLA | -6.763 – 5.436 milyar TL | needs_source |

Bu H1 karşı olgusal bant H2 serbest nakit akışı değildir. DCF, terminal değer veya nakit çarpanı kurulmadı. H2 nakit modelindeki boş sonuçlar değerleme girdisi yapılmadı.

## Alım–satım karar katmanının durumu

Model fiyat farkları bir değerleme hipotezidir. Kaynak eksikleri, gelecek vergi/finansman varsayımları, pay kapsamı, yöntem kalibrasyonu ve geçmiş strateji ölçümü tamamlanmadığı için işlem sinyali `needs_validation` kalır. Pozitif fiyat farkı AL, negatif fark SAT emri değildir. Stop seviyesi veya anlık tetik bu raporun kapsamında değildir.

## Neden Önemli?

Bu parça kâr duyarlılığını hisse fiyatı cinsine çevirir; borcun iki kez düşülmesini ve iskonto ile upside yüzdelerinin karıştırılmasını önler. Varsayımlar ayrıca JSON dosyasında ve kullanılan girdiler manifestte kaydedilir.
