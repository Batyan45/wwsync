import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import json
import importlib.util
from pathlib import Path

# Load wwsync as a module
import types
wwsync_path = Path(__file__).resolve().parent.parent / "wwsync"
wwsync = types.ModuleType("wwsync")
with open(wwsync_path) as f:
    exec(f.read(), wwsync.__dict__)
sys.modules["wwsync"] = wwsync

class TestWWSync(unittest.TestCase):
    
    def setUp(self):
        self.mock_config = {
            "servers": {
                "test_server": {
                    "host": "user@test_host",
                    "mappings": [
                        {
                            "local": "/local/path",
                            "remote": "/remote/path",
                            "excludes": [".git"]
                        }
                    ]
                }
            }
        }

    @patch('wwsync.CONFIG_PATH', Path("/tmp/.wwsync"))
    def test_load_config_create_default(self):
        with patch('wwsync.Path.exists') as mock_exists:
            mock_exists.return_value = False
            with patch('builtins.open', mock_open()) as mock_file:
                with patch('json.dump') as mock_json_dump:
                    config = wwsync.load_config()
                    self.assertIn("servers", config)
                    mock_json_dump.assert_called_once()

    @patch('wwsync.CONFIG_PATH', Path("/tmp/.wwsync"))
    def test_load_config_existing(self):
        with patch('wwsync.Path.exists') as mock_exists:
            mock_exists.return_value = True
            with patch('builtins.open', mock_open(read_data=json.dumps(self.mock_config))):
                config = wwsync.load_config()
                self.assertEqual(config, self.mock_config)

    @patch('subprocess.run')
    def test_run_rsync_safe(self, mock_run):
        wwsync.run_rsync("user@host", "/local", "/remote", [".git"], full_sync=False)
        
        expected_cmd = [
            "rsync", "-avzP", "--exclude", ".git", 
            "/local" + os.sep, "user@host:/remote"
        ]
        
        # Check if subprocess.run was called with command containing these elements
        # args[0] is the command list
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args, expected_cmd)

    @patch('subprocess.run')
    def test_run_rsync_full_dry_run(self, mock_run):
        # Mocking dry-run output
        mock_run.return_value.stdout = "deleting file1.txt\ndeleting file2.txt\n"
        
        with patch('builtins.input', return_value='n'): # User says no
            wwsync.run_rsync("user@host", "/local", "/remote", [], full_sync=True)
            
            # Should call dry-run
            self.assertTrue(mock_run.called)
            args = mock_run.call_args_list[0][0][0]
            self.assertIn("--delete", args)
            self.assertIn("--dry-run", args)
            
            # Should NOT call real run since we said 'n'
            # We expect exactly 1 call (dry run)
            self.assertEqual(mock_run.call_count, 1)

    @patch('subprocess.run')
    def test_run_rsync_full_confirmed(self, mock_run):
         # Mocking dry-run output
        mock_run.return_value.stdout = "deleting file1.txt\n"
        
        with patch('builtins.input', return_value='y'): # User says yes
            wwsync.run_rsync("user@host", "/local", "/remote", [], full_sync=True)
            
            # Should be called twice: dry-run and real run
            self.assertEqual(mock_run.call_count, 2)
            
            # check real run args
            real_run_args = mock_run.call_args_list[1][0][0]
            self.assertIn("--delete", real_run_args)
            self.assertNotIn("--dry-run", real_run_args)

    @patch('subprocess.run')
    def test_run_rsync_full_auto_accept(self, mock_run):
        mock_run.return_value.stdout = "deleting file1.txt\n"
        
        # input() should NOT be called
        with patch('builtins.input') as mock_input:
            wwsync.run_rsync("user@host", "/local", "/remote", [], full_sync=True, auto_accept=True)
            mock_input.assert_not_called()
        
        self.assertEqual(mock_run.call_count, 2)


    @patch('subprocess.run')
    def test_run_remote_session(self, mock_run):
        wwsync.run_remote_session("user@host", "/remote/path")
        
        calls = mock_run.call_args[0][0]
        self.assertEqual(calls[0], "ssh")
        self.assertEqual(calls[2], "user@host")
        self.assertIn("cd /remote/path", calls[3])

if __name__ == '__main__':
    unittest.main()
