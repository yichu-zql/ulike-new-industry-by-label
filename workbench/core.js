// All label decisions and analytics share this engine. No DOM or network dependencies.
export const SCHEMA = 1;
export const STATUS = {included:'纳入',pending:'待复核',excluded:'排除'};
export const norm = x => String(x ?? '').normalize('NFKC').trim().toLowerCase();
export const words = x => [...new Set(String(x || '').split(/[\n,，;；]/).map(norm).filter(Boolean))];
export const clone = x => structuredClone(x);
export function validateRule(r) {
  if (!r || typeof r.name!=='string' || !r.name.trim() || r.name.length>100) throw Error('品类名称必填，最多100字');
  if (!Array.isArray(r.sources) || !r.sources.length || r.sources.some(s=>typeof s!=='string')) throw Error('至少选择一个商品来源');
  for (const k of ['definition','include','exclude','attributes']) if(typeof r[k]!=='string'||r[k].length>10000)throw Error('规则字段无效或过长');
  const attrLines=r.attributes.split('\n').filter(x=>x.trim());
  if(attrLines.length>40||attrLines.some(x=>x.indexOf('=')<1||!words(x.slice(x.indexOf('=')+1)).length))throw Error('属性每行需填写「标签名=关键词」，最多40个标签');
  if(new Set(attrLines.map(x=>x.slice(0,x.indexOf('=')).trim())).size!==attrLines.length)throw Error('属性标签名称不能重复');
  if(typeof r.inherit!=='boolean')throw Error('继承规则无效');
  if(!r.overrides || typeof r.overrides!=='object'||Array.isArray(r.overrides))throw Error('人工复核数据无效');
  for(const [id,o] of Object.entries(r.overrides))if(!id||!o||!STATUS[o.status]||typeof o.note!=='string'||o.note.length>2000||typeof o.signature!=='string')throw Error('人工复核记录无效');
  return r;
}
export function seedCategories() {
  return [['nebulizer','家用医用压缩式雾化器'],['oxygen','家用医用分子筛制氧机']].map(([id,name])=>{
    const r={name,definition:'沿用原研究v3的标题、同型号及历史链接证据；排除配件、非目标设备和专业操作设备。',sources:[id],inherit:true,include:'',exclude:'',attributes:'',overrides:{}};
    return {id,draft:clone(r),revisions:[{version:1,at:'2026-11-04T00:00:00+08:00',rule:clone(r),note:'原研究v3快照'}]};
  });
}
export const signature = p => p.originalSignature || JSON.stringify([p.title,p.brand,p.source_category,p.status,p.reason]);
export function compileRule(r) {validateRule(r);return {...r,yes:words(r.include),no:words(r.exclude),attrs:r.attributes.split('\n').map(s=>{const i=s.indexOf('=');return i>0?[s.slice(0,i).trim(),words(s.slice(i+1))]:null;}).filter(Boolean)};}
export function classify(p,r) {
  const text=p.search || norm([p.title,p.brand,p.source_category,...(p.models||[])].join(' '));
  const tags=r.attrs.filter(([,ws])=>ws.some(w=>text.includes(w))).map(([tag])=>tag);
  const o=r.overrides[p.id];
  if(o){if(o.signature!==signature(p))return {status:'pending',reason:'商品信息已变化，请重新复核；原人工结果已保留',basis:'changed',tags};return {status:o.status,reason:o.note||'人工确认',basis:'manual',tags};}
  const no=r.no.find(w=>text.includes(w));
  if(no)return {status:'excluded',reason:`命中排除词「${no}」`,basis:'rule',tags};
  const yes=r.yes.find(w=>text.includes(w));
  if(yes)return {status:'included',reason:`命中纳入词「${yes}」`,basis:'rule',tags};
  if(r.inherit)return {status:p.status,reason:p.reason,basis:'source',tags};
  return {status:'pending',reason:r.yes.length?'未命中纳入词，保留待复核':'尚未配置纳入规则',basis:'rule',tags};
}
export function mergeProducts(parts) {
  const map=new Map();
  for(const {source,rows} of parts)for(const p of rows){
    const id=`${source}:${p.id}`;
    let x=map.get(id);
    if(!x){x={...p,id,source,sourceId:p.id,records:[],search:norm([p.title,p.brand,p.source_category,...p.models].join(' '))};map.set(id,x);}
    x.records.push(...p.records);
  }
  return [...map.values()];
}
export function periodMonths(s) {
  const out=[];for(let ym=s.from;ym<=s.to;ym=ym%100===12?(Math.floor(ym/100)+1)*100+1:ym+1)out.push(ym);return out;
}
export function inScope(r,s){return r[1]>=s.from&&r[1]<=s.to&&(s.platform==='all'||r[0]===s.platform);}
export function evaluate(products,rule,s) {
  const compiled=compileRule(rule), rows=[];
  for(const p of products){if(!rule.sources.includes(p.source))continue;let gmv=0,sales=0,count=0,missingGmv=false,missingSales=false;
    for(const r of p.records)if(inScope(r,s)){count++;if(r[2]===null)missingGmv=true;else gmv+=r[2];if(r[3]===null)missingSales=true;else sales+=r[3];}
    if(count)rows.push({...p,originalSignature:signature(p),originalReason:p.reason,originalStatus:p.status,...classify(p,compiled),gmv,sales,missingGmv,missingSales});
  }return rows;
}
const unknown = b => !b || ['未识别品牌','未知品牌','未知','unknown','其他'].includes(norm(b));
export function aggregate(rows,s,includePending=false,coverage=true){
  const selected=rows.filter(p=>p.status==='included'||(includePending&&p.status==='pending'));
  const brands=new Map(),prices=new Map(),tags=new Map(),trend=new Map(periodMonths(s).map(m=>[m,{month:m,gmv:0,sales:0,missingGmv:false}]));
  let gmv=0,sales=0,missingGmv=false,missingSales=false,unknownGmv=0;
  for(const p of selected){gmv+=p.gmv;sales+=p.sales;missingGmv ||= p.missingGmv;missingSales ||=p.missingSales;
    const name=unknown(p.brand)?'未识别品牌':p.brand,key=norm(name);
    if(!brands.has(key))brands.set(key,{name,gmv:0,sales:0,groups:0,known:!unknown(name),missing:false});
    const b=brands.get(key);b.gmv+=p.gmv;b.sales+=p.sales;b.groups++;b.missing ||=p.missingGmv;
    if(!b.known)unknownGmv+=p.gmv;
    for(const t of p.tags){if(!tags.has(t))tags.set(t,{name:t,gmv:0,groups:0});tags.get(t).gmv+=p.gmv;tags.get(t).groups++;}
    for(const r of p.records)if(inScope(r,s)){
      const t=trend.get(r[1]);t.gmv+=r[2]??0;t.sales+=r[3]??0;t.missingGmv ||=r[2]===null;
      // Monthly observed revenue / units, not list price or SKU retail price.
      const price=r[2]!==null&&r[3]>0&&r[2]>0?r[2]/r[3]:null;
      const key=price===null?'unknown':price<200?'0':price<500?'1':price<1000?'2':price<2000?'3':'4';
      const name={unknown:'价格未知 / 非正',0:'200元以下',1:'200—500元',2:'500—1,000元',3:'1,000—2,000元',4:'2,000元以上'}[key];
      if(!prices.has(key))prices.set(key,{key,name,gmv:0,sales:0});const bin=prices.get(key);bin.gmv+=r[2]??0;bin.sales+=r[3]??0;
    }
  }
  const bs=[...brands.values()].sort((a,b)=>b.gmv-a.gmv),shareValid=coverage&&!missingGmv&&gmv>0&&!bs.some(b=>b.gmv<0);
  for(const b of bs)b.share=shareValid?b.gmv/gmv:null;
  const cr5=shareValid?bs.filter(b=>b.known).slice(0,5).reduce((sum,b)=>sum+b.gmv,0)/gmv:null;
  return {gmv,sales,groups:selected.length,brandCount:bs.filter(b=>b.known&&(b.gmv>0||b.sales>0)).length,unknownGmv,missingGmv,missingSales,coverage,cr5,asp:!missingGmv&&!missingSales&&sales>0?gmv/sales:null,brands:bs,prices:[...prices.values()].sort((a,b)=>a.key.localeCompare(b.key)),tags:[...tags.values()].sort((a,b)=>b.gmv-a.gmv),trend:[...trend.values()]};
}
export function compare(now,before){
  const comparable=now.coverage&&before.coverage&&!now.missingGmv&&!before.missingGmv;
  const prior=new Map(before.brands.map(b=>[norm(b.name),b]));
  const current=new Set(now.brands.map(b=>norm(b.name))),all=[...now.brands];
  if(comparable)for(const b of before.brands)if(!current.has(norm(b.name)))all.push({...b,gmv:0,sales:0,groups:0,share:now.gmv>0?0:null});
  return {yoy:comparable&&before.gmv>0?now.gmv/before.gmv-1:null,brands:all.map(b=>{const p=prior.get(norm(b.name));return {...b,delta:comparable?b.gmv-(p?.gmv||0):null,shareDelta:comparable&&b.share!==null&&before.gmv>0?b.share-(p?.share||0):null};})};
}
export function impact(draft,published){
  const old=new Map(published.map(p=>[p.id,p]));let changed=0,added=0,removed=0,gmv=0;
  for(const p of draft){const o=old.get(p.id);if(!o||o.status!==p.status||o.tags.join('|')!==p.tags.join('|')){changed++;gmv+=p.gmv;}if(p.status==='included'&&o?.status!=='included')added+=p.gmv;if(o?.status==='included'&&p.status!=='included')removed+=p.gmv;old.delete(p.id);}
  for(const p of old.values()){changed++;gmv+=p.gmv;if(p.status==='included')removed+=p.gmv;}
  return {changed,gmv,added,removed,delta:added-removed};
}
export function queryRows(rows,q){
  const needle=norm(q.search);return rows.filter(p=>(q.status==='all'||p.status===q.status)&&(!needle||p.search.includes(needle))&&(!q.brand||(q.brand==='未识别品牌'?unknown(p.brand):norm(p.brand)===norm(q.brand)))&&(!q.tag||p.tags.includes(q.tag))).sort((a,b)=>b.gmv-a.gmv||a.id.localeCompare(b.id));
}
export function validateDataset(d){
  if(!d||d.schema!==1||typeof d.id!=='string'||!/^import-[a-z0-9-]{1,60}$/.test(d.id)||typeof d.name!=='string'||!d.name.trim()||!Array.isArray(d.products)||!d.products.length||d.products.length>200000)throw Error('数据包结构无效：需要schema=1、import-开头ID、名称和商品数组（最多20万组）');
  if(typeof d.source!=='string'||!d.source.trim()||typeof d.collectedAt!=='string'||!Number.isFinite(Date.parse(d.collectedAt)))throw Error('请提供数据来源source及有效采集时间collectedAt');
  const validMonth=m=>Number.isInteger(m)&&m>=200001&&m<=209912&&m%100>=1&&m%100<=12;
  if(!Array.isArray(d.coverage)||!d.coverage.length||d.coverage.some(x=>!Array.isArray(x)||!['tmall','jd','douyin'].includes(x[0])||!validMonth(x[1])))throw Error('coverage须声明已覆盖的平台与月份');
  const ids=new Set(),coverage=new Set(d.coverage.map(x=>x.join(':')));
  for(const p of d.products){
    if(!p||typeof p.id!=='string'||!p.id||ids.has(p.id))throw Error('商品组ID缺失或重复');ids.add(p.id);
    if(!['title','brand','source_category','reason'].every(k=>typeof p[k]==='string')||!STATUS[p.status]||!Array.isArray(p.models)||p.models.some(x=>typeof x!=='string')||!Array.isArray(p.records)||!p.records.length)throw Error(`商品 ${p.id} 字段不完整`);
    const keys=new Set();for(const r of p.records){if(!Array.isArray(r)||r.length!==5||!coverage.has(`${r[0]}:${r[1]}`)||[r[2],r[3]].some(v=>v!==null&&(typeof v!=='number'||!Number.isFinite(v)))||!Number.isInteger(r[4])||r[4]<1)throw Error(`商品 ${p.id} 月度记录无效`);const k=`${r[0]}:${r[1]}`;if(keys.has(k))throw Error(`商品 ${p.id} 同平台月份重复`);keys.add(k);}
  }return d;
}
export function validateWorkspace(doc){
  if(!doc||doc.schema!==SCHEMA||!Array.isArray(doc.categories)||!doc.categories.length||doc.categories.length>200)throw Error('不支持的备份版本或品类数量');
  const ids=new Set();for(const c of doc.categories){if(typeof c.id!=='string'||!c.id||ids.has(c.id)||!Array.isArray(c.revisions))throw Error('品类ID重复或版本记录无效');ids.add(c.id);validateRule(c.draft);let v=0;for(const r of c.revisions){if(!Number.isInteger(r.version)||r.version<=v||!Number.isFinite(Date.parse(r.at)))throw Error('版本顺序或时间无效');v=r.version;validateRule(r.rule);}}return doc;
}
