"""Game-agnostic launcher logic: exit codes, deadlines, run folders, `latest`, `timings`, `prune`, snapshots and logs."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import devtests_core as core


class TempCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative, text="x"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class ResultTest(TempCase):
    def code(self, report, problems=()):
        with contextlib.redirect_stdout(io.StringIO()):
            return core.result_code(report, list(problems))

    def test_exit_codes(self):
        self.assertEqual(self.code({"status": "complete", "overallPass": True}), 0)
        self.assertEqual(self.code({"status": "complete", "overallPass": False}), 1)
        self.assertEqual(self.code({"status": "complete", "overallPass": True}, ["user save modified"]), 1)
        self.assertEqual(self.code({"status": "interrupted", "overallPass": False}), 2)
        self.assertEqual(self.code({"status": "refused"}), 3)
        self.assertEqual(self.code(None), 2)

    def test_short_limit_sends_no_game_deadline(self):
        self.assertEqual(core.game_deadline(time.monotonic() + 20), 0)
        self.assertEqual(core.game_deadline(time.monotonic() + 600, graceful=False), 0)
        self.assertAlmostEqual(core.game_deadline(time.monotonic() + 600) / 1000, time.time() + 600 - core.DEADLINE_GRACE, delta=2)

    def test_launcher_fault_is_exit_4(self):
        def broken(argv):
            raise KeyError("bug")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(core.guarded(broken, []), 4)
            self.assertEqual(core.guarded(lambda argv: 1, []), 1)

    def test_run_id_names_the_batch_and_a_case_filter(self):
        run_id = core.new_run_id("Run All!", 3)
        self.assertRegex(run_id, r"^\d{8}-\d{6}-run-all--s3$")
        self.assertTrue(core.new_run_id("smoke", 1, cases=["a.*"]).endswith("-smoke-s1-cases"))


class LocalConfigTest(TempCase):
    def test_environment_then_local_file_then_default(self):
        local = self.write("tool.local.json", json.dumps({"gameDir": "D:/Local"}))
        os.environ.pop("CORE_TEST_DIR", None)
        self.assertEqual(core.local_path("CORE_TEST_DIR", local, "gameDir", "C:/Default"), Path("D:/Local"))
        self.assertEqual(core.local_path("CORE_TEST_DIR", self.root / "absent.json", "gameDir", "C:/Default"), Path("C:/Default"))
        os.environ["CORE_TEST_DIR"] = "E:/Env"
        try:
            self.assertEqual(core.local_path("CORE_TEST_DIR", local, "gameDir", "C:/Default"), Path("E:/Env"))
        finally:
            del os.environ["CORE_TEST_DIR"]

    def test_missing_key_falls_back(self):
        local = self.write("tool.local.json", json.dumps({"other": 1}))
        self.assertEqual(core.local_value(local, "maxGames", 3), 3)
        self.assertEqual(core.local_value(local, "other", 3), 1)


class LatestTest(TempCase):
    def latest(self, batch=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = core.latest(self.root / "evidence", batch)
        return code, output.getvalue()

    def test_unfinished_newer_run_is_not_hidden_by_an_older_report(self):
        old = self.write("evidence/run-1/report.json", json.dumps({"request": {"Batch": "a", "Batches": ["a"]}}))
        self.write("evidence/run-1/summary.txt", "older run PASS")
        os.utime(old, (1000, 1000))
        self.write("evidence/run-2/progress.json", json.dumps(
            {"Request": {"Batch": "a", "Batches": ["a"], "Seed": 1}, "Stage": "segment", "BatchIndex": 0,
             "Cases": [{"Result": "pass"}, {"Result": "running"}]}))
        code, text = self.latest()
        self.assertEqual(code, 2)
        self.assertIn("run-2 has no report", text)
        self.assertIn("1 case(s) finished", text)
        self.assertNotIn("older run PASS", text)

    def test_batch_filter_matches_a_run_all_that_included_it(self):
        self.write("evidence/run-1/report.json", json.dumps({"request": {"Batch": "run-all", "Batches": ["diagnostic", "a"]}}))
        self.write("evidence/run-1/summary.txt", "run-all summary")
        self.assertEqual(self.latest("a")[0], 0)
        self.assertEqual(self.latest("b")[0], 1)

    def test_run_without_report_or_progress_still_counts_as_unfinished(self):
        # A launcher that writes its own record (launcher.json) before the game reports must not let an older report show.
        old = self.write("evidence/run-1/report.json", json.dumps({"request": {"Batch": "a"}}))
        self.write("evidence/run-1/summary.txt", "older run PASS")
        os.utime(old, (1000, 1000))
        self.write("evidence/run-2/launcher.json", "{}")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = core.latest(self.root / "evidence", run_files=core.RUN_FILES + ("launcher.json",), unfinished_files=("launcher.json",))
        self.assertEqual(code, 2)
        self.assertIn("run-2 has no report", output.getvalue())

    def test_deployment_record_alone_does_not_hide_an_older_report(self):
        old = self.write("evidence/run-1/report.json", json.dumps({"request": {"Batch": "a"}}))
        self.write("evidence/run-1/summary.txt", "older run PASS")
        os.utime(old, (1000, 1000))
        self.write("evidence/run-2/deployment.json", "{}")
        code, text = self.latest()
        self.assertEqual(code, 0)
        self.assertIn("older run PASS", text)


class TimingsAndPruneTest(TempCase):
    def test_timings_orders_batches_slowest_first(self):
        events = [{"batch": "a", "monotonicSeconds": 0}, {"batch": "b", "monotonicSeconds": 2}, {"batch": "b", "monotonicSeconds": 9},
                  {"monotonicSeconds": 10}]
        self.write("evidence/run-1/events.jsonl", "\n".join(json.dumps(e) for e in events))
        self.write("evidence/run-1/report.json", "{}")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(core.timings(self.root / "evidence"), 0)
        lines = output.getvalue().splitlines()
        self.assertTrue(lines[1].strip().startswith("b") and "8.0 s" in lines[1])
        self.assertTrue(lines[2].strip().startswith("a") and "2.0 s" in lines[2])
        self.assertIn("10.0 s", lines[3])

    def test_prune_keeps_the_newest_runs(self):
        for i, stamp in ((1, 1000), (2, 2000), (3, 3000)):
            os.utime(self.write(f"evidence/run-{i}/report.json", "{}"), (stamp, stamp))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(core.prune(self.root / "evidence", 2), 0)
        self.assertEqual(sorted(p.name for p in (self.root / "evidence").iterdir()), ["run-2", "run-3"])


class ProtectedDataTest(TempCase):
    def test_diff_names_changed_added_and_removed_files_but_ignores_cloud_markers(self):
        save = self.write("Saves/Colony/a.timber", "before")
        gone = self.write("Maps/old.timber")
        vdf = self.write("Saves/steam_autocloud.vdf", "1")
        before = core.tree_snapshot(self.root / "Saves", self.root / "Maps", self.root / "Absent")
        save.write_text("after, longer", encoding="utf-8")
        gone.unlink()
        vdf.write_text("22", encoding="utf-8")
        added = self.write("Maps/new.timber")
        changes = core.snapshot_diff(before, core.tree_snapshot(self.root / "Saves", self.root / "Maps"), ignore=("steam_autocloud.vdf",))
        self.assertEqual(changes, sorted([str(save), str(gone), str(added)]))

    def test_moves_files_new_since_the_snapshot(self):
        self.write("Reports/old.zip")
        before = core.tree_snapshot(self.root / "Reports")
        new = self.write("Reports/crash.zip")
        moved = core.move_new_files(before, self.root / "Reports", self.root / "run")
        self.assertEqual(moved, ["crash.zip"])
        self.assertFalse(new.exists())
        self.assertTrue((self.root / "run/crash.zip").is_file())
        self.assertTrue((self.root / "Reports/old.zip").is_file())


class LogTest(TempCase):
    def test_counts_exceptions_and_errors(self):
        log = self.write("Player.log", "\n".join([
            "Loading mods", "NullReferenceException: Object reference not set", "  at Foo.Bar ()",
            "First uncaught exception", "[Error] something failed", "fine"]))
        counts = core.log_errors(log)
        self.assertEqual(counts["exceptions"], 1)
        self.assertEqual(counts["errors"], 1)
        self.assertTrue(counts["crashed"])
        self.assertIn("NullReferenceException", counts["first"][0])

    def test_keep_log_copies_only_the_tail_of_a_large_file(self):
        source = self.write("Player.log", "a" * 100 + "TAIL")
        self.assertTrue(core.keep_log(source, self.root / "run", keep_bytes=4))
        self.assertEqual((self.root / "run/Player.log").read_text(encoding="utf-8"), "TAIL")
        self.assertFalse(core.keep_log(self.root / "absent.log", self.root / "run2"))

    def test_tail(self):
        path = self.write("x.txt", "1\n2\n3")
        self.assertEqual(core.tail(path, 2), "2\n3")
        self.assertIn("missing", core.tail(self.root / "absent"))


if __name__ == "__main__":
    unittest.main()
