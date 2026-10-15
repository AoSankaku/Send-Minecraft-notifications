"""Targeted tests for public release and local debug executable names."""
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


class PublicWindowsExecutableNameTests(unittest.TestCase):
    def test_uses_full_application_name_version_and_platform(self):
        self.assertEqual(
            build_release.build_windows_release_filename("v1.2.3-beta.1"),
            "send-minecraft-notifications-v1.2.3-beta.1-windows-x64.exe",
        )

    def test_does_not_apply_local_debug_length_limit(self):
        name = build_release.build_windows_release_filename("1.2.3")
        self.assertGreater(len(name), 28)
        self.assertEqual(name, "send-minecraft-notifications-1.2.3-windows-x64.exe")

    def test_preserves_version_metadata_and_sanitizes_tag_separator(self):
        self.assertEqual(
            build_release.build_windows_release_filename("release/v1.2.3+build.4"),
            "send-minecraft-notifications-release-v1.2.3+build.4-windows-x64.exe",
        )

    def test_rejects_unsafe_or_unrepresentable_versions(self):
        for version in ("", "../1.2.3", "v1:2:3", "v1\\2", "--help", "v1\nmalicious", "v" + "1" * 255):
            with self.subTest(version=version), self.assertRaises(ValueError):
                build_release.build_windows_release_filename(version)

    def test_reads_default_release_version_from_metadata(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            metadata = Path(temporary) / "pyproject.toml"
            metadata.write_text('[project]\nversion = "1.2.3b1"\n', encoding="utf-8")
            self.assertEqual(build_release.project_version(metadata), "1.2.3b1")


class BuildNamingIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "dist").mkdir()
        (self.root / "dist" / "send-minecraft-notifications.exe").write_bytes(b"fake completed binary")
        (self.root / "dist" / "send-minecraft-notifications").write_bytes(b"fake completed Linux binary")
        (self.root / "pyproject.toml").write_text('[project]\nname = "smn"\nversion = "1.2.3b1"\n', encoding="utf-8")
        for name in ("README.md", "LICENSE", build_release.CONFIG_TEMPLATE):
            (self.root / name).write_text("public data", encoding="utf-8")
        (self.root / "README.md").write_text(
            "# Project\n<!-- smn:install-ja:start -->\nold release instructions\n<!-- smn:install-ja:end -->\n"
            "<!-- smn:install-en:start -->\nold release instructions\n<!-- smn:install-en:end -->\n",
            encoding="utf-8",
        )

    def build(self, args, environment, target=("windows", "x64", ".exe")):
        with (
            mock.patch.object(build_release, "ROOT", self.root),
            mock.patch.object(build_release, "resolve_target", return_value=target),
            mock.patch.object(build_release.subprocess, "run") as compiler,
            mock.patch.object(build_release, "resolve_source_identity", return_value=("main", "123abcd")) as identity,
            mock.patch.object(build_release, "copy_local_windows_executable") as export,
            mock.patch.dict(build_release.os.environ, environment, clear=True),
            mock.patch("sys.argv", ["build_release.py", *args]),
        ):
            build_release.main()
        compiler.assert_called_once()
        return identity, export

    def assert_release_files(self, expected):
        release = self.root / "dist" / "release"
        self.assertTrue((release / expected).is_file())
        with build_release.zipfile.ZipFile(release / "send-minecraft-notifications-windows-x64.zip") as archive:
            self.assertIn(expected, archive.namelist())
        self.assertIn(expected, (release / "SHA256SUMS-windows-x64.txt").read_text(encoding="utf-8"))

    def test_ci_uses_release_tag_without_branch_or_hash(self):
        identity, export = self.build([], {"GITHUB_ACTIONS": "true", "SMN_RELEASE_VERSION": "v1.2.3-beta.1"})
        self.assert_release_files("send-minecraft-notifications-v1.2.3-beta.1-windows-x64.exe")
        identity.assert_not_called()
        export.assert_not_called()

    def test_manual_ci_build_uses_project_version(self):
        identity, export = self.build([], {"GITHUB_ACTIONS": "true", "SMN_RELEASE_VERSION": ""})
        self.assert_release_files("send-minecraft-notifications-1.2.3b1-windows-x64.exe")
        identity.assert_not_called()
        export.assert_not_called()

    def test_explicit_public_version_overrides_environment_and_stays_in_distribution(self):
        original_readme = (self.root / "README.md").read_bytes()
        identity, export = self.build(["--version", "v2.0.0"], {"SMN_RELEASE_VERSION": "v1.0.0"})
        self.assert_release_files("send-minecraft-notifications-v2.0.0-windows-x64.exe")
        with build_release.zipfile.ZipFile(self.root / "dist/release/send-minecraft-notifications-windows-x64.zip") as archive:
            readme = archive.read("README.md").decode("utf-8")
        self.assertIn("/releases/download/v2.0.0/send-minecraft-notifications-v2.0.0-windows-x64.exe", readme)
        self.assertNotIn("old release instructions", readme)
        self.assertEqual((self.root / "README.md").read_bytes(), original_readme)
        identity.assert_not_called()
        export.assert_not_called()

    def test_local_debug_build_keeps_app_branch_and_hash(self):
        identity, export = self.build([], {})
        self.assert_release_files("smn-main-123abcd.exe")
        identity.assert_called_once()
        export.assert_called_once()

    def test_linux_public_zip_documents_matching_windows_release_name(self):
        identity, export = self.build(
            [], {"GITHUB_ACTIONS": "true", "SMN_RELEASE_VERSION": "v2.0.0", "GH_REPO": "example/fork"},
            target=("linux", "x64", ""),
        )
        with build_release.zipfile.ZipFile(self.root / "dist/release/send-minecraft-notifications-linux-x64.zip") as archive:
            readme = archive.read("README.md").decode("utf-8")
        self.assertIn("example/fork/releases/download/v2.0.0/send-minecraft-notifications-v2.0.0-windows-x64.exe", readme)
        identity.assert_not_called()
        export.assert_not_called()


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
        old_public = self.write_executable("send-minecraft-notifications-v1.0.0-beta1-windows-x64.exe", b"old public binary")
        current = self.write_executable("send-minecraft-notifications-v1.0.0-beta2-windows-x64.exe", b"current binary")
        linux_binary = self.write_executable("send-minecraft-notifications-linux-x64", b"linux")
        archive = self.write_executable("send-minecraft-notifications-windows-x64.zip", b"zip")
        config_example = self.write_executable("send-minecraft-notifications.example.toml", b"template")
        self.checksum_path.write_text(
            self.checksum_line(old_legacy.read_bytes(), old_legacy.name)
            + self.checksum_line(old_dynamic.read_bytes(), old_dynamic.name)
            + self.checksum_line(old_public.read_bytes(), old_public.name)
            + self.checksum_line(current.read_bytes(), current.name),
            encoding="utf-8",
        )

        removed = build_release.cleanup_previous_windows_executables(
            self.release_dir, self.checksum_path, current.name
        )

        self.assertEqual(set(removed), {old_legacy, old_dynamic, old_public})
        self.assertFalse(old_legacy.exists())
        self.assertFalse(old_dynamic.exists())
        self.assertFalse(old_public.exists())
        for retained in (current, linux_binary, archive, config_example):
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


class ReleaseArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(temporary.cleanup)
        self.archive = Path(temporary.name) / "release.zip"

    def write_archive(self, members: dict[str, bytes]) -> set[str]:
        with build_release.zipfile.ZipFile(self.archive, "w") as output:
            for name, content in members.items():
                output.writestr(name, content)
        return set(members)

    def test_allows_public_toml_template_but_no_local_config(self):
        members = {
            "smn-main-123abcd.exe": b"binary",
            "README.md": b"docs",
            "LICENSE": b"license",
            "send-minecraft-notifications.example.toml": b"template",
        }
        build_release.validate_archive(self.archive, self.write_archive(members))

        for secret_name in (
            "send-minecraft-notifications.toml",
            ".env",
            ".env.local",
            ".env-backup",
            ".env.example",
            ".send-minecraft-notifications.toml.random.tmp",
        ):
            with self.subTest(secret_name=secret_name):
                unsafe = members | {secret_name: b"synthetic secret"}
                with self.assertRaisesRegex(RuntimeError, "must never be included"):
                    build_release.validate_archive(self.archive, self.write_archive(unsafe))


if __name__ == "__main__":
    unittest.main()
