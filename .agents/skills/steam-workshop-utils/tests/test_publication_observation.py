import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


sync_workshop = load_module("sync_workshop_publication", ROOT / "scripts" / "sync_workshop.py")


def args():
    return SimpleNamespace(api_key=None, skip_comments=True, comments_limit=0, workers=1)


class PublicationObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = sync_workshop.connect_db(Path(self.tmp.name) / "fixture.sqlite")
        self.addCleanup(self.conn.close)
        sync_workshop.init_schema(self.conn)

    def test_success_records_actual_observation_and_clears_old_failure(self):
        sync_workshop.record_failure(self.conn, "1234567890", "metadata", "old outage")
        detail = {"publishedfileid": "1234567890", "result": 1, "title": "Example Mod"}

        with patch.object(sync_workshop, "fetch_details", return_value=[detail]):
            result = sync_workshop.sync_items(self.conn, ["1234567890"], {}, args())

        item = self.conn.execute(
            "SELECT last_metadata_sync FROM workshop_items WHERE publishedfileid = ?", ("1234567890",)
        ).fetchone()
        failure = self.conn.execute(
            "SELECT 1 FROM sync_failures WHERE publishedfileid = ? AND stage = 'metadata'", ("1234567890",)
        ).fetchone()
        self.assertEqual(result["metadata_failures"], 0)
        self.assertIsNotNone(item["last_metadata_sync"])
        self.assertIsNone(failure)

    def test_failed_refresh_preserves_success_time_and_records_current_attempt(self):
        detail = {"publishedfileid": "1234567890", "result": 1, "title": "Example Mod"}
        with patch.object(sync_workshop, "now_iso", return_value="2026-09-05T10:00:00+00:00"):
            sync_workshop.upsert_item(self.conn, detail)
        self.conn.commit()

        with patch.object(sync_workshop, "fetch_details", side_effect=RuntimeError("Steam unavailable")), patch.object(
            sync_workshop, "now_iso", return_value="2026-09-07T12:00:00+00:00"
        ):
            result = sync_workshop.sync_items(self.conn, ["1234567890"], {}, args())

        item = self.conn.execute(
            "SELECT last_metadata_sync FROM workshop_items WHERE publishedfileid = ?", ("1234567890",)
        ).fetchone()
        failure = self.conn.execute(
            "SELECT message, last_seen FROM sync_failures WHERE publishedfileid = ? AND stage = 'metadata'", ("1234567890",)
        ).fetchone()
        self.assertEqual(result["metadata_failures"], 1)
        self.assertEqual(item["last_metadata_sync"], "2026-09-05T10:00:00+00:00")
        self.assertEqual(dict(failure), {"message": "Steam unavailable", "last_seen": "2026-09-07T12:00:00+00:00"})

    def test_missing_provider_result_is_an_unobserved_failure(self):
        with patch.object(sync_workshop, "fetch_details", return_value=[]):
            result = sync_workshop.sync_items(self.conn, ["9999999999"], {}, args())

        self.assertEqual(result["metadata_failures"], 1)
        self.assertIsNone(self.conn.execute("SELECT 1 FROM workshop_items WHERE publishedfileid = ?", ("9999999999",)).fetchone())
        failure = self.conn.execute(
            "SELECT message FROM sync_failures WHERE publishedfileid = ? AND stage = 'metadata'", ("9999999999",)
        ).fetchone()
        self.assertIn("no metadata", failure["message"])


if __name__ == "__main__":
    unittest.main()
