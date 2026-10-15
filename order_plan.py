"""Conditional worksheet, rounded to published BIST equity price steps; no orders."""
from datetime import datetime, timedelta, time
from pathlib import Path
import json
import math
from timing_rules import previous_weekday

ROOT=Path(__file__).resolve().parent
TICK_SOURCE='https://www.borsaistanbul.com/piyasalar/pay-piyasasi/piyasa-isleyisi'


def tick(price):
    for upper,step in [(20,.01),(50,.02),(100,.05),(250,.10),(500,.25),(1000,.50),(2500,1)]:
        if price < upper:
            return step
    return 2.5


def round_price(price, strictly_above=False):
    step=tick(price)
    units=math.floor(price/step+1e-8)+1 if strictly_above else math.ceil(price/step-1e-8)
    rounded=round(units*step,2)
    if tick(rounded)!=step:
        step=tick(rounded)
        rounded=round(math.ceil(rounded/step-1e-8)*step,2)
    return rounded


def make_plan(ticker,history,targets,capital,risk_fraction,now,position_registered):
    if len(history)<5:
        raise ValueError('Order worksheet needs five completed closes')
    planned_day=now.date() if now.time() < time(19) else now.date()+timedelta(days=1)
    while planned_day.weekday()>4:
        planned_day+=timedelta(days=1)
    # Same-day plans read only the preceding completed session; no future closes.
    history=[r for r in history if r['date'] < planned_day.isoformat()]
    if len(history)<5:
        raise ValueError('Missing prior closes for plan date')
    last_five=[float(r['close']) for r in history[-5:]]
    sma_critical=sum(last_five[-4:])/4
    previous_sma=sum(last_five)/5
    breakout=max(last_five[-3:])
    pullback_possible=last_five[-1]<=previous_sma
    threshold=sma_critical if pullback_possible else max(sma_critical,breakout)
    trigger=round_price(threshold,True)
    entry_mode='pullback' if pullback_possible and sma_critical<breakout else 'breakout'
    ceiling=round_price(trigger+2*tick(trigger))
    pressure,reference=targets['Baskı'],targets['Referans']
    valid=trigger<pressure and ceiling<pressure and reference>ceiling and not position_registered
    blockers=[]
    if not trigger<pressure or not ceiling<pressure:
        blockers.append('timing_outside_buy_region')
    if not reference>ceiling:
        blockers.append('target_below_entry_limit')
    if position_registered:
        blockers.append('position_already_registered')
    stop=round_price(ceiling*.95)
    take=round_price(reference,True)
    risk_per_lot=ceiling-stop+.002*(ceiling+stop)
    lots=min(math.floor(capital*risk_fraction/risk_per_lot),math.floor(capital/(ceiling*1.002))) if valid and risk_per_lot>0 else 0
    required_anchor=previous_weekday(planned_day).isoformat()
    if history[-1]['date']!=required_anchor:
        blockers.append('missing_previous_session_close_calendar_unverified')
        valid=False;lots=0
    return dict(ticker=ticker,planned_date=planned_day.isoformat(),expires_at=planned_day.isoformat()+'T19:00:00+03:00',
        check_time='10:00 Europe/Istanbul' if planned_day!=now.date() or now.time()<time(10) else 'current_session_recheck',
        exchange_calendar_verified=False,anchor_date=history[-1]['date'],
        required_anchor_date=required_anchor,blockers=blockers,
        entry_mode=entry_mode,plan_status='conditional_plan' if valid else 'NO_ORDER',
        mathematical_trigger_threshold=threshold,trigger_tl=trigger,buy_limit_ceiling_tl=ceiling,
        cancel_unfilled_at_or_below_tl=threshold, pressure_threshold_tl=pressure,
        stop_trigger_if_filled_at_ceiling_tl=stop,take_profit_limit_tl=take,
        lot_cap=lots,risk_budget_tl=capital*risk_fraction,planned_risk_including_commission_tl=lots*risk_per_lot,
        registered_position=position_registered,
        requirements='fresh broker quote; completed 5m confirmation; signal remains in buy region; verify exchange session and broker conditional order support',
        order_type='conditional buy stop-limit plan; not an ordinary resting buy limit',
        ready_for_submission=False,broker_execution_verified=False,order_submitted=False,
        tick_source=TICK_SOURCE)


