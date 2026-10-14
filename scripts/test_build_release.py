"""Targeted tests for Windows release executable names and source metadata."""
from pathlib import Path
import tempfile
import unittest
import hashlib
from unittest import mock

import build_release


class WindowsExecutableNameTests(unittest.TestCase):
    def test_reads_application_name_from_project_metadata(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            metadata = Path(temporary) / "pyproject.toml"
            metadata.write_text('[project]\nname = "example-app"\n', encoding="utf-8")
            self.assertEqual(build_release.project_name(metadata), "example-app")

    def test_uses_app_branch_and_short_head_hash(self):
        self.assertEqual(
            build_release.build_windows_filename("smn", "main", "123abcd"),
            "smn-main-123abcd.exe",
        )

    def test_sanitizes_windows_filename_characters(self):
        self.assertEqual(build_release.sanitize_filename_component("my:app"), "my-app")
        self.assertEqual(
            build_release.sanitize_filename_component("feature/fix?bug"),
            "feature-fix-bug",
        )
        self.assertEqual(
            build_release.build_windows_filename("my:app", "f/x", "123abcd"),
            "my-app-f-x-123abcd.exe",
        )

    def test_shortens_long_components_but_keeps_hash_and_extension(self):
        filename = build_release.build_windows_filename(
            "verylongappname", "verylongbranchname", "123abcd"
        )
        self.assertLessEqual(len(filename), 28)
        self.assertTrue(filename.endswith("-123abcd.exe"))
        app, branch, _ = filename.rsplit("-", 2)
        self.assertTrue(app.startswith("very"))
        self.assertTrue(branch.startswith("very"))

    def test_fails_if_limit_cannot_fit_both_components_and_hash(self):
        with self.assertRaisesRegex(ValueError, "cannot fit"):
            build_release.build_windows_filename("smn", "main", "123abcd", max_length=14)

    def test_rejects_non_hex_hash(self):
        with self.assertRaisesRegex(ValueError, "hexadecimal Git hash"):
            build_release.build_windows_filename("smn", "main", "not-a-hash")


class SourceIdentityTests(unittest.TestCase):
    def test_uses_current_local_branch_and_short_head(self):
        def fake_git(_root: Path, *args: str) -> str:
            if args == ("branch", "--show-current"):
                return "main"
            if args == ("rev-parse", "--short=7", "HEAD"):
                return "dfeac5c"
            self.fail(f"Unexpected git command: {args}")

        with mock.patch.object(build_release, "run_git", side_effect=fake_git):
            self.assertEqual(build_release.resolve_source_identity(Path(".")), ("main", "dfeac5c"))

    def test_verifies_configured_branch_ref_and_ancestry(self):
        seen: list[tuple[str, ...]] = []

        def fake_git(_root: Path, *args: str) -> str:
            seen.append(args)
            if args == ("rev-parse", "--short=7", "HEAD"):
                return "dfeac5c"
            return ""

        with mock.patch.object(build_release, "run_git", side_effect=fake_git):
            result = build_release.resolve_source_identity(Path("."), "main")

        self.assertEqual(result, ("main", "dfeac5c"))
        self.assertEqual(
            seen,
            [
                ("check-ref-format", "refs/heads/main"),
                ("show-ref", "--verify", "--quiet", "refs/remotes/origin/main"),
                ("merge-base", "--is-ancestor", "HEAD", "refs/remotes/origin/main"),
                ("rev-parse", "--short=7", "HEAD"),
            ],
        )

    def test_detached_head_without_configured_branch_fails(self):
        with mock.patch.object(build_release, "run_git", return_value=""):
            with self.assertRaisesRegex(RuntimeError, "branch is unknown"):
                build_release.resolve_source_identity(Path("."))

    def test_missing_configured_remote_branch_fails_without_fallback(self):
        def fake_git(_root: Path, *args: str) -> str:
            if args[0] == "show-ref":
                raise RuntimeError("remote branch missing")
            return ""

        with mock.patch.object(build_release, "run_git", side_effect=fake_git) as run_git:
            with self.assertRaisesRegex(RuntimeError, "remote branch missing"):
                build_release.resolve_source_identity(Path("."), "main")
        self.assertEqual(run_git.call_count, 2)


class LocalExportTests(unittest.TestCase):
    def test_copies_completed_executable_to_destination(self):
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parent
        ) as temporary:
            root = Path(temporary)
            binary = root / "smn-main-123abcd.exe"
            binary.write_bytes(b"standalone executable")
            destination = root / "normal-apps" / "[output-executables]"

            exported = build_release.copy_local_windows_executable(
                binary, binary.name, destination
            )

            self.assertEqual(exported, destination / binary.name)
            self.assertEqual(exported.read_bytes(), binary.read_bytes())


class PreviousWindowsExecutableCleanupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.release_dir = self.root / "release"
        self.release_dir.mkdir()
        self.checksum_path = self.release_dir / "SHA256SUMS-windows-x64.txt"

    def write_executable(self, name: str, contents: bytes) -> Path:
        path = self.release_dir / name
        path.write_bytes(contents)
        return path

    @staticmethod
    def checksum_line(contents: bytes, name: str) -> str:
        return f"{hashlib.sha256(contents).hexdigest()}  {name}\n"

    def test_removes_only_verified_old_windows_executables(self):
        old_legacy = self.write_executable(
            "send-minecraft-notifications-windows-x64.exe", b"old legacy binary"
        )
        old_dynamic = self.write_executable("smn-feature-123abcd.exe", b"old dynamic binary")
        current = self.write_executable("smn-main-7654321.exe", b"current binary")
        linux_binary = self.write_executable("send-minecraft-notifications-linux-x64", b"linux")
        archive = self.write_executable("send-minecraft-notifications-windows-x64.zip", b"zip")
        env_example = self.write_executable(".env.example", b"template")
        self.checksum_path.write_text(
            self.checksum_line(old_legacy.read_bytes(), old_legacy.name)
            + self.checksum_line(old_dynamic.read_bytes(), old_dynamic.name)
            + self.checksum_line(current.read_bytes(), current.name),
            encoding="utf-8",
        )

        removed = build_release.cleanup_previous_windows_executables(
            self.release_dir, self.checksum_path, current.name
        )

        self.assertEqual(set(removed), {old_legacy, old_dynamic})
        self.assertFalse(old_legacy.exists())
        self.assertFalse(old_dynamic.exists())
        for retained in (current, linux_binary, archive, env_example):
            self.assertTrue(retained.exists())

    def test_ignores_path_traversal_unrelated_and_malformed_entries(self):
        outside = self.root / "outside.exe"
        outside.write_bytes(b"outside")
        unrelated = self.write_executable("unrelated.exe", b"unrelated")
        modified = self.write_executable("smn-branch-123abcd.exe", b"modified")
        current = self.write_executable("smn-main-7654321.exe", b"current")
        self.checksum_path.write_text(
            self.checksum_line(outside.read_bytes(), "../outside.exe")
            + self.checksum_line(outside.read_bytes(), r"..\outside.exe")
            + self.checksum_line(outside.read_bytes(), "./smn-branch-123abcd.exe")
            + self.checksum_line(unrelated.read_bytes(), unrelated.name)
            + "not-a-sha256  smn-branch-7654321.exe\n",
            encoding="utf-8",
        )

        removed = build_release.cleanup_previous_windows_executables(
            self.release_dir, self.checksum_path, current.name
        )

        self.assertEqual(removed, [])
        self.assertTrue(outside.exists())
        self.assertTrue(unrelated.exists())
        self.assertTrue(modified.exists())

    def test_refuses_to_remove_a_modified_old_executable(self):
        modified = self.write_executable("smn-branch-123abcd.exe", b"modified")
        self.checksum_path.write_text(
            self.checksum_line(b"original binary", modified.name), encoding="utf-8"
        )

        with self.assertRaisesRegex(RuntimeError, "checksum does not match"):
            build_release.cleanup_previous_windows_executables(
                self.release_dir, self.checksum_path, "smn-main-7654321.exe"
            )
        self.assertTrue(modified.exists())

    def test_never_removes_a_symlink(self):
        target = self.root / "outside-target.exe"
        target.write_bytes(b"external binary")
        link = self.release_dir / "smn-feature-123abcd.exe"
        try:
            link.symlink_to(target)
        except OSError as error:
            self.skipTest(f"Symlink creation is unavailable: {error}")
        self.checksum_path.write_text(
            self.checksum_line(target.read_bytes(), link.name), encoding="utf-8"
        )

        removed = build_release.cleanup_previous_windows_executables(
            self.release_dir, self.checksum_path, "smn-main-7654321.exe"
        )

        self.assertEqual(removed, [])
        self.assertTrue(link.is_symlink())
        self.assertTrue(target.exists())


if __name__ == "__main__":
    unittest.main()
