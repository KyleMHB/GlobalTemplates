import importlib.util
import io
import json
import sqlite3
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sync_workshop_artifact_version", ROOT / "scripts" / "sync_workshop.py")
sync_workshop = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(sync_workshop)


def artifact(entries: dict[str, bytes | str]) -> bytes:
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return body.getvalue()


class ArtifactVersionTests(unittest.TestCase):

    def test_uses_only_package_root_manifests_for_release_version(self):
        without_root_version = artifact({
            "package/mod.json": json.dumps({"name": "Example Mod"}),
            "package/dependencies/example/mod.json": json.dumps({"name": "Example", "version": "4.2.0"}),
        })
        self.assertEqual(sync_workshop.inspect_artifact_manifest(without_root_version), {
            "status": "missing", "version": None, "source_path": "package/mod.json", "source_field": "version",
        })

        with_root_version = artifact({
            "package/mod.json": json.dumps({"name": "Example Mod", "version": "1.8.0"}),
            "package/dependencies/example/mod.json": json.dumps({"name": "Example", "version": "4.2.0"}),
        })
        self.assertEqual(sync_workshop.inspect_artifact_manifest(with_root_version), {
            "status": "declared", "version": "1.8.0", "source_path": "package/mod.json", "source_field": "version",
        })

    def test_does_not_promote_a_deep_manifest_when_no_package_root_exists(self):
        nested_only = artifact({
            "package/dependencies/example/mod.json": json.dumps({"name": "Example", "version": "4.2.0"}),
        })
        self.assertEqual(sync_workshop.inspect_artifact_manifest(nested_only)["status"], "missing")

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        sync_workshop.init_schema(self.conn)
        sync_workshop.upsert_item(self.conn, {"publishedfileid": "1234567890", "title": "Example Mod"})

    def tearDown(self):
        self.conn.close()

    def detail(self, content_reference="100", **changes):
        value = {
            "publishedfileid": "1234567890", "filename": "example-mod.zip", "file_size": "1024",
            "file_url": "https://example.invalid/artifact", "hcontent_file": content_reference,
        }
        value.update(changes)
        return value

    def test_reads_version_and_preserves_prerelease_from_nested_mod_json(self):
        result = sync_workshop.inspect_artifact_manifest(artifact({"Example Mod/mod.json": json.dumps({"version": "1.8.0-beta.2"})}))
        self.assertEqual(result, {
            "status": "declared", "version": "1.8.0-beta.2",
            "source_path": "Example Mod/mod.json", "source_field": "version",
        })

    def test_reports_missing_and_ambiguous_manifest_evidence(self):
        self.assertEqual(sync_workshop.inspect_artifact_manifest(artifact({"readme.txt": "hello"}))["status"], "missing")
        result = sync_workshop.inspect_artifact_manifest(artifact({
            "a/mod.json": json.dumps({"version": "1.7.0"}),
            "b/mod.json": json.dumps({"version": "1.8.0"}),
        }))
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["version"])

    def test_rejects_malformed_and_bounded_archives(self):
        with self.assertRaisesRegex(sync_workshop.ArtifactInspectionError, "readable ZIP"):
            sync_workshop.inspect_artifact_manifest(b"not a zip")
        oversized = artifact({"mod.json": json.dumps({"version": "1.8.0"}), "payload.bin": b"x" * 11})
        with patch.object(sync_workshop, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 10):
            with self.assertRaisesRegex(sync_workshop.ArtifactInspectionError, "uncompressed"):
                sync_workshop.inspect_artifact_manifest(oversized)

    def test_failed_new_content_attempt_preserves_successful_provenance(self):
        good = artifact({"mod.json": json.dumps({"version": "1.8.0"})})
        with patch.object(sync_workshop, "fetch_artifact_bytes", return_value=good), patch.object(
            sync_workshop, "now_iso", return_value="2026-09-07T10:00:00+00:00"
        ):
            self.assertEqual(sync_workshop.inspect_and_record_artifact(self.conn, self.detail("100")), "succeeded")
        with patch.object(
            sync_workshop, "fetch_artifact_bytes",
            side_effect=sync_workshop.ArtifactInspectionError("unavailable", "network failed"),
        ), patch.object(sync_workshop, "now_iso", return_value="2026-09-07T11:00:00+00:00"):
            self.assertEqual(sync_workshop.inspect_and_record_artifact(self.conn, self.detail("200")), "unavailable")
        row = self.conn.execute("SELECT * FROM workshop_artifact_versions").fetchone()
        self.assertEqual(row["version"], "1.8.0")
        self.assertEqual(row["content_reference"], "100")
        self.assertEqual(row["observed_at"], "2026-09-07T10:00:00+00:00")
        self.assertEqual(row["attempted_content_reference"], "200")
        self.assertEqual(row["attempt_status"], "unavailable")
        self.assertEqual(row["attempted_at"], "2026-09-07T11:00:00+00:00")
        self.assertIn("network failed", row["attempt_message"])

    def test_rejects_unsupported_format_and_declared_size_before_download(self):
        with patch.object(sync_workshop, "fetch_artifact_bytes") as fetch:
            self.assertEqual(sync_workshop.inspect_and_record_artifact(self.conn, self.detail(filename="mod.exe")), "unsupported")
            self.assertEqual(sync_workshop.inspect_and_record_artifact(
                self.conn, self.detail(file_size=str(sync_workshop.MAX_ARTIFACT_BYTES + 1))
            ), "bounded")
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
