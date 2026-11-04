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
def label_key(r):return (norm(r['brand_name']),norm(r['item_name']),r['jq_cate3'],r['plat'],str(r.get('item_id')),str(r.get('store_id')))
def link_key(r,p):return ('@link',p['target'],key('|'.join((r['plat'],str(r.get('item_id')),str(r.get('store_id')),p['brand'] or ''))))
def model_tokens(b,t):
 t=norm(t).upper().replace('－','-')
 t=re.sub(r'\s*-\s*','-',t)
 if b=='欧姆龙':t=re.sub(r'\bNE\s+(C\d)',r'NE-\1',t)
 if b=='鱼跃':t=re.sub(r'\b403\s+([A-Z])\b',r'403\1',t)
 t=re.sub(r'(?:YUWELL|OMRON|HAIER|PHILIPS|DEDAKJ)(?=\d+L)', '', t)
 t=re.sub(r'(?:\d+(?:\.\d+)?L){2,}', ' ',t)
 if b in ('劲氧 ganityoung','劲氧'):
  t=re.sub(r'YDD-?(\d+B)\s*/\s*(\d+B)',r'YDD-\1 YDD-\2',t)
 tokens=re.findall(r'(?<![A-Z0-9])(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9]+(?:-[A-Z0-9]+)*',t)
 out=[]
 for m in tokens:
  unit=bool(re.fullmatch(r'\d+(?:L|ML|KG|DB|V|W|H|CM|MM|M|D|MIN|HZ|AH|MAH|K|G|KW|PCS|IN1)',m))
  known_short=(b=='鱼跃' and bool(re.fullmatch(r'403[A-Z]*',m))) or (b=='海尔' and m in ['5H','503W','505W']) or (b=='可孚' and m in ['523W','525W'])
  if unit and not known_short:continue
  if len(m)<2:continue
  if b=='欧姆龙' and re.fullmatch(r'(?:NE-?)?C\d{2,4}[A-Z]*',m):m=re.sub(r'^NE-?','',m)
  m=m.replace('-','')
  if b=='可孚':m={'523W':'KJRY523W','Y523W':'KJRY523W','525W':'KJRY525W','Y525W':'KJRY525W','KF105':'KF105YW'}.get(m,m)
  out.append(m)
 if b=='飞利浦' and 'EVERFLO' in t:out.append('EVERFLO')
 if b=='百瑞':
  for m in re.findall(r'(?<![A-Z])BOY\s*(JUNIOR|PRO|CLASSIC|SX)(?![A-Z])',t):out.append('BOY'+m)
  if re.search(r'(?<![A-Z])JUNIOR\s*BOY(?![A-Z])',t):out.append('BOYJUNIOR')
 if b in ('科司德 consider','科司德'):out.extend(re.findall(r'(?<![A-Z])([KS]-T[SK])(?![A-Z])',t))
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
 if re.search('熏蒸床|熏蒸治疗仪|户外电源|移动电源|露营电源',t):return dict(p,status='excluded',reason='熏蒸理疗或供电设备，非目标整机')
 if re.search('储雾罐|储雾筒|峰流速仪|峰速仪|肺活量监测|口鼻气雾剂给药器',t):return dict(p,status='excluded',reason='储雾辅助器具或肺功能检测设备，非雾化整机')
 if re.search('电子口喷|口腔喷雾|吐气棒|吐气器|吸入棒|香氛|植物饮料|清新口气|口气清新|氢氧气机',t):return dict(p,status='excluded',reason='口腔清新喷雾或氢氧设备，非目标用途')
 if re.search('鼻腔喷雾|洗鼻护鼻',t) and not re.search('压缩|雾化药物|药液',t):return dict(p,status='excluded',reason='鼻腔清洗护理设备，非药物压缩雾化器')
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
  ('可孚','oxygen','KF105YW',['home','medical','mechanism'],'https://www.cofoe.com.cn/news/'),
  ('可孚','oxygen','KF106YW',['home','medical','mechanism'],'https://www.cofoe.com.cn/news_page/1809.html'),
  ('百瑞','nebulizer','BOYPRO',['home','medical','mechanism'],'https://www.pari.com/fileadmin/user_upload/PARI.com-DE/Dokumente/IFU/130D2200-Gebrauchsanweisung-PARI-BOY-Pro.pdf'),
  ('鱼跃','oxygen','SPIRIT6',['home'],'https://www.linkedin.com/posts/%E9%B1%BC%E8%B7%83%E5%8C%BB%E7%96%97_yuwell-portableoxygenconcentrator-oxygen-activity-7219619158215335936-xHy0'),
  ('鱼跃','oxygen','8F-5AW',['medical','mechanism'],'https://mpa.gd.gov.cn/attachment/0/533/533033/4255499.pdf'),
  ('飞利浦','oxygen','EVERFLO',['home','medical','mechanism'],'https://www.documents.philips.com/assets/20210225/420e5eb17efa4da0b5f2acda00bc3539.pdf'),
  ('欧姆龙','nebulizer','C801',['home','medical','mechanism'],'https://omronhealthcare.com/nebulizers')
 ]:
  for f in fields:d[(b,target,m.replace('-',''))][f].insert(0,{'source_url':url,'type':'primary_source'})
 # Resolve missing titles through the exact platform/item/store/brand history.
 # Every link sharing a label must qualify; conflicting excluded history blocks inheritance.
 links=collections.defaultdict(dict);blocked=set();titles=collections.defaultdict(set)
 negative=collections.defaultdict(list);positive=set()
 for r in rows:
  p=basic(r)
  if not p['brand'] or len(p['models'])!=1:continue
  k=(p['brand'],p['target'],p['models'][0])
  if p['reason']=='非压缩式雾化器':negative[k].append({'platform':r['plat'],'item_id':str(r['item_id']),'month':r['y_m'],'title':r['item_name']})
  elif p['mechanism'] and p['status'] is None:positive.add(k)
 for k,ev in negative.items():
  if k not in positive:d[k]['excluded_mechanism']=ev[:2]
 link_negative=collections.defaultdict(list);link_models=collections.defaultdict(set);link_positive=set()
 for r in rows:
  p=basic(r)
  if not p['target'] or not r.get('item_id') or not p['brand']:continue
  lk=(p['target'],r['plat'],str(r['item_id']),str(r.get('store_id')),p['brand'])
  tk=('@title',p['target'],key('|'.join((norm(r['brand_name']),norm(r['item_name']),r['jq_cate3']))))
  titles[tk].add(lk)
  link_models[lk].update(p['models'])
  if p['mechanism'] and p['status'] is None:link_positive.add(lk)
  if p['reason'] in ('非压缩式雾化器','非医用分子筛整机','储雾辅助器具或肺功能检测设备，非雾化整机','口腔清新喷雾或氢氧设备，非目标用途'):
   link_negative[lk].append({'platform':r['plat'],'item_id':str(r['item_id']),'month':r['y_m'],'title':r['item_name'],'exclusion_reason':p['reason']})
  if p['status']=='excluded':blocked.add(lk)
  elif re.search('家用|家庭用|居家',norm(r['item_name'])):links[lk]={'platform':r['plat'],'item_id':str(r['item_id']),'month':r['y_m'],'title':r['item_name']}
  elif p['models'] and all(d.get((p['brand'],p['target'],m),{}).get('home') and not d.get((p['brand'],p['target'],m),{}).get('excluded_mechanism') for m in p['models']):
   links[lk]={'platform':r['plat'],'item_id':str(r['item_id']),'month':r['y_m'],'title':r['item_name'],'model_evidence':[{'model':m,'source':d[(p['brand'],p['target'],m)]['home'][0]} for m in p['models']]}
 for tk,lks in titles.items():
  if all(k in links and k not in blocked for k in lks):d[tk]['link_home']=[links[k] for k in sorted(lks)][:3]
  if all(k in link_negative and k not in link_positive and len(link_models[k])<=1 for k in lks):d[tk]['link_excluded']=[link_negative[k][0] for k in sorted(lks)][:3]
 for lk in set(links)|set(link_negative):
  target,plat,item,store,b=lk;dk=('@link',target,key('|'.join((plat,item,store,b))))
  if lk in links and lk not in blocked:d[dk]['link_home']=[links[lk]]
  if lk in link_negative and lk not in link_positive and len(link_models[lk])<=1:d[dk]['link_excluded']=[link_negative[lk][0]]
 return d
