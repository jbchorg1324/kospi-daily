import json
import math
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo('Asia/Seoul')
NOW = datetime.now(TZ)
TODAY = NOW.date()
END_DATE = datetime(2026, 12, 31, tzinfo=TZ).date()
CAPITAL = 1_000_000
STOCKS = {
    '005930.KS': '삼성전자', '000660.KS': 'SK하이닉스', '005380.KS': '현대차',
    '000270.KS': '기아', '035420.KS': 'NAVER', '068270.KS': '셀트리온',
    '055550.KS': '신한지주', '105560.KS': 'KB금융', '086790.KS': '하나금융지주',
    '012330.KS': '현대모비스', '034020.KS': '두산에너빌리티',
    '066570.KS': 'LG전자', '032830.KS': '삼성생명', '009150.KS': '삼성전기',
    '010130.KS': '고려아연', '018260.KS': '삼성에스디에스',
    '017670.KS': 'SK텔레콤', '030200.KS': 'KT', '003550.KS': 'LG',
    '051900.KS': 'LG생활건강', '005490.KS': 'POSCO홀딩스',
    '015760.KS': '한국전력', '024110.KS': '기업은행', '010950.KS': 'S-Oil'
}


def tick(price):
    if price < 2000: return 1
    if price < 5000: return 5
    if price < 20000: return 10
    if price < 50000: return 50
    if price < 200000: return 100
    if price < 500000: return 500
    return 1000


def round_tick(x, direction='nearest'):
    x = max(1, x)
    for _ in range(5):
        t = tick(x)
        y = (math.floor(x/t) if direction == 'down' else math.ceil(x/t) if direction == 'up' else round(x/t)) * t
        if tick(y) == t:
            return int(y)
        x = y
    return int(y)


class ScanSkipped(Exception):
    def __init__(self, category, reason, observation=None):
        super().__init__(reason)
        self.category = category
        self.reason = reason
        self.observation = observation


def skip(category, reason, observation=None):
    raise ScanSkipped(category, reason, observation)


