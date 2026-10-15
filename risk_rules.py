"""Pure risk guards, shared by the paper ledger and focused deterministic checks."""
from datetime import datetime, timedelta
import math
from zoneinfo import ZoneInfo
from order_plan import round_price

TZ=ZoneInfo('Europe/Istanbul')


def quote_guard(row,now,last_processed=None):
    try:
        stamp=datetime.fromisoformat(row['quote_time'])
        if stamp.tzinfo is None:
            return 'timestamp_without_timezone'
        if stamp>now:
            return 'future_timestamp'
        if last_processed:
            prior=datetime.fromisoformat(last_processed)
            if prior.tzinfo is None:
                prior=prior.replace(tzinfo=TZ)
            if stamp<=prior:
                return 'duplicate_or_older_bar'
        if stamp+timedelta(minutes=5)>now:
            return 'unfinished_bar'
        if stamp.date()!=now.date() or (now-stamp).total_seconds()>900:
            return 'stale_bar'
        if row.get('freshness')!='recent_bar_latency_unverified':
            return 'unverified_freshness'
        return None
    except (ValueError,TypeError,KeyError):
        return 'invalid_timestamp'


def entry_band_valid(plan,price,now):
    return (math.isfinite(price) and price>0
        and plan['plan_status']=='conditional_plan'
        and plan['planned_date']==now.date().isoformat()
        and now<datetime.fromisoformat(plan['expires_at'])
        and plan['trigger_tl']<=price<=plan['buy_limit_ceiling_tl']
        and price>plan['cancel_unfilled_at_or_below_tl']
        and price<plan['pressure_threshold_tl'])


def lot_capacity(available_cash,available_risk,entry_price,stop,limit=None,fee=.002):
    values=[available_cash,available_risk,entry_price,stop,fee]
    if not all(math.isfinite(float(v)) for v in values):
        raise ValueError('Nonfinite risk input')
    if entry_price<=0 or stop<=0 or stop>=entry_price or fee<0:
        return 0
    per_lot=entry_price-stop+fee*(entry_price+stop)
    count=min(math.floor(max(available_cash,0)/(entry_price*(1+fee))),
              math.floor(max(available_risk,0)/per_lot))
    return min(count,int(limit)) if limit is not None else count


def advance_trailing_stop(old_stop,old_peak,price):
    if not all(math.isfinite(v) and v>0 for v in [old_stop,old_peak,price]):
        raise ValueError('Invalid stop/peak/price')
    peak=max(old_peak,price)
    return max(old_stop,round_price(peak*.95)),peak
