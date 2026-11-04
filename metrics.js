export const PLATFORMS={all:'三平台合计',tmall:'天猫',jd:'京东',douyin:'抖音'};
export const TARGETS={nebulizer:'家用医用压缩式雾化器',oxygen:'家用医用分子筛制氧机'};
export const LABELS={included:'纳入',pending:'待确认',excluded:'排除'};
export function period(s){return s.mode==='year'?String(s.year):`${s.year}-${String(s.month).padStart(2,'0')}`;}
export function summaryRow(data,s){return data[s.mode==='year'?'annual':'monthly'].find(r=>r['目标类目']===TARGETS[s.target]&&r['平台']===PLATFORMS[s.platform]&&r['期间']===period(s));}
export function months(data,s){return data.monthly.filter(r=>r['目标类目']===TARGETS[s.target]&&r['平台']===PLATFORMS[s.platform]&&r['期间'].startsWith(s.year+'-'));}
export function filterBrands(data,s,search=''){return data.filter(r=>r['平台']===PLATFORMS[s.platform]&&r['期间']===period(s)&&r['期间类型']===(s.mode==='year'?'自然年':'自然月')&&r['品牌'].toLowerCase().includes(search.trim().toLowerCase())).sort((a,b)=>b['已纳入GMV_元']-a['已纳入GMV_元']);}
export function scopedProducts(data,s){return data.flatMap(p=>{const records=p.records.filter(r=>(s.platform==='all'||r[0]===s.platform)&&Math.floor(r[1]/100)===s.year&&(s.mode==='year'||r[1]%100===s.month));if(!records.length)return[];return[{...p,gmv:records.reduce((n,r)=>n+r[2],0),sales:records.reduce((n,r)=>n+r[3],0),monthRows:records.reduce((n,r)=>n+r[4],0)}];});}
export function filterProducts(data,status,search=''){const q=search.trim().toLowerCase();return data.filter(p=>(status==='all'||p.status===status)&&(!q||`${p.title} ${p.brand} ${p.models.join(' ')}`.toLowerCase().includes(q))).sort((a,b)=>b.gmv-a.gmv);}
export function csvText(rows){if(!rows.length)return'';const keys=Object.keys(rows[0]);const value=v=>{let s=v==null?'':String(v);if(/^[=+@\-]/.test(s))s="'"+s;return'"'+s.replaceAll('"','""')+'"';};return'\ufeff'+[keys,...rows.map(r=>keys.map(k=>r[k]))].map(r=>r.map(value).join(',')).join('\r\n');}
