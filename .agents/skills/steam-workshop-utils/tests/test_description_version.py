import importlib.util
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sync_workshop_description_version", ROOT / "scripts" / "sync_workshop.py")
sync_workshop = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(sync_workshop)


class DescriptionVersionTests(unittest.TestCase):
    def test_shared_template_declaration_is_a_supported_input_contract(self):
        declaration = "[b]Mod version:[/b] {mod-version}"
        evidence = sync_workshop.description_version_evidence("Example Mod", declaration.replace("{mod-version}", "2.0.0-beta.1"))
        self.assertEqual(evidence["version"], "2.0.0-beta.1")

    def test_prefers_explicit_template_declaration_and_preserves_prerelease(self):
        evidence = sync_workshop.description_version_evidence(
            "Example Mod 1.7.0",
            "[b]Mod version:[/b] 2.0.0-rc.2+steam.5\n[h2]History[/h2]\nVersion 1.4.0",
        )
        self.assertEqual(evidence["status"], "declared")
        self.assertEqual(evidence["version"], "2.0.0-rc.2+steam.5")
        self.assertEqual(evidence["source_field"], "description")

    def test_supports_existing_title_and_current_heading(self):
        evidence = sync_workshop.description_version_evidence(
            "Example Mod 1.8.0", "[h2]What's New in 1.8.0[/h2]\nA faster crafting release."
        )
        self.assertEqual(evidence["status"], "declared")
        self.assertEqual(evidence["version"], "1.8.0")
        self.assertEqual(evidence["source_field"], "description+title")

    def test_rejects_unrelated_game_dependency_history_and_protocol_numbers(self):
        evidence = sync_workshop.description_version_evidence(
            "Example Mod",
            "Supports game version 2.15.1. Requires Framework 3.2.0. History: release 1.7.0. Protocol 4.6.0.",
        )
        self.assertEqual(evidence["status"], "missing")
        self.assertIsNone(evidence["version"])

    def test_rejects_game_version_suffix_in_title(self):
        evidence = sync_workshop.description_version_evidence(
            "Example Mod for Wayward 2.15.5-beta", "Supports Wayward 2.15.5-beta"
        )
        self.assertEqual(evidence["status"], "missing")

    def test_rejects_release_heading_inside_old_history(self):
        evidence = sync_workshop.description_version_evidence(
            "Example Mod", "[h2]Old release history[/h2]\nWhat's New in 1.7.0\nOld changes"
        )
        self.assertEqual(evidence["status"], "missing")

    def test_rejects_explicit_declaration_inside_old_history(self):
        evidence = sync_workshop.description_version_evidence(
            "Example Mod", "[h2]Old release history[/h2]\n[b]Mod version:[/b] 1.7.0"
        )
        self.assertEqual(evidence["status"], "missing")

    def test_rejects_quoted_release_heading_in_prose(self):
        evidence = sync_workshop.description_version_evidence(
            "Example Mod", "See dependency notes quoting What's New in 4.2.0 for the required framework."
        )
        self.assertEqual(evidence["status"], "missing")

    def test_rejects_dependency_version_declaration(self):
        evidence = sync_workshop.description_version_evidence(
            "Example Mod", "Requires Example Mod version: 4.2.0"
        )
        self.assertEqual(evidence["status"], "missing")

    def test_supports_clear_current_title_and_heading_independently(self):
        self.assertEqual(sync_workshop.description_version_evidence("Example Mod 1.8.0", "")["version"], "1.8.0")
        self.assertEqual(sync_workshop.description_version_evidence("Example Mod", "[h2]What's New in 1.8.0[/h2]")["version"], "1.8.0")

    def test_conflicting_current_declarations_are_ambiguous(self):
        evidence = sync_workshop.description_version_evidence("Example Mod 2.0.0", "[h2]What's New in 2.1.0[/h2]")
        self.assertEqual(evidence["status"], "ambiguous")
        self.assertIsNone(evidence["version"])
        self.assertIn("2.0.0", evidence["excerpt"])
        self.assertIn("2.1.0", evidence["excerpt"])

    def test_multiple_explicit_declarations_are_ambiguous(self):
        evidence = sync_workshop.description_version_evidence(
            "Example Mod", "[b]Mod version:[/b] 2.0.0\n[b]Mod version:[/b] 2.1.0"
        )
        self.assertEqual(evidence["status"], "ambiguous")

    def test_persists_evidence_at_the_successful_metadata_observation_time(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        sync_workshop.init_schema(conn)
        with patch.object(sync_workshop, "now_iso", return_value="2026-09-05T10:00:00+00:00"):
            sync_workshop.upsert_item(conn, {
                "publishedfileid": "1234567890", "title": "Example Mod 1.8.0",
                "description": "[h2]What's New in 1.8.0[/h2]",
            })
        row = conn.execute("SELECT * FROM workshop_description_versions WHERE publishedfileid='1234567890'").fetchone()
        self.assertEqual(row["version"], "1.8.0")
        self.assertEqual(row["observed_at"], "2026-09-05T10:00:00+00:00")
        self.assertIn("does not verify", row["limitations"])


if __name__ == "__main__":
    unittest.main()
