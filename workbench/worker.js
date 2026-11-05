import {createLabelDataClient} from '../data-client.js';
import {csvText} from '../metrics.js';
import {mergeProducts,evaluate,aggregate,compare,impact,queryRows,validateDataset,validateWorkspace,periodMonths,norm} from './core.js';
const client=createLabelDataClient(new URL('../data/',import.meta.url).href);
const imports=new Map(), evaluated=new Map();let manifest,last,latest=0;
const getManifest=async()=>manifest ||=await client.manifest();
const compact=p=>({id:p.id,title:p.title,brand:p.brand,status:p.status,reason:p.reason,basis:p.basis,tags:p.tags,gmv:p.gmv,sales:p.sales,missingGmv:p.missingGmv});
async function sources(){const m=await getManifest();return [...Object.entries(m.targets).map(([id,name])=>({id,name,source:'久谦商品月表 · 原研究候选样本',collectedAt:m.snapshot.finished_at,cutoff:m.as_of_month})),...[...imports.values()].map(d=>({id:d.id,name:d.name,source:d.source,collectedAt:d.collectedAt,cutoff:Math.max(...d.coverage.map(x=>x[1]))}))];}
async function loadProducts(sourceIds,s){
  const m=await getManifest(),parts=[];
  for(const source of sourceIds){
    if(imports.has(source)){parts.push({source,rows:imports.get(source).products});continue;}
    if(!m.targets[source])throw Error(`缺少数据源 ${source}，请导入对应数据包`);
    const names=[];for(let y=Math.floor(s.from/100)-1;y<=Math.floor(s.to/100);y++){const name=`products-${source}-${y}`;if(m.assets[name])names.push(name);}
    // Limit concurrent decompression; immutable shards remain cached in this worker.
    for(let i=0;i<names.length;i+=2){const batch=await Promise.all(names.slice(i,i+2).map(n=>client.load(n)));for(const rows of batch)parts.push({source,rows});}
  }return mergeProducts(parts);
}
function covered(ids,s){
  const plats=s.platform==='all'?['tmall','jd','douyin']:[s.platform];
  return ids.every(id=>{const d=imports.get(id);if(d){const cov=new Set(d.coverage.map(r=>r.join(':')));return periodMonths(s).every(m=>plats.every(p=>cov.has(`${p}:${m}`)));}return periodMonths(s).every(m=>m<=manifest.as_of_month&&!!manifest.assets[`products-${id}-${Math.floor(m/100)}`]);});
}
async function calculate(a,id){
  latest=id;const {draft,published,scope,mode,includePending}=a;
  const key=JSON.stringify({draft,published,scope,mode,includePending});let result=evaluated.get(key);
  if(!result){
    const ids=[...new Set([...draft.sources,...(published?.sources||[])])],products=await loadProducts(ids,scope);
    if(id!==latest)return {superseded:true};
    const dr=evaluate(products,draft,scope),pr=published?evaluate(products,published,scope):[];
    const rule=mode==='draft'?draft:published,active=mode==='draft'?dr:pr,previousScope={...scope,from:scope.from-100,to:scope.to-100};
    const now=aggregate(active,scope,includePending,!!rule&&covered(rule.sources,scope));
    const before=aggregate(rule?evaluate(products,rule,previousScope):[],previousScope,includePending,!!rule&&covered(rule.sources,previousScope));
    const cmp=compare(now,before);now.brands=cmp.brands;now.yoy=cmp.yoy;
    for(const t of now.trend)t.covered=!!rule&&covered(rule.sources,{...scope,from:t.month,to:t.month});
    result={dr,pr,active,stats:now,impact:impact(dr,pr),scope,mode,rule,includePending,counts:Object.fromEntries(['included','pending','excluded'].map(st=>{const rs=dr.filter(p=>p.status===st);return[st,{count:rs.length,gmv:rs.reduce((sum,p)=>sum+p.gmv,0)}];}))};
    evaluated.set(key,result);if(evaluated.size>5)evaluated.delete(evaluated.keys().next().value);
  }
  last=result;return view(a);
}
function view(a){
  if(!last)throw Error('请先载入数据');
  const q=a.query||{status:'all',search:''},rows=queryRows(a.view==='review'?last.dr:last.active.filter(p=>p.status==='included'||last.includePending&&p.status==='pending'),q);
  const page=Math.max(1,Math.min(a.page||1,Math.ceil(rows.length/30)||1));
  const brandRows=last.stats.brands.filter(b=>!a.brandSearch||norm(b.name).includes(norm(a.brandSearch))),bp=Math.max(1,Math.min(a.brandPage||1,Math.ceil(brandRows.length/20)||1));
  last.exportRows=rows;last.exportQuery=q;last.exportView=a.view;
  const {brands,...stats}=last.stats;
  return {stats,brands:brandRows.slice((bp-1)*20,bp*20),brandCount:brandRows.length,brandPage:bp,rows:rows.slice((page-1)*30,page*30).map(compact),total:rows.length,page,impact:last.impact,counts:last.counts};
}
const api={
  async init(){const m=await getManifest();return {sources:await sources(),asOf:m.as_of_month,snapshot:m.snapshot,ruleVersion:m.rule_version};},
  analyze:calculate,
  query:view,
  detail({id,view}){const p=(view==='review'?last?.dr:last?.active)?.find(p=>p.id===id);if(!p)throw Error('商品不在当前范围内');return p;},
  async import({file}){if(file.size>100*1024*1024)throw Error('单个数据包最多100MB');const d=validateDataset(JSON.parse(await file.text()));if(imports.has(d.id))throw Error('来源ID已存在，请使用新ID导入新快照，避免覆盖历史数据');imports.set(d.id,d);evaluated.clear();return {id:d.id,name:d.name,count:d.products.length,sources:await sources()};},
  removeImport({id}){imports.delete(id);evaluated.clear();return true;},
  export({name,version,kind}){
    if(!last)throw Error('尚无可导出数据');
    const common={品类:name,版本:version,口径:last.exportView==='review'||last.mode==='draft'?'规则草稿':'正式本地版本',含待确认:last.exportView==='review'?'按筛选状态':last.includePending?'是':'否',开始月份:last.scope.from,结束月份:last.scope.to,平台:last.scope.platform};
    const rows=kind==='brands'?last.stats.brands.map(b=>({...common,品牌:b.name,GMV_元:b.gmv,销量_件:b.sales,份额:b.share,同比增加额_元:b.delta,份额变化_百分点:b.shareDelta===null?null:b.shareDelta*100})):last.exportRows.map(p=>({...common,商品组ID:p.id,标题:p.title,品牌:p.brand,状态:p.status,依据:p.reason,标签:p.tags.join('；'),GMV_元:p.gmv,金额缺失:p.missingGmv?'部分缺失':'否',销量_件:p.sales}));
    return {blob:new Blob([csvText(rows)],{type:'text/csv;charset=utf-8'}),count:rows.length};
  },
  backup({doc}){validateWorkspace(doc);return new Blob([JSON.stringify({type:'ulike-label-backup',schema:1,createdAt:new Date().toISOString(),workspace:doc,datasets:[...imports.values()]})],{type:'application/json'});},
  async backupParse({file}){if(file.size>200*1024*1024)throw Error('备份文件最多200MB');const b=JSON.parse(await file.text());if(b.type!=='ulike-label-backup'||b.schema!==1||!Array.isArray(b.datasets))throw Error('备份格式不兼容');validateWorkspace(b.workspace);const ids=new Set(['nebulizer','oxygen']);const files=b.datasets.map(d=>{validateDataset(d);if(ids.has(d.id))throw Error('备份来源ID重复');ids.add(d.id);return {id:d.id,file:new Blob([JSON.stringify(d)],{type:'application/json'})};});for(const c of b.workspace.categories)for(const rule of [c.draft,...c.revisions.map(r=>r.rule)])if(rule.sources.some(id=>!ids.has(id)))throw Error('备份缺少品类引用的数据包');return {doc:b.workspace,files};}
};
self.onmessage=async({data:{id,method,args}})=>{try{if(!api[method])throw Error('未知操作');const result=await api[method](args,id);self.postMessage({id,result});}catch(e){self.postMessage({id,error:e.message||String(e)});}};
