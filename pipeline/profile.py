import gzip,json,pathlib,collections,unicodedata,re
from decimal import Decimal
R=pathlib.Path(__file__).resolve().parent
def read(kind):
 with gzip.open(R/'raw'/(kind+'.jsonl.gz'),'rt',encoding='utf-8') as f:
  yield from (json.loads(x) for x in f)
if __name__=='__main__':
 data=list(read('items'));groups=collections.defaultdict(lambda:{'gmv':0,'n':0,'plats':set(),'cats':set(),'months':set()})
 for r in data:
  k=(r['brand_name'] or '',r['item_name'] or '')
  g=groups[k];g['gmv']+=float(r['gmv'] or 0);g['n']+=1;g['plats'].add(r['plat']);g['cats'].add(r['jq_cate3']);g['months'].add(r['y_m'])
 top=[{'brand':k[0],'title':k[1],**{a:sorted(b) if isinstance(b,set) else b for a,b in v.items()}} for k,v in sorted(groups.items(),key=lambda x:-x[1]['gmv'])]
 (R/'title-profile.json').write_text(json.dumps(top,ensure_ascii=False),encoding='utf-8')
 print('rows',len(data),'titles',len(top),'items',len({(r['plat'],r['item_id']) for r in data}))
 print('categories',collections.Counter(r['jq_cate3'] for r in data).most_common(15))
 print(json.dumps([{k:r[k] for k in ['brand','title','gmv']} for r in top[:65]],ensure_ascii=False))
