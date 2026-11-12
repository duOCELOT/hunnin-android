import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('recovery',ROOT/'scripts/recover-empty-submodules.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'source';self.source.mkdir()
        self.git(self.source,'init','-q')
        (self.source/'main.c').write_text('original\n')
        self.git(self.source,'add','main.c')
        self.git(self.source,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','init')
        self.clone=self.root/'clone'
        subprocess.run(['git','clone','-q','--no-checkout',str(self.source),str(self.clone)],check=True)
    def git(self,path,*args):return subprocess.check_output(['git','-C',str(path),*args])
    def test_restore_interrupted_checkout(self):
        self.assertTrue(r.recover(self.clone))
        self.assertEqual((self.clone/'main.c').read_text(),'original\n')
        self.assertFalse(r.recover(self.clone))
    def test_user_file_preserved(self):
        (self.clone/'notes.txt').write_text('keep')
        self.assertFalse(r.recover(self.clone))
        self.assertEqual((self.clone/'notes.txt').read_text(),'keep')
    def test_modified_tracked_file_preserved(self):
        r.recover(self.clone)
        (self.clone/'main.c').write_text('edited')
        self.assertFalse(r.recover(self.clone))
        self.assertEqual((self.clone/'main.c').read_text(),'edited')
if __name__=='__main__':unittest.main()
