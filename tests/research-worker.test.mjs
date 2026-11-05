import test from 'node:test';import assert from 'node:assert/strict';import {Worker} from 'node:worker_threads';import {seedCategories,clone,signature} from '../workbench/core.js';
test('real background worker: bounded pages, rapid-switch latest result, manual edit, CSV and backup roundtrip',async()=>{
 const w=new Worker(new URL('./research-worker-shim.mjs',import.meta.url));let id=0;const pending=new Map();w.on('message',r=>{const p=pending.get(r.id);pending.delete(r.id);r.error?p.reject(Error(r.error)):p.resolve(r.result);});
 const rpc=(method,args={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});w.postMessage({id:n,method,args});});
 try{
  const m=await rpc('init');assert.equal(m.asOf,202609);
  const seed=seedCategories(),params=c=>({draft:c.draft,published:c.revisions[0].rule,scope:{from:202601,to:202609,platform:'all'},mode:'published',includePending:false,view:'review',page:1,query:{status:'all',search:''}});
  const a=rpc('analyze',params(seed[0])),b=rpc('analyze',params(seed[1]));const [old,r]=await Promise.all([a,b]);assert.equal(old.superseded,true);assert.ok(r.total>30);assert.equal(r.rows.length,30);assert.ok(r.brands.length<=20);assert.ok(JSON.stringify(r).length<50000);
  const p=await rpc('detail',{id:r.rows[0].id,view:'review'}),args=params(seed[1]);args.draft=clone(args.draft);args.draft.overrides[p.id]={status:'excluded',signature:signature(p),note:'测试复核'};
  const changed=await rpc('analyze',args);const d=await rpc('detail',{id:p.id,view:'review'});assert.equal(d.status,'excluded');assert.equal(d.basis,'manual');
  assert.equal(changed.stats.gmv,r.stats.gmv,'草稿修改不改变正式分析');
  const exported=await rpc('export',{name:'测试品类',version:'草稿',kind:'products'});const csv=await exported.blob.text();assert.ok(csv.includes('规则草稿'));assert.equal(exported.count,changed.total);
  const backup=await rpc('backup',{doc:{schema:1,categories:seed}});const roundtrip=await rpc('backupParse',{file:backup});assert.equal(roundtrip.doc.categories.length,2);
  const search=await rpc('query',{...args,query:{status:'all',search:'不存在的品牌abcxyz'}});assert.equal(search.total,0);assert.equal(search.page,1);
  const page=await rpc('query',{...args,page:999999});assert.ok(page.page<999999);assert.ok(page.rows.length<=30);
 }finally{await w.terminate();}
});
