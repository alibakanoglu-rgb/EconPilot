"""Counterfactual daily strategy simulation using today's unvalidated valuation thresholds."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json

from execution_trigger import targets_from_report, REPORT, TICKERS
from timing_rules import daily_history, timing_at

ROOT = Path(__file__).resolve().parent
COMMISSION = 0.002  # 0.2% on each buy and sell, not 0.2% for the whole round trip.
INITIAL = 100_000.0


def simulate(ticker, data, targets, use_timing=True, trailing=False, target_mode='current_static',entry_rule='pullback_only'):
    end = datetime.fromisoformat(data[-1]['date']).date()
    start = end - timedelta(days=365)
    indices = [i for i,r in enumerate(data) if datetime.fromisoformat(r['date']).date() >= start]
    if len(indices) < 200 or indices[0] < 63:
        raise ValueError('Need roughly one year of daily data and SMA warmup')
    cash, quantity = INITIAL, 0.0
    entry = None
    pending = None
    trades, curve = [], []
    exposure_days = 0
    peak, max_drawdown = INITIAL, 0.0
    mode = (entry_rule if use_timing else 'threshold_only') + ('_trailing' if trailing else '_fixed') + '_' + target_mode
    active_targets = targets.copy()
    last_target_month = None
    stages = [];cancelled_entries=0
    for i in indices:
        row = data[i]
        price = row['close']
        if target_mode == 'staged_price_proxy' and row['date'][:7] != last_target_month:
            # Only preceding closes are used; missing historical profits are never fabricated.
            anchor = sum(r['close'] for r in data[i-63:i])/63
            active_targets = {'Baskı': anchor*1.05, 'Referans': anchor*1.25}
            last_target_month = row['date'][:7]
            stages.append(dict(ticker=ticker, mode=mode, effective_date=row['date'],
                information_cutoff=data[i-1]['date'], pressure_target=active_targets['Baskı'],
                reference_target=active_targets['Referans'], source='lagged 63-close price proxy; no earnings data'))
        # Dividends go to shares already held before today's close transaction.
        if quantity:
            dividend = quantity * row['dividends']
            cash += dividend
            entry['dividends'] += dividend
        if pending:
            action, signal_date, reason, signal_pressure, signal_target = pending
            pending = None
            if action == 'buy' and price>=signal_pressure:
                # A next-close gap out of the buy region cannot fill a stale entry candidate.
                cancelled_entries+=1
            elif action == 'buy' and not quantity and i != indices[-1]:
                quantity = cash/(price*(1+COMMISSION))
                entry = dict(entry_date=row['date'], signal_date=signal_date, entry_price=price,
                    quantity=quantity, entry_cost=cash, dividends=0.0, stop=price*0.95,
                    position_peak_close=price,take_profit_target=signal_target)
                cash = 0.0
            elif action == 'sell' and quantity:
                proceeds = quantity*price*(1-COMMISSION)
                pnl = proceeds + entry['dividends'] - entry['entry_cost']
                trades.append(dict(ticker=ticker, mode=mode,
                    **entry, exit_date=row['date'], exit_signal_date=signal_date,
                    exit_price=price, reason=reason, pnl_tl=pnl,
                    net_trade_return_pct=pnl/entry['entry_cost']*100))
                cash += proceeds
                quantity, entry = 0.0, None
        if quantity:
            exposure_days += 1
            entry['position_peak_close'] = max(entry['position_peak_close'],price)
            if trailing:
                entry['stop'] = max(entry['stop'],entry['position_peak_close']*0.95)
        if i == indices[-1] and quantity:
            proceeds = quantity*price*(1-COMMISSION)
            pnl = proceeds+entry['dividends']-entry['entry_cost']
            trades.append(dict(ticker=ticker, mode=mode,
                **entry, exit_date=row['date'], exit_signal_date=None, exit_price=price,
                reason='end_of_window_liquidation', pnl_tl=pnl,
                net_trade_return_pct=pnl/entry['entry_cost']*100))
            cash += proceeds
            quantity, entry = 0.0, None
        equity = cash+quantity*price*(1-COMMISSION)
        peak = max(peak, equity)
        drawdown = equity/peak-1
        max_drawdown = min(max_drawdown, drawdown)
        curve.append(dict(ticker=ticker, mode=mode,
            date=row['date'], equity_tl=equity, drawdown_pct=drawdown*100, shares=quantity,
            stop_tl=entry['stop'] if entry else None,
            pressure_target=active_targets['Baskı'],reference_target=active_targets['Referans']))
        if i == indices[-1]:
            continue
        if quantity:
            if price <= entry['stop']:
                pending = ('sell', row['date'], 'close_stop_breached',None,None)
            elif price > entry['take_profit_target']:
                pending = ('sell', row['date'], 'target_crossed',None,None)
        elif price < active_targets['Baskı'] and (not use_timing or timing_at(data,i,include_breakout=entry_rule=='pullback_or_breakout')['confirmed']):
            pending = ('buy', row['date'], entry_rule if use_timing else 'threshold_only',active_targets['Baskı'],active_targets['Referans'])
    # Identical dates, dividends and both-side costs in the passive comparison.
    first, last = data[indices[0]], data[indices[-1]]
    passive_shares = INITIAL/(first['close']*(1+COMMISSION))
    passive_end = passive_shares*last['close']*(1-COMMISSION)
    passive_end += passive_shares*sum(data[i]['dividends'] for i in indices[1:])
    wins = sum(t['pnl_tl'] > 0 for t in trades)
    profits = sum(max(t['pnl_tl'],0) for t in trades)
    losses = -sum(min(t['pnl_tl'],0) for t in trades)
    net_return = (cash/INITIAL-1)*100
    summary = dict(ticker=ticker, mode=mode, target_mode=target_mode, trailing=trailing,entry_rule=entry_rule,
        cancelled_gap_entries=cancelled_entries,
        start_date=first['date'], end_date=last['date'], trading_days=len(indices),
        initial_capital_tl=INITIAL, ending_capital_tl=cash, net_return_pct=net_return,
        buy_hold_net_return_pct=(passive_end/INITIAL-1)*100,
        max_drawdown_pct=max_drawdown*100, closed_trades=len(trades), winning_trades=wins,
        win_rate_pct=wins/len(trades)*100 if trades else None,
        profit_factor=profits/losses if losses else None,
        profit_factor_status='finite' if losses else ('no_losses' if profits else 'no_trades_or_no_profit'),
        exposure_pct=exposure_days/len(indices)*100,
        assessment='no_trades' if not trades else ('positive_counterfactual' if net_return>0 else 'nonpositive_counterfactual'),
        point_in_time_valid=False, strategy_profitability_validated=False)
    return summary,trades,curve,stages


def save_csv(path, rows):
    if not rows:
        path.write_text('ticker,mode,entry_date,exit_date,pnl_tl\n',encoding='utf-8-sig')
        return
    with path.open('w', newline='', encoding='utf-8-sig') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser(description='Bir yıllık karşı olgusal değerleme/zamanlama simülasyonu')
    parser.add_argument('--offline',action='store_true')
    args=parser.parse_args()
    targets=targets_from_report()
    summaries,trades,curves,stages=[],[],[],[]
    sources={}
    for ticker in TICKERS:
        data,info=daily_history(ticker,args.offline)
        sources[ticker]=dict(**info, history_sha256=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest())
        for target_mode in ['current_static','staged_price_proxy']:
            for trailing in [False,True]:
                for entry_rule in ['pullback_only','pullback_or_breakout']:
                    summary,t,c,st=simulate(ticker,data,targets[ticker],True,trailing,target_mode,entry_rule)
                    summaries.append(summary);trades.extend(t);curves.extend(c);stages.extend(st)
    market=ROOT/'data/market';reports=ROOT/'reports'
    market.mkdir(parents=True,exist_ok=True);reports.mkdir(exist_ok=True)
    save_csv(market/'backtest_summary.csv',summaries)
    save_csv(market/'backtest_trades.csv',trades)
    save_csv(market/'backtest_equity_curve.csv',curves)
    save_csv(market/'backtest_target_stages.csv',stages)
    lines=['# EconPilot — bir yıllık zamanlama ve stop simülasyonu','',
        '**Bugünkü varsayımsal hedefler geçmişe uygulanmıştır. Geçmişte bilinen finansal verilerle geçerli bir strateji testi değildir.**','',
        '| Hisse | Kural | Dönem | Net getiri | Al-tut net | Maksimum düşüş | İşlem | Başarı oranı | Kâr/zarar katsayısı |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|']
    print('Hisse | Kural | Net getiri | Al-tut | Max Drawdown | İşlem | Başarı | Kâr/zarar')
    for s in summaries:
        win=f"%{s['win_rate_pct']:.1f}" if s['win_rate_pct'] is not None else 'N/A'
        label=('Bugünkü hedef' if s['target_mode']=='current_static' else 'Aşamalı fiyat vekili')+' / '+('İz süren' if s['trailing'] else 'Sabit')+' / '+('Kesişim+kırılım' if s['entry_rule']=='pullback_or_breakout' else 'Kesişim')
        pf=f"{s['profit_factor']:.2f}" if s['profit_factor'] is not None else ('zarar yok' if s['profit_factor_status']=='no_losses' else 'N/A')
        print(f"{s['ticker']} | {label} | %{s['net_return_pct']:.2f} | %{s['buy_hold_net_return_pct']:.2f} | %{s['max_drawdown_pct']:.2f} | {s['closed_trades']} | {win} | {pf}")
        lines.append(f"| {s['ticker']} | {label} | {s['start_date']} – {s['end_date']} | %{s['net_return_pct']:.2f} | %{s['buy_hold_net_return_pct']:.2f} | %{s['max_drawdown_pct']:.2f} | {s['closed_trades']} | {win} | {pf} |")
    lines += ['', '## Kurallar ve sınırlılıklar','',
        '- SMA5 teyidi: önceki kapanış önceki 5 günlük ortalamanın altında/eşit; yeni kapanış yeni ortalamanın üstünde. Yalnız yukarı kesişim günü giriş sinyali.',
        '- İkinci giriş kuralı kesişime alternatif olarak kapanışın SMA5 üstünde ve önceki üç günün en yüksek kapanışından yüksek olmasını kabul eder. İki kural ayrı karşılaştırılır; sonuçlara göre otomatik en iyi kural seçilmez.',
        '- Sonraki kapanış alım bölgesinin dışına sıçrarsa bekleyen giriş iptal edilir. Girişte sinyal gününün hedefi sabitlenir; açık pozisyonun kâr al hedefi aylık vekille geriye dönük değiştirilmez.',
        '- Bu günlük kapanış karşılaştırması seans içi beş dakikalık bar, iki fiyat adımlık limit bandı veya yüzde 2 riskli ortak portföyün tam simülasyonu değildir; eski tam-sermaye yöntemiyle karşılaştırmadır.',
        '- Sinyal gününün kapanışı kullanılır; işlem izleyen işlem gününün kapanışında yapılır. Aynı kapanışta hem sinyal hem işlem yapılarak geleceği görme avantajı üretilmez.',
        '- Alışta ve satışta ayrı ayrı %0,2 komisyon. Her hisse ayrı 100.000 TL sermayeyle, tek pozisyon ve tam sermaye tahsisiyle simüle edilir. Portföy sonucu değildir.',
        '- Sabit stop girişin %5 altı; iz süren stop pozisyon açıldıktan sonraki en yüksek kapanışın %5 altıdır ve aşağı inmez. Günlük kapanış ihlali sonrası sonraki kapanışta çıkılır; günlük High değil Close zirvesi izlenir. Seans içi stop değildir; kayıp %5’i aşabilir.',
        '- Aşamalı fiyat vekili her ay ilk işlem gününde, yalnız önceki 63 kapanış ortalamasının 1,05/1,25 katıyla güncellenir. Katsayılar açık örnek varsayımdır. Güncel temel hedefleri kullanmaz; tarihi kâr veya adil değer ölçmez. Tarihi bilanço yayın zamanları eksik olduğundan aşamalı temel değerleme testi needs_source kalır.',
        '- Pencere sonunda açık pozisyon komisyonla kapatılır; bu çıkış işlem sayısı/başarı oranına dahildir.',
        '- Nakit temettü elde tutulan paylara eklenir. Yahoo Close ve temettü kullanılır; yeniden yatırma yoktur. Bölünme geçmişi sağlayıcının normalize ettiği fiyat/pay bazına dayanır, ayrı kurumsal işlem doğrulaması yoktur.',
        '- Max Drawdown günlük komisyon sonrası tasfiye değeri üzerinden, başlangıç sermayesi dahil önceki zirveye göre hesaplanır. Seans içi kaybı ölçmez.',
        '- Vergi, fiyat kayması, likidite, sermaye/işlem kısıtları, risksiz nakit getirisi ve enflasyon dikkate alınmadı.',
        '- Mevcut hedeflerin geçmişe uygulanması temel veride geleceği görme yanlılığı taşır. Yalnız iki seçilmiş şirketle, bir yıllık pozitif sonuç güvenilir kârlılık kanıtı değildir.',
        '', '## Neden Önemli?','',
        'Teyitli ve yalnız eşik kuralı aynı veri/komisyonla karşılaştırılır. İşlem günlüğü ve sermaye eğrisi sonucu izlenebilir kılar; kaynak tarihi bilinmeden strateji başarısı iddia edilmez.','']
    (reports/'backtest_summary.md').write_text('\n'.join(lines),encoding='utf-8')
    (reports/'backtest_manifest.json').write_text(json.dumps(dict(
        generated_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,targets=targets,
        target_report_sha256=hashlib.sha256(REPORT.read_bytes()).hexdigest(),
        commission_per_side=COMMISSION, stop_pct=5, initial_capital_per_ticker=INITIAL,
        execution='next_daily_close', target_modes=['current_static','staged_price_proxy'],
        entry_rules=['pullback_only','pullback_or_breakout'],take_profit='frozen_at_entry_signal',
        staged_proxy_policy=dict(prior_closes=63,pressure_factor=1.05,reference_factor=1.25,update='monthly'),
        historical_fundamental_targets='needs_source', point_in_time_valid=False,strategy_profitability_validated=False),
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('\nBugünkü eşiklerle geçmiş simülasyonu; sonuç strateji kârlılığını doğrulamaz.')
    print(f'Rapor: {reports/"backtest_summary.md"}')


if __name__=='__main__':
    main()
