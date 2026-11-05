import {Worker} from 'node:worker_threads';import fs from 'node:fs/promises';import {performance} from 'node:perf_hooks';import {seedCategories} from '../workbench/core.js';
const w=new Worker(new URL('../tests/research-worker-shim.mjs',import.meta.url));let id=0;const calls=new Map();
w.on('message',r=>{const p=calls.get(r.id);calls.delete(r.id);r.error?p.reject(Error(r.error)):p.resolve(r.result);});
const rpc=(method,args={})=>new Promise((resolve,reject)=>{const n=++id;calls.set(n,{resolve,reject});w.postMessage({id:n,method,args});});
const timed=async fn=>{const t=performance.now(),result=await fn();return {ms:Math.round((performance.now()-t)*10)/10,result};};
const params=rule=>({draft:rule,published:rule,scope:{from:202601,to:202609,platform:'all'},mode:'published',includePending:false,view:'review',page:1,query:{status:'all',search:''}});
try{
 await rpc('init');const native=await timed(()=>rpc('analyze',params(seedCategories()[0].draft)));
 const rule={...seedCategories()[0].draft,sources:['import-benchmark'],inherit:true};
 const count=50000,dataset={schema:1,id:'import-benchmark',name:'合成压力样本',source:'自动化合成数据，仅性能测试',collectedAt:new Date().toISOString(),coverage:['tmall','jd','douyin'].flatMap(p=>Array.from({length:21},(_,i)=>[p,i<12?202501+i:202601+i-12])),products:Array.from({length:count},(_,i)=>({id:String(i),title:`家用便携测试设备 ${i}`,brand:`品牌${i%500}`,models:[],status:'included',reason:'合成测试',source_category:'测试',records:[['tmall',202609,100+i,2,1],['tmall',202509,80+i,2,1]]}))};
 const file=new Blob([JSON.stringify(dataset)],{type:'application/json'});await rpc('import',{file});
 let maxDelay=0,last=performance.now();const heartbeat=setInterval(()=>{const now=performance.now();maxDelay=Math.max(maxDelay,now-last-10);last=now;},10);
 const cold=await timed(()=>rpc('analyze',params(rule)));const searches=[];
 for(let i=0;i<20;i++){const r=await timed(()=>rpc('query',{...params(rule),query:{status:'all',search:`品牌${i}`}}));searches.push(r.ms);}
 const warm=await timed(()=>rpc('analyze',params(rule)));clearInterval(heartbeat);searches.sort((a,b)=>a-b);
 const report={at:new Date().toISOString(),environment:`Node ${process.version}, worker_threads, file-backed fetch (not browser/network timing)`,nativeCurrentRows:native.result.total,nativeColdMs:native.ms,syntheticGroups:count,syntheticMonthlyRows:count*2,syntheticColdMs:cold.ms,syntheticWarmMs:warm.ms,searchP50Ms:searches[10],searchP95Ms:searches[18],mainLoopMaxDelayMs:Math.round(maxDelay*10)/10,responseBytes:Buffer.byteLength(JSON.stringify(cold.result)),renderedProductRows:cold.result.rows.length,renderedBrandRows:cold.result.brands.length};
 await fs.mkdir('outputs',{recursive:true});await fs.writeFile('outputs/workbench-performance.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}finally{await w.terminate();}
