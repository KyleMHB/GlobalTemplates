import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sync_workshop_history", ROOT / "scripts" / "sync_workshop.py")
sync_workshop = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(sync_workshop)


def comment(index: int, text: str | None = None):
    key = str(1000 - index)
    return {
        "comment_key": key, "comment_id": key, "position": index,
        "text": text or f"comment {index}", "raw_html": "", "author_id": "42",
        "author_name": "Reader", "author_profile_url": "https://steamcommunity.com/profiles/42",
        "posted_at": f"2026-09-{(index % 28) + 1:02d}T00:00:00+00:00",
        "source_url": f"https://example.test/#comment_{key}", "collected_at": "2026-09-07T00:00:00+00:00",
    }


class CommentHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = sync_workshop.connect_db(Path(self.tmp.name) / "comments.sqlite")
        self.addCleanup(self.conn.close)
        sync_workshop.init_schema(self.conn)

    def fetcher(self, rows, fail_at=None):
        def fetch(_item, _creator, start, count):
            if start == fail_at:
                raise RuntimeError("provider page failed")
            page = [{**row, "position": start + offset} for offset, row in enumerate(rows[start:start + count])]
            return page, len(rows)
        return fetch

    def test_bounded_backfill_resumes_without_duplicates(self):
        rows = [comment(i) for i in range(12)]
        first = sync_workshop.sync_comment_history(self.conn, "item", "creator", 3, 2, self.fetcher(rows))
        self.assertEqual((first["coverage"], first["collected_count"]), ("partial", 6))
        for _ in range(3):
            result = sync_workshop.sync_comment_history(self.conn, "item", "creator", 3, 2, self.fetcher(rows))
        self.assertEqual(result["coverage"], "complete")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0], 12)

    def test_failure_preserves_records_and_progress(self):
        rows = [comment(i) for i in range(8)]
        sync_workshop.sync_comment_history(self.conn, "item", "creator", 2, 2, self.fetcher(rows))
        failed = sync_workshop.sync_comment_history(self.conn, "item", "creator", 2, 3, self.fetcher(rows, fail_at=4))
        self.assertEqual(failed["coverage"], "partial")
        self.assertGreaterEqual(failed["collected_count"], 4)
        self.assertIn("provider page failed", failed["error"])

    def test_new_arrival_and_historical_edit_update_canonical_rows(self):
        rows = [comment(i) for i in range(7)]
        for _ in range(3):
            sync_workshop.sync_comment_history(self.conn, "item", "creator", 3, 3, self.fetcher(rows))
        changed = [comment(99, "new arrival"), *rows]
        changed[5] = {**changed[5], "text": "historically edited"}
        for _ in range(4):
            sync_workshop.sync_comment_history(self.conn, "item", "creator", 3, 3, self.fetcher(changed))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0], 8)
        self.assertEqual(self.conn.execute("SELECT text FROM comments WHERE comment_key=?", (changed[5]["comment_key"],)).fetchone()[0], "historically edited")


if __name__ == "__main__":
    unittest.main()
