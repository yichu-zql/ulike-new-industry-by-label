"""Read-only, consistent-snapshot extraction; reusable local cache. No credentials saved."""
import sys,os,json,gzip,pathlib,datetime,time,hashlib
sys.path.insert(0,os.environ['JQ_DEPENDENCIES'])
import pymysql
ROOT=pathlib.Path(__file__).resolve().parent
RAW=ROOT/'raw';RAW.mkdir(exist_ok=True)
cfg=json.load(sys.stdin)
c=pymysql.connect(**cfg,charset='utf8mb4',connect_timeout=20,read_timeout=900,cursorclass=pymysql.cursors.SSCursor)
queries={
 'industry':"SELECT y_m,plat,jq_cate1,jq_cate2,jq_cate3,cate1,cate2,cate3,cate4,gmv,sales_num,insert_time FROM jq_sale_industry_m WHERE y_m BETWEEN 202301 AND 202612 AND jq_cate3 IN ('雾化器','制氧机')",
 'brands':"SELECT y_m,plat,jq_cate1,jq_cate2,jq_cate3,cate1,cate2,cate3,cate4,brand_name,gmv,sales_num,insert_time FROM jq_sale_brand_m WHERE y_m BETWEEN 202301 AND 202612 AND jq_cate3 IN ('雾化器','制氧机')",
 'items':"SELECT y_m,plat,jq_cate1,jq_cate2,jq_cate3,cate1,cate2,cate3,cate4,brand_name,store_name,store_id,item_name,item_id,url,gmv,sales_num,asp,insert_time FROM jq_sale_item_m WHERE y_m BETWEEN 202301 AND 202612 AND (jq_cate3 IN ('雾化器','制氧机') OR item_name REGEXP '雾化|制氧|氧气机|吸氧机')"
}
meta={'started_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'queries':queries,'tables':{}}
try:
 with c.cursor() as q:
  q.execute('SET SESSION TRANSACTION READ ONLY')
  q.execute('SET SESSION MAX_EXECUTION_TIME=600000')
  q.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT')
 for kind,sql in queries.items():
  t=time.monotonic();n=0;last='';h=hashlib.sha256()
  with c.cursor() as q,gzip.open(RAW/(kind+'.jsonl.gz.tmp'),'wt',encoding='utf-8') as f:
   q.execute(sql);cols=[x[0] for x in q.description]
   for row in q:
    obj=dict(zip(cols,row));line=json.dumps(obj,ensure_ascii=False,default=str,separators=(',',':'))+'\n'
    f.write(line);h.update(line.encode());n+=1;last=max(last,str(obj['insert_time']))
  (RAW/(kind+'.jsonl.gz.tmp')).replace(RAW/(kind+'.jsonl.gz'))
  meta['tables'][kind]={'rows':n,'last_insert_time':last,'sha256':h.hexdigest(),'seconds':round(time.monotonic()-t,1)}
  print(kind,json.dumps(meta['tables'][kind]),flush=True)
 meta['finished_at']=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
 (RAW/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
finally:c.close()
