#!/usr/bin/env python3
"""Fail-closed, allowlisted deployment from an uploaded development ZIP to a production app directory.
No DB migrations or webserver restart. Requires manual maintenance window and rollback decision.
"""
import argparse, hashlib, json, os, pathlib, shutil, sys, tempfile, time, zipfile

CODE_FILES={'app/main.py','app/db.py','app/config.py','app/market_permissions.py','app/seo_delivery.py','app/seo_health.py','app/seo_measurement.py','app/seo_repository.py','static/admin.html','requirements.txt'}
# NEVER replace the GoDaddy Passenger bootstrap automatically.
FORBIDDEN=('passenger_wsgi.py','.env','indian_family_market.db','scorer_data/','scorer2_data/','sports_data/','travel_data/','static/uploads/','data/','scorer2_frontend/','app/scorer2/','operator-evidence')

def sha(data):return hashlib.sha256(data).hexdigest()
def is_safe(n):return n in CODE_FILES and not any(n==f or n.startswith(f) for f in FORBIDDEN)
def die(msg):raise SystemExit('HOLD: '+msg)
def atomic_write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.release-',dir=str(path.parent))
 try:
  with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def main():
 a=argparse.ArgumentParser();a.add_argument('--release',required=True);a.add_argument('--root',required=True);a.add_argument('--state-dir',required=True);a.add_argument('--mode',choices=['plan','apply','rollback'],default='plan');a.add_argument('--approval',default='');a.add_argument('--run-id',default='');args=a.parse_args()
 root=pathlib.Path(args.root).resolve();state=pathlib.Path(args.state_dir).resolve()
 if not root.is_dir() or not (root/'app/main.py').is_file():die('production root does not contain app/main.py')
 if root==state or root in state.parents or state in root.parents:die('state-dir must be outside production root')
 if args.mode=='rollback':
  if args.approval!='ROLLBACK' or not args.run_id:die('rollback needs --approval ROLLBACK and --run-id')
  manifest=state/args.run_id/'manifest.json'
  if not manifest.is_file():die('unknown run-id')
  info=json.loads(manifest.read_text()); entries=info['files']
  for n,v in entries.items():
   path=root/n
   if sha(path.read_bytes())!=v['new_sha256']:die('production drift since deployment: '+n)
  for n,v in entries.items():
   path=root/n
   if v['existed']:atomic_write(path,(manifest.parent/'before'/n).read_bytes())
   else:path.unlink()
  print('ROLLBACK COMPLETED; restart Passenger manually; database migrations were not reversed.');return
 with zipfile.ZipFile(args.release) as z:
  if z.testzip():die('release ZIP integrity failed')
  names=z.namelist();selected={n:z.read(n) for n in names if is_safe(n) and not n.endswith('/')}
  if any(n not in names for n in ('app/main.py','app/db.py','static/admin.html')):die('release missing core files')
  if len(selected)!=len(set(selected)):die('duplicate selected paths')
  if not selected:die('no allowlisted files')
  changes={}
  for n,data in sorted(selected.items()):
   path=root/n;old=path.read_bytes() if path.is_file() else None
   if old!=data:changes[n]={'existed':old is not None,'old_sha256':sha(old) if old is not None else None,'new_sha256':sha(data),'bytes':len(data)}
  print(json.dumps({'mode':args.mode,'root':str(root),'changed':changes,'excluded_passenger_wsgi':True,'database_migration':'manual review required'},indent=2))
  if args.mode=='plan':return
  if args.approval!='APPLY-REVIEWED':die('apply requires --approval APPLY-REVIEWED')
  if not changes:die('no changes to deploy')
  if not os.access(root,os.W_OK):die('production root not writable')
  runid=time.strftime('%Y%m%d-%H%M%S',time.gmtime());run=state/runid
  if run.exists():die('run id collision')
  run.mkdir(parents=True)
  # Back up all modified code BEFORE touching any live file.
  for n,v in changes.items():
   if v['existed']:
    backup=run/'before'/n;backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/n,backup)
    if sha(backup.read_bytes())!=v['old_sha256']:die('backup verification failed: '+n)
  manifest={'run_id':runid,'release_sha256':sha(pathlib.Path(args.release).read_bytes()),'files':changes,'status':'prepared','notes':'No DB migration or restart; restore database separately only under DBA approval'}
  (run/'manifest.json').write_text(json.dumps(manifest,indent=2))
  completed=[]
  try:
   for n in changes:
    path=root/n;actual=sha(path.read_bytes()) if path.is_file() else None
    if actual!=changes[n]['old_sha256']:raise RuntimeError('concurrent change: '+n)
    atomic_write(path,selected[n]);completed.append(n)
   manifest['status']='applied';(run/'manifest.json').write_text(json.dumps(manifest,indent=2))
  except Exception:
   for n in reversed(completed):
    if changes[n]['existed']:atomic_write(root/n,(run/'before'/n).read_bytes())
    else:(root/n).unlink(missing_ok=True)
   manifest['status']='failed_and_reverted';(run/'manifest.json').write_text(json.dumps(manifest,indent=2));raise
  print('APPLIED run-id='+runid+'; restart Passenger manually, then smoke-test. Rollback using --mode rollback --run-id '+runid)
if __name__=='__main__':main()
