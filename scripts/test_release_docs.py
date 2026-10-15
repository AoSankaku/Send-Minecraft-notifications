"""Focused checks for versioned documentation and safe README updates."""
import base64
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import release_docs


REPOSITORY = "example/project"
TAG = "v2.3.4-beta.1"
EXE = "send-minecraft-notifications-v2.3.4-beta.1-windows-x64.exe"
LEGACY_EXE = "smn-main-123abcd.exe"
TEMPLATE = """# Project

Keep these instructions.
<!-- smn:install-ja:start -->
old Japanese commands
<!-- smn:install-ja:end -->

Other configuration.
<!-- smn:install-en:start -->
old English commands
<!-- smn:install-en:end -->

License stays here.
"""


class DocumentationTests(unittest.TestCase):
    def test_readme_updates_both_languages_and_preserves_other_sections(self):
        updated = release_docs.render_readme(TEMPLATE, TAG, REPOSITORY, EXE)
        self.assertIn("Keep these instructions.", updated)
        self.assertIn("Other configuration.", updated)
        self.assertIn("License stays here.", updated)
        self.assertNotIn("old Japanese commands", updated)
        self.assertNotIn("old English commands", updated)
        self.assertEqual(updated.count(f"releases/download/{TAG}/send-minecraft-notifications-linux-x64"), 2)
        self.assertEqual(updated.count(f"releases/download/{TAG}/{EXE}"), 2)
        self.assertIn("curl -fL -o", updated)
        self.assertIn("curl.exe -fL -o", updated)
        self.assertIn("sha256sum --check --ignore-missing", updated)
        self.assertIn("--check-config", updated)
        self.assertIn("send-minecraft-notifications.toml", updated)
        self.assertIn("--config /path/to/Send-Minecraft-notifications/.env", updated)
        self.assertIn("The first run creates `send-minecraft-notifications.toml`", updated)
        self.assertIn("original `.env`", updated)
        self.assertEqual(release_docs.render_readme(updated, TAG, REPOSITORY, EXE), updated)

    def test_new_release_replaces_all_previous_managed_urls(self):
        previous = release_docs.render_readme(TEMPLATE, "v1.0.0-beta0", REPOSITORY, "smn-main-7654321.exe")
        updated = release_docs.render_readme(previous, TAG, REPOSITORY, EXE)
        self.assertNotIn("v1.0.0-beta0", updated)
        self.assertNotIn("7654321.exe", updated)
        self.assertIn(TAG, updated)

    def test_published_beta1_instructions_keep_legacy_env_behavior(self):
        rendered = release_docs.render_readme(TEMPLATE, "v1.0.0-beta1", REPOSITORY, LEGACY_EXE)
        self.assertIn("create a `.env` template", rendered)
        self.assertIn("generated `.env`", rendered)
        self.assertNotIn("send-minecraft-notifications.toml", rendered)
        self.assertIn("releases/download/v1.0.0-beta1/", rendered)

    def test_beta0_instructions_also_keep_legacy_env_behavior(self):
        rendered = release_docs.installation_section(
            "v1.0.0-beta0", REPOSITORY, LEGACY_EXE, "en"
        )
        self.assertIn("create a `.env` template", rendered)
        self.assertNotIn("send-minecraft-notifications.toml", rendered)

    def test_release_notes_for_future_release_explain_toml_migration(self):
        rendered = release_docs.render_notes("## Changes\n", TAG, REPOSITORY, EXE)
        self.assertIn("send-minecraft-notifications.toml", rendered)
        self.assertIn("preserves the original `.env`", rendered)
        self.assertIn("--config /path/to/Send-Minecraft-notifications/.env", rendered)

    def test_release_notes_preserve_changelog_and_do_not_duplicate_instructions(self):
        original = "## Changes\n\nRetain the maintainer's notes.\n"
        first = release_docs.render_notes(original, "v1.0.0-beta0", REPOSITORY, LEGACY_EXE)
        updated = release_docs.render_notes(first, TAG, REPOSITORY, EXE)
        self.assertTrue(updated.endswith(original))
        self.assertEqual(updated.count("<!-- smn:release-install:start -->"), 1)
        self.assertNotIn("v1.0.0-beta0", updated)
        self.assertEqual(release_docs.render_notes(updated, TAG, REPOSITORY, EXE), updated)

    def test_missing_duplicate_or_reversed_markers_fail_without_partial_output(self):
        start = "<!-- smn:install-ja:start -->"
        end = "<!-- smn:install-ja:end -->"
        reversed_markers = TEMPLATE.replace(start, "PLACEHOLDER").replace(end, start).replace("PLACEHOLDER", end)
        for broken in (TEMPLATE.replace(start, ""), TEMPLATE + start, reversed_markers):
            with self.subTest(document=broken), self.assertRaises(ValueError):
                release_docs.render_readme(broken, TAG, REPOSITORY, EXE)
        with self.assertRaises(ValueError):
            release_docs.render_notes("<!-- smn:release-install:end -->", TAG, REPOSITORY, EXE)

    def test_api_and_command_inputs_reject_shell_markdown_and_path_injection(self):
        for tag in ("v1.0.0\nmalicious", "$(command)", "`command`", "--help"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release_docs.installation_section(tag, REPOSITORY, EXE, "ja")
        for repository in ("https://example.com", "owner/repo/contents", "owner/repo?ref=other"):
            with self.subTest(repository=repository), self.assertRaises(ValueError):
                release_docs.installation_section(TAG, repository, EXE, "ja")
        for invalid_exe in ("../app.exe", "smn-main-123abcd.exe",
                            "send-minecraft-notifications-v9.9.9-windows-x64.exe"):
            with self.subTest(windows_exe=invalid_exe), self.assertRaises(ValueError):
                release_docs.installation_section(TAG, REPOSITORY, invalid_exe, "en")

    def test_public_versioned_names_validate_for_any_tag(self):
        for tag in ("v1.0.0-beta0", "v1.0.0-beta1", TAG):
            name = release_docs.release_windows_filename(tag)
            with self.subTest(tag=tag):
                release_docs.validate_inputs(tag, REPOSITORY, name)
        with self.assertRaises(ValueError):
            release_docs.validate_inputs(TAG, REPOSITORY, LEGACY_EXE)

    def test_windows_filename_cli_uses_release_tag_without_git_or_network(self):
        with mock.patch("sys.argv", ["release_docs.py", "windows-filename", "--tag", "release/v2.3.4+build",
                                     "--repo", REPOSITORY]):
            with mock.patch.object(release_docs.subprocess, "run", side_effect=AssertionError("unexpected subprocess")):
                with mock.patch("builtins.print") as output:
                    release_docs.main()
        output.assert_called_once_with("send-minecraft-notifications-release-v2.3.4+build-windows-x64.exe")
        with mock.patch("sys.argv", ["release_docs.py", "windows-filename", "--tag", "$(bad)",
                                     "--repo", REPOSITORY]):
            with self.assertRaises(ValueError):
                release_docs.main()

    def test_historical_release_docs_require_the_actual_published_filename(self):
        with mock.patch("sys.argv", ["release_docs.py", "notes", "--tag", "v1.0.0-beta1",
                                     "--repo", REPOSITORY, "--output", "unused.md"]):
            with self.assertRaises(SystemExit) as error:
                release_docs.main()
        self.assertEqual(error.exception.code, 2)

    def test_tag_slash_and_plus_are_encoded_in_urls(self):
        tag = "release/v2.3.4+build"
        section = release_docs.installation_section(
            tag, REPOSITORY, release_docs.release_windows_filename(tag), "en"
        )
        self.assertIn("/download/release%2Fv2.3.4%2Bbuild/", section)

    def test_readme_cli_writes_the_release_tag_into_a_distributable_readme(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            source = Path(directory) / "README.md"
            output = Path(directory) / "packaged-README.md"
            source.write_text(TEMPLATE, encoding="utf-8")
            with mock.patch("sys.argv", ["release_docs.py", "readme", "--tag", TAG,
                                        "--repo", REPOSITORY, "--windows-exe", EXE,
                                        "--path", str(source), "--output", str(output)]):
                release_docs.main()
            self.assertEqual(source.read_text(encoding="utf-8"), TEMPLATE)
            self.assertEqual(output.read_text(encoding="utf-8"), release_docs.render_readme(TEMPLATE, TAG, REPOSITORY, EXE))


class ReadmeSyncTests(unittest.TestCase):
    def setUp(self):
        self.release = {
            "tag_name": TAG, "draft": False, "published_at": "2026-10-15T10:00:00Z",
            "assets": [{"name": EXE}, {"name": "send-minecraft-notifications-linux-x64"}],
        }
        self.writes = []
        self.original = TEMPLATE
        self.releases = [[self.release]]

    def fake_api(self, endpoint, *, payload=None, paginate=False):
        if endpoint == f"repos/{REPOSITORY}/releases":
            self.assertTrue(paginate)
            return self.releases
        if endpoint == f"repos/{REPOSITORY}":
            return {"default_branch": "release/main"}
        if endpoint.endswith("README.md?ref=release%2Fmain"):
            return {"type": "file", "encoding": "base64", "sha": "current-blob-sha",
                    "content": base64.b64encode(self.original.encode()).decode()}
        if endpoint.endswith("README.md") and payload:
            self.writes.append(payload)
            return {"commit": {"sha": "new-commit-sha"}}
        self.fail(f"Unexpected API request: {endpoint}")

    def test_updates_default_branch_using_blob_sha_and_preserves_current_content(self):
        with mock.patch.object(release_docs, "github_api", side_effect=self.fake_api):
            self.assertTrue(release_docs.sync_readme(TAG, REPOSITORY))
        self.assertEqual(len(self.writes), 1)
        payload = self.writes[0]
        self.assertEqual(payload["branch"], "release/main")
        self.assertEqual(payload["sha"], "current-blob-sha")
        updated = base64.b64decode(payload["content"]).decode()
        self.assertEqual(updated, release_docs.render_readme(TEMPLATE, TAG, REPOSITORY, EXE))

    def test_latest_publication_is_selected_across_pages_and_drafts_are_ignored(self):
        old = self.release | {"tag_name": "v1.0.0", "published_at": "2026-10-10T00:00:00Z"}
        draft = self.release | {"tag_name": "v9.0.0", "draft": True, "published_at": None}
        self.releases = [[old, draft], [self.release]]
        with mock.patch.object(release_docs, "github_api", side_effect=self.fake_api):
            self.assertTrue(release_docs.sync_readme(TAG, REPOSITORY))

    def test_older_release_rerun_cannot_roll_readme_back(self):
        with mock.patch.object(release_docs, "github_api", side_effect=self.fake_api) as api:
            self.assertFalse(release_docs.sync_readme("v1.0.0", REPOSITORY))
        self.assertEqual(api.call_count, 1)
        self.assertEqual(self.writes, [])

    def test_unchanged_readme_creates_no_commit(self):
        self.original = release_docs.render_readme(TEMPLATE, TAG, REPOSITORY, EXE)
        with mock.patch.object(release_docs, "github_api", side_effect=self.fake_api):
            self.assertFalse(release_docs.sync_readme(TAG, REPOSITORY))
        self.assertEqual(self.writes, [])

    def test_missing_markers_and_ambiguous_assets_never_write(self):
        self.original = "New content without managed sections"
        with mock.patch.object(release_docs, "github_api", side_effect=self.fake_api), self.assertRaises(ValueError):
            release_docs.sync_readme(TAG, REPOSITORY)
        self.assertEqual(self.writes, [])
        self.release["assets"].append({"name": "send-minecraft-notifications-v2.3.4-beta.1-alt-windows-x64.exe"})
        with mock.patch.object(release_docs, "github_api", side_effect=self.fake_api), self.assertRaises(ValueError):
            release_docs.sync_readme(TAG, REPOSITORY)
        self.assertEqual(self.writes, [])

    def test_concurrent_update_failure_is_propagated_without_retry(self):
        def fail_write(endpoint, **kwargs):
            if kwargs.get("payload"):
                raise subprocess.CalledProcessError(1, ["gh", "api"], stderr="409 Conflict")
            return self.fake_api(endpoint, **kwargs)

        with mock.patch.object(release_docs, "github_api", side_effect=fail_write) as api:
            with self.assertRaises(subprocess.CalledProcessError):
                release_docs.sync_readme(TAG, REPOSITORY)
        self.assertEqual(sum(call.kwargs.get("payload") is not None for call in api.call_args_list), 1)


if __name__ == "__main__":
    unittest.main()
