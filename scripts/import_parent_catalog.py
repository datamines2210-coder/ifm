"""Import a verified parent catalog JSON file.

Expected JSON: [{"id","name","category","state","price","mrp","unit","description","image"}]
Run only after obtaining an official export/feed from The Indian Family.
"""
import json, sys
required={'id','name','category','state','price','mrp','unit','description'}
path=sys.argv[1] if len(sys.argv)>1 else 'parent_catalog.json'
with open(path,encoding='utf-8') as f: data=json.load(f)
for i,p in enumerate(data):
    missing=required-set(p)
    if missing: raise SystemExit(f'row {i}: missing {sorted(missing)}')
print(json.dumps(data,ensure_ascii=False,indent=2))
