"""Keep an auditable, non-trading record of published stock-screening signals.

Runs after generate.py. history.json MUST be committed to git for persistence.
Signals are stored once per signal date/ticker, without rewriting initial prices.
Returns are close-to-close price observations, NOT executable trading performance.
"""
from __future__ import annotations
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import yfinance as yf

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / 'history.json'
SUMMARY = ROOT / 'performance.json'
SIGNAL = ROOT / 'data.json'
TODAY = datetime.now(ZoneInfo('Asia/Seoul')).date()
HORIZONS = (1, 5, 20)

def load(path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'{path.name} 파일을 읽을 수 없습니다. 기존 기록 보존을 위해 실행 중단: {exc}') from exc

def prices_for(ticker):
    df = yf.Ticker(ticker + '.KS').history(period='8mo', interval='1d', auto_adjust=False, raise_errors=False)
    if df is None or df.empty or 'Close' not in df.columns:
        raise ValueError('주가 데이터가 비었습니다')
    series = df['Close'].dropna()
    result = {}
    for day, value in series.items():
        day = day.date() if hasattr(day, 'date') else date.fromisoformat(str(day)[:10])
        if day <= TODAY and float(value)>0:
            result[day.isoformat()] = float(value)
    return result

def main():
    incoming = load(SIGNAL, {})
    saved = load(HISTORY, {'version':1, 'records':[]})
    if not isinstance(saved, dict) or not isinstance(saved.get('records'), list):
        raise RuntimeError('history.json 형식 오류: 기존 기록은 절대 덮어쓰지 않습니다')
    records = saved['records']
    known = {(str(r.get('signal_date')),str(r.get('ticker'))) for r in records}

    # Record the TOP 3 technical shortlist once on the day it was published.
    # Never turn past WAIT signals into hypothetical recommendations.
    signal_date = str(incoming.get('date',''))
    new_rows = 0
    if incoming.get('status') == 'CANDIDATE' and signal_date == TODAY.isoformat():
        shortlist = incoming.get('short_term', [])
        if not shortlist and incoming.get('selection'):
            shortlist = [incoming['selection']]
        for rank, p in enumerate(shortlist[:3], 1):
            ticker = str(p.get('ticker',''))
            key = (signal_date, ticker)
            if not ticker or key in known: continue
            if not p.get('close') or not p.get('date'): continue
            records.append({
                'signal_date':signal_date, 'rank':rank, 'ticker':ticker,
                'name':str(p.get('name','')), 'reference_date':str(p['date']),
                'reference_close':float(p['close']), 'suggested_entry':p.get('entry'),
                'target':p.get('target'), 'stop':p.get('stop'),
                'horizons':{}, 'tracking_note':'추천 생성일 이후 1/5/20거래일 종가 변화. 매매 체결 결과 아님.'
            })
            known.add(key); new_rows += 1

    # A signal's origin close is the PRE-SIGNAL reference day; do not use it
    # as if the specified order executed at that price. Return measures change
    # from reference close to the Nth completed session AFTER signal date.
    tickers = sorted({r['ticker'] for r in records if any(str(h) not in r.get('horizons',{}) for h in HORIZONS)})
    caches = {}
    for ticker in tickers:
        try: caches[ticker] = prices_for(ticker)
        except Exception as exc: print('TRACK_PRICE_ERROR',ticker,type(exc).__name__,str(exc)[:100])
    for r in records:
        series = caches.get(r['ticker'])
        if not series: continue
        session_dates = sorted(d for d in series if d > r['signal_date'])
        for n in HORIZONS:
            if str(n) in r.setdefault('horizons',{}): continue
            if len(session_dates) < n: continue
            asof = session_dates[n-1]
            # Exclude current ongoing trading session; cannot use incomplete closes.
            if asof >= TODAY.isoformat(): continue
            observed = series[asof]
            base = float(r['reference_close'])
            r['horizons'][str(n)] = {'date':asof, 'close':round(observed,2),
                'return_pct':round((observed/base - 1)*100,3)}
    saved['updated_at'] = datetime.now(ZoneInfo('Asia/Seoul')).isoformat()
    saved['version'] = 1
    HISTORY.write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    stats = {}
    for n in HORIZONS:
        vals = [float(r['horizons'][str(n)]['return_pct']) for r in records if str(n) in r.get('horizons',{})]
        stats[str(n)] = {'evaluated':len(vals),'average_return_pct':round(sum(vals)/len(vals),3) if vals else None,
                         'positive_rate_pct':round(sum(v>0 for v in vals)/len(vals)*100,1) if vals else None}
    result = {'updated_at':saved['updated_at'], 'total_signals':len(records), 'new_signals':new_rows,
              'stats':stats,'recent':list(reversed(records[-30:])),
              'note':'전일 종가 기준 추천 후 1/5/20거래일 가격 변화. 거래 체결·비용·배당·액면분할 보정·벤치마크를 반영하지 않으며 실현수익률이 아닙니다.'}
    SUMMARY.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TRACK_SUMMARY','records',len(records),'new',new_rows,'completed',[(n,stats[str(n)]['evaluated']) for n in HORIZONS])

if __name__ == '__main__': main()
