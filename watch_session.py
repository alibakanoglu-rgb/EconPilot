"""Bounded foreground session observer for paper decisions; no scheduling or broker API."""
import argparse
from datetime import datetime, time as clock_time
from pathlib import Path
import json
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
TZ=ZoneInfo('Europe/Istanbul')
STATUS=ROOT/'reports/session_watch_status.json'
REPORT=ROOT/'reports/session_watch_summary.md'
LOCK=ROOT/'data/market/session_watch.lock'


def save_status(status):
    STATUS.parent.mkdir(exist_ok=True,parents=True)
    temporary=STATUS.with_suffix('.tmp')
    temporary.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(STATUS)
    lines=['# EconPilot — seans izleme durumu','',
        f"- Son güncelleme: {status['updated_at']}",
        f"- Durum: {status['status']}",
        f"- Tamamlanan gözlem: {status['completed_cycles']}",
        f"- Kontrol aralığı: {status['interval_seconds']} saniye",
        f"- Operasyonel pencere: {status['window_start']} – {status['window_end']} İstanbul saati, hafta içi",
        '- Resmî tatil ve özel seans takvimi doğrulanmadı; bu pencere yapılandırma varsayımıdır.',
        '- Gerçek emir gönderilmez. İzleme bu terminal açıkken çalışır; yeniden başlatma veya ertesi güne otomatik uyanma yoktur.',
        '- Seans dışında veri çağrısı yapılmaz. Eksik önceki kapanış veya eski fiyat kâğıt giriş oluşturmaz.',
        '- Ctrl+C izlemeyi durdurur; kâğıt hesabın durumu korunur. Açık kâğıt pozisyonlar otomatik kapatılmaz.',
        '', '## Son gözlem özeti','']
    for ticker,row in status.get('last_signals',{}).items():
        lines.append(f"- {ticker}: {row['signal']}; fiyat {row['price']:.2f} TL; veri zamanı {row['quote_time']}; {row['freshness']}.")
    if 'last_paper_summary' in status:
        p=status['last_paper_summary']
        lines.append(f"- Kâğıt hesap: {p['equity_tl']:.2f} TL; açık {p['positions']}, bekleyen {p['pending']}, kapanan {p['trades']}.")
    if status.get('paper_feed_block'):
        lines.append('- Kâğıt hesap engeli: '+status['paper_feed_block'])
    if status.get('last_error'):
        lines.append('- Son hata: '+status['last_error'])
    lines+=['','## Neden Önemli?','',
        'Bu çalıştırıcı aynı gözlem zincirini tekrar tekrar elle başlatma ihtiyacını azaltır. Tek süreç kilidi, son durum kaydı ve sınırlı hata tekrarları ile izlenebilir bir çalışma sağlar.','']
    REPORT.write_text('\n'.join(lines),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description='Seans içinde kâğıt karar izleme')
    parser.add_argument('--watch',action='store_true',help='Terminal açıkken pencere sonuna kadar tekrarla.')
    parser.add_argument('--interval',type=int,default=300,help='Gözlem aralığı; en az 60 saniye.')
    parser.add_argument('--max-cycles',type=int,default=0,help='Sıfır: pencere sonuna kadar; pozitif: gözlem sınırı.')
    parser.add_argument('--start',default='10:05',help='Operasyonel başlangıç HH:MM; resmî seans saati iddiası değil.')
    parser.add_argument('--end',default='17:55',help='Operasyonel bitiş HH:MM.')
    args=parser.parse_args()
    if args.interval<60 or args.max_cycles<0:
        parser.error('Aralık en az 60 saniye ve döngü sınırı sıfır/pozitif olmalı.')
    try:
        start=clock_time.fromisoformat(args.start);end=clock_time.fromisoformat(args.end)
    except ValueError:
        parser.error('Saat biçimi HH:MM olmalı.')
    if start>=end:
        parser.error('Başlangıç bitişten önce olmalı.')
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    try:
        descriptor=os.open(LOCK,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError('Başka seans izleyici veya eski kilit var; süreç durumu incelenmeden ikinci izleyici açılmaz.')
    os.write(descriptor,json.dumps(dict(pid=os.getpid(),started_at=datetime.now(TZ).isoformat())).encode())
    os.close(descriptor)
    status=dict(status='starting',started_at=datetime.now(TZ).isoformat(),updated_at=datetime.now(TZ).isoformat(),
        completed_cycles=0,consecutive_failures=0,interval_seconds=args.interval,
        window_start=args.start,window_end=args.end,exchange_calendar_verified=False,
        mode='foreground_watch' if args.watch else 'single_observation')
    outcome=0
    try:
        while True:
            now=datetime.now(TZ)
            status['updated_at']=now.isoformat()
            if now.weekday()>4 or not start<=now.time()<end:
                status['status']='outside_observation_window'
                save_status(status)
                print(f"{now:%Y-%m-%d %H:%M}: izleme penceresi dışında. Ağ çağrısı yapılmadı.")
                break
            status['status']='observing';save_status(status)
            print(f"\n{now:%H:%M:%S} — güncel fiyat ve kâğıt kayıt",flush=True)
            try:
                result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'execution_trigger.py')],
                    cwd=ROOT,timeout=120,check=False)
                if result.returncode:
                    raise RuntimeError('Karar zinciri çıkış kodu '+str(result.returncode))
                snapshot=json.loads((ROOT/'data/market/execution_trigger_latest.json').read_text(encoding='utf-8'))
                # Unknown feed latency may be observed, but cannot enter the paper ledger.
                feed_verified=bool(snapshot['rows']) and all(
                    row.get('feed_latency_verified') is True for row in snapshot['rows'])
                if feed_verified:
                    from paper_trading import record_snapshot
                    record_snapshot(snapshot)
                    status.pop('paper_feed_block',None)
                else:
                    status['paper_feed_block']='feed_latency_not_verified'
                    print('KÂĞIT HESAP ENGELİ: fiyat akışının gecikmesi doğrulanmadı; hesaba işlem aktarılmadı.',flush=True)
                paper=json.loads((ROOT/'data/market/paper_trading_state.json').read_text(encoding='utf-8'))
                status['last_signals']={r['ticker']:{key:r[key] for key in ['signal','price','quote_time','freshness']} for r in snapshot['rows']}
                status['last_paper_summary']=dict(equity_tl=paper['equity_tl'],positions=len(paper['positions']),
                    pending=len(paper['pending']),trades=len(paper['trades']))
                review=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'build_forward_review.py')],
                    cwd=ROOT,timeout=30,check=False)
                if review.returncode:
                    raise RuntimeError('İleri değerlendirme raporu çıkış kodu '+str(review.returncode))
                status['completed_cycles']+=1;status['consecutive_failures']=0
                status.pop('last_error',None)
            except (subprocess.TimeoutExpired,RuntimeError,ValueError,OSError,KeyError) as error:
                status['consecutive_failures']+=1
                status['last_error']=type(error).__name__+': '+str(error)
                print('Gözlem tamamlanamadı: '+status['last_error'])
                if status['consecutive_failures']>=3 or not args.watch:
                    status['status']='failed';outcome=1;break
            status['updated_at']=datetime.now(TZ).isoformat()
            status['status']='waiting' if args.watch else 'completed'
            save_status(status)
            if not args.watch or (args.max_cycles and status['completed_cycles']>=args.max_cycles):
                status['status']='completed';break
            remaining=(datetime.combine(datetime.now(TZ).date(),end,tzinfo=TZ)-datetime.now(TZ)).total_seconds()
            if remaining<=0:
                status['status']='window_finished';break
            time.sleep(min(args.interval,remaining))
    except KeyboardInterrupt:
        status['status']='stopped_by_user'
        print('\nİzleme durdu; kâğıt kayıt korundu.')
    finally:
        status['updated_at']=datetime.now(TZ).isoformat()
        save_status(status)
        LOCK.unlink()
    # Outside-session runs may refresh the read-only report without fetching prices.
    if status['completed_cycles']==0 and (ROOT/'data/market/paper_strategy_baseline.json').exists():
        review=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'build_forward_review.py')],
            cwd=ROOT,timeout=30,check=False)
        if review.returncode:
            outcome=1
    print(f'Durum raporu: {REPORT}')
    return outcome


if __name__=='__main__':
    sys.exit(main())
