"""Synthetic risk checks only; no market data, accounts, or paper ledger are touched."""
from datetime import datetime
from zoneinfo import ZoneInfo
import unittest

from risk_rules import quote_guard,entry_band_valid,lot_capacity,advance_trailing_stop

TZ=ZoneInfo('Europe/Istanbul')


class RiskChecks(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,15,10,15,tzinfo=TZ)
        self.row={'quote_time':'2026-10-15T10:05:00+03:00','freshness':'recent_bar_latency_unverified'}
        self.plan=dict(plan_status='conditional_plan',planned_date='2026-10-15',
            expires_at='2026-10-15T19:00:00+03:00',trigger_tl=392.5,buy_limit_ceiling_tl=393,
            cancel_unfilled_at_or_below_tl=392.25,pressure_threshold_tl=463.77)

    def test_fresh_completed_bar(self):
        self.assertIsNone(quote_guard(self.row,self.now))

    def test_duplicate(self):
        self.assertEqual(quote_guard(self.row,self.now,self.row['quote_time']),'duplicate_or_older_bar')

    def test_stale(self):
        self.row['quote_time']='2026-10-14T17:55:00+03:00'
        self.assertEqual(quote_guard(self.row,self.now),'stale_bar')

    def test_future(self):
        self.row['quote_time']='2026-10-15T11:00:00+03:00'
        self.assertEqual(quote_guard(self.row,self.now),'future_timestamp')

    def test_unfinished(self):
        self.row['quote_time']='2026-10-15T10:13:00+03:00'
        self.assertEqual(quote_guard(self.row,self.now),'unfinished_bar')

    def test_missing_timezone(self):
        self.row['quote_time']='2026-10-15T10:05:00'
        self.assertEqual(quote_guard(self.row,self.now),'timestamp_without_timezone')

    def test_price_jump(self):
        self.assertFalse(entry_band_valid(self.plan,400,self.now))

    def test_entry_in_band(self):
        self.assertTrue(entry_band_valid(self.plan,392.75,self.now))

    def test_expired_plan(self):
        self.assertFalse(entry_band_valid(self.plan,392.75,datetime(2026,10,16,10,15,tzinfo=TZ)))

    def test_95_lots(self):
        self.assertEqual(lot_capacity(100000,2000,393,373.5),95)

    def test_shared_risk_budget(self):
        first=lot_capacity(100000,2000,393,373.5)
        reserved=first*(393-373.5+.002*(393+373.5))
        self.assertEqual(lot_capacity(100000-first*393*1.002,2000-reserved,83,78.85),0)

    def test_stop_breached_no_new_lots(self):
        self.assertEqual(lot_capacity(100000,2000,370,373.5),0)

    def test_trailing_never_moves_down(self):
        stop,peak=advance_trailing_stop(380,400,395)
        self.assertEqual((stop,peak),(380,400))

    def test_trailing_moves_up(self):
        stop,peak=advance_trailing_stop(380,400,420)
        self.assertEqual((stop,peak),(399,420))

    def test_gap_can_exceed_five_percent(self):
        stop,peak=advance_trailing_stop(373.5,393,370)
        self.assertLess(370,stop)
        self.assertGreater((1-370/393)*100,5)


if __name__=='__main__':
    unittest.main(verbosity=2)
