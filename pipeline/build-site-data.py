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
for r in read('items'):
 ck=(norm(r['brand_name']),norm(r['item_name']),r['jq_cate3']);p=cache[ck]
 if not p['target']:continue
 group=groups[(p['target'],r['y_m']//100)];id=key('|'.join(str(x) for x in ck))
 if id not in group:group[id]={'id':id,'title':r['item_name'],'brand':p['brand'] or '未识别品牌','status':p['status'],'reason':p['reason'],'models':p['models'],'basis':p['basis'],'evidence':p['evidence'],'url':r['url'],'records':{}}
 g=group[id];rk=(r['plat'],r['y_m']);v=g['records'].setdefault(rk,[Decimal(0),Decimal(0),0])
 v[0]+=Decimal(r['gmv'] or 0);v[1]+=Decimal(r['sales_num'] or 0);v[2]+=1
for (target,year),group in groups.items():
 rows=[]
 for g in group.values():
  g['records']=[[p,ym,float(v[0]),float(v[1]),v[2]] for (p,ym),v in sorted(g['records'].items())];rows.append(g)
 raw=json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode();h=hashlib.sha256(raw).hexdigest();f=f'products-{target}-{year}.{h[:16]}.json'
 (DATA/f).write_bytes(raw);gz=gzip.compress(raw,mtime=0);(DATA/(f+'.gz')).write_bytes(gz)
 assets[f'products-{target}-{year}']={'path':f,'gzip':f+'.gz','bytes':len(raw),'gzip_bytes':len(gz),'sha256':h}
m['assets']=assets;m.pop('cache_hits',None)
m['site_version']='1.0.0';m['site_published_date']='2026-11-04'
(DATA/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
# data-client.js is maintained with the site source.
(SITE/'.nojekyll').touch()
print('assets',len(assets),'summary gzip',assets['summary']['gzip_bytes'],'product sizes',[(k,v['gzip_bytes']) for k,v in assets.items() if k.startswith('products')])