def scan(ticker, name):
    history = yf.Ticker(ticker).history(period='5mo', interval='1d', auto_adjust=False, raise_errors=False)
    if history is None or history.empty:
        skip('DATA_ERROR', '가격 데이터가 비어 있음')
    required = ['Open', 'High', 'Low', 'Close', 'Volume']
    if not all(c in history.columns for c in required):
        skip('DATA_ERROR', '가격 데이터 열 누락')
    df = history[required].dropna().copy()
    try:
        ix = pd.to_datetime(df.index)
        if ix.tz is not None:
            ix = ix.tz_convert(TZ).tz_localize(None)
        df.index = ix.normalize()
    except (ValueError, TypeError, AttributeError) as exc:
        skip('DATA_ERROR', f'날짜 변환 실패: {exc}')
    # Pre-market screener: only use completed sessions before today's KST date.
    df = df[df.index.date < TODAY]
    if len(df) < 51:
        skip('DATA_ERROR', f'분석 기간 부족({len(df)}거래일)')
    dt = df.index[-1].date()
    if (TODAY-dt).days > 4:
        skip('DATA_ERROR', f'최근 데이터 오래됨(최신 {dt})')
    close = float(df.Close.iloc[-1])
    vol = float(df.Volume.iloc[-1])
    avgvol = float(df.Volume.iloc[-21:-1].mean())
    if not all(math.isfinite(v) for v in (close, vol, avgvol)) or close <= 0 or vol <= 0 or avgvol <= 0:
        skip('DATA_ERROR', '가격·거래량 값 오류')
    ma5 = float(df.Close.tail(5).mean())
    ma20 = float(df.Close.tail(20).mean())
    ma50 = float(df.Close.tail(50).mean())
    prevclose = df.Close.shift(1)
    tr = pd.concat([df.High-df.Low, (df.High-prevclose).abs(), (df.Low-prevclose).abs()], axis=1).max(axis=1)
    atr = float(tr.tail(14).mean())
    ratio = atr / close
    momentum5 = close/float(df.Close.iloc[-6])-1
    momentum20 = close/float(df.Close.iloc[-21])-1
    relative_vol = vol/avgvol
    if not all(math.isfinite(v) for v in (ma5,ma20,ma50,atr,ratio,momentum5,momentum20,relative_vol)):
        skip('DATA_ERROR', '지표 계산 오류')
    # 관찰 점수는 우선순위 표시용 규칙 점수일 뿐, 기대수익률이나 매수 확률이 아님.
    score = (30 if close >= ma20 else 0) + (20 if ma5 >= ma20 else 0) + \
            (15 if momentum5 >= -.02 else 0) + (15 if -.08 <= momentum20 <= .26 else 0) + \
            (10 if relative_vol >= .55 else 0) + (10 if .011 <= ratio <= .085 else 0)
    obs = dict(ticker=ticker.split('.')[0], name=name, date=str(dt), close=int(round(close)),
               score=int(score), momentum5=round(momentum5*100,2),
               volume_ratio=round(relative_vol,2), atr_percent=round(ratio*100,2),
               status='WATCH', reason='')
    fails=[]
    if close < 2000 or close > CAPITAL: fails.append('주가가 분석 허용 범위 밖')
    if not (.011 <= ratio <= .085): fails.append('ATR 변동성 조건 미충족')
    if close < ma20 or ma5 < ma20 or momentum5 < -.02 or momentum20 < -.08 or momentum20 > .26:
        fails.append('이동평균·모멘텀 조건 미충족')
    if relative_vol < .55: fails.append('거래량 조건 미충족')
    if fails:
        obs['reason']=' / '.join(fails)
        skip('FILTERED', fails[0], obs)
    entry = round_tick(close, 'nearest')
    target = round_tick(entry+max(1.4*atr,entry*.018), 'up')
    stop = round_tick(entry-max(1.0*atr,entry*.012), 'down')
    qty = int(CAPITAL//entry)
    if qty < 1 or stop <= 0 or target <= entry or stop >= entry:
        skip('FILTERED', '매수가·목표가·손절가 조건 미충족', obs)
    obs['status']='PASS'
    obs['reason']='모든 필터 통과'
    return dict(ticker=ticker.split('.')[0], name=name, close=int(round(close)), date=str(dt),
                entry=entry, target=target, stop=stop, qty=qty, cost=qty*entry,
                cash=CAPITAL-qty*entry, profit=(target-entry)*qty, loss=(entry-stop)*qty,
                score=score, atr_percent=round(ratio*100,2), volume_ratio=round(relative_vol,2),
                momentum5=round(momentum5*100,2), ma20=int(round(ma20)),
                reason=f'전일 종가가 20일 이동평균선 위, 최근 5일 수익률 {momentum5*100:+.1f}%, 거래량/20일 평균 {relative_vol:.2f}배')


def main():
    result = dict(watchlist=[], asof=NOW.strftime('%Y-%m-%d %H:%M KST'), date=str(TODAY),
                  deadline=str(END_DATE), capital=CAPITAL, status='WAIT',
                  reason='데이터 검증 중', selection=None, alternatives=[],
                  method='전일 종가 기반 추세·거래량·ATR 필터. 추천은 거래 체결을 의미하지 않으며 장 시작 전 재확인 필요.')
    diagnostics = dict(total=len(STOCKS), data_ok=0, data_error=0,
                       filtered=0, candidates=0, reasons={}, details=[])
    if TODAY > END_DATE:
        result.update(status='ENDED', reason='프로젝트 종료일이 지났습니다.')
    elif TODAY.weekday() >= 5:
        result.update(status='WAIT', reason='주말: 국내 주식시장 휴장')
    else:
        picks = []
        watchlist = []
        reasons = Counter()
        for ticker, name in STOCKS.items():
            code = ticker.split('.')[0]
            try:
                row = scan(ticker, name)
                diagnostics['data_ok'] += 1
                picks.append(row)
                watchlist.append(dict(ticker=code, name=name, score=100, status='PASS', reason='모든 필터 통과',date=row['date'],close=row['close'],momentum5=row['momentum5'],volume_ratio=row['volume_ratio'],atr_percent=row['atr_percent']))
                print(f'PASS {code} {name}')
            except ScanSkipped as exc:
                if exc.category == 'DATA_ERROR':
                    diagnostics['data_error'] += 1
                else:
                    diagnostics['data_ok'] += 1
                    diagnostics['filtered'] += 1
                reasons[exc.reason] += 1
                if exc.observation is not None: watchlist.append(exc.observation)
                diagnostics['details'].append(dict(ticker=code, name=name, status=exc.category, reason=exc.reason))
                print(f'{exc.category} {code} {name}: {exc.reason}')
            except Exception as exc:
                diagnostics['data_error'] += 1
                why = f'예외 {type(exc).__name__}: {str(exc)[:160]}'
                reasons[why] += 1
                diagnostics['details'].append(dict(ticker=code, name=name, status='DATA_ERROR', reason=why))
                print(f'DATA_ERROR {code} {name}: {why}')
        # 데이터 정상 종목 중 관찰 점수 상위 3개를 매수 추천과 별개로 공개
        watchlist.sort(key=lambda x:(x['score'], x['momentum5']), reverse=True)
        result['watchlist'] = watchlist[:3]
        diagnostics['candidates'] = len(picks)
        diagnostics['reasons'] = dict(reasons)
        picks.sort(key=lambda x: x['score'], reverse=True)
        # If most of the universe failed to load, avoid showing a potentially misleading top pick.
        if diagnostics['data_ok'] < max(1, len(STOCKS)//2):
            result.update(status='DATA_ERROR', reason=f'주가 데이터 정상 조회 {diagnostics["data_ok"]}/{len(STOCKS)}개. 데이터 부족으로 추천 중단.')
        elif picks:
            for p in picks:
                p.pop('score', None)
            result.update(status='CANDIDATE', reason='전일 종가 기준 조건을 통과한 종목 중 상위 1개',
                          selection=picks[0], alternatives=picks[1:4])
        else:
            result.update(status='WAIT', reason=f'{diagnostics["data_ok"]}개 종목의 데이터를 확인했으나 매수 조건을 통과한 종목이 없습니다.')
    result['diagnostics'] = diagnostics
    (ROOT/'data.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SUMMARY', json.dumps({k:v for k,v in diagnostics.items() if k!='details'}, ensure_ascii=False))
    print(result['status'], result['reason'], (result['selection'] or {}).get('name'))


if __name__ == '__main__':
    main()