def publish_sheet(plans,now):
    lines=['# EconPilot — şartlı emir çalışma sayfası','',
        f"**Üretim:** {now.isoformat()}. Varsayımsal değerleme ve örnek risk kuralları; emir gönderilmedi.",
        '', '| Hisse | Plan günü / kontrol | Durum | Tetik | Azami alış limiti | Lot üst sınırı | Dolum bekleyen emri iptal | Başlangıç stop tetiği | Kâr al limiti |',
        '|---|---|---|---:|---:|---:|---|---:|---:|']
    print('\n=== ŞARTLI EMİR ÇALIŞMA SAYFASI ===')
    for p in plans:
        print(f"{p['ticker']} | {p['planned_date']} {p['check_time']} | {p['plan_status']} / {p['entry_mode']}")
        print(f"  Gerekli kapanış: {p['required_anchor_date']} | Kaynak kapanış: {p['anchor_date']} | Son geçerlilik: {p['expires_at']}")
        print(f"  Tetik >= {p['trigger_tl']:.2f} | Azami alış limiti {p['buy_limit_ceiling_tl']:.2f} | Lot üst sınırı {p['lot_cap']}")
        print(f"  Dolumdan önce fiyat <= {p['cancel_unfilled_at_or_below_tl']:.6f} veya > {p['buy_limit_ceiling_tl']:.2f}: ALIŞ İPTAL / PUSU")
        print(f"  Dolum {p['buy_limit_ceiling_tl']:.2f} ise stop {p['stop_trigger_if_filled_at_ceiling_tl']:.2f} | Kâr al {p['take_profit_limit_tl']:.2f} | Komisyon dahil plan risk {p['planned_risk_including_commission_tl']:.2f} TL")
        if not p['lot_cap']:
            print('  EMİR YOK: '+', '.join(p['blockers']))
        lines.append(f"| {p['ticker']} | {p['planned_date']} / {p['check_time']} | {p['plan_status']} ({p['entry_mode']}) | {p['trigger_tl']:.2f} | {p['buy_limit_ceiling_tl']:.2f} | {p['lot_cap']} | ≤{p['cancel_unfilled_at_or_below_tl']:.6f} veya >{p['buy_limit_ceiling_tl']:.2f} | {p['stop_trigger_if_filled_at_ceiling_tl']:.2f} | {p['take_profit_limit_tl']:.2f} |")
    lines+=['','## Kontrol sırası','',
        '1. Saat 19:00 öncesi bugünkü hafta içi seansı, sonrası sonraki hafta içi için plan hazırlanır. Saat kesimi operasyonel varsayımdır; resmi takvim değildir. Önceki hafta içinin tamamlanmış kapanışı eksikse NO_ORDER; tatil/özel seans takvimi doğrulanmadığı için tatil günlerinde otomatik açılmaz.',
        '1a. Plan yalnız yazılı tarihinde, operasyonel 19:00 kesimine kadar kontrol içindir. Eski order_sheet.md seviyeleri yeniden kullanılmaz; komutla yenilenir. Güncel broker fiyatı plan şartları ve geçerlilikle tekrar değerlendirilir.',
        '2. Tetik temasına anında piyasa emri verilmez. Tamamlanan 5 dakikalık barın tetik üstünde olması, SMA5 teyidi ve güncel aracı kurum fiyatının limit bandında kalması gerekir. Yahoo gecikmesi doğrulanmış anlık veri değildir.',
        '3. Tetik üstüne sıçrayıp azami limit aşılırsa kovalanmaz. Normal alış limitini tetikten önce girme: kırılım beklenirken aşağı fiyatlarda dolabilir. Koşullu stop-limit desteği aracı kurumda doğrulanmadan plan emir sayılmaz.',
        '4. Bekleyen giriş iptali yalnız dolum öncesine aittir. Pozisyon açılınca gerçek dolum fiyatını --entry ile kaydet; başlangıç stopunu gerçek dolumun yüzde 95 seviyesine fiyat adımıyla yukarı yuvarla. Stop sonra izlenen zirveyle yalnız yukarı gider.',
        '5. Kâr al ve stop birbirinin alternatifi; OCO/braket desteği yoksa bir çıkış gerçekleştiğinde diğerini iptal et. Burada broker entegrasyonu, otomatik emir/iptal veya seans boyu izleme yapılmaz.',
        '6. Lot azami giriş limitine ve her tarafta yüzde 0,2 komisyona göre hesaplanır; önceki fiyatın 96 lotu sabit taşınmaz. Boşluk/kayma kaybı 2.000 TL üzerine çıkarabilir. Sermaye iki hisseye aynı anda tam tahsis edilemez.',
        '', '## Kaynak ve model kapsamı','',
        f'Fiyat adımları: [Borsa İstanbul resmi pay tablosu]({TICK_SOURCE}). Standart pay adımları kullanıldı; günlük taban/tavan ve hisseye özel tedbirler broker ekranından doğrulanmalıdır.',
        'Önceki günlük SMA5 kesişim backtestinin sayıları yeni seans içi kırılım kuralının ölçülmüş başarısı sayılmaz. Hacimli teyit eklenmedi; tamamlanan barın fiyat kırılımı kullanılır.',
        '', '## Neden Önemli?','',
        'Bu parça tetik ile emir limitini ayırır, gerçek giriş riskine göre lotu hesaplar ve dolum öncesi iptal ile pozisyon stopunu karıştırmayı önler.','']
    lines += ['', '## Veri geçerliliği', '']
    for p in plans:
        lines.append(f"- {p['ticker']}: kaynak {p['anchor_date']}, gerekli {p['required_anchor_date']}, son geçerlilik {p['expires_at']}; engeller: {', '.join(p['blockers']) or 'kaynak kapanışında engel yok; broker koşulları hâlâ gerekli'}.")
    (ROOT/'reports/order_sheet.md').write_text('\n'.join(lines),encoding='utf-8')
    (ROOT/'data/market/order_sheet.json').write_text(json.dumps(dict(generated_at=now.isoformat(),plans=plans),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Plan için güncel broker fiyatı ve seans koşulları doğrulanmalıdır; henüz gönderilebilir emir yok.')
