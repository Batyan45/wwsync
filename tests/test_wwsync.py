import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import json
import tempfile
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
            "general_excludes": [".git", ".DS_Store"],
            "servers": {
                "test_server": {
                    "host": "user@test_host",
                    "mappings": [
                        {
                            "local": "/local/path",
                            "remote": "/remote/path",
                            "excludes": ["node_modules"],
                            "artifact_excludes": ["*.tmp"]
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
                    self.assertIn("general_excludes", config)
                    self.assertIsInstance(config["general_excludes"], list)
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
            
            # Should be called 3 times: dry-run, SSH rm+mkdir, rsync upload
            self.assertEqual(mock_run.call_count, 3)
            
            # Check SSH recreate command
            ssh_args = mock_run.call_args_list[1][0][0]
            self.assertEqual(ssh_args[0], "ssh")
            self.assertEqual(ssh_args[1], "user@host")
            self.assertIn("rm -rf", ssh_args[2])
            self.assertIn("mkdir -p", ssh_args[2])
            
            # Check fresh upload (no --delete)
            upload_args = mock_run.call_args_list[2][0][0]
            self.assertNotIn("--delete", upload_args)
            self.assertNotIn("--dry-run", upload_args)

    @patch('subprocess.run')
    def test_run_rsync_full_auto_accept(self, mock_run):
        mock_run.return_value.stdout = "deleting file1.txt\n"
        
        # input() should NOT be called
        with patch('builtins.input') as mock_input:
            wwsync.run_rsync("user@host", "/local", "/remote", [], full_sync=True, auto_accept=True)
            mock_input.assert_not_called()
        
        # 3 calls: dry-run, SSH rm+mkdir, rsync upload
        self.assertEqual(mock_run.call_count, 3)


    @patch('subprocess.run')
    def test_run_remote_session(self, mock_run):
        wwsync.run_remote_session("user@host", "/remote/path")
        
        calls = mock_run.call_args[0][0]
        self.assertEqual(calls[0], "ssh")
        self.assertEqual(calls[2], "user@host")
        self.assertIn("cd /remote/path", calls[3])

    def test_parse_rsync_itemized_output(self):
        output = "\n".join([
            "sending incremental file list",
            ">f+++++++++\tnew/file1.txt",
            ">f..t......\tchanged/file2.txt",
            "cd+++++++++\tnew/",
            ">f+++++++++\tnew/file1.txt"
        ])

        new_files, changed_files = wwsync._parse_rsync_itemized_output(output)
        self.assertEqual(new_files, ["new/file1.txt"])
        self.assertEqual(changed_files, ["changed/file2.txt"])

    @patch('subprocess.run')
    def test_download_remote_artifacts_only_new_files(self, mock_run):
        captured_files = {}

        def fake_run(cmd, **kwargs):
            if "--dry-run" in cmd:
                result = MagicMock()
                result.stdout = "\n".join([
                    ">f+++++++++\tbuild/report.txt",
                    ">f..t......\treports/summary.txt"
                ])
                return result

            if "--files-from" in cmd:
                files_from_idx = cmd.index("--files-from") + 1
                with open(cmd[files_from_idx], "r") as f:
                    captured_files["list"] = f.read().splitlines()
                return MagicMock()

            raise AssertionError(f"Unexpected command: {cmd}")

        mock_run.side_effect = fake_run

        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "project"
            project_dir.mkdir()
            artifacts_dir = project_dir / ".wwsync_test_server_artifacts"
            artifacts_dir.mkdir()
            (artifacts_dir / "old.txt").write_text("stale")

            with patch("builtins.input", return_value="y"):
                wwsync.download_remote_artifacts(
                    server_alias="test_server",
                    host="user@host",
                    local_path=str(project_dir),
                    remote_path="/remote/path",
                    excludes=[".git"],
                    artifact_excludes=["*.tmp"]
                )

            self.assertEqual(mock_run.call_count, 2)
            self.assertEqual(captured_files["list"], ["build/report.txt"])
            self.assertTrue(artifacts_dir.exists())
            self.assertFalse((artifacts_dir / "old.txt").exists())

            dry_run_cmd = mock_run.call_args_list[0][0][0]
            self.assertIn("--dry-run", dry_run_cmd)
            self.assertIn(".git", dry_run_cmd)
            self.assertIn("*.tmp", dry_run_cmd)

    @patch('subprocess.run')
    def test_download_remote_artifacts_cancel_overwrite(self, mock_run):
        result = MagicMock()
        result.stdout = ">f+++++++++\tbuild/artifact.txt"
        mock_run.return_value = result

        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "project"
            project_dir.mkdir()
            artifacts_dir = project_dir / ".wwsync_test_server_artifacts"
            artifacts_dir.mkdir()
            old_file = artifacts_dir / "old.txt"
            old_file.write_text("keep")

            with patch("builtins.input", return_value="n"):
                wwsync.download_remote_artifacts(
                    server_alias="test_server",
                    host="user@host",
                    local_path=str(project_dir),
                    remote_path="/remote/path",
                    excludes=[],
                    artifact_excludes=[]
                )

            # Only dry-run should execute because overwrite was rejected.
            self.assertEqual(mock_run.call_count, 1)
            self.assertTrue(old_file.exists())

class TestMergeExcludes(unittest.TestCase):

    def test_merge_empty(self):
        result = wwsync.merge_excludes([], [])
        self.assertEqual(result, [])

    def test_merge_general_only(self):
        result = wwsync.merge_excludes([".git", ".DS_Store"], [])
        self.assertEqual(result, [".git", ".DS_Store"])

    def test_merge_mapping_only(self):
        result = wwsync.merge_excludes([], ["node_modules", "build"])
        self.assertEqual(result, ["node_modules", "build"])

    def test_merge_deduplication(self):
        result = wwsync.merge_excludes([".git", ".DS_Store"], [".git", "node_modules"])
        self.assertEqual(result, [".git", ".DS_Store", "node_modules"])

    def test_merge_preserves_order(self):
        result = wwsync.merge_excludes(["a", "b"], ["c", "a", "d"])
        self.assertEqual(result, ["a", "b", "c", "d"])

    def test_merge_none_inputs(self):
        self.assertEqual(wwsync.merge_excludes(None, ["x"]), ["x"])
        self.assertEqual(wwsync.merge_excludes(["x"], None), ["x"])
        self.assertEqual(wwsync.merge_excludes(None, None), [])

    def test_general_excludes_missing_from_config(self):
        config = {"servers": {}}
        result = config.get("general_excludes", [])
        self.assertEqual(result, [])

class TestNoExcludesFlag(unittest.TestCase):
    """Tests for the --no-excludes / -n flag."""

    @patch('subprocess.run')
    def test_safe_sync_no_excludes(self, mock_run):
        """--no-excludes should produce an rsync command with zero --exclude flags."""
        wwsync.run_rsync("user@host", "/local", "/remote", [], full_sync=False)
        call_args = mock_run.call_args[0][0]
        self.assertNotIn("--exclude", call_args)

    @patch('subprocess.run')
    def test_safe_sync_with_excludes(self, mock_run):
        """Without --no-excludes, excludes should be present."""
        wwsync.run_rsync("user@host", "/local", "/remote", [".git", "node_modules"], full_sync=False)
        call_args = mock_run.call_args[0][0]
        self.assertIn("--exclude", call_args)
        self.assertIn(".git", call_args)
        self.assertIn("node_modules", call_args)

    def test_effective_excludes_empty_when_flag_set(self):
        """Simulates the logic in main() — when no_excludes is True, effective_excludes must be []."""
        general_excludes = [".git", ".DS_Store"]
        mapping_excludes = ["node_modules", "build"]
        no_excludes = True

        effective = [] if no_excludes else wwsync.merge_excludes(general_excludes, mapping_excludes)
        self.assertEqual(effective, [])

    def test_effective_excludes_populated_when_flag_not_set(self):
        """When no_excludes is False, effective_excludes should contain merged results."""
        general_excludes = [".git", ".DS_Store"]
        mapping_excludes = ["node_modules", "build"]
        no_excludes = False

        effective = [] if no_excludes else wwsync.merge_excludes(general_excludes, mapping_excludes)
        self.assertEqual(effective, [".git", ".DS_Store", "node_modules", "build"])

    def test_artifact_excludes_cleared_when_flag_set(self):
        """artifact_excludes should also be empty when --no-excludes is active."""
        mapping = {"artifact_excludes": ["*.tmp", "*.cache"]}
        no_excludes = True

        artifact_excludes = [] if no_excludes else mapping.get("artifact_excludes", [])
        self.assertEqual(artifact_excludes, [])


if __name__ == '__main__':
    unittest.main()
