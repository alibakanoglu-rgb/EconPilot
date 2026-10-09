# BIST 100 | Temel finansal tarama

**Dönem:** 2025 ilk yarı (KAP periyot 2)
**Kapsam:** KAP dosyalarında kaydı bulunan şirketler; PAHOL için bu dönemde kayıt bulunamadı.

## Bu tarama neyi gösteriyor?

- 100 şirket için kapsam satırı oluşturuldu.
- 86 şirkette gelir ve net kâr üzerinden net marj hesaplanabildi.
- 81 genel sektör şirketinde özkaynak / varlık oranı hesaplandı.
- Banka ve sigorta şirketlerinde, mevcutsa finans sektörü faaliyet hasılatı gelir temeli olarak kullanıldı.

## Sektör özeti

| Sektör türü | Şirket sayısı | Net marjı hesaplanan | Medyan net marj (%) |
|---|---:|---:|---:|
| banks | 7 | 0 | — |
| general | 81 | 79 | 5.78 |
| holding | 7 | 7 | 1.22 |
| insurance | 3 | 0 | — |
| par-banks | 1 | 0 | — |

## Yöntem ve sınırlar

- Net marj = net dönem kârı / uygun gelir kalemi. Finans kuruluşlarında gelir kaleminin kapsamı farklı olabilir; sektörler arasında doğrudan kıyaslanmamalıdır.
- Özkaynak / varlık oranı yalnızca KAP tablosunda `general` olarak sınıflanan şirketler için hesaplandı.
- Veriler 2025 ilk yarısına aittir; tek dönem şirketlerin büyüme eğilimini göstermez.
- Güncel hisse fiyatı, piyasa değeri ve nakit akışı bu veri setinde yoktur. Bu nedenle değerleme veya al/sat sonucu üretmez.
- Bu çıktı genel bilgilendirme amaçlı bir finansal taramadır; yatırım tavsiyesi değildir.

Detaylı CSV: `data\kap\processed\bist100_basic_metrics_2025_h1.csv`
