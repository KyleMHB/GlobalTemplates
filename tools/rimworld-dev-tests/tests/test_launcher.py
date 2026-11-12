"""Launcher logic that needs no game: mod sets, the runtime manifest, save snapshots, exit codes and `latest`."""
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
import rimtest


def make_config(root, **overrides):
    values = dict(name="Example", arg_prefix="ex", root=root, mod_dir=root / "installed", runtime_root=root,
                  production_dll=root / "Assemblies/Example.dll", dev_assemblies=root / "installed/Assemblies",
                  dev_build=root / "work/Example.DevTests.dll", dev_project=root / "DevTests", evidence_root=root / "evidence",
                  runtime_folders=("Assemblies", "Defs"), runtime_files=("LoadFolders.xml",), game_command=["RimWorld.exe"],
                  userdata=root / "userdata", package_id="author.example", mod_sets={"default": ["author.example"]},
                  batch_mod_sets={})
    values.update(overrides)
    return rimtest.Config(**values)


def mod(package_id, dependencies=(), load_after=()):
    return rimtest.ModInfo(package_id, package_id, [list(d) for d in dependencies], set(load_after), set())


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


class ModSetTest(TempCase):
    def test_merge_keeps_each_sets_order(self):
        merged = rimtest.merge_sets([["harmony", "core", "mine"], ["harmony", "core", "other", "mine"]])
        self.assertEqual(merged, ["harmony", "core", "other", "mine"])

    def test_reports_missing_dependency_and_load_order(self):
        config = make_config(self.root)
        index = {"core": mod("core"), "author.example": mod("author.example", dependencies=[["lib"]], load_after=["late"]),
                 "late": mod("late")}
        problems = rimtest.mod_problems(config, ["core", "author.example", "late", "absent"], index)
        self.assertTrue(any("requires lib" in p for p in problems))
        self.assertTrue(any("must load after late" in p for p in problems))
        self.assertTrue(any("absent is not installed" in p for p in problems))

    def test_steam_suffixed_id_counts_as_the_mod(self):
        config = make_config(self.root)
        index = {"lib": mod("lib"), "author.example": mod("author.example", dependencies=[["lib"]])}
        self.assertEqual(rimtest.mod_problems(config, ["lib_steam", "author.example"], index), [])


class ManifestTest(TempCase):
    def test_skips_pdb_developer_dlls_and_configured_exclusions(self):
        for name in ("Assemblies/Example.dll", "Assemblies/Example.pdb", "Assemblies/Example.DevTests.dll",
                     "Assemblies/RimWorldDevTests.dll", "Assemblies/Showcase.json", "Defs/Things.xml", "LoadFolders.xml"):
            self.write(name)
        config = make_config(self.root, runtime_exclusions=("Showcase.json",))
        self.assertEqual(sorted(rimtest.runtime_manifest(config, self.root)),
                         ["assemblies/example.dll", "defs/things.xml", "loadfolders.xml"])

    def test_names_the_config_entry_that_disagrees(self):
        config = make_config(self.root)
        environment = {"runtimeConfig": {"folders": ["Assemblies", "Defs"], "files": ["LoadFolders.xml"], "exclusions": ["Showcase.json"]}}
        self.assertIn('"runtimeExclusions"', rimtest.runtime_config_difference(config, environment))
        self.assertEqual(rimtest.runtime_config_difference(config, {}), "")


class SnapshotTest(TempCase):
    def test_notices_a_changed_save(self):
        save = self.write("Saves/Colony.rws", "before")
        before = rimtest.snapshot_saves(self.root / "Saves")
        save.write_text("after, longer", encoding="utf-8")
        self.assertNotEqual(before, rimtest.snapshot_saves(self.root / "Saves"))

    def test_pins_prefs_that_change_run_behaviour(self):
        prefs = self.write("Prefs.xml", "<a><autosaveIntervalDays>7</autosaveIntervalDays><langFolderName>German</langFolderName><uiScale>2</uiScale></a>")
        rimtest.pin_prefs(prefs)
        text = prefs.read_text(encoding="utf-8")
        self.assertIn("<autosaveIntervalDays>1</autosaveIntervalDays>", text)
        self.assertIn("<langFolderName>English</langFolderName>", text)
        self.assertIn("<uiScale>2</uiScale>", text)


class ResultTest(TempCase):
    def code(self, report, problems=()):
        with contextlib.redirect_stdout(io.StringIO()):
            return rimtest.result_code(report, list(problems))

    def test_exit_codes(self):
        self.assertEqual(self.code({"status": "complete", "overallPass": True}), 0)
        self.assertEqual(self.code({"status": "complete", "overallPass": False}), 1)
        self.assertEqual(self.code({"status": "complete", "overallPass": True}, ["user save modified"]), 1)
        self.assertEqual(self.code({"status": "interrupted", "overallPass": False}), 2)
        self.assertEqual(self.code({"status": "refused"}), 3)

    def test_short_limit_sends_no_game_deadline(self):
        self.assertEqual(rimtest.game_deadline(time.monotonic() + 20), 0)
        self.assertEqual(rimtest.game_deadline(time.monotonic() + 600, graceful=False), 0)
        self.assertAlmostEqual(rimtest.game_deadline(time.monotonic() + 600) / 1000, time.time() + 600 - rimtest.DEADLINE_GRACE, delta=2)

    def test_unknown_batch_is_refused_only_for_the_listed_build(self):
        config = make_config(self.root)
        self.write("evidence/batches.json", json.dumps({"developerHash": "abc", "runAll": [], "batches": [{"id": "known", "cases": []}]}))
        rimtest.check_batch(config, "known", {"developerHash": "abc"})
        rimtest.check_batch(config, "run-all", {"developerHash": "abc"})
        rimtest.check_batch(config, "typo", {"developerHash": "another build"})
        with self.assertRaises(RuntimeError):
            rimtest.check_batch(config, "typo", {"developerHash": "abc"})


class LatestTest(TempCase):
    def latest(self, batch=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = rimtest.latest(make_config(self.root), batch)
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


if __name__ == "__main__":
    unittest.main()
