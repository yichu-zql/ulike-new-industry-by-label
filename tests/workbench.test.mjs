import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {seedCategories,clone,compileRule,classify,signature,mergeProducts,evaluate,aggregate,compare,impact,queryRows,validateDataset,validateWorkspace,periodMonths} from '../workbench/core.js';
const manifest=JSON.parse(fs.readFileSync(new URL('../data/manifest.json',import.meta.url)));
const load=n=>JSON.parse(fs.readFileSync(new URL('../data/'+manifest.assets[n].path,import.meta.url)));
const p={id:'a',title:'家用儿童便携设备',brand:'品牌A',status:'pending',reason:'证据不足',source_category:'器械',models:[],records:[['tmall',202609,200,2,1]],source:'nebulizer',search:'家用儿童便携设备 品牌a'};
const s={from:202609,to:202609,platform:'all'},base=seedCategories()[0].draft;
test('precedence, literal matching, source inheritance and unknowns',()=>{
 const rule={...clone(base),inherit:false,include:'家用',exclude:'儿童',attributes:'便携=便携,旅行'};
 assert.equal(classify(p,compileRule(rule)).status,'excluded');rule.exclude='';assert.equal(classify(p,compileRule(rule)).status,'included');
 rule.include='[a-z]';assert.equal(classify(p,compileRule(rule)).status,'pending');
 rule.overrides.a={status:'included',note:'人工证据',signature:signature(p)};rule.exclude='家用';assert.equal(classify(p,compileRule(rule)).basis,'manual');
 assert.equal(classify({...p,title:'变更商品'},compileRule(rule)).basis,'changed');
});
test('manual decisions preserve source fingerprint after keyword classification and repeated review',()=>{
 const rule={...clone(base),inherit:false,include:'家用'};const row=evaluate([p],rule,s)[0];assert.equal(row.status,'included');
 rule.overrides.a={status:'excluded',note:'配件',signature:signature(row)};
 const next=evaluate([p],rule,s)[0];assert.equal(next.status,'excluded');assert.equal(next.basis,'manual');
 rule.overrides.a={status:'included',note:'确认整机',signature:signature(next)};
 assert.equal(evaluate([p],rule,s)[0].status,'included');
});
test('all native target/year/platform baseline totals reconcile to published snapshot',()=>{
 const summary=load('summary');let checked=0;
 for(const c of seedCategories())for(const year of [2023,2024,2025,2026]){
  const products=mergeProducts([{source:c.id,rows:load(`products-${c.id}-${year}`)}]);
  for(const [platform,name] of Object.entries(manifest.platforms)){
   const scope={from:year*100+1,to:year*100+(year===2026?9:12),platform},rows=evaluate(products,c.draft,scope),stats=aggregate(rows,scope);
   const expected=summary.annual.find(r=>r.目标类目===manifest.targets[c.id]&&r.平台===name&&r.期间===String(year));
   assert.ok(Math.abs(stats.gmv-expected.已纳入GMV_元)<.1,`${c.id}/${year}/${platform}`);
   assert.equal(stats.brandCount,expected.涉及成交品牌数);assert.ok(Math.abs(stats.brands.reduce((a,b)=>a+b.gmv,0)-stats.gmv)<.01);checked++;
  }
 }assert.equal(checked,32);
});
test('unknown brand denominator, missing amounts, weighted price and overlap tags',()=>{
 const r={...clone(base),inherit:false,include:'家用',attributes:'便携=便携\n儿童=儿童'};
 const rows=evaluate([p,{...p,id:'b',brand:'未知',records:[['tmall',202609,100,1,1]]}],r,s),a=aggregate(rows,s);
 assert.equal(a.gmv,300);assert.equal(a.asp,100);assert.equal(a.brandCount,1);assert.equal(a.cr5,2/3);assert.equal(a.tags.length,2);assert.equal(a.tags[0].gmv,300);
 assert.equal(queryRows(rows,{status:'all',brand:'未识别品牌'}).length,1);
 const missing=aggregate(evaluate([{...p,records:[['tmall',202609,null,1,1]]}],r,s),s);assert.equal(missing.asp,null);assert.equal(missing.cr5,null);
 assert.equal(compare(a,missing).yoy,null);assert.equal(compare({...a,coverage:false},a).yoy,null);
});
test('same rule recomputes history; exited brands retain negative contribution',()=>{
 const r={...clone(base),inherit:false,include:'家用'};
 const data=[p,{...p,id:'b',brand:'品牌B',records:[['tmall',202509,100,1,1]]}];
 const now=aggregate(evaluate(data,r,s),s),prior={...s,from:202509,to:202509},before=aggregate(evaluate(data,r,prior),prior);
 const c=compare(now,before);assert.equal(c.yoy,1);assert.equal(c.brands.find(b=>b.name==='品牌B').delta,-100);assert.equal(c.brands.reduce((n,b)=>n+b.delta,0),100);
});
test('impact handles removed source products and draft does not mutate published',()=>{
 const pub=clone(base),draft=clone(pub);draft.inherit=false;draft.include='家用';
 const before=evaluate([p],pub,s),after=evaluate([p],draft,s);assert.equal(impact(after,before).added,200);assert.equal(pub.include,'');
 assert.equal(impact([],after).removed,200);assert.equal(impact([],after).changed,1);
});
test('imports reject duplicate IDs, duplicate months, unsupported scope and missing not zero',()=>{
 const d={schema:1,id:'import-test',name:'测试',source:'测试源',collectedAt:'2026-11-05',coverage:[['tmall',202609]],products:[{...p,id:'x'}]};
 assert.equal(validateDataset(d).products.length,1);
 assert.throws(()=>validateDataset({...d,products:[d.products[0],d.products[0]]}));
 assert.throws(()=>validateDataset({...d,products:[{...p,records:[...p.records,...p.records]}]}));
 assert.throws(()=>validateDataset({...d,coverage:[['tmall',202613]]}));
 assert.throws(()=>validateDataset({...d,products:[{...p,records:[['tmall',202609,'100',1,1]]}]}));
 assert.equal(validateDataset({...d,products:[{...p,records:[['tmall',202609,null,null,1]]}]}).products[0].records[0][2],null);
});
test('backup schema, revision order and attribute grammar are checked',()=>{
 const d={schema:1,categories:seedCategories()};assert.equal(validateWorkspace(d),d);assert.throws(()=>validateWorkspace({...d,schema:2}));
 const x=clone(d);x.categories[0].revisions.push(clone(x.categories[0].revisions[0]));assert.throws(()=>validateWorkspace(x));
 assert.throws(()=>compileRule({...base,attributes:'格式错误'}));assert.throws(()=>compileRule({...base,attributes:'便携=便携\n便携=旅行'}));
});
test('month arithmetic handles year boundaries and per platform filtering',()=>{
 assert.deepEqual(periodMonths({from:202511,to:202602}),[202511,202512,202601,202602]);
 assert.equal(evaluate([p],base,{...s,platform:'jd'}).length,0);
});
