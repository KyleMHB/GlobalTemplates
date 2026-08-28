import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("report_workshop", ROOT / "scripts" / "report_workshop.py")
report_workshop = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(report_workshop)

SYNC_SPEC = importlib.util.spec_from_file_location("sync_workshop", ROOT / "scripts" / "sync_workshop.py")
sync_workshop = importlib.util.module_from_spec(SYNC_SPEC)
assert SYNC_SPEC.loader is not None
SYNC_SPEC.loader.exec_module(sync_workshop)


BASIC_TEMPLATE = report_workshop.load_templates(ROOT / "references" / "check-templates.json")["basic"]


def make_db() -> tuple[tempfile.TemporaryDirectory, Path]:
    tmp = tempfile.TemporaryDirectory()
    db_path = Path(tmp.name) / "fixture.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE workshop_items (
            publishedfileid TEXT PRIMARY KEY,
            title TEXT,
            appid TEXT,
            creator TEXT,
            description TEXT,
            metadata_json TEXT,
            last_metadata_sync TEXT,
            last_comment_sync TEXT
        );
        CREATE TABLE comments (
            publishedfileid TEXT,
            comment_key TEXT,
            author TEXT,
            text TEXT,
            position INTEGER,
            created_at TEXT,
            raw_json TEXT,
            PRIMARY KEY (publishedfileid, comment_key)
        );
        CREATE TABLE evidence (
            publishedfileid TEXT,
            category TEXT,
            source_type TEXT,
            source_key TEXT,
            term TEXT,
            snippet TEXT,
            confidence TEXT,
            PRIMARY KEY (publishedfileid, category, source_type, source_key, term, snippet)
        );
        CREATE TABLE sync_failures (
            publishedfileid TEXT,
            stage TEXT,
            message TEXT,
            last_seen TEXT,
            PRIMARY KEY (publishedfileid, stage, message)
        );
        """
    )
    conn.execute(
        "INSERT INTO workshop_items (publishedfileid, title, appid, creator, description, metadata_json, last_metadata_sync, last_comment_sync) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("100000", "Alpha Mod", "108600", "creator", "", "{}", "2026-05-17T00:00:00Z", "2026-05-17T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    return tmp, db_path


def add_evidence(conn: sqlite3.Connection, category: str, source_key: str, snippet: str, position: int | None = None) -> None:
    source_type = "comment" if position is not None else "description"
    conn.execute(
        "INSERT OR REPLACE INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("100000", category, source_type, source_key, category, snippet, "reported" if source_type == "comment" else "direct"),
    )
    if position is not None:
        conn.execute(
            "INSERT OR REPLACE INTO comments VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("100000", source_key, "user", snippet, position, "", "{}"),
        )
    conn.commit()


def build_report(db_path: Path):
    conn = report_workshop.connect_db(db_path)
    try:
        report_workshop.init_report_schema(conn)
        return report_workshop.fetch_report(
            conn,
            ["100000"],
            report_workshop.selected_categories(SimpleNamespace(category=None), BASIC_TEMPLATE),
            "basic",
            BASIC_TEMPLATE,
        )
    finally:
        conn.close()


class ReportWorkshopTests(unittest.TestCase):
    def test_basic_check_reports_selected_mod_overlap_and_compatibility(self):
        items = [
            {
                "publishedfileid": "100000",
                "title": "Alpha Mod",
                "evidence": {
                    "overlap": [{
                        "item_id": "100000", "title": "Alpha Mod", "category": "overlap",
                        "source_type": "description", "source_key": "100000", "term": "overlap",
                        "snippet": "Overlaps with Beta Mod.", "confidence": "direct", "comment_position": None,
                    }],
                    "compatibility": [{
                        "item_id": "100000", "title": "Alpha Mod", "category": "compatibility",
                        "source_type": "description", "source_key": "100000", "term": "compatible",
                        "snippet": "Compatible with Beta Mod.", "confidence": "direct", "comment_position": None,
                    }],
                    "resolved": [],
                },
            },
            {"publishedfileid": "200000", "title": "Beta Mod", "evidence": {"resolved": []}},
        ]

        questions = {question["id"]: question for question in report_workshop.build_question_results(items, BASIC_TEMPLATE)}

        self.assertEqual(questions["mod_overlaps"]["evidence"][0]["status"], "between_selected_mods")
        self.assertEqual(questions["mod_compatibility"]["evidence"][0]["status"], "compatible_selected_mods")
        self.assertEqual(questions["mod_compatibility"]["status"], "evidence_found")

    def test_compatibility_extraction_excludes_negative_wording(self):
        positive = sync_workshop.extract_evidence_for_text(
            "100000", "description", "100000", "This mod is compatible with Beta Mod and works alongside it."
        )
        negative = sync_workshop.extract_evidence_for_text(
            "100000", "description", "100000", "This mod is not compatible with Beta Mod and does not work with it."
        )

        self.assertIn("compatibility", {row[1] for row in positive})
        self.assertNotIn("compatibility", {row[1] for row in negative})

    def test_basic_check_filters_positive_performance_mentions(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sqlite3.connect(db_path)
        add_evidence(conn, "performance", "c1", "This reduces lag and has no performance impact.", 0)
        add_evidence(conn, "performance", "c2", "This mod lags the game and causes heavy lag.", 1)
        conn.close()

        report = build_report(db_path)
        question = next(q for q in report["questions"] if q["id"] == "performance_reports")
        snippets = [entry["snippet"] for entry in question["evidence"]]
        self.assertEqual(snippets, ["This mod lags the game and causes heavy lag."])

    def test_newer_resolved_comment_suppresses_older_problem(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sqlite3.connect(db_path)
        add_evidence(conn, "errors", "old", "This crashes on load.", 4)
        add_evidence(conn, "resolved", "new", "Author fixed it, works now.", 0)
        conn.close()

        report = build_report(db_path)
        question = next(q for q in report["questions"] if q["id"] == "user_errors")
        self.assertEqual(question["evidence"], [])
        self.assertEqual(len(question["resolved"]), 1)
        self.assertEqual(question["resolved"][0]["resolved_reason"], "newer_comment")

    def test_older_resolved_comment_does_not_suppress_newer_problem(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sqlite3.connect(db_path)
        add_evidence(conn, "errors", "new", "This crashes on load.", 0)
        add_evidence(conn, "resolved", "old", "This was fixed before.", 4)
        conn.close()

        report = build_report(db_path)
        question = next(q for q in report["questions"] if q["id"] == "user_errors")
        self.assertEqual(len(question["evidence"]), 1)
        self.assertEqual(question["resolved"], [])

    def test_manual_resolution_suppresses_active_evidence(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sqlite3.connect(db_path)
        add_evidence(conn, "errors", "c1", "This crashes on load.", 0)
        conn.close()

        initial = build_report(db_path)
        entry = next(q for q in initial["questions"] if q["id"] == "user_errors")["evidence"][0]
        conn = report_workshop.connect_db(db_path)
        report_workshop.init_report_schema(conn)
        report_workshop.record_manual_resolution(conn, entry)
        conn.close()

        report = build_report(db_path)
        question = next(q for q in report["questions"] if q["id"] == "user_errors")
        self.assertEqual(question["evidence"], [])
        self.assertEqual(question["resolved"][0]["resolved_reason"], "manual")

    def test_html_contains_static_controls_and_parent_filter_logic(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sqlite3.connect(db_path)
        add_evidence(conn, "performance", "c1", "This mod has bad performance and fps drops.", 0)
        conn.close()

        html = report_workshop.render_html(build_report(db_path), server_mode=False)
        self.assertIn("<details class=\"actions\">", html)
        self.assertIn("Persistent resolution requires running this report", html)
        self.assertIn("document.querySelectorAll('.question')", html)
        self.assertIn("visibleModCards", html)

    def test_linkify_text_does_not_rewrite_generated_href_ids(self):
        linked = report_workshop.linkify_text("Alpha Mod mentions 1234567890.", {"1234567890": "Alpha Mod"})

        self.assertEqual(linked.count("<a href="), 2)
        self.assertNotIn('id=<a href=', linked)
        self.assertIn('href="https://steamcommunity.com/sharedfiles/filedetails/?id=1234567890">Alpha Mod</a>', linked)
        self.assertIn('href="https://steamcommunity.com/sharedfiles/filedetails/?id=1234567890">1234567890</a>', linked)

    def test_manual_resolution_rejects_mismatched_fingerprint(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sqlite3.connect(db_path)
        add_evidence(conn, "errors", "c1", "This crashes on load.", 0)
        conn.close()

        report = build_report(db_path)
        entry = next(q for q in report["questions"] if q["id"] == "user_errors")["evidence"][0]
        payload = dict(entry)
        payload["snippet"] = "Different evidence text."
        conn = report_workshop.connect_db(db_path)
        report_workshop.init_report_schema(conn)
        try:
            with self.assertRaises(ValueError):
                report_workshop.record_manual_resolution(conn, payload)
        finally:
            conn.close()

    def test_report_server_validates_current_report_fingerprint(self):
        tmp, db_path = make_db()
        self.addCleanup(tmp.cleanup)
        conn = sqlite3.connect(db_path)
        add_evidence(conn, "errors", "c1", "This crashes on load.", 0)
        conn.close()

        args = SimpleNamespace(
            db=db_path,
            ids="100000",
            input=None,
            list_name=None,
            include_archived=False,
            all=False,
            category=None,
            check="basic",
        )
        server = report_workshop.ReportServer(("127.0.0.1", 0), report_workshop.ReportRequestHandler, args, BASIC_TEMPLATE)
        try:
            server.validate_csrf({"csrf_token": server.csrf_token})
            with self.assertRaises(ValueError):
                server.validate_csrf({"csrf_token": "wrong"})
            with self.assertRaises(ValueError):
                server.validate_report_fingerprint({"fingerprint": "not-current"}, "active")
        finally:
            server.server_close()

    def test_basic_check_wording_is_evidence_based_without_target_version(self):
        questions = {question["id"]: question for question in BASIC_TEMPLATE["questions"]}

        self.assertEqual(questions["dependency_fulfillment"]["question"], "Is there dependency evidence that needs review?")
        self.assertEqual(questions["game_version_compatibility"]["question"], "Is there version or build concern evidence?")
        self.assertIn("No target game version is assumed", questions["game_version_compatibility"]["description"])


if __name__ == "__main__":
    unittest.main()
