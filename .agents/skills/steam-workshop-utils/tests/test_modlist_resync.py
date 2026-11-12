import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


sync_workshop = load_module("sync_workshop", ROOT / "scripts" / "sync_workshop.py")
report_workshop = load_module("report_workshop_for_modlist", ROOT / "scripts" / "report_workshop.py")


def make_db() -> tuple[tempfile.TemporaryDirectory, Path]:
    tmp = tempfile.TemporaryDirectory()
    db_path = Path(tmp.name) / "fixture.sqlite"
    conn = sync_workshop.connect_db(db_path)
    sync_workshop.init_schema(conn)
    for item_id, title in (("100000", "Alpha Mod"), ("200000", "Beta Mod"), ("300000", "Gamma Mod")):
        conn.execute(
            """
            INSERT INTO workshop_items (
                publishedfileid, title, description, creator, appid, file_size,
                time_created, time_updated, subscriptions, favorited, tags_json, raw_json, last_metadata_sync
            ) VALUES (?, ?, '', 'creator', 108600, 0, 0, 0, 0, 0, '[]', '{}', ?)
            """,
            (item_id, title, sync_workshop.now_iso()),
        )
    conn.commit()
    conn.close()
    return tmp, db_path


class ModlistResyncTests(unittest.TestCase):
    def test_anonymized_fixture_has_all_comment_roots(self):
        fixture = json.loads((ROOT / "tests" / "fixtures" / "workshop-comments.json").read_text(encoding="utf-8"))
        comments = sync_workshop.parse_comments("1234567890", fixture["comments_html"])
        self.assertEqual(len(comments), fixture["total_count"])
        release = next(row for row in comments if row["comment_id"] == "100000000000000001")
        self.assertEqual(release["author_id"], "76561197960266728")
        self.assertEqual(release["posted_at"], "2026-08-28T12:49:28+00:00")
        self.assertIn("Improved cleanup when a session ends.", release["text"])
        legacy = {entry["kind"]: entry["key"] for entry in release["legacy_fragments"]}
        self.assertEqual(legacy["posted_time"], sync_workshop.legacy_fragment_key("1234567890", "28 Aug @ 5:49am"))
        self.assertEqual(legacy["body"], sync_workshop.legacy_fragment_key("1234567890", release["text"]))
        author_key = sync_workshop.legacy_fragment_key("1234567890", "Example Author 1")
        self.assertEqual(legacy["author"], author_key)
        self.assertGreater(sum(author_key in {entry["key"] for entry in row["legacy_fragments"]} for row in comments), 1)

    def test_nested_comment_is_one_structured_record(self):
        markup = """
        <div class="commentthread_comment responsive_body_text" id="comment_100000000000000001">
          <div class="commentthread_comment_avatar"><a href="https://steamcommunity.com/profiles/76561197960266728/">avatar</a></div>
          <div class="commentthread_comment_content">
            <div class="commentthread_comment_author">
              <a class="commentthread_author_link" data-miniprofile="1000" href="https://steamcommunity.com/profiles/76561197960266728/">Example Author 1</a>
              <span class="commentthread_comment_timestamp" data-timestamp="1788724800">6 Sep @ 10:00pm</span>
            </div>
            <div class="commentthread_comment_text">Example Mod 1.8.0 is now available.<br>What's new:<br>- Full release-note text.</div>
            <div class="commentthread_comment_actions">Reply</div>
          </div>
        </div>
        """

        comments = sync_workshop.parse_comments("1234567890", markup)

        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["comment_id"], "100000000000000001")
        self.assertEqual(comments[0]["comment_key"], "100000000000000001")
        self.assertEqual(comments[0]["author_id"], "76561197960266728")
        self.assertEqual(comments[0]["author_name"], "Example Author 1")
        self.assertEqual(comments[0]["author_profile_url"], "https://steamcommunity.com/profiles/76561197960266728/")
        self.assertEqual(comments[0]["posted_at"], "2026-09-06T20:00:00+00:00")
        self.assertEqual(comments[0]["text"], "Example Mod 1.8.0 is now available.\nWhat's new:\n- Full release-note text.")
        self.assertIn("#comment_100000000000000001", comments[0]["source_url"])

    def test_same_text_with_different_comment_ids_remains_distinct(self):
        markup = """
        <div class="commentthread_comment" id="comment_101"><div class="commentthread_comment_text">Same text</div></div>
        <div class="commentthread_comment" id="comment_102"><div class="commentthread_comment_text">Same text</div></div>
        """
        self.assertEqual([row["comment_key"] for row in sync_workshop.parse_comments("100000", markup)], ["101", "102"])

    def test_preview_resync_does_not_create_missing_db(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / "missing.sqlite"

        code = sync_workshop.main(["resync", "--list", "default", "--ids", "100000", "--db", str(db_path)])

        self.assertEqual(code, 0)
        self.assertFalse(db_path.exists())

    def test_bootstrap_apply_and_repeat_diff(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sync_workshop.connect_db(db_path)
        diff = sync_workshop.diff_modlist(conn, "default", ["100000", "200000"])
        self.assertEqual(diff["counts"]["added"], 2)
        self.assertEqual(diff["counts"]["unchanged"], 0)

        sync_workshop.apply_modlist_diff(conn, "default", ["100000", "200000"], [])
        repeated = sync_workshop.diff_modlist(conn, "default", ["100000", "200000"])
        conn.close()

        self.assertEqual(repeated["counts"]["added"], 0)
        self.assertEqual(repeated["counts"]["unchanged"], 2)

    def test_remove_and_restore_archived_mod(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sync_workshop.connect_db(db_path)
        sync_workshop.apply_modlist_diff(conn, "default", ["100000", "200000"], [])
        removed = sync_workshop.diff_modlist(conn, "default", ["100000"])
        sync_workshop.apply_modlist_diff(conn, "default", ["100000"], [entry["id"] for entry in removed["removed"]])
        restored = sync_workshop.diff_modlist(conn, "default", ["100000", "200000"])
        conn.close()

        self.assertEqual([entry["id"] for entry in removed["removed"]], ["200000"])
        self.assertEqual(restored["counts"]["added"], 1)
        self.assertTrue(restored["added"][0]["restored"])

    def test_purge_archived_deletes_cache_rows(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sync_workshop.connect_db(db_path)
        sync_workshop.apply_modlist_diff(conn, "default", ["100000", "200000"], [])
        removed = sync_workshop.diff_modlist(conn, "default", ["100000"])
        sync_workshop.apply_modlist_diff(conn, "default", ["100000"], [entry["id"] for entry in removed["removed"]])
        sync_workshop.purge_archived_items(conn, "default", ["200000"])

        self.assertIsNone(conn.execute("SELECT 1 FROM workshop_items WHERE publishedfileid = '200000'").fetchone())
        self.assertIsNone(conn.execute("SELECT 1 FROM modlist_items WHERE list_name = 'default' AND publishedfileid = '200000'").fetchone())
        conn.close()

    def test_report_list_excludes_archived_by_default(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sync_workshop.connect_db(db_path)
        sync_workshop.apply_modlist_diff(conn, "default", ["100000", "200000"], [])
        removed = sync_workshop.diff_modlist(conn, "default", ["100000"])
        sync_workshop.apply_modlist_diff(conn, "default", ["100000"], [entry["id"] for entry in removed["removed"]])
        conn.close()

        report_conn = report_workshop.connect_db(db_path)
        report_workshop.init_report_schema(report_conn)
        args = SimpleNamespace(list_name="default", include_archived=False, all=False, ids=None, input=None)
        active_ids = report_workshop.collect_ids(report_conn, args)
        args.include_archived = True
        all_ids = report_workshop.collect_ids(report_conn, args)
        report_conn.close()

        self.assertEqual(active_ids, ["100000"])
        self.assertEqual(set(all_ids), {"100000", "200000"})

    def test_shifted_comment_position_updates_existing_row(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sync_workshop.connect_db(db_path)
        comment_key = "stable-comment"

        sync_workshop.upsert_comments(
            conn,
            "100000",
            [{"comment_key": comment_key, "position": 3, "text": "This crashes on load.", "raw_html": ""}],
            10,
        )
        sync_workshop.upsert_comments(
            conn,
            "100000",
            [{"comment_key": comment_key, "position": 0, "text": "This crashes on load.", "raw_html": ""}],
            10,
        )

        row = conn.execute("SELECT COUNT(*) AS count, position FROM comments WHERE publishedfileid = '100000'").fetchone()
        conn.close()
        self.assertEqual(row["count"], 1)
        self.assertEqual(row["position"], 0)

    def test_comment_upsert_enriches_author_and_updates_body(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sync_workshop.connect_db(db_path)
        sync_workshop.upsert_comments(conn, "100000", [{"comment_key": "101", "comment_id": "101", "position": 0, "text": "Original", "raw_html": ""}], 10)
        sync_workshop.upsert_comments(conn, "100000", [{
            "comment_key": "101", "comment_id": "101", "position": 0, "text": "Edited", "raw_html": "",
            "author_id": "76561197960266728", "author_name": "New display name",
            "author_profile_url": "https://steamcommunity.com/profiles/76561197960266728/",
            "posted_at": "2026-09-06T20:00:00+00:00", "source_url": "https://example.test/#comment_101",
        }], 10)
        row = conn.execute("SELECT * FROM comments WHERE publishedfileid='100000'").fetchone()
        conn.close()
        self.assertEqual(row["text"], "Edited")
        self.assertEqual(row["author_id"], "76561197960266728")
        self.assertEqual(row["author_name"], "New display name")
        self.assertNotEqual(row["collected_at"], None)

    def test_comment_upsert_persists_legacy_fragment_identity_evidence(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sync_workshop.connect_db(db_path)
        fragments = [{"key": "legacy-key", "kind": "body", "text": "Legacy body"}]
        sync_workshop.upsert_comments(conn, "100000", [{
            "comment_key": "101", "comment_id": "101", "position": 0, "text": "Canonical body", "raw_html": "",
            "legacy_fragments": fragments,
        }], 10)

        row = conn.execute("SELECT legacy_fragments_json FROM comments WHERE publishedfileid='100000'").fetchone()
        conn.close()

        self.assertEqual(json.loads(row["legacy_fragments_json"]), fragments)

    def test_incomplete_comment_fetch_preserves_cached_history(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sync_workshop.connect_db(db_path)

        sync_workshop.upsert_comments(
            conn,
            "100000",
            [
                {"comment_key": "old", "position": 0, "text": "Old comment.", "raw_html": ""},
                {"comment_key": "keep", "position": 1, "text": "Kept comment.", "raw_html": ""},
            ],
            10,
        )
        sync_workshop.upsert_comments(
            conn,
            "100000",
            [{"comment_key": "keep", "position": 0, "text": "Kept comment.", "raw_html": ""}],
            10,
        )

        keys = [row["comment_key"] for row in conn.execute("SELECT comment_key FROM comments WHERE publishedfileid = '100000' ORDER BY comment_key")]
        conn.close()
        self.assertEqual(keys, ["keep", "old"])


if __name__ == "__main__":
    unittest.main()
