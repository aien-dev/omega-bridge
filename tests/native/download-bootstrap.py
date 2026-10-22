"""Real HTTP download-to-shell tests; uses only an isolated home and prefix."""
import functools
import http.server
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

INSTALLER = Path(sys.argv.pop(1)).resolve()
ARCHIVE = Path(sys.argv.pop(1)).resolve()

class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root/'home'; self.home.mkdir()
        self.prefix = self.home/'prefix space'
        self.web = self.root/'web'; self.web.mkdir()
        self.scratch = self.root/'tmp'; self.scratch.mkdir()
        shutil.copyfile(INSTALLER, self.web/'install.sh')
        shutil.copyfile(ARCHIVE, self.web/'package.tar.gz')
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(self.web))
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
        thread = threading.Thread(target=self.server.serve_forever,daemon=True); thread.start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)
        self.url = 'http://127.0.0.1:'+str(self.server.server_port)
        self.env = {**os.environ,'HOME':str(self.home),'TMPDIR':str(self.scratch),
                    'OMEGA_DOWNLOAD_URL':self.url+'/package.tar.gz','LC_ALL':'C'}

    def bootstrap(self,*args):
        # Exactly the curl | sh transport, retaining both process statuses.
        downloader=subprocess.Popen(['curl','-fsSL',self.url+'/install.sh'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        result=subprocess.run(['sh','-s','--',*args],stdin=downloader.stdout,env=self.env,capture_output=True,text=True,timeout=90)
        downloader.stdout.close(); error=downloader.stderr.read(); downloader.stderr.close(); status=downloader.wait()
        self.assertEqual(status,0,error)
        self.assertEqual(list(self.scratch.iterdir()),[],'bootstrap temporary source leaked')
        return result

    def test_real_curl_pipe_installs_omega_and_runs_project(self):
        result=self.bootstrap('--prefix',str(self.prefix))
        self.assertEqual(result.returncode,0,result.stderr)
        executable=self.prefix/'bin/omega'
        self.assertTrue(executable.exists())
        project=self.root/'project';project.mkdir()
        source=project/'hello.om';source.write_text('text msg "DOWNLOAD\\n"\nfn main to int\nw = write 1 msg 0 len msg\nret 0\nend\n')
        result=subprocess.run([str(executable),'run',str(source)],cwd=project,env=self.env,capture_output=True,text=True)
        self.assertEqual((result.returncode,result.stdout),(0,'DOWNLOAD\n'),result.stderr)
        for name in ['om','omg']:
            self.assertEqual((self.prefix/'bin'/name).resolve(),executable.resolve())
        result=subprocess.run([str(executable),'uninstall'],env=self.env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(executable.exists())

    def test_tampered_download_is_rejected_before_installation(self):
        (self.web/'package.tar.gz').write_bytes(b'not the pinned distribution')
        result=self.bootstrap('--prefix',str(self.prefix))
        self.assertEqual(result.returncode,65,result.stderr)
        self.assertFalse(self.prefix.exists())

    def test_missing_download_fails_without_installation(self):
        self.env['OMEGA_DOWNLOAD_URL']=self.url+'/missing.tar.gz'
        result=self.bootstrap('--prefix',str(self.prefix))
        self.assertEqual(result.returncode,74,result.stderr)
        self.assertFalse(self.prefix.exists())

    def test_existing_omega_command_is_not_overwritten(self):
        (self.prefix/'bin').mkdir(parents=True)
        target=self.prefix/'bin/omega';target.write_text('UNRELATED')
        result=self.bootstrap('--prefix',str(self.prefix))
        self.assertEqual(result.returncode,73,result.stderr)
        self.assertEqual(target.read_text(),'UNRELATED')
        self.assertFalse((self.prefix/'bin/om').exists())
        self.assertFalse((self.prefix/'lib/omega-native').exists())

    def test_bad_arguments_do_not_download_or_install(self):
        (self.web/'package.tar.gz').unlink()
        result=self.bootstrap('--unknown')
        self.assertEqual(result.returncode,64,result.stderr)
        self.assertFalse(self.prefix.exists())

if __name__=='__main__':unittest.main(verbosity=2)
