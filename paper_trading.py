"""Prospective observation-only paper ledger; no broker or real-position writes."""
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import json
import math
import os
from zoneinfo import ZoneInfo

from order_plan import round_price
from risk_rules import quote_guard,entry_band_valid,lot_capacity,advance_trailing_stop

ROOT=Path(__file__).resolve().parent
MARKET=ROOT/'data/market'
REPORTS=ROOT/'reports'
TZ=ZoneInfo('Europe/Istanbul')
FEE=.002


def record_snapshot(snapshot,capital=100000,risk_fraction=.02):
    MARKET.mkdir(parents=True,exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    state_path=MARKET/'paper_trading_state.json'
    lock_path=MARKET/'paper_trading.lock'
    # Refuse overlapping writers instead of risking duplicate simulated fills.
    try:
        descriptor=os.open(lock_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError('Kâğıt işlem kaydı kilitli; eşzamanlı çalıştırma veya yarım kalan yazım incelenmeli.')
    os.close(descriptor)
    try:
        now=datetime.now(TZ)
        state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else dict(
            version='0.1',started_at=now.isoformat(),initial_capital_tl=capital,risk_fraction=risk_fraction,
            cash_tl=capital,positions={},pending={},last_quotes={},events=[],trades=[],
            equity_peak_tl=capital,max_drawdown_pct=0.0)
        if state['initial_capital_tl']!=capital or state['risk_fraction']!=risk_fraction:
            raise ValueError('Mevcut kâğıt hesap sermaye/risk politikası farklı; sessizce değiştirilemez.')
        evaluated=datetime.fromisoformat(snapshot['evaluated_at'])
        if evaluated.tzinfo is None or (now-evaluated).total_seconds()<0 or (now-evaluated).total_seconds()>120:
            raise ValueError('Kâğıt kayıt için son iki dakika içinde üretilmiş zaman damgalı görüntü gerekiyor.')
        target_path=ROOT/'reports/pilot_valuation_summary.md'
        if hashlib.sha256(target_path.read_bytes()).hexdigest()!=snapshot['target_report_sha256']:
            raise ValueError('Hedef raporu görüntüden sonra değişmiş.')
        plans={p['ticker']:p for p in snapshot['plans']}
        initial_event_count=len(state['events'])
        rule_hashes=dict(snapshot.get('rule_code_hashes',{}))
        rule_hashes['paper_trading.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        rule_hashes['risk_rules.py']=hashlib.sha256((ROOT/'risk_rules.py').read_bytes()).hexdigest()
        fingerprint=hashlib.sha256(json.dumps(rule_hashes,sort_keys=True).encode()).hexdigest()
        strategy=dict(version='paper_forward_1',capital_tl=capital,risk_fraction=risk_fraction,
            fee_per_side=FEE,stop_fraction=.05,
            targets={r['ticker']:dict(pressure=r['pressure_threshold_tl'],reference=r['reference_target_tl']) for r in snapshot['rows']},
            rule_code_hashes=rule_hashes)
        strategy_id=hashlib.sha256(json.dumps(strategy,sort_keys=True).encode()).hexdigest()
        baseline_path=MARKET/'paper_strategy_baseline.json'
        if baseline_path.exists():
            baseline=json.loads(baseline_path.read_text(encoding='utf-8'))
            if baseline['strategy_id']!=strategy_id:
                raise ValueError('Dondurulmuş kâğıt strateji değişti; aynı deneyde yeni hedef/kod/risk kullanılmaz. Yeni deney açıkça tanımlanmalı.')
        else:
            baseline=dict(frozen_at=now.isoformat(),strategy_id=strategy_id,strategy=strategy,
                existing_closed_trades=len(state['trades']))
            baseline_path.write_text(json.dumps(baseline,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        state['strategy_id']=strategy_id

        def event(ticker,kind,**values):
            state['events'].append(dict(observed_at=now.isoformat(),ticker=ticker,event=kind,
                rule_fingerprint=fingerprint,**values))

        def risk_reserved(exclude=None):
            held=sum(p['lots']*max(p['entry_price']-p['stop_tl']+FEE*(p['entry_price']+p['stop_tl']),0)
                for t,p in state['positions'].items() if t!=exclude)
            pending=sum(p['reserved_risk_tl'] for t,p in state['pending'].items() if t!=exclude)
            return held+pending

        # Expiry is checked even when no new quote arrives; duplicate bars cannot keep orders alive.
        for ticker, pending_entry in list(state['pending'].items()):
            if now>=datetime.fromisoformat(pending_entry['plan']['expires_at']):
                state['pending'].pop(ticker)
                event(ticker,'paper_entry_cancelled',reason='plan_expired_without_new_bar')

        for row in snapshot['rows']:
            ticker=row['ticker'];price=float(row['price']);stamp=row['quote_time']
            if not math.isfinite(price) or price<=0:
                raise ValueError('Geçersiz kâğıt fiyat.')
            reason=quote_guard(row,now,state['last_quotes'].get(ticker))
            if reason=='duplicate_or_older_bar':
                continue
            if reason:
                if ticker in state['pending']:
                    old=state['pending'][ticker]
                    if now>=datetime.fromisoformat(old['plan']['expires_at']):
                        state['pending'].pop(ticker)
                        event(ticker,'paper_entry_cancelled',reason='plan_expired')
                event(ticker,'observation_blocked',quote_time=stamp,reason=reason,price=price)
                continue
            # Invalid future timestamps never poison the last successfully processed bar.
            state['last_quotes'][ticker]=stamp
            position=state['positions'].get(ticker)
            if position:
                position['stop_tl'],position['peak_observed']=advance_trailing_stop(position['stop_tl'],position['peak_observed'],price)
                position['last_mark_price']=price
                position['last_mark_time']=stamp
                exit_reason='trailing_stop' if price<=position['stop_tl'] else ('take_profit' if price>=position['take_profit_tl'] else None)
                if exit_reason:
                    proceeds=position['lots']*price*(1-FEE)
                    pnl=proceeds-position['entry_cost_tl']
                    state['cash_tl']+=proceeds
                    state['trades'].append(dict(ticker=ticker,entry_observed_at=position['entry_observed_at'],
                        exit_observed_at=now.isoformat(),entry_quote_time=position['entry_quote_time'],exit_quote_time=stamp,
                        entry_price=position['entry_price'],exit_price=price,lots=position['lots'],
                        pnl_tl=pnl,net_return_pct=pnl/position['entry_cost_tl']*100,reason=exit_reason,
                        target_report_sha256=position['target_report_sha256'],actual_broker_fill=False))
                    event(ticker,'paper_exit',reason=exit_reason,price=price,lots=position['lots'],pnl_tl=pnl)
                    state['positions'].pop(ticker)
                else:
                    event(ticker,'paper_position_mark',price=price,stop_tl=position['stop_tl'])
                continue
            pending=state['pending'].get(ticker)
            if pending:
                plan=pending['plan']
                cancellation=(now.date().isoformat()!=plan['planned_date']
                    or now>=datetime.fromisoformat(plan['expires_at'])
                    or snapshot['target_report_sha256']!=pending['target_report_sha256']
                    or pending['rule_fingerprint']!=fingerprint
                    or price<=plan['cancel_unfilled_at_or_below_tl']
                    or price>plan['buy_limit_ceiling_tl'] or price>=plan['pressure_threshold_tl'])
                if cancellation:
                    state['pending'].pop(ticker)
                    event(ticker,'paper_entry_cancelled',reason='date_target_or_price_band_changed',price=price)
                    continue
                # Fill only on a later observed bar; the signal bar itself cannot be the fill.
                if (stamp>pending['signal_quote_time'] and row['signal']=='AL_AKTİF'
                    and row.get('plan_matches_quote') and entry_band_valid(plan,price,now)):
                    stop=round_price(price*.95)
                    available_risk=max(capital*risk_fraction-risk_reserved(ticker),0)
                    other_cash_reserved=sum(p['reserved_cash_tl'] for t,p in state['pending'].items() if t!=ticker)
                    count=lot_capacity(state['cash_tl']-other_cash_reserved,available_risk,price,stop,pending['lots'],FEE)
                    state['pending'].pop(ticker)
                    if count<=0:
                        event(ticker,'paper_entry_cancelled',reason='portfolio_cash_or_risk_limit')
                        continue
                    cost=count*price*(1+FEE)
                    state['cash_tl']-=cost
                    state['positions'][ticker]=dict(lots=count,entry_price=price,entry_cost_tl=cost,
                        entry_observed_at=now.isoformat(),entry_quote_time=stamp,
                        peak_observed=price,stop_tl=stop,take_profit_tl=plan['take_profit_limit_tl'],
                        last_mark_price=price,last_mark_time=stamp,
                        target_report_sha256=pending['target_report_sha256'],
                        entry_rule_fingerprint=fingerprint,actual_broker_fill=False)
                    event(ticker,'paper_entry',price=price,lots=count,stop_tl=stop)
                continue
            plan=plans[ticker]
            if (row['signal']=='AL_AKTİF' and row.get('plan_matches_quote') and entry_band_valid(plan,price,now)):
                available_risk=max(capital*risk_fraction-risk_reserved(),0)
                risk_per_lot=plan['buy_limit_ceiling_tl']-plan['stop_trigger_if_filled_at_ceiling_tl']+FEE*(plan['buy_limit_ceiling_tl']+plan['stop_trigger_if_filled_at_ceiling_tl'])
                reserved_cash=sum(p['reserved_cash_tl'] for p in state['pending'].values())
                count=lot_capacity(state['cash_tl']-reserved_cash,available_risk,
                    plan['buy_limit_ceiling_tl'],plan['stop_trigger_if_filled_at_ceiling_tl'],plan['lot_cap'],FEE)
                if count:
                    state['pending'][ticker]=dict(signal_observed_at=now.isoformat(),signal_quote_time=stamp,
                        plan=json.loads(json.dumps(plan)),lots=count,reserved_risk_tl=count*risk_per_lot,
                        reserved_cash_tl=count*plan['buy_limit_ceiling_tl']*(1+FEE),
                        target_report_sha256=snapshot['target_report_sha256'],rule_fingerprint=fingerprint)
                    event(ticker,'paper_entry_armed',lots=count,signal_quote_time=stamp)
                else:
                    event(ticker,'observation_blocked',reason='portfolio_cash_or_risk_limit')
            else:
                event(ticker,'no_entry',signal=row['signal'],price=price)
        equity=state['cash_tl']+sum(p['lots']*p['last_mark_price']*(1-FEE) for p in state['positions'].values())
        state['equity_peak_tl']=max(state['equity_peak_tl'],equity)
        state['max_drawdown_pct']=min(state['max_drawdown_pct'],(equity/state['equity_peak_tl']-1)*100)
        state['updated_at']=now.isoformat()
        state['equity_tl']=equity
        state['paper_net_return_pct']=(equity/capital-1)*100
        state['strategy_profitability_validated']=False
        state['dividends_and_corporate_actions_modeled']=False
        state['income_scope']='sampled-price paper simulation; not total return'
        state['last_rule_code_hashes']=rule_hashes
        temporary=state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        temporary.replace(state_path)
        trades=state['trades'];wins=sum(t['pnl_tl']>0 for t in trades)
        win_rate=wins/len(trades)*100 if trades else None
        new_events=state['events'][initial_event_count:]
        report=['# EconPilot — ileriye dönük kâğıt işlem kaydı','',
            f"Başlangıç: {state['started_at']}; son güncelleme: {now.isoformat()}.",
            f"- Dondurulmuş deney sürümü: {strategy_id[:16]}; dondurma zamanı: {baseline['frozen_at']}.",
            f"- Örnek sermaye: {capital:,.2f} TL; ortak işlem risk bütçesi: {capital*risk_fraction:,.2f} TL.",
            f"- Nakit: {state['cash_tl']:,.2f} TL; örnek tasfiye değeri: {equity:,.2f} TL.",
            f"- Açık pozisyon: {len(state['positions'])}; bekleyen giriş adayı: {len(state['pending'])}; kapanan kâğıt işlem: {len(trades)}.",
            f"- Örnek getiri: %{state['paper_net_return_pct']:.2f}; gözlenen azami düşüş: %{state['max_drawdown_pct']:.2f}.",
            '- Başarı oranı: '+(f'%{win_rate:.1f}' if win_rate is not None else 'hesaplanamaz — kapanan işlem yok'),
            '', '## Son gözlem olayları','']
        report+=['- '+e['ticker']+': '+e['event']+'; '+str(e.get('reason','')) for e in new_events] or ['- Yeni fiyat barı yok; tekrar işlenmedi.']
        report+=['','## Kapsam ve sınırlılıklar','',
            '- Gerçek emir veya dolum yoktur. Gerçek pozisyon dosyası değişmez; kâğıt kayıt ayrı tutulur.',
            '- Yalnız kayıt başladıktan sonra gözlenen adaylar işlenir. Eski backtest kazançları, kaçırılan barlar ve görülmeyen işlemler bu hesaba eklenmez.',
            '- İlk uygun bar giriş adayını kurar; daha sonra gözlenen uygun bar varsayımsal dolum sağlar. Alış/satışta yüzde 0,2 komisyon; piyasa derinliği ve gerçek dolum bilinmez.',
            '- İki hisse aynı 100.000 TL örnek hesap ve toplam 2.000 TL başlangıç risk tavanını paylaşır. Boşluk, kayma ve ardışık zararlar gerçek kaybı bu tutarın üzerine çıkarabilir.',
            '- Zirve/stop yalnız yeni ve güncel gözlemlerde ilerler. Çalıştırmalar arası kaçırılan zirve, stop teması, temettü ve bölünmeler otomatik modellenmedi. Rapor toplam yatırım getirisi değildir.',
            '- Yahoo 5 dakikalık barı doğrulanmış anlık broker verisi değildir. Eski ve tekrarlanan bar giriş/çıkış oluşturmaz.',
            '- Komut her çağrıda bir görüntü işler; arka planda seans boyu izleme yoktur. Yeterli ileri gözlem ve işlem olmadan strateji başarı iddiası kurulmaz.',
            '- Hedefler, sermaye, risk, komisyon ve kural kodu deney başlangıcında sabitlenir. Değişirse aynı deney sürdürülmez; eski hesap silinmeden ayrı deney tanımlanmalıdır.',
            '', '## Neden Önemli?','',
            'Bu kayıt bugünden itibaren görülen sinyalin hangi sürüm, fiyat ve kuralla oluştuğunu korur. Sonradan geçmişi değiştirmeden işlem mantığını gözlemlemeyi sağlar.','']
        (REPORTS/'paper_trading_summary.md').write_text('\n'.join(report),encoding='utf-8')
        print('\n=== İLERİYE DÖNÜK KÂĞIT İŞLEM KAYDI ===')
        print(f"Örnek hesap: {equity:.2f} TL | Açık: {len(state['positions'])} | Bekleyen: {len(state['pending'])} | Kapanan: {len(trades)}")
        print('Son olaylar: '+('; '.join(e['ticker']+' '+e['event'] for e in new_events) or 'yeni bar yok'))
        print('İşlem yoksa başarı/getiri kanıtı yok; kayıt gerçek aracı kurum hesabı değildir.')
        return state
    finally:
        lock_path.unlink()


if __name__=='__main__':
    snapshot=json.loads((MARKET/'execution_trigger_latest.json').read_text(encoding='utf-8'))
    record_snapshot(snapshot)
