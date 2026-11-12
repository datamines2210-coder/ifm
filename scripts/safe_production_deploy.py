#!/usr/bin/env python3
"""Reviewed manifest-only release deployment; Python 3.8 compatible. No DB or restart."""
import argparse, hashlib, json, os, pathlib, re, shutil, tempfile, time, zipfile

def hold(message): raise SystemExit('HOLD: '+message)
def sha(data): return hashlib.sha256(data).hexdigest()
def safe(name):
    if not isinstance(name,str) or not name or '\\' in name or name.startswith('/') or '\x00' in name: return False
    parts=name.split('/')
    if any(p in ('','.','..') or p.startswith('.') for p in parts): return False
    if name in ('requirements.txt',): return True
    if parts[0]=='app' and len(parts)>1 and name.endswith('.py') and not any(p in ('scorer2',) for p in parts): return True
    if parts[0]=='static' and len(parts)==2 and name.endswith(('.html','.js','.css')): return True
    return False

def inside(root,path):
    try: path.resolve().relative_to(root.resolve()); return True
    except ValueError: return False

def target(root,name):
    p=root.joinpath(*name.split('/'))
    if not inside(root,p): hold('path escape: '+name)
    return p

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.deploy-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def write_json(path,obj): atomic(path,json.dumps(obj,indent=2,sort_keys=True).encode())
def read_json(path): return json.loads(path.read_text(encoding='utf-8'))
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('release','root','state-dir'): p.add_argument('--'+arg,required=True)
    p.add_argument('--manifest');p.add_argument('--mode',choices=('plan','apply','verify','rollback'),default='plan')
    p.add_argument('--approval',default='');p.add_argument('--run-id',default='')
    a=p.parse_args(argv);root=pathlib.Path(a.root).expanduser().resolve();state=pathlib.Path(a.state_dir).expanduser().resolve();release=pathlib.Path(a.release).expanduser().resolve()
    if not root.is_dir() or not (root/'app/main.py').is_file():hold('invalid application root')
    if inside(root,state) or inside(state,root):hold('state directory must be separate from application root')
    if not release.is_file() or not zipfile.is_zipfile(str(release)):hold('release ZIP missing or invalid')
    digest=sha(release.read_bytes())
    if a.mode in ('verify','rollback'):
        if not a.run_id or not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[0-9a-f]{8}',a.run_id):hold('valid --run-id required')
        run=state/a.run_id;mf=run/'manifest.json'
        if not mf.is_file():hold('deployment record not found')
        record=read_json(mf)
        if record.get('root')!=str(root) or record.get('release_sha256')!=digest:hold('deployment root or release mismatch')
        if record.get('status')!='applied':hold('deployment not in applied state')
        files=record['files']
        for name,info in files.items():
            if not safe(name):hold('unsafe deployment record: '+name)
            path=target(root,name)
            current=sha(path.read_bytes()) if path.is_file() else None
            if current!=info['new_sha256']:hold('production drift: '+name)
        if a.mode=='verify': print('VERIFIED run-id='+a.run_id+' files='+str(len(files)));return
        if a.approval!='ROLLBACK':hold('rollback requires --approval ROLLBACK')
        for name,info in files.items():
            if info['existed']:
                before=run/'before'/name
                if not before.is_file() or sha(before.read_bytes())!=info['old_sha256']:hold('backup invalid: '+name)
        for name,info in files.items():
            dest=target(root,name)
            if info['existed']:atomic(dest,(run/'before'/name).read_bytes())
            else:dest.unlink()
        record['status']='rolled_back';write_json(mf,record)
        print('ROLLED BACK run-id='+a.run_id+'; restart Passenger manually');return
    with zipfile.ZipFile(str(release)) as z:
        if z.testzip() is not None:hold('release ZIP integrity failed')
        names=z.namelist()
        if len(names)!=len(set(names)):hold('duplicate ZIP entries')
        for n in names:
            if n.startswith('/') or '\\' in n or '..' in n.split('/') or '\x00' in n:hold('unsafe ZIP entry: '+n)
        eligible=sorted(n for n in names if safe(n) and not n.endswith('/'))
        if not eligible:hold('release has no eligible code files')
        approved=[]
        if a.manifest:
            m=read_json(pathlib.Path(a.manifest).expanduser())
            approved=m.get('files')
            if not isinstance(approved,list) or not approved or len(approved)!=len(set(approved)) or not all(isinstance(n,str) for n in approved):hold('manifest must have unique nonempty files list')
            for n in approved:
                if not safe(n):hold('manifest unsafe file: '+n)
                if n not in names:hold('manifest file absent from release: '+n)
        if a.mode=='apply' and not approved:hold('apply requires reviewed --manifest')
        selected=approved if approved else eligible
        changes={}
        for n in selected:
            dest=target(root,n);new=z.read(n);old=dest.read_bytes() if dest.is_file() else None
            if new!=old:changes[n]={'existed':old is not None,'old_sha256':sha(old) if old is not None else None,'new_sha256':sha(new),'bytes':len(new)}
        print(json.dumps({'mode':a.mode,'release':str(release),'release_sha256':digest,'eligible_files':eligible,'approved_files':approved,'changed':changes,'eligible_not_approved':sorted(set(eligible)-set(approved)) if approved else [],'database_migration':'NOT performed','passenger_restart':'NOT performed'},indent=2))
        if a.mode=='plan':return
        if a.approval!='APPLY-REVIEWED':hold('apply requires --approval APPLY-REVIEWED')
        if not changes:hold('no changes to deploy')
        runid=time.strftime('%Y%m%d-%H%M%S',time.gmtime())+'-'+digest[:8]
        run=state/runid
        if run.exists():hold('run id already exists')
        run.mkdir(parents=True)
        for n,info in changes.items():
            if info['existed']:
                dest=target(root,n);before=run/'before'/n;before.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(str(dest),str(before))
                if sha(before.read_bytes())!=info['old_sha256']:hold('backup hash mismatch: '+n)
        record={'run_id':runid,'root':str(root),'release_sha256':digest,'files':changes,'status':'prepared'}
        write_json(run/'manifest.json',record)
        completed=[]
        try:
            for n,info in changes.items():
                dest=target(root,n);current=sha(dest.read_bytes()) if dest.is_file() else None
                if current!=info['old_sha256']:raise RuntimeError('concurrent file change: '+n)
                atomic(dest,z.read(n));completed.append(n)
            record['status']='applied';write_json(run/'manifest.json',record)
        except Exception:
            for n in reversed(completed):
                info=changes[n];dest=target(root,n)
                if info['existed']:atomic(dest,(run/'before'/n).read_bytes())
                elif dest.exists():dest.unlink()
            record['status']='failed_and_reverted';write_json(run/'manifest.json',record)
            raise
        print('APPLIED run-id='+runid+'; verify, then restart Passenger manually')
if __name__=='__main__':main()
