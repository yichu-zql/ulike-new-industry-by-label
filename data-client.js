// Lightweight future-site client. Manifest is revalidated; immutable assets are cached.
export function createLabelDataClient(base = './data/') {
  const root = new URL(base, globalThis.location?.href || 'http://localhost/');
  let manifestPromise;
  const cache = new Map();
  async function manifest() {
    return manifestPromise ||= fetch(new URL('manifest.json', root), {cache:'no-cache'})
      .then(r=>{if(!r.ok)throw new Error(`数据清单加载失败 (${r.status})`);return r.json();})
      .then(m=>{if(m.schema_version!==1)throw new Error('不支持的数据版本');return m;})
      .catch(e=>{manifestPromise=null;throw e;});
  }
  async function load(name) {
    if(cache.has(name))return cache.get(name);
    const promise=(async()=>{
      const m=await manifest(), a=m.assets[name];
      if(!a)throw new Error(`数据分片不存在: ${name}`);
      if(typeof DecompressionStream!=='undefined') {
        const r=await fetch(new URL(a.gzip,root),{cache:'force-cache'});
        if(!r.ok)throw new Error(`数据加载失败 (${r.status})`);
        const raw=await r.arrayBuffer();
        // Handle hosts that decompress gzip automatically, as well as Pages .gz files.
        const bytes=new Uint8Array(raw);
        const text=bytes[0]===0x1f&&bytes[1]===0x8b
          ?await new Response(new Blob([raw]).stream().pipeThrough(new DecompressionStream('gzip'))).text()
          :new TextDecoder().decode(raw);
        return JSON.parse(text);
      }
      const r=await fetch(new URL(a.path,root),{cache:'force-cache'});
      if(!r.ok)throw new Error(`数据加载失败 (${r.status})`);
      return r.json();
    })();
    cache.set(name,promise);
    try{return await promise;}catch(e){cache.delete(name);throw e;}
  }
  return {manifest,load,clear(){cache.clear();manifestPromise=null;}};
}
