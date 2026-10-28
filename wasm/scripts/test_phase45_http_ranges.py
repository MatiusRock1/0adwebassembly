"""Exact bounded HTTP payloads are required by the persistent archive backend."""
from functools import partial
import http.client
from http.server import ThreadingHTTPServer
import importlib.util
from pathlib import Path
import tempfile
import threading
import unittest

spec=importlib.util.spec_from_file_location('isolated_server',Path(__file__).with_name('serve-phase2.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class Ranges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory()
        cls.payload=bytes(range(256))*1025
        (Path(cls.directory.name)/'public.zip').write_bytes(cls.payload)
        class Quiet(module.IsolatedHandler):
            def log_message(self,*args):pass
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=cls.directory.name))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.directory.cleanup()
    def request(self,value,method='GET'):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        connection.request(method,'/public.zip',headers={'Range':value})
        response=connection.getresponse();body=response.read();headers=dict(response.getheaders());status=response.status;connection.close()
        self.assertEqual(headers['Cross-Origin-Opener-Policy'],'same-origin')
        self.assertEqual(headers['Cross-Origin-Embedder-Policy'],'require-corp')
        return status,headers,body
    def test_exact_payload(self):
        for start,end in [(0,0),(255,65560),(len(self.payload)-9,len(self.payload)-1)]:
            with self.subTest(start=start):
                status,headers,body=self.request(f'bytes={start}-{end}')
                self.assertEqual(status,206);self.assertEqual(body,self.payload[start:end+1])
                self.assertEqual(headers['Content-Range'],f'bytes {start}-{end}/{len(self.payload)}')
                self.assertEqual(int(headers['Content-Length']),len(body))
    def test_open_and_suffix_ranges(self):
        for value,expected in [('bytes=5-',self.payload[5:]),('bytes=-13',self.payload[-13:]),('bytes=0-9999999',self.payload)]:
            with self.subTest(value=value):self.assertEqual(self.request(value)[2],expected)
    def test_invalid_ranges(self):
        for value in ['bytes=9-3','bytes=9999999-','bytes=-0','bytes=-','bytes=0-2,4-8','items=0-1']:
            with self.subTest(value=value):
                status,headers,body=self.request(value)
                self.assertEqual(status,416);self.assertEqual(body,b'')
                self.assertEqual(headers['Content-Range'],f'bytes */{len(self.payload)}')
    def test_head_returns_no_payload(self):
        status,headers,body=self.request('bytes=3-8','HEAD')
        self.assertEqual(status,206);self.assertEqual(headers['Content-Length'],'6');self.assertEqual(body,b'')

if __name__=='__main__':unittest.main()
