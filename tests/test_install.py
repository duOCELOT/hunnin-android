import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.home=self.root/'home';self.home.mkdir()
        self.prefix=self.root/'prefix';self.bin=self.prefix/'bin';self.bin.mkdir(parents=True)
        self.pkg=self.root/'package with spaces';shutil.copytree(ROOT,self.pkg,ignore=shutil.ignore_patterns('.git','dist','__pycache__'))
        self.log=self.root/'calls'
        self.env=dict(os.environ,HOME=str(self.home),PREFIX=str(self.prefix),PATH=str(self.bin)+':'+os.environ['PATH'],LOG=str(self.log),ARCH='aarch64')
        self.command('pkg','#!/bin/sh\nexit 0\n')
        self.command('uname','#!/bin/sh\necho "$ARCH"\n')
        self.command('dpkg','#!/bin/sh\necho "$ARCH"\n')
        self.command('df','#!/bin/sh\nprintf "fs blocks used available mount\\nf 30000000 0 20000000 /tmp\\n"\n')
        self.command('proot-distro', '''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
a=sys.argv[1:]
with open(os.environ['LOG'],'a') as f:f.write(json.dumps(a)+'\\n')
if a==['install','--help']:print('--name',file=sys.stderr)
elif a[0]=='install':(Path(os.environ['PREFIX'])/'var/lib/proot-distro/containers'/a[2]/'rootfs/root').mkdir(parents=True)
elif a[0]=='login' and os.environ.get('FAIL_SETUP'):sys.exit(2)
''')
    def command(self,name,text):
        p=self.bin/name;p.write_text(text);p.chmod(0o755)
    def run_install(self,*args):return subprocess.run(['bash',str(self.pkg/'install.sh'),*args],env=self.env,capture_output=True,text=True)
    def test_preflight_no_install(self):
        self.assertEqual(self.run_install('--check').returncode,0)
        self.assertFalse(self.log.exists())
        self.env['ARCH']='armv7l'
        self.assertNotEqual(self.run_install('--check').returncode,0)
    def test_install_and_retry(self):
        for _ in range(2):
            result=self.run_install();self.assertEqual(result.returncode,0,result.stderr)
        calls=[json.loads(x) for x in self.log.read_text().splitlines()]
        self.assertEqual(len([a for a in calls if a[:2]==['install','--name']]),1)
        self.assertIn('HUNINN Android managed launcher',(self.bin/'huninn').read_text())
        config=json.loads((self.home/'.config/huninn-android/config.json').read_text())
        self.assertEqual(config['container'],'huninn-android')
    def test_failed_setup_does_not_publish_command(self):
        self.env['FAIL_SETUP']='1'
        self.assertNotEqual(self.run_install().returncode,0)
        self.assertFalse((self.bin/'huninn').exists())
        self.env.pop('FAIL_SETUP')
        self.assertEqual(self.run_install().returncode,0)
    def test_unrelated_launcher_preserved(self):
        self.command('huninn','#!/bin/sh\necho unrelated\n')
        self.assertNotEqual(self.run_install().returncode,0)
        self.assertIn('unrelated',(self.bin/'huninn').read_text())
    def test_reuse_requires_managed_environment(self):
        self.assertNotEqual(self.run_install('--reuse-huninn-idf').returncode,0)
        p=self.prefix/'var/lib/proot-distro/containers/huninn-idf/rootfs/root';p.mkdir(parents=True)
        (p/'.huninn-idf-managed').touch()
        self.assertEqual(self.run_install('--reuse-huninn-idf').returncode,0)
        calls=[json.loads(x) for x in self.log.read_text().splitlines()]
        self.assertFalse(any(a[:2]==['install','--name'] for a in calls))
if __name__=='__main__':unittest.main()
