import pathlib,json,gzip,hashlib,collections,sys,shutil
from decimal import Decimal
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from classify import norm,key
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
for r in read('items'):
 ck=(norm(r['brand_name']),norm(r['item_name']),r['jq_cate3']);p=cache[ck]
 if not p['target']:continue
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
s['mixed']=[dict(zip(('target','platform','month','source_category','reason','status'),k),gmv=float(v[0]),sales=float(v[1])) for k,v in sorted(mixed.items())]
raw=json.dumps(s,ensure_ascii=False,separators=(',',':')).encode();h=hashlib.sha256(raw).hexdigest();f=f'summary.{h[:16]}.json';gz=gzip.compress(raw,mtime=0)
(DATA/f).write_bytes(raw);(DATA/(f+'.gz')).write_bytes(gz)
assets['summary']={'path':f,'gzip':f+'.gz','bytes':len(raw),'gzip_bytes':len(gz),'sha256':h}
m['assets']=assets;m.pop('cache_hits',None)
m['scope']='标题含家用直接纳入；明确非目标商品仍排除；同品牌标准型号关联家用证据；混合链接单列，金额不拆分'
m['site_version']='2.0.0';m['site_published_date']='2026-11-04'
(DATA/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
shutil.copyfile(ROOT/'data-client.js',SITE/'data-client.js')
(SITE/'.nojekyll').touch()
print('assets',len(assets),'summary gzip',assets['summary']['gzip_bytes'],'product sizes',[(k,v['gzip_bytes']) for k,v in assets.items() if k.startswith('products')])
