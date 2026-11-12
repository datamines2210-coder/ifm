import importlib.util, io, json, pathlib, tempfile, unittest, zipfile
from contextlib import redirect_stdout
P=pathlib.Path(__file__).resolve().parents[1]/'scripts'/'safe_production_deploy.py'
spec=importlib.util.spec_from_file_location('deploy',P);d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
class DeploymentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=pathlib.Path(self.tmp.name);self.root=self.base/'app_root';(self.root/'app').mkdir(parents=True);(self.root/'app/main.py').write_text('old');self.state=self.base/'state';self.release=self.base/'release.zip';self.manifest=self.base/'approved.json'
  with zipfile.ZipFile(self.release,'w') as z:z.writestr('app/main.py','new');z.writestr('static/admin.html','admin');z.writestr('.env','SECRET')
 def call(self,mode,extra=None):
  args=['--release',str(self.release),'--root',str(self.root),'--state-dir',str(self.state),'--mode',mode]+(extra or [])
  out=io.StringIO()
  with redirect_stdout(out):d.main(args)
  return out.getvalue()
 def test_missing_manifest_file_rejected(self):
  self.manifest.write_text(json.dumps({'files':['app/router.py']}))
  with self.assertRaisesRegex(SystemExit,'manifest file absent from release: app/router.py'):self.call('plan',['--manifest',str(self.manifest)])
 def test_apply_verify_rollback(self):
  self.manifest.write_text(json.dumps({'files':['app/main.py','static/admin.html']}))
  self.call('plan',['--manifest',str(self.manifest)])
  out=self.call('apply',['--manifest',str(self.manifest),'--approval','APPLY-REVIEWED']);run=out.split('APPLIED run-id=')[1].split(';')[0]
  self.assertEqual((self.root/'app/main.py').read_text(),'new');self.assertIn('VERIFIED',self.call('verify',['--run-id',run]));self.call('rollback',['--run-id',run,'--approval','ROLLBACK']);self.assertEqual((self.root/'app/main.py').read_text(),'old');self.assertFalse((self.root/'static/admin.html').exists())
 def test_protected_rejected(self):
  self.manifest.write_text(json.dumps({'files':['.env']}))
  with self.assertRaisesRegex(SystemExit,'unsafe'):self.call('plan',['--manifest',str(self.manifest)])
if __name__=='__main__':unittest.main()
