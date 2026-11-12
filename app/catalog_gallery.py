"""Catalog product galleries. Metadata is stored in persistent data/catalog_galleries.
No SQL schema changes; primary image remains the catalog.image column.
"""
import base64, binascii, fcntl, json, os, re, uuid
from pathlib import Path
from fastapi import HTTPException
from .db import catalog_product, save_catalog_product

ROOT=Path(__file__).resolve().parent.parent
GALLERIES=ROOT/'data'/'catalog_galleries'
UPLOADS=ROOT/'static'/'uploads'/'catalog'
EXT={'image/jpeg':'jpg','image/png':'png','image/webp':'webp','image/gif':'gif','image/avif':'avif'}

def _path(pid):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,140}',pid): raise HTTPException(400,'Invalid product ID')
    return GALLERIES/(pid+'.json')

def _read(pid, primary):
    path=_path(pid)
    try: records=json.loads(path.read_text('utf-8')) if path.exists() else []
    except (ValueError,OSError): raise HTTPException(500,'Product gallery metadata unreadable')
    if not isinstance(records,list): raise HTTPException(500,'Invalid gallery metadata')
    records=[x for x in records if isinstance(x,dict) and isinstance(x.get('url'),str) and x['url']]
    if primary and not any(x['url']==primary for x in records): records.insert(0,{'url':primary,'alt':''})
    if primary: records.sort(key=lambda x:x['url']!=primary)
    return records[:8]

def get_gallery(pid, public=False):
    row=catalog_product(pid)
    if not row or (public and not row['active']): raise HTTPException(404,'Product not found')
    return {'product_id':pid,'images':_read(pid,str(row['image'] or '')),'primary':str(row['image'] or ''),'max_images':8}

def _write(pid, records):
    GALLERIES.mkdir(parents=True,exist_ok=True)
    path=_path(pid);tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with tmp.open('w',encoding='utf-8') as f:
            json.dump(records,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
        os.replace(str(tmp),str(path))
    finally:
        if tmp.exists(): tmp.unlink()

def _check_image(data_url):
    try:
        header,encoded=data_url.split(',',1)
        mime=header[5:].split(';',1)[0].lower()
        if mime not in EXT or ';base64' not in header.lower(): raise ValueError()
        raw=base64.b64decode(encoded,validate=True)
        if not raw or len(raw)>6*1024*1024: raise ValueError()
        valid={'image/jpeg':raw.startswith(b'\xff\xd8\xff'), 'image/png':raw.startswith(b'\x89PNG\r\n\x1a\n'), 'image/gif':raw[:6] in (b'GIF87a',b'GIF89a'), 'image/webp':raw.startswith(b'RIFF') and raw[8:12]==b'WEBP','image/avif':len(raw)>12 and raw[4:8]==b'ftyp' and (b'avif' in raw[8:32] or b'avis' in raw[8:32])}
        if not valid[mime]: raise ValueError()
        return raw,EXT[mime]
    except (ValueError,KeyError,binascii.Error): raise HTTPException(400,'Invalid image: JPEG, PNG, WebP, GIF or AVIF, maximum 6 MB each')

def _locked(pid,operation):
    GALLERIES.mkdir(parents=True,exist_ok=True)
    with (GALLERIES/(pid+'.lock')).open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        try:return operation()
        finally:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)

def upload(pid, images):
    _path(pid)
    if not isinstance(images,list) or not images or len(images)>8: raise HTTPException(400,'Select 1 to 8 images')
    decoded=[_check_image(x.get('data_url','')) for x in images if isinstance(x,dict)]
    if len(decoded)!=len(images): raise HTTPException(400,'Invalid upload payload')
    def action():
        row=catalog_product(pid)
        if not row:raise HTTPException(404,'Product not found')
        primary=str(row['image'] or '');records=_read(pid,primary)
        if len(records)+len(decoded)>8:raise HTTPException(400,'Maximum 8 images per product including primary')
        UPLOADS.mkdir(parents=True,exist_ok=True)
        created=[]
        try:
            for raw,ext in decoded:
                name=pid+'-'+uuid.uuid4().hex[:16]+'.'+ext
                path=UPLOADS/name
                with path.open('xb') as f:f.write(raw)
                created.append(path)
                records.append({'url':'/static/uploads/catalog/'+name,'alt':''})
            _write(pid,records)
            if not primary:
                current=dict(row);current['image']=records[0]['url'];save_catalog_product(current,pid)
            return get_gallery(pid)
        except Exception:
            for path in created:
                try:path.unlink()
                except OSError:pass
            raise
    return _locked(pid,action)

def update(pid, urls, primary):
    _path(pid)
    if not isinstance(urls,list) or len(urls)>8 or len(urls)!=len(set(urls)):raise HTTPException(400,'Invalid gallery order')
    def action():
        row=catalog_product(pid)
        if not row:raise HTTPException(404,'Product not found')
        existing=_read(pid,str(row['image'] or ''))
        lookup={x['url']:x for x in existing}
        if any(not isinstance(u,str) or u not in lookup for u in urls):raise HTTPException(400,'Unknown image')
        if urls and primary not in urls:raise HTTPException(400,'Primary must be in gallery')
        if not urls and primary:raise HTTPException(400,'Invalid primary')
        ordered=[lookup[u] for u in urls]
        # Update catalog primary first; a failed update must not delete existing metadata.
        if str(row['image'] or '')!=(primary or ''):
            current=dict(row);current['image']=primary or '';save_catalog_product(current,pid)
        _write(pid,ordered)
        return get_gallery(pid)
    return _locked(pid,action)
