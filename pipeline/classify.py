"""Deterministic labels. No per-row LLM calls. Evidence remains distinguishable from verification."""
import re,json,pathlib,unicodedata,hashlib,collections
ROOT=pathlib.Path(__file__).resolve().parent
RULES=json.loads((ROOT/'rules.json').read_text(encoding='utf-8'))
RX={k:re.compile(v,re.I) for k,v in RULES.items() if isinstance(v,str) and k!='version'}
def norm(s):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',s or '')).strip().lower()
def brand(s):
 s=norm(s)
 if s in ('','其他','其它','其他品牌','其他 other','其它 other','other','others','无品牌','无','未识别品牌','不详','unknown','通用'):return None
 return RULES['brand_aliases'].get(s,s)
def key(s):return hashlib.sha256(s.encode()).hexdigest()[:20]
def model_tokens(b,t):
 t=norm(t).upper().replace('－','-')
 t=re.sub(r'(?:YUWELL|OMRON|HAIER|PHILIPS|DEDAKJ)(?=\d+L)', '', t)
 t=re.sub(r'(?:\d+(?:\.\d+)?L){2,}', ' ',t)
 tokens=re.findall(r'(?<![A-Z0-9])(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9]+(?:-[A-Z0-9]+)*',t)
 out=[]
 for m in tokens:
  unit=bool(re.fullmatch(r'\d+(?:L|ML|KG|DB|V|W|H|CM|MM|M|D|MIN|HZ|AH|MAH|K|G|KW|PCS|IN1)',m))
  known_short=(b=='鱼跃' and m in ['403M','403K'])
  if unit and not known_short:continue
  if len(m)<3:continue
  if b=='欧姆龙' and re.fullmatch(r'(?:NE-)?C\d{2,4}[A-Z]*',m):m=re.sub(r'^NE-','',m)
  out.append(m)
 if b=='飞利浦' and 'EVERFLO' in t:out.append('EVERFLO')
 return sorted(set(out))
def basic(r):
 t=norm(r['item_name']);b=brand(r['brand_name']);cat=r['jq_cate3']
 oxygen=bool(re.search('制氧|氧气机|吸氧机|造氧机',t))
 nebulizer=bool(re.search('雾化器|雾化机|雾化仪|雾化泵|雾化吸入',t))
 target='oxygen' if oxygen else ('nebulizer' if nebulizer else ('oxygen' if cat=='制氧机' else 'nebulizer' if cat=='雾化器' else None))
 p={'target':target,'brand':b,'models':model_tokens(b,t),'home':bool(RX['home'].search(t)),
    'medical':bool(RX['medical'].search(t)),'mechanism':bool(RX['molecular' if target=='oxygen' else 'compressor'].search(t)),
    'status':None,'reason':None,'basis':'title','evidence':[]}
 if not target:return dict(p,status='excluded',reason='非目标设备')
 if RX['professional'].search(t):return dict(p,status='excluded',reason='专业操作或集中供氧设备')
 if '医院专用' in t:return dict(p,status='pending',reason='院用宣传与个人使用边界待确认')
 if RX['nonmedical'].search(t):return dict(p,status='excluded',reason='非目标用途')
 # A bundled accessory is not itself an accessory-only listing. Ambiguous bundles stay pending.
 stripped=re.sub(r'(赠送|赠|送|配备|标配|搭配|含|带|配|终身领|\+)(?:\d+套|\d+片|专用)?(?:吸氧管|雾化面罩|吸氧面罩|过滤棉|雾化杯|配件|耗材|湿化瓶|氧气管|雾化套装)[^ ]*','',t)
 if RX['accessory'].search(stripped):
  first_device=re.search('制氧机|吸氧机|氧气机|雾化器|雾化机|雾化仪|雾化泵',stripped)
  first_acc=RX['accessory'].search(stripped)
  uncertain=first_device and first_device.start()<first_acc.start() and not re.search('配件|耗材|适配|适用于|更换|替换|维修',stripped)
  return dict(p,status='pending' if uncertain else 'excluded',reason='整机与配件混合标题待确认' if uncertain else '配件耗材商品')
 if re.search('洗鼻器|冲洗器|鼻腔冲洗',t):
  return dict(p,status='pending' if nebulizer else 'excluded',reason='雾化与洗鼻功能待确认' if nebulizer else '非目标用途')
 if re.search('租赁|出租|租用|维修服务|上门维修|二手|回收|定金|订金|补差价|补邮费',t):return dict(p,status='excluded',reason='租赁二手服务或非整机交易')
 if target=='oxygen' and RX['other_oxygen'].search(t):return dict(p,status='excluded',reason='非医用分子筛整机')
 if target=='oxygen' and re.search('呼吸机.{0,8}(组合|套装)|呼吸机\+|无创|双水平|单水平',t):return dict(p,status='pending',reason='呼吸机与制氧机组合待拆分')
 if target=='nebulizer' and RX['other_nebulizer'].search(t):
  return dict(p,status='pending' if p['mechanism'] else 'excluded',reason='多原理混售待确认' if p['mechanism'] else '非压缩式雾化器')
 # Category-only recalls that lack a device noun require review, never automatic admission.
 if not (oxygen or nebulizer):return dict(p,status='pending',reason='标题未明确整机')
 return p
def build_dictionary(rows):
 d=collections.defaultdict(lambda:collections.defaultdict(list))
 for r in rows:
  p=basic(r)
  if p['status'] or not p['brand'] or len(p['models'])!=1:continue
  m=p['models'][0];k=(p['brand'],p['target'],m)
  for f in ('home','medical','mechanism'):
   if p[f] and len(d[k][f])<3:
    evidence={'platform':r['plat'],'item_id':str(r['item_id']),'month':r['y_m'],'title':r['item_name']}
    if evidence not in d[k][f]:d[k][f].append(evidence)
 # Exact-model primary sources supplement titles, without inferring adjacent model variants.
 for b,target,m,fields,url in [
  ('鱼跃','oxygen','8F-5AW',['medical','mechanism'],'https://mpa.gd.gov.cn/attachment/0/533/533033/4255499.pdf'),
  ('飞利浦','oxygen','EVERFLO',['home','medical','mechanism'],'https://www.documents.philips.com/assets/20210225/420e5eb17efa4da0b5f2acda00bc3539.pdf'),
  ('欧姆龙','nebulizer','C801',['home','medical','mechanism'],'https://omronhealthcare.com/nebulizers')
 ]:
  for f in fields:d[(b,target,m)][f].insert(0,{'source_url':url,'type':'primary_source'})
 return d
def classify(r,d):
 p=basic(r)
 if p['status']:return p
 if len(p['models'])>1:return dict(p,status='pending',reason='多型号或比较型号待确认')
 if len(p['models'])==1 and p['brand']:
  m=p['models'][0];ev=d.get((p['brand'],p['target'],m),{})
  for f in ('home','medical','mechanism'):
   if not p[f] and ev.get(f):
    p[f]=True;p['basis']='same_model';p['evidence'].append({'field':f,'model':m,'source':ev[f][0]})
 missing=[{'home':'家用或个人使用','medical':'医疗用途','mechanism':'分子筛原理' if p['target']=='oxygen' else '压缩原理'}[f] for f in ('home','medical','mechanism') if not p[f]]
 return dict(p,status='pending' if missing else 'included',reason='待确认：'+'、'.join(missing) if missing else '标题及同品牌同型号证据符合')
