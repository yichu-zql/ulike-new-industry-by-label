import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const site=path.resolve(here,'..');
const out=path.resolve(here,'../outputs/medical-label-review-20261104');
const m=JSON.parse(await fs.readFile(path.join(site,'data/manifest.json'),'utf8'));
const data=JSON.parse(await fs.readFile(path.join(site,'data',m.assets.summary.path),'utf8'));
const w=Workbook.create();
const platforms=['天猫','京东','抖音'];
const cats=Object.values(m.targets);
const monthly=cats.flatMap(c=>platforms.flatMap(p=>data.monthly.filter(r=>r['目标类目']===c&&r['平台']===p).sort((a,b)=>a['期间'].localeCompare(b['期间']))));
const datestr=s=>new Date(s+'-01T00:00:00Z');
const monthlyRows=monthly.map(r=>[r['目标类目'],r['平台'],datestr(r['期间']),r['已纳入销量_件'],r['已纳入GMV_元'],r['已纳入GMV_元']===null?'暂未取得':'已覆盖样本']);
const brands=cats.flatMap(c=>[2023,2024,2025,2026].map(y=>{const get=p=>data.annual.find(r=>r['目标类目']===c&&r['平台']===p&&r['期间']===String(y))['涉及成交品牌数'];return[c,y,...platforms.map(get),get('三平台合计'),y===2026?'1—9月':'1—12月'];}));
function make(name,title,notes,heads,rows,widths){
 const s=w.worksheets.add(name);s.showGridLines=false;const end=String.fromCharCode(64+heads.length),last=9+rows.length;
 s.getRange(`A1:${end}${last}`).format={font:{name:'Microsoft YaHei',size:10,color:'#263445'},verticalAlignment:'center',rowHeight:24};
 s.getRange('A2').values=[[title]];s.getRange('A2').format.font={size:15,bold:true,color:'#204C47'};
 notes.forEach((n,i)=>{s.getRange(`A${i+3}`).values=[[n]];s.getRange(`A${i+3}`).format.font={size:10,color:'#59666A'};});
 s.getRange(`A9:${end}9`).values=[heads];s.getRange(`A9:${end}9`).format={fill:'#204C47',font:{bold:true,color:'#FFFFFF'},rowHeight:30,horizontalAlignment:'center'};
 s.getRange(`A10:${end}${last}`).values=rows;
 widths.forEach((v,i)=>s.getRangeByIndexes(0,i,last,1).format.columnWidthPx=v);
 s.tables.add(`A9:${end}${last}`,true,name==='月度明细'?'MonthlyData':name==='年度品牌数'?'AnnualBrands':'CategoryAnnual');
 if(rows.length>20)s.freezePanes.freezeRows(9);
 return s;
}
const a=make('月度明细','家用医疗设备月度明细',[
 '来源：久谦商品月表。2023.01—2026.09，天猫、京东、抖音。2026.10—12数据缺失留空。',
 '打标逻辑：家用（含家庭用、居家）直接纳入；同品牌标准型号及同平台商品历史链接补充证据。',
 '明确的非目标原理、专业操作设备、配件、储雾罐、口腔清新喷雾等排除。证据不足不计入。',
 '符合口径的混合链接按整条链接计入，未拆分配件或套餐。数据为已覆盖样本，非完整行业总量。',
 'GMV为人民币元，使用源字段gmv；销量沿用sales_num。规则v3.0.0，复核日期2026-11-04。'
],['类目','统计平台','年月','销量（件）','GMV（元）','数据状态'],monthlyRows,[255,95,110,145,175,135]);
a.getRange(`C10:C${9+monthlyRows.length}`).setNumberFormat('yyyy-mm');
a.getRange(`D10:D${9+monthlyRows.length}`).setNumberFormat('#,##0');
a.getRange(`E10:E${9+monthlyRows.length}`).setNumberFormat('#,##0.00');
a.getRange(`C10:E${9+monthlyRows.length}`).format.horizontalAlignment='right';
const b=make('年度品牌数','各类目年度成交品牌数',[
 '统计范围与月度明细一致，仅统计已纳入且GMV或销量大于零的已识别品牌。',
 '年度品牌数按品牌去重，不累加月度品牌数。三平台合计取品牌并集，不累加各平台数量。',
 '品牌统一已确认的中英文别名。未识别品牌不计入；2026年为1—9月累计。',
 '原始商品样本有截断迹象，因此这里是已覆盖商品的成交品牌数，不等于全行业品牌数。',
 '来源：久谦商品月表，规则v3.0.0。详细打标逻辑见月度明细上方备注。'
],['类目','自然年','天猫品牌数','京东品牌数','抖音品牌数','三平台去重品牌数','覆盖月份'],brands,[255,90,125,125,125,165,115]);
b.getRange('B10:B17').setNumberFormat('0');b.getRange('C10:F17').setNumberFormat('#,##0');b.getRange('B10:F17').format.horizontalAlignment='right';
const platformKeys={'天猫':'tmall','京东':'jd','抖音':'douyin'};
function comparison(cat,plat,period){
 const target=Object.keys(m.targets).find(k=>m.targets[k]===cat),year=String(period).slice(0,4),month=String(period).length>4?Number(String(period).slice(5)):null;
 const rows=data.category_comparison.filter(r=>r.target===target&&String(r.month).startsWith(year)&&(plat==='三平台合计'||r.platform===platformKeys[plat])&&(!month||r.month%100===month));
 if(!rows.length)return[null,null,null,null];
 const sum=k=>Math.round(rows.reduce((s,r)=>s+r[k],0)*100)/100;
 return[sum('category_gmv'),sum('labeled_in'),sum('labeled_out'),sum('labeled_in')+sum('labeled_out')];
}
const comparisonHeads=['原始类目','统计平台','期间','原类目行业GMV（元）','类目内打标GMV（元）','打标占原类目','跨类目补充GMV（元）','全部打标GMV（元）','状态'];
const annualComparison=cats.flatMap(cat=>[2023,2024,2025,2026].map(year=>{const [raw,inc,out,total]=comparison(cat,'三平台合计',year);return[cat==='家用医用压缩式雾化器'?'雾化器':'制氧机','三平台合计',year,raw,inc,null,out,total,year===2026?'1—9月':'全年'];}));
const monthlyComparison=monthly.map(r=>{const [raw,inc,out,total]=comparison(r['目标类目'],r['平台'],r['期间']);return[r['目标类目']==='家用医用压缩式雾化器'?'雾化器':'制氧机',r['平台'],datestr(r['期间']),raw,inc,null,out,total,raw===null?'暂未取得':'已覆盖样本'];});
const c=make('类目销售额与占比','原始类目销售额与打标占比',[
 '分母为久谦行业月表原始雾化器／制氧机GMV；分子只取同类目、同平台、同期间的已纳入商品。',
 '跨类目补充GMV单列，不进入占比分子。全部打标GMV＝类目内打标GMV＋跨类目补充GMV。',
 '商品表存在截断，占比反映已取得样本的识别结果，不代表完整目标市场份额。所有金额为人民币元。',
 '上方为三平台年度汇总，下方为各平台自然月明细。不同粒度不重复加总；2026年为1—9月。',
 '来源：久谦行业月表与商品月表。同一数据快照、标签规则v3.0.0。'
],comparisonHeads,annualComparison,[120,110,110,175,175,115,175,175,115]);
c.getRange('B20').values=[['各平台自然月明细']];c.getRange('B20').format.font={bold:true,size:12};
const lastComparison=21+monthlyComparison.length;
c.getRange(`A21:I21`).values=[comparisonHeads];c.getRange('A21:I21').format={fill:'#204C47',font:{name:'Microsoft YaHei',size:10,bold:true,color:'#FFFFFF'},rowHeight:30,horizontalAlignment:'center'};
c.getRange(`A22:I${lastComparison}`).values=monthlyComparison;c.getRange(`A22:I${lastComparison}`).format={font:{name:'Microsoft YaHei',size:10,color:'#263445'},rowHeight:24,verticalAlignment:'center'};
c.tables.add(`A21:I${lastComparison}`,true,'CategoryMonthly');
c.getRange('C10:C17').setNumberFormat('0');c.getRange(`C22:C${lastComparison}`).setNumberFormat('yyyy-mm');
for(const range of ['D10:H17',`D22:H${lastComparison}`]){c.getRange(range).setNumberFormat('#,##0.00');c.getRange(range).format.horizontalAlignment='right';}
for(const range of ['F10:F17',`F22:F${lastComparison}`])c.getRange(range).setNumberFormat('0.00%');
for(let i=0;i<annualComparison.length;i++){
 const row=i+10;
 for(const col of ['D','E','G'])c.getRange(`${col}${row}`).formulas=[[`=SUMIFS(${col}$22:${col}$${lastComparison},$A$22:$A$${lastComparison},A${row},$C$22:$C$${lastComparison},">="&DATE(C${row},1,1),$C$22:$C$${lastComparison},"<"&DATE(C${row}+1,1,1))`]];
 c.getRange(`F${row}`).formulas=[[`=IF(D${row}=0,"",E${row}/D${row})`]];c.getRange(`H${row}`).formulas=[[`=E${row}+G${row}`]];
}
monthlyComparison.forEach((r,i)=>{if(r[3]!==null){const row=i+22;c.getRange(`F${row}`).formulas=[[`=IF(D${row}=0,"",E${row}/D${row})`]];c.getRange(`H${row}`).formulas=[[`=E${row}+G${row}`]];}});
w.recalculate();
annualComparison.forEach((r,i)=>{for(const [col,index] of [['D',3],['E',4],['G',6],['H',7]])if(Math.abs(c.getRange(`${col}${i+10}`).values[0][0]-r[index])>.03)throw Error('Category annual reconciliation failed');});
if(monthlyRows.length!==288||brands.length!==8)throw Error('Unexpected coverage');
for(const cat of cats)for(const plat of platforms)for(const year of [2023,2024,2025,2026]){
 const rows=monthly.filter(r=>r['目标类目']===cat&&r['平台']===plat&&r['期间'].startsWith(String(year)));
 const annual=data.annual.find(r=>r['目标类目']===cat&&r['平台']===plat&&r['期间']===String(year));
 for(const k of ['已纳入GMV_元','已纳入销量_件'])if(Math.abs(rows.reduce((v,r)=>v+(r[k]??0),0)-annual[k])>.02)throw Error('Monthly annual mismatch');
}
console.log((await w.inspect({kind:'table',range:'年度品牌数!A9:G17',tableMaxRows:9,tableMaxCols:7,maxChars:1800})).ndjson);
console.log((await w.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:10},maxChars:500})).ndjson);
await fs.mkdir(out,{recursive:true});
for(const name of ['月度明细','年度品牌数','类目销售额与占比']){const blob=await w.render({sheetName:name,range:name==='月度明细'?'A2:F16':name==='年度品牌数'?'A2:G17':'A2:I17',scale:1,format:'png'});await fs.writeFile(path.join(here,`v3-preview-${name}.png`),new Uint8Array(await blob.arrayBuffer()));}
const file=path.join(out,'家用医疗设备_月度明细与年度品牌数.xlsx');
await(await SpreadsheetFile.exportXlsx(w)).save(file);
await fs.mkdir(path.join(site,'downloads'),{recursive:true});await fs.copyFile(file,path.join(site,'downloads/medical-category-v3.xlsx'));
console.log(JSON.stringify({file,monthly_rows:monthlyRows.length,annual_brand_rows:brands.length,missing_month_rows:monthlyRows.filter(x=>x[4]===null).length}));
