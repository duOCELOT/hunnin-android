import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cli',ROOT/'bin/huninn.py')
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)

class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.workspace=Path(self.tmp.name)/'projects with spaces';self.workspace.mkdir()
    def create(self):
        cli.new_project(self.workspace,'teste','esp32s3')
        return self.workspace/'teste'
    def test_new_and_preserve_existing(self):
        p=self.create()
        self.assertIn('project(teste)',(p/'CMakeLists.txt').read_text())
        self.assertEqual(cli.project(self.workspace,'teste'),(p,'esp32s3'))
        with self.assertRaises(ValueError):self.create()
    def test_names_and_symlinks(self):
        for name in ('../outside','a/b','x;echo', 'with space', '-arg'):
            with self.assertRaises(ValueError):cli.new_project(self.workspace,name,'esp32s3')
        (self.workspace/'link').symlink_to(self.workspace)
        with self.assertRaises(ValueError):cli.project(self.workspace,'link')
    def plan(self):
        p=self.create();build=p/'build-android';build.mkdir()
        (build/'app.bin').write_bytes(b'firmware')
        data={'extra_esptool_args':{'chip':'esp32s3'},'flash_settings':{'flash_mode':'dio','flash_freq':'80m','flash_size':'16MB'},'flash_files':{'0x10000':'app.bin'}}
        (build/'flasher_args.json').write_text(json.dumps(data))
        return p,build,data
    def test_flash_args(self):
        p,_,_=self.plan()
        self.assertEqual(cli.flash_plan(p,'esp32s3'),['--flash_mode','dio','--flash_freq','80m','--flash_size','16MB','0x10000','app.bin'])
        with self.assertRaises(ValueError):cli.flash_plan(p,'esp32')
    def test_flash_path_escape_and_offsets(self):
        p,build,data=self.plan()
        (p/'other.bin').write_bytes(b'outside')
        for files in ({'0x10000':'../other.bin'}, {'-1':'app.bin'}, {'0x1000000':'app.bin'}, {'0x10001':'app.bin'}, {'0x10000':'app.bin','65536':'app.bin'}):
            data['flash_files']=files;(build/'flasher_args.json').write_text(json.dumps(data))
            with self.assertRaises(ValueError):cli.flash_plan(p,'esp32s3')
    def test_guest_routing_keeps_paths_as_arguments(self):
        cmd=cli.guest('huninn-android',self.workspace,'build','teste','esp32s3')
        self.assertIn(str(self.workspace)+':/work/projects',cmd)
        self.assertEqual(cmd[-3:],['build','teste','esp32s3'])
    def test_flash_cancel_never_starts_esptool(self):
        self.plan()
        with patch.object(cli,'load_config',return_value=('huninn-android',self.workspace)),patch('builtins.input',return_value='no'),patch.object(cli.subprocess,'call') as call:
            self.assertEqual(cli.main(['flash','teste']),1)
            call.assert_not_called()

if __name__=='__main__':unittest.main()
