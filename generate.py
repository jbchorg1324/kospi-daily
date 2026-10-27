import json
import math
from collections import Counter
import time
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
    '005930.KS': '삼성전자',
    '000660.KS': 'SK하이닉스',
    '005380.KS': '현대차',
    '000270.KS': '기아',
    '035420.KS': 'NAVER',
    '068270.KS': '셀트리온',
    '055550.KS': '신한지주',
    '105560.KS': 'KB금융',
    '086790.KS': '하나금융지주',
    '012330.KS': '현대모비스',
    '034020.KS': '두산에너빌리티',
    '066570.KS': 'LG전자',
    '032830.KS': '삼성생명',
    '009150.KS': '삼성전기',
    '010130.KS': '고려아연',
    '018260.KS': '삼성에스디에스',
    '017670.KS': 'SK텔레콤',
    '030200.KS': 'KT',
    '003550.KS': 'LG',
    '051900.KS': 'LG생활건강',
    '005490.KS': 'POSCO홀딩스',
    '015760.KS': '한국전력',
    '024110.KS': '기업은행',
    '010950.KS': 'S-Oil',
    '207940.KS': '삼성바이오로직스',
    '373220.KS': 'LG에너지솔루션',
    '000810.KS': '삼성화재',
    '033780.KS': 'KT&G',
    '096770.KS': 'SK이노베이션',
    '003670.KS': '포스코퓨처엠',
    '006400.KS': '삼성SDI',
    '051910.KS': 'LG화학',
    '003490.KS': '대한항공',
    '028260.KS': '삼성물산',
    '090430.KS': '아모레퍼시픽',
    '316140.KS': '우리금융지주',
    '138040.KS': '메리츠금융지주',
    '004020.KS': '현대제철',
    '011200.KS': 'HMM',
    '009540.KS': 'HD한국조선해양',
    '010140.KS': '삼성중공업',
    '042660.KS': '한화오션',
    '329180.KS': 'HD현대중공업',
    '267250.KS': 'HD현대',
    '081660.KS': '휠라홀딩스',
    '047810.KS': '한국항공우주',
    '012450.KS': '한화에어로스페이스',
    '079550.KS': 'LIG넥스원',
    '000880.KS': '한화',
    '005830.KS': 'DB손해보험',
    '001450.KS': '현대해상',
    '071050.KS': '한국금융지주',
    '006800.KS': '미래에셋증권',
    '016360.KS': '삼성증권',
    '039490.KS': '키움증권',
    '011070.KS': 'LG이노텍',
    '008770.KS': '호텔신라',
    '004170.KS': '신세계',
    '139480.KS': '이마트',
    '023530.KS': '롯데쇼핑',
    '097950.KS': 'CJ제일제당',
    '271560.KS': '오리온',
    '004370.KS': '농심',
    '007310.KS': '오뚜기',
    '280360.KS': '롯데웰푸드',
    '000080.KS': '하이트진로',
    '000100.KS': '유한양행',
    '128940.KS': '한미약품',
    '185750.KS': '종근당',
    '069620.KS': '대웅제약',
    '326030.KS': 'SK바이오팜',
    '302440.KS': 'SK바이오사이언스',
    '192820.KS': '코스맥스',
    '161890.KS': '한국콜마',
    '002790.KS': '아모레G',
    '009830.KS': '한화솔루션',
    '011170.KS': '롯데케미칼',
    '006260.KS': 'LS',
    '010120.KS': 'LS ELECTRIC',
    '298040.KS': '효성중공업',
    '000720.KS': '현대건설',
    '047040.KS': '대우건설',
    '006360.KS': 'GS건설',
    '028050.KS': '삼성E&A',
    '009420.KS': '한올바이오파마',
    '001040.KS': 'CJ',
    '001740.KS': 'SK네트웍스',
    '034730.KS': 'SK',
    '003230.KS': '삼양식품',
    '069960.KS': '현대백화점',
    '020150.KS': '롯데에너지머티리얼즈',
    '000150.KS': '두산',
    '078930.KS': 'GS',
    '029780.KS': '삼성카드',
    '036460.KS': '한국가스공사',
    '002380.KS': 'KCC',
    '175330.KS': 'JB금융지주',
    '005300.KS': '롯데칠성',
    '241560.KS': '두산밥캣',
    '383220.KS': 'F&F',
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



