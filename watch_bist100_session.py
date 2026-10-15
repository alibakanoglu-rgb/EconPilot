"""Observe the saved BIST universe; append quotes without creating orders."""
import argparse
from datetime import datetime, time as clock_time, timedelta
import json
import math
import os
from pathlib import Path
import time
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/market'
TZ = ZoneInfo('Europe/Istanbul')


def observe():
    companies = pd.read_csv(ROOT / 'data/kap/bist100_constituents.csv')
    companies = companies.dropna(subset=['ticker']).copy()
    companies['ticker'] = companies['ticker'].str.strip().str.upper()
    companies = companies.drop_duplicates('ticker')
    # Primary symbols remain exclusively in the independent paper session watcher.
    companies = companies[~companies['ticker'].isin({'TUPRS', 'CCOLA'})]
    # Fetch previous daily closes once per date; intraday polls reuse this cache.
    reference_date = datetime.now(TZ).date()
    reference_path = DATA / f'bist100_previous_close_{reference_date}.json'
    if reference_path.exists():
        references = json.loads(reference_path.read_text(encoding='utf-8'))
    else:
        references = {}
        symbols = [ticker + '.IS' for ticker in companies['ticker']]
        daily = yf.download(symbols, period='5d', interval='1d', auto_adjust=False,
                            group_by='ticker', threads=2, progress=False,
                            timeout=15, multi_level_index=True)
        for ticker in companies['ticker']:
            try:
                history = daily.xs(ticker + '.IS', axis=1, level=0).dropna(subset=['Close'])
                history = history[pd.to_datetime(history.index).date < reference_date].sort_index()
                close = float(history['Close'].iloc[-1])
                if math.isfinite(close) and close > 0:
                    references[ticker] = dict(price=close, date=str(history.index[-1].date()))
            except (KeyError, ValueError, IndexError):
                continue
        if references:
            reference_path.write_text(json.dumps(references, allow_nan=False), encoding='utf-8')
    rows = []
    cycle = datetime.now(TZ).isoformat()
    for offset in range(0, len(companies), 10):
        batch = companies.iloc[offset:offset + 10]
        symbols = [ticker + '.IS' for ticker in batch['ticker']]
        print(f'BIST gözlem: {offset + 1}-{offset + len(batch)} / {len(companies)}', flush=True)
        try:
            frame = yf.download(symbols, period='5d', interval='5m',
                                auto_adjust=False, group_by='ticker', threads=2,
                                progress=False, timeout=15, multi_level_index=True)
            batch_error = None
        except Exception as error:
            frame = pd.DataFrame()
            batch_error = type(error).__name__ + ': ' + str(error)[:160]
        for company in batch.to_dict('records'):
            row = dict(observed_at=cycle, ticker=company['ticker'],
                       company=company.get('company', ''), mode='observation_only',
                       source='Yahoo/yfinance completed 5m bar', price=None,
                       quote_time=None, bar_volume=None, session_volume=None, age_minutes=None,
                       previous_session_last_bar=None, change_from_previous_session_bar_pct=None,
                       daily_change_pct=None, previous_close=None, previous_close_date=None, interval_seconds=900,
                       status='no_data', error=batch_error)
            try:
                symbol = company['ticker'] + '.IS'
                if frame.empty:
                    raise ValueError('No price data')
                if not isinstance(frame.columns, pd.MultiIndex):
                    raise ValueError('Unexpected download column layout')
                quotes = frame.xs(symbol, axis=1, level=0).copy()
                quotes.index = pd.to_datetime(quotes.index, utc=True).tz_convert(TZ)
                quotes['Close'] = pd.to_numeric(quotes['Close'], errors='coerce')
                now = datetime.now(TZ)
                # Ignore the unfinished bar; never substitute missing prices.
                quotes = quotes[(quotes.index + timedelta(minutes=5) <= now)]
                quotes = quotes[quotes['Close'].notna() & (quotes['Close'] > 0)].sort_index()
                if quotes.empty:
                    raise ValueError('No completed positive-price bar')
                timestamp = quotes.index[-1]
                price = float(quotes['Close'].iloc[-1])
                if not math.isfinite(price):
                    raise ValueError('Nonfinite price')
                age = (now - timestamp.to_pydatetime()).total_seconds() / 60
                volume = float(quotes['Volume'].iloc[-1]) if 'Volume' in quotes else float('nan')
                row.update(price=price, quote_time=timestamp.isoformat(),
                           bar_volume=volume if math.isfinite(volume) else None,
                           age_minutes=round(age, 2),
                           status='recent_bar_latency_unverified' if timestamp.date() == now.date() and age <= 30 else 'stale')
                session = quotes[quotes.index.date == timestamp.date()]
                if 'Volume' in session:
                    volumes = pd.to_numeric(session['Volume'], errors='coerce')
                    total_volume = volumes.sum(min_count=1)
                    if pd.notna(total_volume) and math.isfinite(float(total_volume)):
                        row['session_volume'] = float(total_volume)
                previous = quotes[quotes.index.date < timestamp.date()]
                if not previous.empty:
                    previous_close = float(previous['Close'].iloc[-1])
                    row['previous_session_last_bar'] = previous_close
                    row['change_from_previous_session_bar_pct'] = (price / previous_close - 1) * 100
                reference = references.get(company['ticker'])
                if reference and timestamp.date() == reference_date:
                    row['previous_close'] = reference['price']
                    row['previous_close_date'] = reference['date']
                    row['daily_change_pct'] = (price / reference['price'] - 1) * 100
            except Exception as error:
                row['error'] = row['error'] or type(error).__name__ + ': ' + str(error)[:160]
            rows.append(row)
        if offset + 10 < len(companies):
            time.sleep(1)

    # Every poll is an observation, including repeated bars and missing symbols.
    date = datetime.now(TZ).strftime('%Y-%m-%d')
    log = DATA / 'session_observations' / f'bist100_{date}.jsonl'
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('a', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    # Public CSV has a stable five-column contract; detailed metadata stays in JSONL.
    columns = ['symbol', 'price', 'change_pct', 'volume', 'timestamp']
    result = pd.DataFrame([{
        'symbol': row['ticker'],
        'price': row['price'],
        'change_pct': row['daily_change_pct'],
        'volume': row['session_volume'],
        'timestamp': row['quote_time'],
    } for row in rows], columns=columns)
    temporary = DATA / 'bist100_session_latest.tmp'
    result.to_csv(temporary, columns=columns, index=False, sep=',',
                  encoding='utf-8-sig', decimal='.', lineterminator='\n')
    temporary.replace(DATA / 'bist100_session_latest.csv')
    available = sum(row['price'] is not None for row in rows)
    stale = sum(row['status'] == 'stale' for row in rows)
    summary = [f'# BIST 100 fiyat gözlemi', '', f'- Son tarama başlangıcı: {cycle}',
               '- Arka plan tarama aralığı: 900 saniye; TUPRS ve CCOLA bu süreçten hariç.',
               f'- Evren: {len(rows)}; fiyat bulunan: {available}; eski veri: {stale}; eksik: {len(rows)-available}.',
               '- Kaydedilmiş endeks listesi kullanılır; güncel endeks üyeliği doğrulanmadı.',
               '- Fiyatlar gecikmeli olabilir; veri zamanı ve veri yaşı her satırda tutulur.',
               '- daily_change_pct: Yahoo önceki mevcut günlük kapanışına göre değişim; kapanış tarihi ayrıca tutulur. Eksik referansta boş bırakılır.',
               '- session_volume: son veri gününün indirilen tamamlanmış barlarının toplam hacmi; eksiksiz seans hacmi garanti edilmez.',
               '- Bu kayıtlar fiyat gözlemidir; hedef değer, işlem sinyali veya kâğıt dolum üretmez.',
               '- Yeniden okunan aynı bar yeni piyasa verisi veya bağımsız işlem sayılmaz.',
               '', f'Günlük kayıt: {log.name}', '']
    (ROOT / 'reports/bist100_session_summary.md').write_text('\n'.join(summary), encoding='utf-8')
    print(f'{datetime.now(TZ):%H:%M:%S} BIST kayıt: {available}/{len(rows)} fiyat; {stale} eski; {len(rows)-available} eksik. Emir yok.', flush=True)
    print(f'Kayıt: {log}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--initial-delay', type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.initial_delay <= 900:
        parser.error('--initial-delay must be between 0 and 900 seconds')
    DATA.mkdir(parents=True, exist_ok=True)
    lock = DATA / 'bist100_session_watch.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError('BIST izleyici kilidi var; ikinci süreç başlatılmadı.')
    with os.fdopen(descriptor, 'w') as handle:
        json.dump({'pid': os.getpid(), 'started_at': datetime.now(TZ).isoformat()}, handle)
    try:
        failures = 0
        if args.initial_delay:
            print(f'İlk taramaya {args.initial_delay} saniye; son kayıt korunuyor.', flush=True)
            time.sleep(args.initial_delay)
        while True:
            now = datetime.now(TZ)
            if now.weekday() > 4 or not clock_time(10, 5) <= now.time() < clock_time(17, 55):
                print('İzleme penceresi dışında; ağ çağrısı yapılmadı.', flush=True)
                break
            started = time.monotonic()
            try:
                observe()
                failures = 0
            except Exception as error:
                failures += 1
                print(f'Kayıt hatası: {type(error).__name__}: {error}', flush=True)
                if failures >= 3:
                    raise
            if not args.watch:
                break
            remaining = (datetime.combine(datetime.now(TZ).date(), clock_time(17, 55), TZ) - datetime.now(TZ)).total_seconds()
            if remaining <= 0:
                break
            time.sleep(min(max(0, 900 - (time.monotonic() - started)), remaining))
    except KeyboardInterrupt:
        print('BIST gözlem durduruldu; kayıtlar korundu.', flush=True)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
