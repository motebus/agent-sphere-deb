"""Test the exact embedded classifier without reading or changing host config."""
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import types
import unittest
from unittest import mock

SOURCE=(Path(__file__).resolve().parents[1]/'agent-sphere-apps.sh').read_text()
CODE=SOURCE.split("python3 - <<'MCP_PREFLIGHT'\n",1)[1].split('\nMCP_PREFLIGHT\n',1)[0]
module=types.ModuleType('embedded_mcp_preflight');exec(compile(CODE,'embedded_mcp_preflight','exec'),module.__dict__)
STOCK='[mcp_servers.mote-bridge-mcp]\ncommand="/usr/bin/mote"\nargs=["mcp","serve"]\nenabled=true\ndefault_tools_approval_mode="auto"\n'


class McpPreflightTests(unittest.TestCase):
    def setUp(self):
        self.record='3.0.0-2\namd64\ninstall ok installed\n '+module.NORMAL+' 7582d273536ba7102097a3c090f916d0'
        self.config=STOCK
        self.checked=[]
        def inspect(path,**kwargs):
            self.checked.append((path,kwargs))
            return None if path==module.CONFIG and self.config is None else ((self.config.encode() if path==module.CONFIG else b'fixture'), ('fingerprint',path,self.config if path==module.CONFIG else 0))
        self.inspect=mock.patch.object(module,'checked',side_effect=inspect);self.inspect.start();self.addCleanup(self.inspect.stop)
        self.query=mock.patch.object(module.subprocess,'run',side_effect=lambda *a,**k:subprocess.CompletedProcess(a,0,self.record,''));self.query.start();self.addCleanup(self.query.stop)
        self.exists=mock.patch.object(module.os.path,'lexists',return_value=False);self.exists.start();self.addCleanup(self.exists.stop)

    def test_exact_stock_and_absent_tables_are_supported_with_bound_state(self):
        before=module.classify();self.assertTrue(before.startswith('installed:'))
        self.config=STOCK+'\n[unrelated]\nvalue="preserved"\n'
        self.assertNotEqual(module.classify(),before)
        self.config='[unrelated]\nvalue="preserved"\n';self.assertTrue(module.classify().startswith('installed:'))
        self.config=None;self.assertTrue(module.classify().startswith('installed:'))
        self.assertIn((module.INFO+'prerm',{'digest':'ab66dbe928eb706c0275dc1431f6350a24a55c13d77b6e34a3d4d7651f5aecac','mode':0o755}),self.checked)

    def test_custom_old_or_new_table_is_rejected(self):
        for config in (STOCK.replace('enabled=true','enabled=false'), STOCK.replace('enabled=true','enabled=1'), STOCK+'extra="custom"\n',
                       STOCK+'\n[mcp_servers.mote-mcpd]\ncommand="custom"\n',STOCK.replace('"serve"','"doctor"')):
            with self.subTest(config=config):
                self.config=config
                with self.assertRaisesRegex(ValueError,'customized'):module.classify()

    def test_invalid_config_is_not_silently_overwritten(self):
        for config in ('[broken', 'mcp_servers="wrong-type"'):
            self.config=config
            with self.assertRaises(ValueError):module.classify()

    def test_unknown_metadata_and_locked_conffile_owner_are_rejected(self):
        original=self.record
        for record in (original.replace('3.0.0-2','3.0.0-1'),original.replace('amd64','all'),
                       original.replace('install ok installed','install ok unpacked'),
                       original+'\n '+module.IDENTITY+' '+'a'*32,
                       original+' obsolete',original.replace('7582d273536ba7102097a3c090f916d0','b'*32)):
            self.record=record
            with self.assertRaises(ValueError):module.classify()

    def test_residual_record_does_not_execute_old_helper_or_require_removed_files(self):
        self.record=self.record.replace('install ok installed','deinstall ok config-files')
        self.assertTrue(module.classify().startswith('config-files:'))
        self.assertEqual({p for p,_ in self.checked},{module.IDENTITY,module.CONFIG})

    def test_obsolete_residual_requires_actual_successor_ownership(self):
        self.record=self.record.replace('install ok installed','deinstall ok config-files')+' obsolete'
        def query(args,**kwargs):
            value='mote-mcpd: '+module.NORMAL if '-S' in args else ('3.0.0-3|amd64|install ok installed' if args[-1]=='mote-mcpd' else self.record)
            return subprocess.CompletedProcess(args,0,value,'')
        with mock.patch.object(module.subprocess,'run',side_effect=query):
            self.assertTrue(module.classify().startswith('config-files:'))
        def new_successor(args,**kwargs):
            result=query(args,**kwargs)
            result.stdout=result.stdout.replace('3.0.0-3|', '3.1.0-1|')
            return result
        with mock.patch.object(module.subprocess,'run',side_effect=new_successor):
            self.assertTrue(module.classify().startswith('config-files:'))
        with self.assertRaisesRegex(ValueError,'successor owner'):module.classify()

    def test_added_cleanup_hook_is_rejected(self):
        with mock.patch.object(module.os.path,'lexists',return_value=True):
            with self.assertRaisesRegex(ValueError,'unreviewed legacy MCP'):module.classify()

    def test_exact_empty_relationship_record_is_absent(self):
        self.record='\n\nunknown ok not-installed\n'
        self.assertEqual(module.classify(),'absent');self.assertEqual(self.checked,[])
        for record in ('3.0.0-2\n\nunknown ok not-installed\n','\namd64\nunknown ok not-installed\n','\n\ninstall ok not-installed\n','\n\nunknown ok not-installed\n /etc/owned '+ 'a'*32):
            self.record=record
            with self.assertRaises(ValueError):module.classify()

    def test_absence_and_query_failure_are_distinct(self):
        with mock.patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','')):
            self.assertEqual(module.classify(),'absent')
        with mock.patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],2,'','')):
            with self.assertRaisesRegex(ValueError,'cannot inspect'):module.classify()


class CheckedFileTests(unittest.TestCase):
    def test_nonregular_and_unsafe_modes_fail_before_reading(self):
        for mode,uid,gid in ((stat.S_IFLNK|0o777,0,0),(stat.S_IFREG|0o666,0,0),(stat.S_IFREG|0o644,1000,0)):
            metadata=types.SimpleNamespace(st_mode=mode,st_uid=uid,st_gid=gid)
            with mock.patch.object(module.os,'lstat',return_value=metadata),mock.patch.object(module.os,'open') as opened:
                with self.assertRaisesRegex(ValueError,'unsafe'):module.checked('/fixture')
                opened.assert_not_called()

    def test_missing_optional_is_distinct_from_required(self):
        with mock.patch.object(module.os,'lstat',side_effect=FileNotFoundError):
            self.assertIsNone(module.checked('/fixture',optional=True))
            with self.assertRaisesRegex(ValueError,'missing'):module.checked('/fixture')
