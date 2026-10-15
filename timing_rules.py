"""Shared daily-close timing rule and bounded Yahoo/local data reader."""
import csv
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import math

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo('Europe/Istanbul')


def previous_weekday(day):
    day -= timedelta(days=1)
    while day.weekday() > 4:
        day -= timedelta(days=1)
    return day


def timing_at(rows, index, include_breakout=False):
    if index < 5:
        return dict(confirmed=False, status='insufficient_history', sma5=None)
    closes = [float(row['close']) for row in rows[index-5:index+1]]
    previous_sma = sum(closes[:5])/5
    current_sma = sum(closes[1:])/5
    # Confirmation occurs at today's close; any simulated fill must be later.
    crossing = closes[-2] <= previous_sma and closes[-1] > current_sma
    three_day_high = max(float(r['close']) for r in rows[index-3:index])
    breakout = closes[-1] > current_sma and closes[-1] > three_day_high
    return dict(confirmed=crossing or (include_breakout and breakout),
                status='pullback_cross' if crossing else ('trend_breakout' if include_breakout and breakout else 'no_confirmation'),
                pullback_confirmed=crossing, breakout_confirmed=breakout,
                previous_three_close_high=three_day_high,
                sma5=current_sma, previous_sma5=previous_sma)


def next_close_threshold(rows):
    if len(rows) < 5:
        return dict(status='insufficient_history', critical_price=None, fresh_cross_possible=False)
    closes = [float(r['close']) for r in rows[-5:]]
    # x > (last_four_sum + x)/5 iff x > last_four_sum/4.
    critical = sum(closes[-4:])/4
    predecessor_ok = closes[-1] <= sum(closes)/5
    return dict(status='ready' if predecessor_ok else 'already_above_sma5_no_fresh_cross_next_day',
                critical_price=critical, strict_comparison='next_close > critical_price',
                breakout_price=max(float(r['close']) for r in rows[-3:]),
                prior_close=closes[-1], prior_sma5=sum(closes)/5,
                fresh_cross_possible=predecessor_ok, anchor_date=rows[-1]['date'])


def intraday_timing(rows, quote_date, price):
    completed = [r for r in rows if r['date'] < quote_date]
    if len(completed) < 5:
        return dict(confirmed=False,status='insufficient_history',sma5=None)
    expected = previous_weekday(datetime.fromisoformat(quote_date).date()).isoformat()
    if completed[-1]['date'] != expected:
        return dict(confirmed=False,status='missing_previous_session_close',sma5=None,
                    required_anchor_date=expected, observed_anchor_date=completed[-1]['date'],
                    exchange_calendar_verified=False)
    preceding = [float(r['close']) for r in completed[-5:]]
    current_sma = (sum(preceding[-4:])+price)/5
    pullback = preceding[-1] <= sum(preceding)/5 and price > current_sma
    threshold = max(preceding[-3:])
    breakout = price > current_sma and price > threshold
    return dict(confirmed=pullback or breakout,
        status='pullback_intraday_candidate' if pullback else ('breakout_completed_5m_bar' if breakout else 'no_confirmation'),
        sma5=current_sma,previous_three_close_high=threshold,
        pullback_confirmed=pullback,breakout_confirmed=breakout,
        daily_close_confirmed=False)


def daily_history(ticker, offline=False):
    now = datetime.now(TZ)
    rows, source = [], 'Yahoo/yfinance daily Close; dividends separate'
    error = None
    if not offline:
        try:
            import yfinance as yf
            frame = yf.Ticker(ticker+'.IS').history(period='18mo', interval='1d',
                auto_adjust=False, actions=True, timeout=15)
            for stamp, row in frame.iterrows():
                rows.append(dict(date=stamp.strftime('%Y-%m-%d'), close=float(row['Close']),
                    dividends=float(row.get('Dividends', 0)), stock_splits=float(row.get('Stock Splits', 0))))
            if not rows:
                raise ValueError('Empty Yahoo history')
        except Exception as exc:
            error = type(exc).__name__
            rows = []
    if not rows:
        source = 'local cached Yahoo daily prices'
        with (ROOT/'data/market/bist100_daily_prices.csv').open(encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                if row['ticker'] == ticker:
                    rows.append(dict(date=row['date'], close=float(row['close']),
                        dividends=float(row.get('dividends') or 0), stock_splits=float(row.get('stock_splits') or 0)))
    # Conservative operational cutoff; partial same-day daily bars are excluded before 19:00.
    today = now.strftime('%Y-%m-%d')
    rows = sorted((r for r in rows if r['date'] < today or
        (r['date'] == today and now.time() >= time(19))), key=lambda r:r['date'])
    if len({r['date'] for r in rows}) != len(rows):
        raise ValueError('Duplicate daily dates')
    if any(not math.isfinite(r['close']) or r['close'] <= 0 or
           not math.isfinite(r['dividends']) for r in rows):
        raise ValueError('Invalid daily price/dividend')
    if len(rows) < 6:
        raise ValueError('Insufficient daily history')
    return rows, dict(source=source, latest_date=rows[-1]['date'], fetch_error_type=error,
        stale_calendar_days=(now.date()-datetime.fromisoformat(rows[-1]['date']).date()).days,
        same_day_cutoff='19:00 Istanbul operational rule; not a realtime-feed guarantee')
