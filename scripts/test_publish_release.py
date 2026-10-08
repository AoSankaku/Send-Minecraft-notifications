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
        for platform, suffix in (("windows-x64", ".exe"), ("linux-x64", "")):
            names = (
                f"send-minecraft-notifications-{platform}{suffix}",
                f"send-minecraft-notifications-{platform}.zip",
            )
            for name in names:
                (self.assets / name).write_bytes(name.encode())
            sums = "".join(
                f"{hashlib.sha256((self.assets / name).read_bytes()).hexdigest()}  {name}\n"
                for name in names
            )
            (self.assets / f"SHA256SUMS-{platform}.txt").write_text(sums)
        self.commands = self.root / "commands.jsonl"
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        gh = fake_bin / "gh"
        gh.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "with open(os.environ['FAKE_GH_LOG'], 'a') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "command = sys.argv[2]\n"
            "if os.environ.get('FAKE_GH_FAIL') == command:\n"
            "    sys.exit(9)\n"
            "if command == 'view':\n"
            "    state = os.environ.get('FAKE_GH_STATE', 'absent')\n"
            "    if state == 'absent': sys.exit(1)\n"
            "    print(state)\n"
        )
        gh.chmod(0o755)
        self.environment = dict(os.environ)
        self.environment.update(
            PATH=str(fake_bin) + os.pathsep + os.environ["PATH"],
            TAG_NAME="1.2.3", GH_REPO="example/project", GH_TOKEN="fake-token",
            FAKE_GH_LOG=str(self.commands), FAKE_GH_STATE="absent", FAKE_GH_FAIL="",
        )

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
        self.assertEqual(set(create[3:9]), {str(path) for path in self.assets.iterdir()})
        self.assertIn("--draft=false", commands[2])
        self.assertIn("--prerelease=false", commands[2])

    def test_draft_retry_uploads_before_publishing(self):
        result, commands = self.run_script(FAKE_GH_STATE="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([command[1] for command in commands], ["view", "upload", "edit"])
        self.assertIn("--clobber", commands[1])

    def test_published_release_is_preserved(self):
        result, commands = self.run_script(FAKE_GH_STATE="false")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([command[1] for command in commands], ["view"])

    def test_upload_failure_never_publishes(self):
        result, commands = self.run_script(FAKE_GH_STATE="true", FAKE_GH_FAIL="upload")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([command[1] for command in commands], ["view", "upload"])

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
        for tag in ("1.2.3-rc.1", "v1.2.3-beta.1"):
            with self.subTest(tag=tag):
                self.commands.unlink(missing_ok=True)
                result, commands = self.run_script(TAG_NAME=tag)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(commands[-1][2], tag)
                self.assertIn("--prerelease=true", commands[-1])


if __name__ == "__main__":
    unittest.main()
