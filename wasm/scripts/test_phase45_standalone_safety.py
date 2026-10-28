import importlib.util
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

class StandaloneSafety(unittest.TestCase):
    def test_dry_modes_never_spawn_processes_or_connect_to_browser(self):
        temporary_root=Path(__file__).resolve().parents[1]/'build/phase4-5/test-tmp'
        temporary_root.mkdir(parents=True,exist_ok=True)
        for name in ['benchmark-phase4-5-standalone','verify-phase4-5-standalone']:
            module=load(name)
            with self.subTest(name=name),tempfile.TemporaryDirectory(dir=temporary_root) as temporary:
                self.assertTrue(Path(temporary).resolve().is_relative_to(temporary_root.resolve()))
                output=Path(temporary)/'plan'
                with patch.object(sys,'argv',[name,'--dry-run','--output',str(output)]),patch.object(module.subprocess,'Popen',side_effect=AssertionError('Process started in dry mode')):
                    self.assertEqual(module.main(),0)
                self.assertTrue((output/'plan.json').is_file())
                self.assertFalse((output/'summary.json').exists())

    def test_occupied_port_is_rejected_before_a_browser_can_be_launched(self):
        module=load('benchmark-phase4-5-standalone')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen()
            with self.assertRaises(OSError):module.require_free_port(listener.getsockname()[1])

if __name__=='__main__':unittest.main()
