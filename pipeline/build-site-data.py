import pathlib,json,gzip,hashlib,collections,sys,shutil
from decimal import Decimal
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from classify import norm,key,label_key
from profile import read
SITE=ROOT.parent;DATA=SITE/'data';DATA.mkdir(exist_ok=True)
OLD=SITE/'outputs/web-data'
m=json.loads((OLD/'manifest.json').read_text(encoding='utf-8'));assets={}
for name,a in m['assets'].items():
 if name=='summary' or name=='coverage' or name.startswith('brands-'):
  assets[name]=a
  for k in ('path','gzip'):shutil.copyfile(OLD/a[k],DATA/a[k])
cache={tuple(x['key']):x['result'] for x in json.loads((ROOT/'label-cache.json').read_text(encoding='utf-8'))['labels']}
groups=collections.defaultdict(dict)
mixed=collections.defaultdict(lambda:[Decimal(0),Decimal(0)])
pending_reasons=collections.defaultdict(Decimal)
transitions=collections.defaultdict(Decimal)
comparison=collections.defaultdict(lambda:collections.defaultdict(Decimal))
category_target={'雾化器':'nebulizer','制氧机':'oxygen'}
for r in read('industry'):
 if r['jq_cate3'] in category_target:comparison[(category_target[r['jq_cate3']],r['plat'],r['y_m'])]['category_gmv']+=Decimal(r['gmv'] or 0)
before_path=ROOT/'label-cache-before-v3.json'
before={tuple(x['key']):x['result'] for x in json.loads(before_path.read_text(encoding='utf-8'))['labels']} if before_path.exists() else {}
for r in read('items'):
 ck=label_key(r);p=cache[ck]
 if not p['target']:continue
 if p['status']=='included':comparison[(p['target'],r['plat'],r['y_m'])]['labeled_in' if category_target.get(r['jq_cate3'])==p['target'] else 'labeled_out']+=Decimal(r['gmv'] or 0)
 if p['status']=='pending':pending_reasons[(p['target'],r['plat'],r['y_m'],p['reason'])]+=Decimal(r['gmv'] or 0)
 prev=before.get(ck) or before.get(ck[:3])
 if prev and prev['status']!=p['status']:transitions[(p['target'],r['plat'],r['y_m'],prev['status'],p['status'])]+=Decimal(r['gmv'] or 0)
 if p.get('mixed_reason'):
  mk=(p['target'],r['plat'],r['y_m'],' > '.join(str(r.get(k) or '') for k in ('jq_cate1','jq_cate2','jq_cate3')),p['mixed_reason'],p['status'])
  mixed[mk][0]+=Decimal(r['gmv'] or 0);mixed[mk][1]+=Decimal(r['sales_num'] or 0)
 group=groups[(p['target'],r['y_m']//100)];id=key('|'.join(str(x) for x in ck))
 if id not in group:group[id]={'id':id,'title':r['item_name'],'brand':p['brand'] or '未识别品牌','status':p['status'],'reason':p['reason'],'models':p['models'],'basis':p['basis'],'evidence':p['evidence'],'mixed_reason':p.get('mixed_reason'),'source_category':p.get('source_category'),'url':r['url'],'records':{}}
 g=group[id];rk=(r['plat'],r['y_m']);v=g['records'].setdefault(rk,[Decimal(0),Decimal(0),0])
 v[0]+=Decimal(r['gmv'] or 0);v[1]+=Decimal(r['sales_num'] or 0);v[2]+=1
for (target,year),group in groups.items():
 rows=[]
 for g in group.values():
  g['records']=[[p,ym,float(v[0]),float(v[1]),v[2]] for (p,ym),v in sorted(g['records'].items())];rows.append(g)
 raw=json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode();h=hashlib.sha256(raw).hexdigest();f=f'products-{target}-{year}.{h[:16]}.json'
 (DATA/f).write_bytes(raw);gz=gzip.compress(raw,mtime=0);(DATA/(f+'.gz')).write_bytes(gz)
 assets[f'products-{target}-{year}']={'path':f,'gzip':f+'.gz','bytes':len(raw),'gzip_bytes':len(gz),'sha256':h}
# Include the compact mixed-link audit with the already-loaded summary, no new request.
a=assets['summary'];s=json.loads((DATA/a['path']).read_text(encoding='utf-8'))
# Currency rounding is performed once per platform-month; all-platform totals sum those amounts.
for r in s['monthly']:
 if r['平台']=='三平台合计' and r['已纳入GMV_元'] is not None:
  rr=[x for x in s['monthly'] if x['目标类目']==r['目标类目'] and x['期间']==r['期间'] and x['平台']!='三平台合计']
  for f in ('已纳入GMV_元','待确认GMV_元'):r[f]=float(sum((Decimal(str(x[f])) for x in rr),Decimal(0)))
for r in s['annual']:
 if r['平台']=='三平台合计':
  rr=[x for x in s['monthly'] if x['目标类目']==r['目标类目'] and x['期间'].startswith(r['期间']) and x['平台']=='三平台合计' and x['已纳入GMV_元'] is not None]
  for f in ('已纳入GMV_元','待确认GMV_元'):r[f]=float(sum((Decimal(str(x[f])) for x in rr),Decimal(0)))
s['mixed']=[dict(zip(('target','platform','month','source_category','reason','status'),k),gmv=float(v[0]),sales=float(v[1])) for k,v in sorted(mixed.items())]
s['pending_reasons']=[dict(zip(('target','platform','month','reason'),k),gmv=float(v)) for k,v in sorted(pending_reasons.items())]
s['review_transitions']=[dict(zip(('target','platform','month','before','after'),k),gmv=float(v)) for k,v in sorted(transitions.items())]
s['category_comparison']=[dict(zip(('target','platform','month'),k),**{f:float(v.get(f,Decimal(0)).quantize(Decimal('.01'))) for f in ('category_gmv','labeled_in','labeled_out')}) for k,v in sorted(comparison.items())]
for r in s['category_comparison']:
 total=next(x['已纳入GMV_元'] for x in s['monthly'] if x['目标类目']==m['targets'][r['target']] and x['平台']==m['platforms'][r['platform']] and x['期间']==f"{r['month']//100}-{r['month']%100:02d}")
 r['labeled_out']=float(Decimal(str(total))-Decimal(str(r['labeled_in'])))
raw=json.dumps(s,ensure_ascii=False,separators=(',',':')).encode();h=hashlib.sha256(raw).hexdigest();f=f'summary.{h[:16]}.json';gz=gzip.compress(raw,mtime=0)
(DATA/f).write_bytes(raw);(DATA/(f+'.gz')).write_bytes(gz)
assets['summary']={'path':f,'gzip':f+'.gz','bytes':len(raw),'gzip_bytes':len(gz),'sha256':h}
m['assets']=assets;m.pop('cache_hits',None)
m['scope']='标题含家用直接纳入；明确非目标商品仍排除；同品牌标准型号关联家用证据；混合链接单列，金额不拆分'
m['site_version']='3.0.0';m['site_published_date']='2026-11-04'
(DATA/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
shutil.copyfile(ROOT/'data-client.js',SITE/'data-client.js')
(SITE/'.nojekyll').touch()
print('assets',len(assets),'summary gzip',assets['summary']['gzip_bytes'],'product sizes',[(k,v['gzip_bytes']) for k,v in assets.items() if k.startswith('products')])
