"""Evaluate user-defined price thresholds; never submit brokerage orders."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import math
import re
import subprocess
import sys
from zoneinfo import ZoneInfo
from timing_rules import daily_history, timing_at, next_close_threshold, intraday_timing
from order_plan import make_plan, publish_sheet, round_price

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'reports/pilot_valuation_summary.md'
ISTANBUL = ZoneInfo('Europe/Istanbul')
TICKERS = ('TUPRS', 'CCOLA')


def number(text):
    match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*(?:TL)?\s*', text)
    if not match:
        raise ValueError(f'Geçersiz fiyat hücresi: {text}')
    result = float(match.group(1).replace(',', '.'))
    if not math.isfinite(result) or result <= 0:
        raise ValueError('Fiyat pozitif olmalı.')
    return result


def targets_from_report():
    text = REPORT.read_text(encoding='utf-8-sig')
    # Match the named first table; never use the separate EV/EBIT table by accident.
    section = text.split('## Üç senaryo — kâr çarpanı yöntemi', 1)[1].split('### Formüller', 1)[0]
    targets = {}
    for ticker in TICKERS:
        found = {}
        for line in section.splitlines():
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if len(cells) == 9 and cells[0] == ticker and cells[1] in {'Baskı', 'Referans'}:
                if cells[1] in found:
                    raise ValueError('Raporda yinelenen hedef satırı.')
                found[cells[1]] = number(cells[4])
        if set(found) != {'Baskı', 'Referans'} or found['Baskı'] >= found['Referans']:
            raise ValueError(f'{ticker}: hedefler eksik veya eşik sırası yanlış.')
        targets[ticker] = found
    return targets


def cached_quote(ticker):
    path = ROOT / 'data/market/bist100_price_metrics.csv'
    with path.open(encoding='utf-8-sig', newline='') as handle:
        matches = [row for row in csv.DictReader(handle) if row['ticker'] == ticker]
    if len(matches) != 1:
        raise ValueError('Yerel fiyat eksik veya yineleniyor.')
    row = matches[0]
    return dict(price=number(row['last_close']), quote_time=row['last_date'],
                source='local cached close', freshness='cached_not_live')


def latest_quote(ticker, now, offline):
    if offline:
        return cached_quote(ticker)
    try:
        import yfinance as yf
        frame = yf.Ticker(ticker + '.IS').history(
            period='5d', interval='5m', auto_adjust=False, timeout=12,
        )
        if frame.empty or 'Close' not in frame:
            raise ValueError('Fiyat verisi boş.')
        # Use completed five-minute bars, not an unfinished intraday bar.
        eligible = [(stamp, float(row['Close'])) for stamp, row in frame.iterrows()
                    if stamp.tzinfo is not None
                    and stamp.to_pydatetime().astimezone(ISTANBUL) + timedelta(minutes=5) <= now
                    and math.isfinite(float(row['Close'])) and float(row['Close']) > 0]
        if not eligible:
            raise ValueError('Tamamlanmış fiyat barı yok.')
        stamp, price = eligible[-1]
        stamp = stamp.to_pydatetime().astimezone(ISTANBUL)
        age = (now - stamp).total_seconds()/60
        freshness = 'recent_bar_latency_unverified' if stamp.date() == now.date() and age <= 30 else 'stale_or_market_closed'
        return dict(price=price, quote_time=stamp.isoformat(), source='Yahoo/yfinance completed 5m bar',
                    freshness=freshness, age_minutes=round(age, 1))
    except Exception as error:
        # A fallback never acquires today's date or an unverified live label.
        quote = cached_quote(ticker)
        quote['fetch_error_type'] = type(error).__name__
        return quote


def main():
    parser = argparse.ArgumentParser(description='TUPRS/CCOLA eşik ve %5 risk matrisi')
    parser.add_argument('--offline', action='store_true', help='Son kayıtlı kapanış fiyatıyla çalış.')
    parser.add_argument('--entry', action='append', default=[], metavar='TICKER=PRICE',
                        help='Gerçek giriş fiyatını yerel iz süren stop kaydına bağla; örnek TUPRS=390')
    parser.add_argument('--peak', action='append', default=[], metavar='TICKER=PRICE', help='Bilinen pozisyon zirvesi; giriş kaydı gerekir.')
    parser.add_argument('--close-position', action='append', default=[], choices=TICKERS, help='Yerel pozisyon izleme kaydını kapat; emir göndermez.')
    parser.add_argument('--capital', type=float, default=100000)
    parser.add_argument('--risk-fraction', type=float, default=0.02)
    parser.add_argument('--with-backtest', action='store_true', help='Aynı terminalde stop karşılaştırmasını da yazdır.')
    parser.add_argument('--paper', action='store_true', help='Bu gözlemi ayrı kâğıt işlem hesabına kaydet; gerçek emir yok.')
    args = parser.parse_args()
    if args.paper and (args.entry or args.peak or args.close_position):
        raise ValueError('--paper gerçek pozisyon kayıt seçenekleriyle birlikte kullanılmaz.')
    entries = {}
    for pair in args.entry:
        ticker, value = pair.split('=', 1)
        if ticker not in TICKERS or ticker in entries:
            raise ValueError('Giriş fiyatı şirketi geçersiz veya yineleniyor.')
        entries[ticker] = number(value)
    if not math.isfinite(args.capital) or args.capital <= 0 or not math.isfinite(args.risk_fraction) or not 0 < args.risk_fraction <= 1:
        raise ValueError('Sermaye ve risk oranı geçersiz.')
    peaks = {}
    for pair in args.peak:
        ticker, value = pair.split('=',1)
        if ticker not in TICKERS or ticker in peaks:
            raise ValueError('Zirve şirketi geçersiz veya yineleniyor.')
        peaks[ticker] = number(value)
    state_path = ROOT/'data/market/execution_positions.json'
    positions = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() and not args.paper else {}
    for ticker in args.close_position:
        positions.pop(ticker,None)
    for ticker, entry_value in entries.items():
        if ticker in positions and positions[ticker]['entry_price'] != entry_value:
            raise ValueError('Kayıtlı giriş farklı; önce --close-position ile kaydı kapat.')
        positions.setdefault(ticker,dict(entry_price=entry_value,peak_observed=entry_value))
    if any(ticker not in positions for ticker in peaks):
        raise ValueError('--peak için --entry veya kayıtlı pozisyon gerekir.')
    targets = targets_from_report()
    now = datetime.now(ISTANBUL)
    rows = []
    plans = []
    print('EconPilot — fiyat eşiği ve risk matrisi')
    print('Model hedefleri varsayımsal; sinyaller eşik çıktısıdır. Emir gönderilmez.')
    print('Bugün:', now.strftime('%Y-%m-%d %H:%M %Z'))
    for ticker in TICKERS:
        quote = latest_quote(ticker, now, args.offline)
        price = quote['price']
        pressure, reference = targets[ticker]['Baskı'], targets[ticker]['Referans']
        history, history_info = daily_history(ticker, args.offline)
        plan_history = history.copy()
        # Never use a daily confirmation newer than the quote being classified.
        history = [r for r in history if r['date'] <= quote['quote_time'][:10]]
        # Intraday candidates use only daily closes before the quote's own date.
        timing = intraday_timing(history,quote['quote_time'][:10],price)
        completed_before_quote=[r for r in history if r['date']<quote['quote_time'][:10]]
        timing_date = completed_before_quote[-1]['date'] if completed_before_quote else None
        next_timing = next_close_threshold(history)
        if price < pressure:
            active=timing['confirmed'] and quote['freshness']=='recent_bar_latency_unverified'
            signal = 'AL_AKTİF' if active else 'AL_İZLEMEDE / PUSUDA'
            region = 'Alım bölgesi; pullback veya trend kırılım teyidi'
        elif price > reference:
            signal, region = 'SAT', 'Satış / kâr al bölgesi'
        else:
            signal, region = 'BEKLE', 'Adil / nötr eşik bölgesi'
        position = positions.get(ticker)
        entry = float(position['entry_price']) if position else price
        peak_price = max(entry,price,float(position['peak_observed']) if position else price,peaks.get(ticker,entry))
        if position:
            position['peak_observed'] = peak_price
            position['last_observed_quote_time'] = quote['quote_time']
        # Persist only explicitly registered positions; no real holding is invented.
        stop = round_price(peak_price * 0.95 if position else price * 0.95)
        stop_breached = position is not None and price <= stop
        if stop_breached:
            signal, region = 'SAT', 'İzlenen zirveye göre %5 stop eşiği aşıldı'
        current_plan=make_plan(ticker,plan_history,targets[ticker],args.capital,args.risk_fraction,now,position is not None)
        plans.append(current_plan)
        plan_matches_quote=(current_plan['planned_date']==quote['quote_time'][:10]
            and current_plan['planned_date']==now.date().isoformat()
            and current_plan['plan_status']=='conditional_plan'
            and current_plan['trigger_tl']<=price<=current_plan['buy_limit_ceiling_tl'])
        if signal=='AL_AKTİF' and not plan_matches_quote:
            signal='AL_İZLEMEDE / PUSUDA'
            region='Teknik aday; plan tarihi/limit bandı veya pozisyon engeli'
        risk_budget = args.capital*args.risk_fraction
        distance = price-stop
        # Include assumed entry and stop-exit commissions in each lot's risk.
        lot_risk = distance + 0.002*(price+stop) if distance>0 else None
        risk_lots = math.floor(risk_budget/lot_risk) if lot_risk else 0
        cash_lots = math.floor(args.capital/(price*1.002))
        capacity_lots = min(risk_lots,cash_lots)
        eligible_new_lots = capacity_lots if signal=='AL_AKTİF' and not position else 0
        upside = (reference/price-1)*100
        margin = (1-price/reference)*100
        rows.append(dict(ticker=ticker, signal=signal, region=region, **quote,
                         pressure_threshold_tl=pressure, reference_target_tl=reference,
                         timing=timing, timing_date=timing_date, timing_source=history_info['source'],
                         next_close_timing=next_timing,
                         plan_matches_quote=plan_matches_quote,
                         entry_reference_tl=entry, entry_source='registered_position' if position else 'proposed_at_quote',
                         proposed_entry_tl=price if signal == 'AL_AKTİF' else None,
                         stop_tl=stop, risk_pct=5, stop_breached=stop_breached,
                         observed_position_peak=peak_price if position else None,
                         trailing_state='observed_peak_only' if position else 'no_registered_position',
                         capital_tl=args.capital,risk_budget_tl=risk_budget,risk_per_lot_tl=lot_risk,
                         max_lot_capacity=capacity_lots,eligible_new_entry_lots=eligible_new_lots,
                         upside_pct=upside, margin_of_safety_pct=margin,
                         realtime_verified=False, target_validated=False, order_submitted=False))
        print(f'\n{ticker}: {signal} | {region}')
        print(f'  Fiyat: {price:.2f} TL | Veri zamanı: {quote["quote_time"]}')
        print(f'  Alım eşiği: < {pressure:.2f} TL | Kâr al eşiği: > {reference:.2f} TL')
        print(f'  Giriş referansı: {entry:.2f} TL | Hedef: {reference:.2f} TL | Stop: {stop:.2f} TL')
        print(f'  Model fiyat farkı: %{upside:.2f} | Güvenlik marjı: %{margin:.2f}')
        print(f'  Veri durumu: {quote["freshness"]} | Kaynak: {quote["source"]}')
        print(f'  Zamanlama: {timing["status"]} | Günlük teyit tarihi: {timing_date}')
        if next_timing['critical_price'] is not None:
            print(f'  Sonraki işlem günü SMA5 kritik kapanış: > {next_timing["critical_price"]:.6f} TL ve < {pressure:.2f} TL')
            if not next_timing['fresh_cross_possible']:
                print(f'  Pullback kesişimi kapalı; trend devamı için ayrıca son 3 kapanış zirvesi > {next_timing["breakout_price"]:.6f} TL kırılımı izlenir.')
            if next_timing['critical_price'] >= pressure:
                print('  SMA5 teyidi ile alım eşiği arasında uygun fiyat aralığı yok; yalnız fiyatı yükseltmek AL_AKTİF üretmez.')
        print(f'  Sermaye: {args.capital:.0f} TL | Risk bütçesi: {risk_budget:.0f} TL | Lot kapasitesi: {capacity_lots} | Teyitli yeni giriş lotu: {eligible_new_lots}')
        print('  Lot kapasitesi iki hisseye aynı anda ayrı ayrı tahsis edilemez; kayma ve fiyat boşluğu risk bütçesini aşabilir.')
        if position:
            print(f'  Kayıtlı giriş: {entry:.2f} TL | İzlenen zirve: {peak_price:.2f} TL | İz süren stop: {stop:.2f} TL')
            print('  Zirve yalnız bildirilen/çalıştırmada gözlenen fiyatları kapsar; aradaki seans zirveleri otomatik doğrulanmadı.')
        if quote['freshness'] != 'recent_bar_latency_unverified':
            print('  Sinyal son kayıtlı/eski veri içindir; anlık işlem teyidi değildir.')
        if not position:
            print('  Stop yeni giriş için önerilen eşiktir; mevcut pozisyon stopu değerlendirilmedi.')
    market = ROOT / 'data/market'
    market.mkdir(exist_ok=True, parents=True)
    if not args.paper and (positions or state_path.exists()):
        temporary = state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(positions,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        temporary.replace(state_path)
    snapshot = dict(
        evaluated_at=now.isoformat(), target_report_sha256=hashlib.sha256(REPORT.read_bytes()).hexdigest(),
        rule_code_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ['execution_trigger.py','timing_rules.py','order_plan.py']},
        rows=rows, plans=plans,
        assumptions='User-defined thresholds; pullback or 3-close breakout; completed 5m price bar; no profitability validation')
    latest_path = market/'execution_trigger_latest.json'
    temporary = latest_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(latest_path)
    print('\n%5 fiyat eşiği azami gerçekleşen zararı garanti etmez; boşluk ve kayma etkisi hesaplanmadı.')
    publish_sheet(plans,now)
    # Preserve each observation; never infer that a planned order was actually filled.
    archive=ROOT/'reports/execution_runs'
    archive.mkdir(parents=True,exist_ok=True)
    run_id=now.strftime('%Y%m%dT%H%M%S%f%z')
    (archive/(run_id+'.json')).write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (archive/(run_id+'.md')).write_text((ROOT/'reports/order_sheet.md').read_text(encoding='utf-8'),encoding='utf-8')
    with (market/'execution_decision_journal.jsonl').open('a',encoding='utf-8') as handle:
        handle.write(json.dumps(dict(run_id=run_id,**snapshot),ensure_ascii=False)+'\n')
    print(f'Karar kaydı: {run_id}; eski planın üzerine yazılan önceki kayıtlardan işlem gerçekleştiği çıkarılmaz.')
    if args.paper:
        from paper_trading import record_snapshot
        record_snapshot(snapshot,args.capital,args.risk_fraction)
    if args.with_backtest:
        print('\n=== Sabit / İz Süren Stop Karşılaştırması ===',flush=True)
        command = [sys.executable,'-X','utf8',str(ROOT/'backtest_engine.py')]
        if args.offline:
            command.append('--offline')
        subprocess.run(command,check=True,cwd=ROOT)


if __name__ == '__main__':
    main()