def fundamentals(ticker, name, price_date):
    """Provider snapshot ONLY. No unverified figure is a fair-value estimate."""
    info = yf.Ticker(ticker).info or {}

    def number(key):
        try:
            value = float(info.get(key))
            return round(value, 4) if math.isfinite(value) else None
        except (TypeError, ValueError, OverflowError):
            return None

    forward_pe = number('forwardPE')
    trailing_pe = number('trailingPE')
    pbr = number('priceToBook')
    roe = number('returnOnEquity')
    earnings_growth = number('earningsGrowth')
    revenue_growth = number('revenueGrowth')
    # Yahoo's earningsGrowth field does NOT establish the period or forward forecast.
    # ForwardPE may be stale or have an inconsistent forecast period.
    available = sum(v is not None for v in (forward_pe, trailing_pe, pbr, roe, earnings_growth))
    notes = []
    if forward_pe is None or forward_pe <= 0:
        notes.append('예상 PER 없음 또는 무효')
    if trailing_pe is None or trailing_pe <= 0:
        notes.append('과거 PER 없음 또는 무효')
    if pbr is None or pbr <= 0:
        notes.append('PBR 미확인')
    if roe is None:
        notes.append('ROE 미확인')
    if earnings_growth is None:
        notes.append('이익증감 데이터 미확인')
    if earnings_growth is not None and abs(earnings_growth) >= 1:
        notes.append('이익증감 절댓값 100% 이상: 기준 기간 확인 필요')
    if forward_pe is not None and (forward_pe < 3 or forward_pe > 80):
        notes.append('예상 PER 극단값: 추정 실적 확인 필요')
    notes.append('공시 대조·업종 비교·자료 기준 기간 미검증')
    return dict(ticker=ticker.split('.')[0], name=name,
                forward_pe=forward_pe, trailing_pe=trailing_pe, pbr=pbr,
                roe=roe, earnings_growth=earnings_growth, revenue_growth=revenue_growth,
                available=available, price_date=price_date,
                source='Yahoo Finance/yfinance', status='VERIFY_PENDING',
                status_label='평가 보류', notes=notes,
                forecast_period='미확인', earnings_growth_period='미확인',
                verified=False)


def main():
    result = dict(watchlist=[], short_term=[], value_candidates=[], valuation_coverage={'checked':0,'sufficient':0,'errors':0}, asof=NOW.strftime('%Y-%m-%d %H:%M KST'), date=str(TODAY),
                  deadline=str(END_DATE), capital=CAPITAL, status='WAIT',
                  reason='데이터 검증 중', selection=None, alternatives=[],
                  method='사전 지정한 코스피 100종목 대상 전일 종가 기반 추세·거래량·ATR 필터. 실시간 시세·거래대금 순위 아님. 거래 전 확인 필요.')
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
        # 관찰 목록은 이미 통과한 종목이 아닌 제외 종목 중 상위 3개
        watchlist.sort(key=lambda x:(x['score'], x['momentum5']), reverse=True)
        result['watchlist'] = [x for x in watchlist if x['status'] != 'PASS'][:3]
        diagnostics['candidates'] = len(picks)
        diagnostics['reasons'] = dict(reasons)
        picks.sort(key=lambda x:(x['score'], x['momentum5'], x['volume_ratio']), reverse=True)
        # Risk cap: at most 1% of starting capital at the indicated stop, and 50% deployed in one name.
        for p in picks:
            risk_per_share = p['entry'] - p['stop']
            qty = min(CAPITAL // p['entry'], (CAPITAL // 2) // p['entry'],
                      int((CAPITAL * .01) // risk_per_share)) if risk_per_share > 0 else 0
            p.update(qty=int(qty), cost=int(qty * p['entry']), cash=int(CAPITAL-qty*p['entry']),
                     profit=int((p['target']-p['entry'])*qty),loss=int(risk_per_share*qty))
        actionable = [p for p in picks if p['qty'] > 0]
        result['short_term'] = [{k:v for k,v in p.items() if k != 'score'} for p in actionable[:3]]
        # Limit slow fundamental requests to a disclosed subset. No fake metrics or forecasts.
        # Mix the most promising technical names with a fixed financial/value baseline.
        screened = [r['ticker']+'.KS' for r in watchlist[:15]]
        screened += ['005930.KS','000660.KS','005380.KS','000270.KS','105560.KS',
                     '055550.KS','086790.KS','316140.KS','024110.KS','005490.KS']
        seen=set(); universe=[]
        for code in screened:
            if code in STOCKS and code not in seen:
                seen.add(code); universe.append(code)
        metrics=[]
        for code in universe[:25]:
            result['valuation_coverage']['checked'] += 1
            try:
                row=fundamentals(code, STOCKS[code], str(TODAY))
                if row['available'] >= 3:
                    result['valuation_coverage']['sufficient'] += 1
                    metrics.append(row)
            except Exception as exc:
                result['valuation_coverage']['errors'] += 1
                print('FUNDAMENTAL_ERROR',code,type(exc).__name__,str(exc)[:130])
        # Data completeness order only; do NOT imply valuation ranking.
        metrics.sort(key=lambda r:r['available'],reverse=True)
        result['value_candidates']=metrics[:5]
        result['valuation_warning']='미검증 제공처 수치로는 저평가 여부를 판단할 수 없어 전체 평가 보류. 공시·컨센서스 출처별 대조가 필요합니다.'

        # If most of the universe failed to load, avoid showing a potentially misleading top pick.
        if diagnostics['data_ok'] < max(1, len(STOCKS)//2):
            result.update(status='DATA_ERROR', reason=f'주가 데이터 정상 조회 {diagnostics["data_ok"]}/{len(STOCKS)}개. 데이터 부족으로 추천 중단.')
        elif actionable:
            for p in picks:
                p.pop('score', None)
            result.update(status='CANDIDATE', reason='전일 종가 기준 조건을 통과한 종목 중 상위 1개',
                          selection=actionable[0], alternatives=actionable[1:4])
        else:
            result.update(status='WAIT', reason=f'{diagnostics["data_ok"]}개 종목의 데이터를 확인했으나 매수 조건을 통과한 종목이 없습니다.')
    result['diagnostics'] = diagnostics
    (ROOT/'data.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SUMMARY', json.dumps({k:v for k,v in diagnostics.items() if k!='details'}, ensure_ascii=False))
    print(result['status'], result['reason'], (result['selection'] or {}).get('name'))


if __name__ == '__main__':
    main()
