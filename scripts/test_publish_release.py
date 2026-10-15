"""Exercise release publication with a fake gh CLI; no GitHub requests are made."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().with_name("publish_release.sh")


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "Requires Linux bash")
class PublishReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="smn-publish-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.assets = self.root / "release-assets"
        self.assets.mkdir()
        self.install_windows_asset("1.2.3")
        for platform, suffix in (("linux-x64", ""),):
            binary_name = (
                f"send-minecraft-notifications-{platform}{suffix}"
            )
            names = (binary_name, f"send-minecraft-notifications-{platform}.zip")
            for name in names:
                (self.assets / name).write_bytes(name.encode())
            sums = "".join(
                f"{hashlib.sha256((self.assets / name).read_bytes()).hexdigest()}  {name}\n"
                for name in names
            )
            (self.assets / f"SHA256SUMS-{platform}.txt").write_text(sums)
        self.commands = self.root / "commands.jsonl"
        self.notes = self.root / "notes.jsonl"
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        gh = fake_bin / "gh"
        gh.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "with open(os.environ['FAKE_GH_LOG'], 'a') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "command = sys.argv[2]\n"
            "if '--notes-file' in sys.argv:\n"
            "    body = Path(sys.argv[sys.argv.index('--notes-file') + 1]).read_text(encoding='utf-8')\n"
            "    with open(os.environ['FAKE_GH_NOTES'], 'a', encoding='utf-8') as log:\n"
            "        log.write(json.dumps({'command': command, 'body': body}) + '\\n')\n"
            "if os.environ.get('FAKE_GH_FAIL') == command:\n"
            "    sys.exit(9)\n"
            "if command == 'view':\n"
            "    state = os.environ.get('FAKE_GH_STATE', 'absent')\n"
            "    if state == 'absent': sys.exit(1)\n"
            "    if 'body' in sys.argv:\n"
            "        print(os.environ.get('FAKE_GH_BODY', 'Original changelog'))\n"
            "        sys.exit(0)\n"
            "    print(state)\n"
        )
        gh.chmod(0o755)
        self.environment = dict(os.environ)
        self.environment.update(
            PATH=str(fake_bin) + os.pathsep + os.environ["PATH"],
            TAG_NAME="1.2.3", GH_REPO="example/project", GH_TOKEN="fake-token",
            FAKE_GH_LOG=str(self.commands), FAKE_GH_NOTES=str(self.notes),
            FAKE_GH_STATE="absent", FAKE_GH_FAIL="",
        )

    def install_windows_asset(self, tag):
        exe_name = f"send-minecraft-notifications-{tag.replace('/', '-')}-windows-x64.exe"
        for path in self.assets.glob("*.exe"):
            path.unlink()
        exe = self.assets / exe_name
        exe.write_bytes(exe_name.encode())
        archive_name = "send-minecraft-notifications-windows-x64.zip"
        archive = self.assets / archive_name
        if not archive.exists():
            archive.write_bytes(archive_name.encode())
        sums = "".join(
            f"{hashlib.sha256((self.assets / name).read_bytes()).hexdigest()}  {name}\n"
            for name in (exe_name, archive_name)
        )
        (self.assets / "SHA256SUMS-windows-x64.txt").write_text(sums)

    def run_script(self, **environment):
        result = subprocess.run(
            ["bash", str(SCRIPT), str(self.assets)], cwd=self.root,
            env=self.environment | environment, capture_output=True, timeout=10,
        )
        commands = [json.loads(line) for line in self.commands.read_text().splitlines()] if self.commands.exists() else []
        return result, commands

    def test_new_release_is_published_after_uploading_all_assets(self):
        result, commands = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([command[1] for command in commands], ["view", "create", "edit"])
        create = commands[1]
        for flag in ("--verify-tag", "--draft", "--generate-notes"):
            self.assertIn(flag, create)
        self.assertIn("--notes-file", create)
        self.assertEqual(set(create[3:9]), {str(path) for path in self.assets.iterdir()})
        self.assertIn("--draft=false", commands[2])
        self.assertIn("--prerelease=false", commands[2])
        notes = json.loads(self.notes.read_text().splitlines()[0])["body"]
        self.assertIn("https://github.com/example/project/releases/download/1.2.3/", notes)
        self.assertIn("curl -fL -o send-minecraft-notifications-linux-x64", notes)
        self.assertIn("curl.exe -fL -o send-minecraft-notifications-1.2.3-windows-x64.exe", notes)

    def test_draft_retry_uploads_before_publishing(self):
        result, commands = self.run_script(FAKE_GH_STATE="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([command[1] for command in commands], ["view", "view", "upload", "edit", "edit"])
        self.assertIn("--clobber", commands[2])
        self.assertIn("--draft=false", commands[-1])
        notes = json.loads(self.notes.read_text().splitlines()[0])["body"]
        self.assertIn("Original changelog", notes)
        self.assertEqual(notes.count("<!-- smn:release-install:start -->"), 1)

    def test_published_release_is_preserved(self):
        result, commands = self.run_script(FAKE_GH_STATE="false")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([command[1] for command in commands], ["view"])

    def test_upload_failure_never_publishes(self):
        result, commands = self.run_script(FAKE_GH_STATE="true", FAKE_GH_FAIL="upload")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([command[1] for command in commands], ["view", "view", "upload"])

    def test_draft_notes_failure_never_publishes(self):
        result, commands = self.run_script(FAKE_GH_STATE="true", FAKE_GH_FAIL="edit")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("--draft=false", commands[-1])

    def test_create_failure_never_publishes(self):
        result, commands = self.run_script(FAKE_GH_FAIL="create")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([command[1] for command in commands], ["view", "create"])

    def test_corrupt_binary_never_calls_github(self):
        (self.assets / "send-minecraft-notifications-linux-x64").write_bytes(b"corrupt")
        result, commands = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, [])

    def test_missing_platform_asset_never_calls_github(self):
        (self.assets / "send-minecraft-notifications-linux-x64.zip").unlink()
        result, commands = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, [])

    def test_prerelease_tags_with_or_without_v_prefix(self):
        for tag in ("1.2.3-rc.1", "v1.2.3-beta.1", "v1.0.0-beta0"):
            with self.subTest(tag=tag):
                self.commands.unlink(missing_ok=True)
                self.install_windows_asset(tag)
                result, commands = self.run_script(TAG_NAME=tag)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(commands[-1][2], tag)
                self.assertIn("--prerelease=true", commands[-1])
                self.assertIn("--latest=false", commands[-1])

    def test_multiple_executables_never_call_github(self):
        (self.assets / "send-minecraft-notifications-1.2.3-feature-windows-x64.exe").write_bytes(b"second application executable")
        result, commands = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one Windows EXE", result.stderr.decode())
        self.assertEqual(commands, [])

    def test_unrelated_executable_never_calls_github(self):
        (self.assets / "unrelated.exe").write_bytes(b"unexpected executable")
        result, commands = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, [])

    def test_debug_or_wrong_version_executable_never_calls_github(self):
        for wrong_name in ("smn-main-123abcd.exe", "send-minecraft-notifications-v9.9.9-windows-x64.exe"):
            with self.subTest(name=wrong_name):
                for current in self.assets.glob("*.exe"):
                    current.rename(self.assets / wrong_name)
                result, commands = self.run_script()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("does not match release tag", result.stderr.decode())
                self.assertEqual(commands, [])
                (self.assets / wrong_name).rename(
                    self.assets / "send-minecraft-notifications-1.2.3-windows-x64.exe"
                )

    def test_release_asset_can_exceed_local_debug_filename_limit(self):
        long_tag = "v1.2345678901234567890-beta.123"
        self.install_windows_asset(long_tag)
        result, commands = self.run_script(TAG_NAME=long_tag)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--prerelease=true", commands[-1])


if __name__ == "__main__":
    unittest.main()
