"""Read-only assessment of the frozen experiment; no trades or rules are changed."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

from risk_rules import quote_guard

ROOT=Path(__file__).resolve().parent
MARKET=ROOT/'data/market'
REPORTS=ROOT/'reports'


def stamp(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:
        raise ValueError('Missing timestamp timezone')
    return result


def main():
    baseline_path=MARKET/'paper_strategy_baseline.json'
    state_path=MARKET/'paper_trading_state.json'
    journal_path=MARKET/'execution_decision_journal.jsonl'
    baseline=json.loads(baseline_path.read_text(encoding='utf-8'))
    state=json.loads(state_path.read_text(encoding='utf-8'))
    frozen=stamp(baseline['frozen_at'])
    changed=[]
    for name,expected in baseline['strategy']['rule_code_hashes'].items():
        path=ROOT/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            changed.append(name)
    epoch_matches=state.get('strategy_id')==baseline['strategy_id']
    tickers=sorted(baseline['strategy']['targets'])
    data={t:dict(samples=0,bars=set(),days=set(),repeated=0,reasons=Counter(),latest_quote=None) for t in tickers}
    excluded_runs=0;malformed_lines=0;partial_lines=0;accepted_runs=0;wrong_rule_rows=0
    with journal_path.open(encoding='utf-8') as handle:
        for line in handle:
            if not line.endswith('\n'):
                partial_lines+=1
                continue
            try:
                run=json.loads(line)
                observed=stamp(run['evaluated_at'])
                if observed<frozen:
                    excluded_runs+=1
                    continue
                accepted_runs+=1
                for row in run['rows']:
                    ticker=row['ticker']
                    if ticker not in data:
                        continue
                    d=data[ticker];d['samples']+=1
                    if any(run.get('rule_code_hashes',{}).get(path)!=expected
                           for path,expected in baseline['strategy']['rule_code_hashes'].items()
                           if path in {'execution_trigger.py','timing_rules.py','order_plan.py'}):
                        d['reasons']['rule_version_mismatch']+=1;wrong_rule_rows+=1
                        continue
                    reason=quote_guard(row,observed)
                    if reason:
                        d['reasons'][reason]+=1
                        continue
                    quote=row['quote_time']
                    if quote in d['bars']:
                        d['repeated']+=1
                        continue
                    d['bars'].add(quote);d['days'].add(stamp(quote).date().isoformat())
                    d['latest_quote']=max(d['latest_quote'] or quote,quote)
            except (ValueError,KeyError,TypeError):
                malformed_lines+=1
    # Exclude any trades predating the frozen epoch, without rewriting the ledger.
    trades=[t for t in state['trades'] if stamp(t['entry_observed_at'])>=frozen]
    winners=sum(t['pnl_tl']>0 for t in trades)
    realized=sum(t['pnl_tl'] for t in trades)
    days=set().union(*(d['days'] for d in data.values()))
    enough_for_review=len(days)>=20 and len(trades)>=20
    status='needs_more_observations'
    if changed or not epoch_matches or wrong_rule_rows:
        status='strategy_version_mismatch'
    elif malformed_lines:
        status='journal_integrity_needs_review'
    elif enough_for_review:
        status='ready_for_descriptive_review_not_validation'
    rows=[]
    for ticker,d in data.items():
        counts=Counter(t['reason'] for t in trades if t['ticker']==ticker)
        rows.append(dict(ticker=ticker,observation_rows=d['samples'],unique_fresh_bars=len(d['bars']),
            unique_observed_days=len(d['days']),repeated_fresh_bars=d['repeated'],
            rejected_rows=dict(d['reasons']),latest_fresh_bar=d['latest_quote'],closed_trades=sum(counts.values()),
            exit_reasons=dict(counts)))
    summary=dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),
        frozen_at=baseline['frozen_at'],strategy_id=baseline['strategy_id'],status=status,
        code_changes=changed,ledger_epoch_matches=epoch_matches,
        post_freeze_runs=accepted_runs,pre_freeze_runs_excluded=excluded_runs,
        malformed_journal_lines=malformed_lines,partial_lines_deferred=partial_lines,
        rows=rows,closed_post_freeze_trades=len(trades),realized_paper_pnl_tl=realized if trades else None,
        win_rate_pct=winners/len(trades)*100 if trades else None,
        observed_days=len(days),descriptive_review_gate=dict(min_days=20,min_closed_trades=20,
            is_statistical_confidence_guarantee=False),strategy_profitability_validated=False)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS/'forward_review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# EconPilot — ileri gözlem değerlendirmesi','',
        f"**Durum:** {status}; deney sürümü `{baseline['strategy_id'][:16]}`.",
        f"**Dondurma tarihi:** {baseline['frozen_at']}. Önceki {excluded_runs} çalışma yeni deneye karıştırılmadı.",
        '', '## Gözlem kapsamı','',
        '| Hisse | Kaydedilen görüntü | Benzersiz güncel bar | Gözlenen gün | Kapanan işlem |',
        '|---|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['ticker']} | {r['observation_rows']} | {r['unique_fresh_bars']} | {r['unique_observed_days']} | {r['closed_trades']} |")
    lines+=['','## Sonuç değerlendirmesi','',
        '- Gerçekleşmiş kâğıt kâr/zararı: '+(f'{realized:,.2f} TL' if trades else 'hesaplanamaz — kapanan işlem yok'),
        '- Başarı oranı: '+(f'%{winners/len(trades)*100:.1f}' if trades else 'hesaplanamaz — kapanan işlem yok'),
        f'- Betimleyici inceleme eşiği: en az 20 gözlenen gün ve 20 kapanan işlem; şu an {len(days)} gün / {len(trades)} işlem.',
        '- Bu eşik rutin inceleme için örnek başlangıç ölçütüdür; istatistiksel güven, yatırım önerisi veya kârlılık onayı değildir.',
        '- Gözlenen gün sayısı tam seans kapsandığı anlamına gelmez. Eksik/kaçırılan barlar yeni fiyatmış gibi doldurulmaz.',
        '', '## Veri ve kural kontrolü','',
        f'- Mevcut kodun dondurulmuş sürümle uyumu: {"eşleşti" if not changed else "UYUŞMAZLIK: "+", ".join(changed)}.',
        f'- Kâğıt hesap deney kimliği: {"eşleşti" if epoch_matches else "UYUŞMAZLIK"}.',
        f'- Bozuk kayıt satırı: {malformed_lines}; yazımı tamamlanmamış ve ertelenen satır: {partial_lines}.']
    for r in rows:
        lines.append(f"- {r['ticker']} reddedilen gözlemler: {r['rejected_rows'] or 'yok'}; tekrar bar: {r['repeated_fresh_bars']}.")
    lines+=['','## Kullanım sınırı','',
        'Bu rapor dosyaları yalnız okur; giriş/çıkış, hedef veya risk kuralını değiştirmez. Eski backtest kârları ileri hesaba eklenmez. Temettü, bölünme, kayma, gerçek dolum ve tüm seans kapsamı doğrulanmış değildir.',
        'Yeterli gerçek ileri gözlem toplanmadan hangi stratejinin kârlı olduğu seçilmez. Kod sürümü veya defter uyumsuzsa önce bu fark çözülür.',
        '', '## Neden Önemli?','',
        'Bu değerlendirme kaç veri ve işlemle konuştuğumuzu görünür kılar. Tek kazançlı işlem veya tekrar eden fiyat görüntüsüyle yanlış başarı sonucu çıkarılmasını önler.','']
    (REPORTS/'forward_review.md').write_text('\n'.join(lines),encoding='utf-8')
    print(f'İleri değerlendirme: {status} | {len(days)} gözlenen gün | {len(trades)} kapanan işlem')
    print(f'Rapor: {REPORTS/"forward_review.md"}')


if __name__=='__main__':
    main()
