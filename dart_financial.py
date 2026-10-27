"""DART official annual financial statement diagnostic. No API key is written to output."""
import os, io, json, zipfile, datetime, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

API='https://opendart.fss.or.kr/api/'
TARGETS={'005930':'삼성전자','000660':'SK하이닉스','271560':'오리온','326030':'SK바이오팜','033780':'KT&G'}
OUT=Path(__file__).parent/'dart_financial.json'
KEY=os.environ.get('DART_API_KEY','').strip()

def get_bytes(endpoint,params):
    qs=urllib.parse.urlencode({'crtfc_key':KEY,**params})
    req=urllib.request.Request(API+endpoint+'?'+qs,headers={'User-Agent':'KOSPI-Daily/1.0'})
    with urllib.request.urlopen(req,timeout=30) as response:
        return response.read()

def api(endpoint,params):
    return json.loads(get_bytes(endpoint,params).decode('utf-8-sig'))

def number(v):
    if v in (None,'','-'): return None
    try: return int(str(v).replace(',','').strip())
    except ValueError: return None

def corp_mapping():
    content=get_bytes('corpCode.xml',{})
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        xml=z.read('CORPCODE.xml')
    root=ET.fromstring(xml)
    matched={}
    for entry in root.findall('list'):
        code=(entry.findtext('stock_code') or '').strip()
        if code in TARGETS:
            matched[code]=(entry.findtext('corp_code') or '').strip()
    return matched

def statement(corp_code,year):
    result=api('fnlttSinglAcnt.json',{'corp_code':corp_code,'bsns_year':year,'reprt_code':'11011'})
    if result.get('status')!='000': return None, result.get('message','공시 없음')
    items=result.get('list',[])
    # Consolidated accounts take priority; standalone used only if CFS missing entirely.
    chosen=[x for x in items if x.get('fs_div')=='CFS'] or [x for x in items if x.get('fs_div')=='OFS']
    scope='연결' if chosen and chosen[0].get('fs_div')=='CFS' else '별도'
    output={}
    names={'매출액':('매출액','영업수익'),'영업이익':('영업이익','영업이익(손실)'),
           '당기순이익':('당기순이익','당기순이익(손실)')}
    for label, aliases in names.items():
        # Prefer income statement, not cashflow/balance-sheet duplicates.
        found=next((x for x in chosen if x.get('sj_div')=='IS' and x.get('account_nm') in aliases),None)
        if found is None:
            found=next((x for x in chosen if x.get('sj_div')=='CIS' and x.get('account_nm') in aliases),None)
        output[label]=number(found.get('thstrm_amount')) if found else None
    return {'year':year,'scope':scope,'unit':'KRW','values':output},None

def main():
    output={'source':'금융감독원 OpenDART / fnlttSinglAcnt','checked_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
            'report':'사업보고서(연간)', 'note':'2025년·2024년 확정 사업보고서 비교. PER·PBR·ROE 및 미래 성장률이 아님.', 'companies':[], 'status':'OK'}
    if not KEY:
        output.update(status='MISSING_KEY',error='Actions 비밀키 DART_API_KEY 미전달')
    else:
        try:
            mapping=corp_mapping()
            for ticker,name in TARGETS.items():
                item={'ticker':ticker,'name':name,'data':[], 'status':'OK'}
                if ticker not in mapping:
                    item.update(status='NO_CORP_CODE',error='DART 기업코드 미발견')
                else:
                    for yr in (2025,2024):
                        try:
                            data,err=statement(mapping[ticker],yr)
                            if data:item['data'].append(data)
                            else:item.setdefault('notes',[]).append(f'{yr}: {err}')
                        except Exception as exc:
                            item.setdefault('notes',[]).append(f'{yr}: {type(exc).__name__} 요청 실패')
                    if len(item['data'])<2:item['status']='PARTIAL'
                output['companies'].append(item)
                print(f"DART {ticker} {name}: {item['status']}, 연간 자료 {len(item['data'])}건")
        except Exception as exc:
            output.update(status='DATA_ERROR',error=f'{type(exc).__name__}: 조회 실패')
    OUT.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print('DART 진단 결과 생성:',output['status'])

if __name__=='__main__':main()
