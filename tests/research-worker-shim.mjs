import {parentPort} from 'node:worker_threads';import fs from 'node:fs/promises';
globalThis.self=globalThis;self.postMessage=x=>parentPort.postMessage(x);
const realFetch=globalThis.fetch;
globalThis.fetch=async function(url,options){const u=new URL(url);if(u.protocol!=='file:')return realFetch(url,options);try{return new Response(await fs.readFile(u),{status:200});}catch{return new Response('',{status:404});}};
await import('../workbench/worker.js');parentPort.on('message',data=>self.onmessage({data}));
