import json
import math
from datetime import datetime, timedelta
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
 '005930.KS':'삼성전자','000660.KS':'SK하이닉스','005380.KS':'현대차',
 '000270.KS':'기아','035420.KS':'NAVER','068270.KS':'셀트리온',
 '055550.KS':'신한지주','105560.KS':'KB금융','086790.KS':'하나금융지주',
 '012330.KS':'현대모비스','034020.KS':'두산에너빌리티',
 '066570.KS':'LG전자','032830.KS':'삼성생명','009150.KS':'삼성전기',
 '010130.KS':'고려아연','018260.KS':'삼성에스디에스',
 '017670.KS':'SK텔레콤','030200.KS':'KT','003550.KS':'LG',
 '051900.KS':'LG생활건강','005490.KS':'POSCO홀딩스',
 '015760.KS':'한국전력','024110.KS':'기업은행','010950.KS':'S-Oil'
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
        if tick(y) == t: return int(y)
        x = y
    return int(y)

def scan(ticker, name):
    history = yf.Ticker(ticker).history(period='5mo', interval='1d', auto_adjust=False, raise_errors=False)
    if history is None or len(history) < 55: return None
    df = history[['Open','High','Low','Close','Volume']].dropna().copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    # Premarket strategy: use only sessions completed before today's Korean session.
    df = df[df.index.date < TODAY]
    if len(df) < 51: return None
    dt = df.index[-1].date()
    if (TODAY-dt).days > 4: return None
    close=float(df.Close.iloc[-1]); vol=float(df.Volume.iloc[-1]); avgvol=float(df.Volume.iloc[-21:-1].mean())
    if close < 2000 or close > CAPITAL or vol <= 0 or avgvol <= 0: return None
    ma5=float(df.Close.tail(5).mean()); ma20=float(df.Close.tail(20).mean()); ma50=float(df.Close.tail(50).mean())
    prevclose=df.Close.shift(1)
    tr=pd.concat([df.High-df.Low,(df.High-prevclose).abs(),(df.Low-prevclose).abs()],axis=1).max(axis=1)
    atr=float(tr.tail(14).mean()); ratio=atr/close
    if not (.011 <= ratio <= .085): return None
    momentum5=close/float(df.Close.iloc[-6])-1
    momentum20=close/float(df.Close.iloc[-21])-1
    # Avoid heavily extended and plunging shares. Require constructive trend.
    if close < ma20 or ma5 < ma20 or momentum5 < -.02 or momentum20 < -.08 or momentum20 > .26: return None
    relative_vol=vol/avgvol
    if relative_vol < .55: return None
    score=2.0*(close/ma20-1)+1.4*momentum5+.6*momentum20+.018*min(relative_vol,2)+.02*(ma20/ma50-1)
    entry=round_tick(close, 'nearest')
    target=round_tick(entry+max(1.4*atr,entry*.018), 'up')
    stop=round_tick(entry-max(1.0*atr,entry*.012), 'down')
    qty=int(CAPITAL//entry)
    if qty < 1 or stop <= 0 or target <= entry or stop >= entry: return None
    return dict(ticker=ticker.split('.')[0],name=name,close=int(round(close)),date=str(dt),entry=entry,target=target,stop=stop,qty=qty,cost=qty*entry,cash=CAPITAL-qty*entry,profit=(target-entry)*qty,loss=(entry-stop)*qty,score=score,atr_percent=round(ratio*100,2),volume_ratio=round(relative_vol,2),momentum5=round(momentum5*100,2),ma20=int(round(ma20)),reason=f'전일 종가가 20일 이동평균선 위, 최근 5일 수익률 {momentum5*100:+.1f}%, 거래량/20일 평균 {relative_vol:.2f}배')

def main():
    result=dict(asof=NOW.strftime('%Y-%m-%d %H:%M KST'),date=str(TODAY),deadline=str(END_DATE),capital=CAPITAL,status='WAIT',reason='데이터 검증 중',selection=None,alternatives=[],method='전일 종가 기반 추세·거래량·ATR 필터. 추천은 거래 체결을 의미하지 않으며 장 시작 전 재확인 필요.')
    if TODAY > END_DATE:
        result.update(status='ENDED',reason='프로젝트 종료일이 지났습니다.')
    elif TODAY.weekday() >= 5:
        result.update(status='WAIT',reason='주말: 국내 주식시장 휴장')
    else:
        picks=[]
        for ticker,name in STOCKS.items():
            try:
                row=scan(ticker,name)
                if row: picks.append(row)
            except Exception as exc:
                print(f'WARNING {ticker}: {exc}')
        picks.sort(key=lambda x:x['score'],reverse=True)
        if picks:
            for p in picks: p.pop('score',None)
            result.update(status='CANDIDATE',reason='전일 종가 기준 조건을 통과한 종목 중 상위 1개',selection=picks[0],alternatives=picks[1:4])
        else:
            result.update(status='WAIT',reason='조건 충족 종목 없음 또는 가격 데이터 조회 실패. 거래 권고 없음.')
    (ROOT/'data.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(result['status'],result['reason'],(result['selection'] or {}).get('name'))

if __name__=='__main__': main()
