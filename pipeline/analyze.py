"""Build monthly/annual observed sales, exact brand unions, coverage audits and hashed web assets."""
import json,gzip,pathlib,collections,hashlib,time,csv,decimal,datetime,shutil,os
from classify import RULES,norm,brand,key,basic,build_dictionary,classify
from profile import read
D=decimal.Decimal
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path(os.environ.get('LABEL_OUTPUT_DIR',str(ROOT.parents[1]/'outputs'/'medical-label-20261104')));OUT.mkdir(parents=True,exist_ok=True)
WEB=OUT/'web-data';WEB.mkdir(exist_ok=True)
PLATS={'tmall':'天猫','jd':'京东','douyin':'抖音','all':'三平台合计'}
TARGETS=RULES['targets']; CATS={'雾化器':'nebulizer','制氧机':'oxygen'}
def jd(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':'),default=str),encoding='utf-8')
def csvout(name,rows):
 if not rows:return
 with (OUT/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def dec(x):return D(str(x)) if x is not None else None
def amt(x):return float(x.quantize(D('.01')))
def dedup(rows,kind):
 groups=collections.defaultdict(list)
 for r in rows:
  if kind=='items':
   k=(r['plat'],r['y_m'],str(r['item_id']),str(r['store_id']))
   if r['item_id'] is None:k+=('missing_id',r['url'],r['item_name'])
  else:
   k=tuple(r[x] for x in ['plat','y_m','jq_cate1','jq_cate2','jq_cate3','cate1','cate2','cate3','cate4']+(['brand_name'] if kind=='brands' else []))
  groups[k].append(r)
 clean=[];conflicts=[];removed=0
 for k,rs in groups.items():
  metrics={(r['gmv'],r['sales_num']) for r in rs}
  if len(metrics)>1:
   conflicts.append({'table':kind,'key':list(k),'records':rs});continue
  # Multiple classification-bearing titles are ambiguous even if amounts match.
  if kind=='items' and len({(norm(r['item_name']),brand(r['brand_name']),r['jq_cate3']) for r in rs})>1:
   conflicts.append({'table':kind,'key':list(k),'records':rs});continue
  clean.append(max(rs,key=lambda r:str(r['insert_time'])));removed+=len(rs)-1
 return clean,{'raw_rows':len(rows),'clean_rows':len(clean),'duplicates_removed':removed,'conflict_keys':len(conflicts)},conflicts
def bucket():return {'gmv':D(0),'sales':D(0),'missing_gmv':0,'missing_sales':0,'rows':0,'brands':set(),'unknown':0,'months':set(),'items':set()}
def add(b,r,bname=None):
 b['rows']+=1;b['months'].add(r['y_m'])
 for col,out in [('gmv','gmv'),('sales_num','sales')]:
  if r[col] is None:b['missing_'+('gmv' if col=='gmv' else 'sales')]+=1
  else:b[out]+=dec(r[col])
 active=(dec(r['gmv']) or 0)>0 or (dec(r['sales_num']) or 0)>0
 if active:
  if bname:b['brands'].add(bname)
  else:b['unknown']+=1
 if 'item_id' in r:b['items'].add((r['plat'],str(r['item_id'])))
def main():
 t=time.perf_counter();tables={};audits={};conflicts=[]
 for kind in ('industry','brands','items'):
  tables[kind],audits[kind],cf=dedup(list(read(kind)),kind);conflicts.extend(cf)
 jd(ROOT/'conflicts.json',conflicts)
 data=tables['items'];d=build_dictionary(data)
 dict_serial=[{'key':list(k),'evidence':v} for k,v in sorted(d.items())]
 cache_fingerprint=hashlib.sha256((json.dumps(RULES,sort_keys=True,ensure_ascii=False)+json.dumps(dict_serial,sort_keys=True,ensure_ascii=False)+(ROOT/'classify.py').read_text(encoding='utf-8')).encode()).hexdigest()
 cache_path=ROOT/'label-cache.json';cached={}
 if cache_path.exists():
  old=json.loads(cache_path.read_text(encoding='utf-8'))
  if old.get('fingerprint')==cache_fingerprint:cached={tuple(x['key']):x['result'] for x in old['labels']}
 memo={};cache_hits=0;summary=collections.defaultdict(bucket);bgroups=collections.defaultdict(bucket);labels={};coverage=collections.defaultdict(lambda:collections.defaultdict(bucket));statuses=collections.Counter()
 for kind in ('industry','brands','items'):
  for r in tables[kind]:
   if r['jq_cate3'] in CATS:
    add(coverage[(r['jq_cate3'],r['plat'],r['y_m'])][kind],r,brand(r.get('brand_name')))
 for r in data:
  ck=(norm(r['brand_name']),norm(r['item_name']),r['jq_cate3'])
  if ck not in memo:
   if ck in cached:memo[ck]=cached[ck];cache_hits+=1
   else:memo[ck]=classify(r,d)
  p=memo[ck];status=p['status'];target=p['target'];statuses[status]+=1
  label_id=key('|'.join(str(x) for x in ck))
  if label_id not in labels:
   labels[label_id]={'label_id':label_id,'brand':p['brand'],'title':r['item_name'],'target':target,'status':status,'reason':p['reason'],'basis':p['basis'],'models':p['models'],'evidence':p['evidence'],'sample_url':r['url'],'gmv':D(0),'rows':0,'platforms':set(),'months':set(),'items':set()}
  l=labels[label_id];l['gmv']+=dec(r['gmv']) or 0;l['rows']+=1;l['platforms'].add(r['plat']);l['months'].add(r['y_m']);l['items'].add((r['plat'],str(r['item_id'])))
  if target:
   for plat in (r['plat'],'all'):
    for period in (r['y_m'],r['y_m']//100):
     add(summary[(target,plat,period,status)],r,p['brand'])
     if status=='included':add(bgroups[(target,plat,period,p['brand'] or '未识别品牌')],r,p['brand'])
 last=max(r['y_m'] for r in data);first=min(r['y_m'] for r in data)
 monthly=[];annual=[]
 for target in TARGETS:
  for plat in PLATS:
   for period in [y*100+m for y in range(2023,2027) for m in range(1,13)]+list(range(2023,2027)):
    isyear=period<10000;available=period<=last if not isyear else period<=last//100
    b=summary[(target,plat,period,'included')];p=summary[(target,plat,period,'pending')]
    srcmonths=sorted({ym for (cat,pl,ym),v in coverage.items() if CATS[cat]==target and (plat=='all' or plat==pl) and (ym//100==period if isyear else ym==period)})
    gmv_value=sum((summary[(target,plat,period*100+m,'included')]['gmv'].quantize(D('.01')) for m in range(1,13)),D(0)) if isyear else b['gmv']
    pending_value=sum((summary[(target,plat,period*100+m,'pending')]['gmv'].quantize(D('.01')) for m in range(1,13)),D(0)) if isyear else p['gmv']
    row={'目标类目':TARGETS[target],'平台':PLATS[plat],'期间':str(period) if isyear else f'{period//100}-{period%100:02d}',
      '覆盖月份':len(srcmonths),'已纳入GMV_元':amt(gmv_value) if available else None,'已纳入销量_件':float(b['sales']) if available else None,
      '涉及成交品牌数':len(b['brands']) if available else None,'未识别品牌成交记录数':b['unknown'] if available else None,
      '待确认GMV_元':amt(pending_value) if available else None,'待确认商品数':len(p['items']) if available else None,
      '已纳入金额缺失记录数':b['missing_gmv'] if available else None,'已纳入销量缺失记录数':b['missing_sales'] if available else None,
      '数据状态':'暂未取得' if not available else ('2026年1—9月累计；已覆盖样本' if isyear and period==2026 else '已覆盖样本，非完整行业总量')}
    (annual if isyear else monthly).append(row)
 cov=[]
 for (cat,plat,ym),v in sorted(coverage.items()):
  i=v['industry'];it=v['items'];br=v['brands'];ratio=float(it['gmv']/i['gmv']) if i['gmv']>0 else None
  cov.append({'原始久谦三级':cat,'平台':PLATS[plat],'月份':f'{ym//100}-{ym%100:02d}','行业表GMV_元':amt(i['gmv']),
   '商品表GMV_元':amt(it['gmv']),'商品金额覆盖率':ratio,'品牌表GMV_元':amt(br['gmv']),'商品行数':it['rows'],
   '商品已识别成交品牌数':len(it['brands']),'品牌表已识别成交品牌数':len(br['brands']),
   '行业金额缺失行数':i['missing_gmv'],'商品金额缺失行数':it['missing_gmv'],
   '备注':'商品低于行业表' if ratio is not None and ratio<.99 else '商品超过行业表，口径待核对' if ratio is not None and ratio>1.01 else '金额接近仍不证明全量'})
 brandrows=[]
 for (target,plat,period,bname),b in sorted(bgroups.items()):
  brandrows.append({'目标类目':TARGETS[target],'平台':PLATS[plat],'期间类型':'自然年' if period<10000 else '自然月',
   '期间':str(period) if period<10000 else f'{period//100}-{period%100:02d}','品牌':bname,'已纳入GMV_元':amt(b['gmv']),'已纳入销量_件':float(b['sales'])})
 labelrows=[]
 for l in sorted(labels.values(),key=lambda x:-x['gmv']):
  labelrows.append({'标签ID':l['label_id'],'目标类目':TARGETS.get(l['target'],'非目标商品'),'标准品牌':l['brand'] or '未识别品牌',
   '商品标题':l['title'],'判定':{'included':'纳入','excluded':'排除','pending':'待确认'}[l['status']],
   '依据类型':'同品牌同型号证据' if l['basis']=='same_model' else '当前标题规则','判定原因':l['reason'],'型号':'；'.join(l['models']),
   '累计GMV_元':amt(l['gmv']),'商品数':len(l['items']),'月记录数':l['rows'],'平台':'；'.join(PLATS[x] for x in sorted(l['platforms'])),
   '首次月份':min(l['months']),'最后月份':max(l['months']),'样例链接':l['sample_url'],'证据':json.dumps(l['evidence'],ensure_ascii=False)})
 for name,rows in [('自然年汇总',annual),('自然月汇总',monthly),('覆盖率核验',cov),('品牌明细',brandrows),('商品标签',labelrows)]:csvout(name,rows)
 reviews=[r for r in labelrows if r['判定']=='待确认' and r['目标类目']!='非目标商品'];csvout('待确认清单',reviews)
 # Save all label decisions once; rows retain source snapshot references, no monthly LLM repetition.
 jd(ROOT/'label-cache.json',{'rule_version':RULES['version'],'fingerprint':cache_fingerprint,'labels':memo_serial(memo)})
 jd(ROOT/'model-evidence.json',[{'brand':k[0],'target':k[1],'model':k[2],'evidence':v} for k,v in d.items()])
 # Content-hashed immutable assets: tiny summary first, details fetched by target and status/page.
 assets={}
 def asset(name,obj):
  raw=json.dumps(obj,ensure_ascii=False,separators=(',',':'),default=str).encode();sha=hashlib.sha256(raw).hexdigest()[:16]
  f=f'{name}.{sha}.json';(WEB/f).write_bytes(raw)
  (WEB/(f+'.gz')).write_bytes(gzip.compress(raw,mtime=0))
  assets[name]={'path':f,'gzip':f+'.gz','bytes':len(raw),'gzip_bytes':(WEB/(f+'.gz')).stat().st_size,'sha256':hashlib.sha256(raw).hexdigest()}
 asset('summary',{'annual':annual,'monthly':monthly})
 asset('coverage',cov)
 for target in TARGETS:
  for year in range(2023,2027):asset(f'brands-{target}-{year}',[r for r in brandrows if r['目标类目']==TARGETS[target] and r['期间'].startswith(str(year))])
  for st in ('纳入','排除','待确认'):
   rr=[r for r in labelrows if r['目标类目']==TARGETS[target] and r['判定']==st]
   for page in range(0,len(rr),200):asset(f'labels-{target}-'+{'纳入':'included','排除':'excluded','待确认':'pending'}[st]+f'-{page//200+1}',rr[page:page+200])
 manifest={'schema_version':1,'rule_version':RULES['version'],'as_of_month':last,'snapshot':json.loads((ROOT/'raw/manifest.json').read_text(encoding='utf-8')),
  'scope':'家用或个人使用；排除需要专业人员操作的院用设备；纳入按标题及同型号证据，非逐项注册验证',
  'metric_status':'observed_sample_not_total_market','gmv_definition':'源字段gmv；沿用现有项目退后口径，源表未提供退款字段，未获源方再次确认',
  'platforms':PLATS,'targets':TARGETS,'assets':assets,'audits':audits,'status_counts':dict(statuses),'label_count':len(memo),'model_count':len(d),
  'source_coverage_note':'行业/品牌大盘仅作对账，品牌数取纳入商品的成交品牌并集。商品表存在截断迹象。','cache_hits':cache_hits}
 # Database SQL is local provenance, not needed on the future public page.
 manifest['snapshot'].pop('queries',None)
 jd(WEB/'manifest.json',manifest)
 jd(OUT/'workbook-data.json',{'annual':annual,'monthly':monthly,'coverage':cov,'brands':brandrows,'review':reviews[:200],'metadata':manifest})
 # Independent audit invariants.
 checks=[]
 for target in TARGETS:
  for plat in PLATS:
   for y in range(2023,2027):
    yearly=summary[(target,plat,y,'included')]
    month=[summary[(target,plat,y*100+m,'included')] for m in range(1,13)]
    assert yearly['gmv']==sum((x['gmv'] for x in month),D(0))
    assert yearly['sales']==sum((x['sales'] for x in month),D(0))
    assert yearly['brands']==set().union(*(x['brands'] for x in month))
 for target in TARGETS:
  for ym in range(202301,last+1):
   if not 1<=ym%100<=12:continue
   allb=summary[(target,'all',ym,'included')]
   assert allb['gmv']==sum((summary[(target,p,ym,'included')]['gmv'] for p in PLATS if p!='all'),D(0))
   assert allb['brands']==set().union(*(summary[(target,p,ym,'included')]['brands'] for p in PLATS if p!='all'))
 checks=['32组年度金额/销量等于逐月合计','32组年度品牌数等于月份品牌并集','90组跨平台金额及品牌去重一致','2026年10—12月保留缺失','商品状态互斥']
 report={'audits':audits,'statuses':dict(statuses),'unique_labels':len(memo),'dictionary_models':len(d),'checks':checks,'elapsed_seconds':round(time.perf_counter()-t,2),
  'annual_all':[r for r in annual if r['平台']=='三平台合计'],'coverage_summary':{p:{'min':min(r['商品金额覆盖率'] for r in cov if r['平台']==p and r['商品金额覆盖率'] is not None),
  'max':max(r['商品金额覆盖率'] for r in cov if r['平台']==p and r['商品金额覆盖率'] is not None),'rows_500':sum(r['商品行数']==500 for r in cov if r['平台']==p)} for p in ['天猫','京东','抖音']},
  'asset_summary':assets['summary'],'cache_hits':cache_hits,'top_pending':reviews[:30]}
 jd(ROOT/'audit-report.json',report)
 print(json.dumps({k:v for k,v in report.items() if k!='top_pending'},ensure_ascii=False))
def memo_serial(memo):return [{'key':list(k),'result':v} for k,v in memo.items()]
if __name__=='__main__':main()
