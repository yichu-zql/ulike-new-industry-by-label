import {SCHEMA,seedCategories,validateWorkspace} from './core.js';
let connection;
function db(){return connection ||=new Promise((resolve,reject)=>{const r=indexedDB.open('ulike-label-workbench',1);r.onupgradeneeded=()=>{r.result.createObjectStore('settings');r.result.createObjectStore('datasets');};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(Error('无法打开本地存储，请检查浏览器隐私或空间设置'));});}
async function transaction(store,mode,operation){const d=await db();return new Promise((resolve,reject)=>{const tx=d.transaction(store,mode);let result;const r=operation(tx.objectStore(store));r.onsuccess=()=>result=r.result;tx.oncomplete=()=>resolve(result);tx.onerror=()=>reject(Error('本地保存失败，可能空间不足；请立即导出备份'));tx.onabort=()=>reject(Error('本地保存已中止'));});}
export async function load(){const saved=await transaction('settings','readonly',s=>s.get('workspace'));return saved?validateWorkspace(saved):{schema:SCHEMA,categories:seedCategories()};}
export const save=doc=>{validateWorkspace(doc);return transaction('settings','readwrite',s=>s.put(doc,'workspace'));};
export const saveDataset=(id,file)=>transaction('datasets','readwrite',s=>s.put({id,file},id));
export const datasets=()=>transaction('datasets','readonly',s=>s.getAll());
export async function restore(doc,files){validateWorkspace(doc);const d=await db();return new Promise((resolve,reject)=>{const tx=d.transaction(['settings','datasets'],'readwrite');tx.objectStore('settings').put(doc,'workspace');tx.objectStore('datasets').clear();for(const f of files)tx.objectStore('datasets').put(f,f.id);tx.oncomplete=resolve;tx.onerror=()=>reject(Error('恢复失败，原数据未改变'));tx.onabort=()=>reject(Error('恢复事务已中止'));});}