def legacy_classify(r,d):
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

MIXED={'整机与配件混合标题待确认','雾化与洗鼻功能待确认','呼吸机与制氧机组合待拆分','多原理混售待确认','多型号或比较型号待确认'}
def classify(r,d):
 p=legacy_classify(r,d)
 p['mixed_reason']=p['reason'] if p['reason'] in MIXED else None
 p['source_category']=' > '.join(str(r.get(k) or '') for k in ('jq_cate1','jq_cate2','jq_cate3')).strip(' >')
 if p['status']=='excluded':return p
 tk=('@title',p['target'],key('|'.join((norm(r['brand_name']),norm(r['item_name']),r['jq_cate3']))))
 excluded=d.get(link_key(r,p),{}).get('link_excluded') or d.get(tk,{}).get('link_excluded')
 if excluded:
  p['evidence'] += [{'field':'exclusion','model':'同链接历史','source':s} for s in excluded]
  return dict(p,status='excluded',reason='历史链接明确非目标商品：'+excluded[0]['exclusion_reason'],basis='same_link',mixed_reason=None)
 if len(p['models'])==1 and d.get((p['brand'],p['target'],p['models'][0]),{}).get('excluded_mechanism'):
  p['evidence'] += [{'field':'exclusion','model':p['models'][0],'source':s} for s in d[(p['brand'],p['target'],p['models'][0])]['excluded_mechanism']]
  return dict(p,status='excluded',reason='同品牌同型号证据明确为非压缩式雾化器',basis='same_model',mixed_reason=None)
 if re.search('家用|家庭用|居家',norm(r['item_name'])):
  return dict(p,status='included',reason='用户口径：标题含家用或同义家庭用/居家，直接纳入'+('；混合链接金额未拆分' if p['mixed_reason'] else ''),basis='home_policy')
 tk=('@title',p['target'],key('|'.join((norm(r['brand_name']),norm(r['item_name']),r['jq_cate3']))))
 linked=d.get(link_key(r,p),{}).get('link_home') or d.get(tk,{}).get('link_home')
 if linked:
  p['evidence'] += [{'field':'home','model':'同链接历史','source':s} for s in linked]
  return dict(p,status='included',reason='同平台同商品链接历史标题或型号已确认家用'+('；混合链接金额未拆分' if p['mixed_reason'] else ''),basis='same_link')
 # Every model must independently have home evidence; never propagate between brands or variants.
 if p['brand'] and p['models'] and all(d.get((p['brand'],p['target'],m),{}).get('home') for m in p['models']):
  p['evidence'] += [{'field':'home','model':m,'source':d[(p['brand'],p['target'],m)]['home'][0]} for m in p['models']]
  return dict(p,status='included',reason='同品牌标准型号关联家用证据'+('；混合链接金额未拆分' if p['mixed_reason'] else ''),basis='same_model')
 return p
