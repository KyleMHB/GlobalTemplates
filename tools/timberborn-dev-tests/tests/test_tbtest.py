"""Timberborn adapter logic that needs no game, Steam or registry: pref names, mod discovery, isolation plans, the request,
the launch command, the runner install and the summary."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tbtest


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

    def manifest(self, relative, mod_id, required=()):
        data = {"Name": mod_id, "Id": mod_id, "Version": "1.0", "MinimumGameVersion": "1.0"}
        if required:
            data["RequiredMods"] = [{"Id": r, "MinimumVersion": "1.0"} for r in required]
        return self.write(relative, json.dumps(data))


class PrefNameTest(unittest.TestCase):
    def test_unity_suffix_is_the_djb2_xor_hash(self):
        # (5381 * 33) ^ ord("a") = 177573 ^ 97 = 177604, worked by hand.
        self.assertEqual(tbtest.unity_pref_name("a"), "a_h177604")

    def test_disable_key_names_source_folder_and_id(self):
        mod = tbtest.InstalledMod("Steam Workshop", "3284904751", "Harmony")
        self.assertEqual(mod.enabled_key, "ModEnabled.Steam Workshop.3284904751.Harmony")


class ModDiscoveryTest(TempCase):
    def test_picks_the_highest_version_folder_not_above_the_game_case_insensitively(self):
        folder = self.root / "Mod"
        self.manifest("Mod/version-1.0/manifest.json", "Old")
        self.manifest("Mod/Version-1.1/manifest.json", "Current")
        self.manifest("Mod/version-9.0/manifest.json", "Future")
        self.assertEqual(tbtest.manifest_id(folder, (1, 1, 2, 8)), "Current")

    def test_no_eligible_version_means_the_game_skips_the_mod(self):
        self.manifest("Mod/version-9.0/manifest.json", "Future")
        self.assertIsNone(tbtest.manifest_id(self.root / "Mod", (1, 1, 2, 8)))

    def test_lenient_manifest_still_yields_its_id(self):
        self.write("Mod/manifest.json", '{ "Id": "Loose.Mod", "Name": "x", }')
        self.assertEqual(tbtest.manifest_id(self.root / "Mod", (1, 1, 2, 8)), "Loose.Mod")

    def test_required_mods_come_from_the_version_folder_the_game_picks(self):
        self.manifest("workshop/1/manifest.json", "Stairs", required=["Old.Dep"])
        self.manifest("workshop/1/VERSION-1.1/manifest.json", "Stairs", required=["Materials"])
        found = tbtest.installed_mods(self.root / "workshop", self.root / "Mods", (1, 1, 2, 8))
        self.assertEqual(found[0].required, ("Materials",))

    def test_bare_version_folder_counts_as_the_current_game(self):
        # ModRepository reads "version-" with no number as the running game version, so it beats version-1.0.
        self.manifest("Mod/version-1.0/manifest.json", "Old")
        self.manifest("Mod/version-/manifest.json", "Current")
        self.assertEqual(tbtest.manifest_id(self.root / "Mod", (1, 1, 2, 8)), "Current")

    def test_trailing_comma_keeps_the_required_mods(self):
        self.write("workshop/1/manifest.json", '{ "Id": "Loose", "RequiredMods": [ { "Id": "Harmony", }, ], }')
        found = tbtest.installed_mods(self.root / "workshop", self.root / "Mods", (1, 1, 2, 8))
        self.assertEqual(found, [tbtest.InstalledMod("Steam Workshop", "1", "Loose", ("Harmony",))])

    def test_lists_workshop_and_local_mods_except_the_runner(self):
        self.manifest("workshop/111/manifest.json", "Harmony")
        self.manifest("Mods/Local/manifest.json", "My.Local")
        self.manifest(f"Mods/{tbtest.RUNNER_FOLDER}/manifest.json", tbtest.RUNNER_ID)
        # A mod's dev folder carries the runner's Id whatever its name, and isolation must never disable it.
        self.manifest("Mods/My.LocalDevTests/manifest.json", tbtest.RUNNER_ID)
        self.write("Mods/NotAMod/readme.txt")
        found = tbtest.installed_mods(self.root / "workshop", self.root / "Mods", (1, 1, 2, 8))
        self.assertEqual(found, [tbtest.InstalledMod("Steam Workshop", "111", "Harmony"), tbtest.InstalledMod("Local", "Local", "My.Local")])


def mod(source, folder, mod_id, *required):
    return tbtest.InstalledMod(source, folder, mod_id, tuple(required))


class ModSetTest(unittest.TestCase):
    def test_set_is_the_mod_plus_its_transitive_required_mods(self):
        installed = [mod("Steam Workshop", "1", "Stairs", "Materials"), mod("Steam Workshop", "2", "Materials", "Harmony"),
                     mod("Steam Workshop", "3", "Harmony"), mod("Steam Workshop", "4", "Other", "Harmony")]
        selected, problems = tbtest.select_mods("Stairs", installed)
        self.assertEqual(problems, [])
        self.assertEqual([m.folder for m in selected], ["1", "2", "3"])

    def test_one_copy_per_id_and_the_local_copy_wins(self):
        # The game loads a Local and a Workshop copy of the same Id side by side, so only one may stay enabled.
        workshop, local = mod("Steam Workshop", "9", "My.Mod"), mod("Local", "MyMod", "My.Mod")
        selected, _ = tbtest.select_mods("My.Mod", [workshop, local])
        self.assertEqual(selected, [local])

    def test_ids_match_exactly_as_the_game_compares_them(self):
        selected, problems = tbtest.select_mods("my.mod", [mod("Local", "MyMod", "My.Mod")])
        self.assertEqual(selected, [])
        self.assertEqual(problems, ["the mod under test (my.mod) is not installed in Mods or the Workshop"])

    def test_missing_dependency_names_who_requires_it(self):
        _, problems = tbtest.select_mods("Stairs", [mod("Local", "Stairs", "Stairs", "Materials")])
        self.assertEqual(problems, ["Stairs requires Materials, which is not installed"])

    def test_dependency_cycle_ends(self):
        installed = [mod("Local", "A", "A", "B"), mod("Local", "B", "B", "A")]
        selected, problems = tbtest.select_mods("A", installed)
        self.assertEqual(([m.mod_id for m in selected], problems), (["A", "B"], []))


class IsolationPlanTest(unittest.TestCase):
    def test_enables_the_set_and_disables_everything_else(self):
        keep, other = mod("Local", "MyMod", "My.Mod"), mod("Steam Workshop", "9", "My.Mod")
        values = tbtest.disable_values([keep, other], keep=[keep])
        self.assertEqual(values, {tbtest.unity_pref_name(keep.enabled_key): [4, 1], tbtest.unity_pref_name(other.enabled_key): [4, 0]})

    def test_disables_every_mod_through_its_hashed_value(self):
        mods = [tbtest.InstalledMod("Local", "Local", "My.Local")]
        # [REG_DWORD, 0]: the same [type, data] shape as a snapshot value, so restore_plan can compare them.
        self.assertEqual(tbtest.disable_values(mods), {tbtest.unity_pref_name("ModEnabled.Local.Local.My.Local"): [4, 0]})

    def test_runner_priority_puts_its_starter_before_every_mod(self):
        # ModSorter orders by OriginalIndex - ModPriority, so only a priority above any index guarantees the runner's starter
        # runs first and sees the mod's startup errors.
        values = tbtest.dev_folder_keys(tbtest.RUNNER_FOLDER)
        self.assertEqual(values["ModEnabled.Local.TimberbornDevTests.TimberbornDevTests"], 1)
        self.assertGreater(values["ModPriority.Local.TimberbornDevTests.TimberbornDevTests"], 10000)

    def test_the_dev_folder_is_named_after_the_mod_and_kept_enabled_first(self):
        folder = tbtest.dev_folder_name("Author.My Mod")
        self.assertEqual(folder, "Author.MyModDevTests")
        self.assertEqual(tbtest.dev_folder_name(None), tbtest.RUNNER_FOLDER)
        self.assertEqual(tbtest.dev_folder_keys(folder),
                         {"ModEnabled.Local.Author.MyModDevTests.TimberbornDevTests": 1,
                          "ModPriority.Local.Author.MyModDevTests.TimberbornDevTests": tbtest.RUNNER_PRIORITY})

    def test_restore_plan_returns_the_key_to_the_snapshot_exactly(self):
        snapshot = {"kept": [4, 1], "changed": [4, 1], "deleted": [3, {"b64": "AA=="}]}
        current = {"kept": [4, 1], "changed": [4, 0], "added": [4, 0]}
        removals, writes = tbtest.restore_plan(snapshot, current)
        self.assertEqual(removals, ["added"])
        self.assertEqual(writes, {"changed": [4, 1], "deleted": [3, {"b64": "AA=="}]})


class ConfigTest(TempCase):
    def test_devtests_json_names_the_mod_under_test(self):
        path = self.write("MyMod/DevTests/devtests.json", json.dumps({"name": "My Mod", "modId": "My.Mod"}))
        config = tbtest.load_config(path)
        self.assertEqual((config.name, config.mod_id, config.root), ("My Mod", "My.Mod", (self.root / "MyMod").resolve()))
        self.assertIsNone(config.dev_build)

    def test_dev_build_is_relative_to_the_mod_root(self):
        path = self.write("MyMod/DevTests/devtests.json", json.dumps({"modId": "My.Mod", "devBuild": "DevTests/bin/MyMod.DevTests.dll"}))
        self.assertEqual(tbtest.load_config(path).dev_build, (self.root / "MyMod/DevTests/bin/MyMod.DevTests.dll").resolve())

    def test_preflight_refuses_a_missing_dev_build_a_dev_dll_in_the_production_folder_and_a_foreign_dev_folder(self):
        path = self.write("MyMod/DevTests/devtests.json", json.dumps({"modId": "My.Mod", "devBuild": "bin/MyMod.DevTests.dll"}))
        config = tbtest.load_config(path)
        self.write("Mods/MyMod/MyMod.DevTests.dll")
        self.manifest("Mods/My.ModDevTests/manifest.json", "Someone.Else")
        problems = tbtest.dev_problems(config, self.root / "Mods/MyMod", self.root / "Mods/My.ModDevTests")
        self.assertEqual(len(problems), 3)
        self.assertIn("build DevTests first", problems[0])
        self.assertIn("MyMod.DevTests.dll", problems[1])
        self.assertIn("My.ModDevTests", problems[2])

    def test_preflight_passes_a_built_dev_dll_and_a_clean_production_folder(self):
        path = self.write("MyMod/DevTests/devtests.json", json.dumps({"modId": "My.Mod", "devBuild": "bin/MyMod.DevTests.dll"}))
        self.write("MyMod/bin/MyMod.DevTests.dll")
        self.write("Mods/MyMod/MyMod.dll", "production")
        self.manifest("Mods/My.ModDevTests/manifest.json", tbtest.RUNNER_ID)
        config = tbtest.load_config(path)
        self.assertEqual(tbtest.dev_problems(config, self.root / "Mods/MyMod", self.root / "Mods/My.ModDevTests"), [])

    def test_devtests_json_without_mod_id_is_refused(self):
        path = self.write("MyMod/DevTests/devtests.json", json.dumps({"name": "My Mod"}))
        with self.assertRaisesRegex(ValueError, "modId"):
            tbtest.load_config(path)


class FakePrefs:
    def __init__(self):
        self.restored = []

    def restore(self, snapshot):
        self.restored.append(snapshot)
        return len(snapshot)


class RecoveryTest(TempCase):
    def test_state_left_by_a_killed_run_is_restored_and_cleared(self):
        # A state file from before dev folders were recorded means the runner folder.
        state = self.write("work/state.json", json.dumps({"runId": "run-1", "prefs": {"a": [4, 1]}}))
        self.manifest(f"Mods/{tbtest.RUNNER_FOLDER}/manifest.json", tbtest.RUNNER_ID)
        prefs = FakePrefs()
        message = tbtest.recover(state, self.root / "Mods", prefs)
        self.assertEqual(prefs.restored, [{"a": [4, 1]}])
        self.assertFalse(state.exists())
        self.assertFalse((self.root / "Mods" / tbtest.RUNNER_FOLDER).exists())
        self.assertIn("run-1", message)

    def test_the_dev_folder_the_run_recorded_is_removed(self):
        state = self.write("work/state.json", json.dumps({"runId": "run-1", "prefs": {}, "devFolder": "My.ModDevTests"}))
        self.manifest("Mods/My.ModDevTests/manifest.json", tbtest.RUNNER_ID)
        self.write("Mods/My.ModDevTests/MyMod.DevTests.dll")
        tbtest.recover(state, self.root / "Mods", FakePrefs())
        self.assertFalse((self.root / "Mods/My.ModDevTests").exists())

    def test_prefs_left_changed_names_each_value_the_restore_missed(self):
        self.assertEqual(tbtest.prefs_left_changed({"a": [4, 1], "b": [4, 0]}, {"a": [4, 1], "b": [4, 1], "c": [4, 0]}), ["b", "c"])
        self.assertEqual(tbtest.prefs_left_changed({"a": [4, 1]}, {"a": [4, 1]}), [])

    def test_nothing_left_behind_means_nothing_to_restore(self):
        prefs = FakePrefs()
        self.assertIsNone(tbtest.recover(self.root / "work/state.json", self.root / "Mods", prefs))
        self.assertEqual(prefs.restored, [])


class RequestAndLaunchTest(TempCase):
    def test_request_carries_the_batch_map_and_deadline(self):
        request = tbtest.build_request("run-1", self.root / "run-1", "smoke", "_Mini", speed=30, hours=2, deadline_ms=123, probe_prefs={"k": 0})
        self.assertEqual(request["Batch"], "smoke")
        self.assertEqual(request["Map"], "_Mini")
        self.assertEqual(request["DeadlineUtcMs"], 123)
        self.assertEqual(request["RunDir"], str(self.root / "run-1"))
        self.assertEqual(request["ProbePrefs"], {"k": 0})
        self.assertTrue(request["SettlementName"])

    def test_request_names_the_mod_under_test_and_keep_open(self):
        request = tbtest.build_request("run-1", self.root, "smoke", None, 30, 2, 0, mod_name="My Mod",
                                       mod_assemblies=["MyMod"], keep_open=True)
        self.assertEqual((request["ModName"], request["ModAssemblies"], request["KeepOpen"]), ("My Mod", ["MyMod"], True))

    def test_mod_assemblies_are_every_dll_the_game_would_load_from_the_mod_folder(self):
        self.write("Mods/MyMod/version-1.1/MyMod.dll")
        self.write("Mods/MyMod/version-1.1/Libs/Helper.dll")
        self.write("Mods/MyMod/manifest.json")
        self.assertEqual(tbtest.mod_assemblies(self.root / "Mods/MyMod"), ["Helper", "MyMod"])

    def test_launch_goes_through_steam_with_the_log_in_the_run_folder(self):
        command = tbtest.launch_command("C:/Steam/steam.exe", self.root / "run/Player.log")
        self.assertEqual(command, ["C:/Steam/steam.exe", "-applaunch", "1062090", "-skipModManager", "-logFile", str(self.root / "run/Player.log")])

    def test_install_writes_only_the_runner_manifest_and_request(self):
        dll = self.write("build/TimberbornDevTests.dll")
        self.manifest(f"Mods/{tbtest.RUNNER_FOLDER}/manifest.json", tbtest.RUNNER_ID)
        self.write(f"Mods/{tbtest.RUNNER_FOLDER}/stale.dll")
        folder = tbtest.install_runner([dll], self.root / "Mods", {"RunId": "r"})
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["TimberbornDevTests.dll", "manifest.json", "request.json"])
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["Id"], tbtest.RUNNER_ID)
        self.assertEqual(json.loads((folder / "request.json").read_text(encoding="utf-8")), {"RunId": "r"})

    def test_install_puts_the_runner_and_the_dev_dll_in_the_mods_dev_folder_and_leaves_the_mod_alone(self):
        runner = self.write("build/TimberbornDevTests.dll")
        dev = self.write("MyMod/DevTests/bin/MyMod.DevTests.dll")
        self.write("MyMod/DevTests/bin/TimberbornDevTests.dll", "an old copy beside the dev build")
        production = self.write("Mods/MyMod/MyMod.dll", "production")
        folder = tbtest.install_runner([runner, dev], self.root / "Mods", {"RunId": "r"}, folder="My.ModDevTests")
        self.assertEqual(folder, self.root / "Mods/My.ModDevTests")
        self.assertEqual(sorted(p.name for p in folder.iterdir()),
                         ["MyMod.DevTests.dll", "TimberbornDevTests.dll", "manifest.json", "request.json"])
        self.assertEqual((folder / "TimberbornDevTests.dll").read_text(encoding="utf-8"), "x")
        self.assertEqual(sorted(p.name for p in production.parent.iterdir()), ["MyMod.dll"])

    def test_install_never_replaces_a_folder_that_is_not_the_runners(self):
        self.manifest("Mods/My.ModDevTests/manifest.json", "Someone.Else")
        with self.assertRaisesRegex(RuntimeError, "not a runner folder"):
            tbtest.install_runner([self.write("build/TimberbornDevTests.dll")], self.root / "Mods", {}, folder="My.ModDevTests")
        self.assertTrue((self.root / "Mods/My.ModDevTests/manifest.json").is_file())

    def test_request_points_relative_fixtures_at_the_mods_fixture_folder(self):
        request = tbtest.build_request("run-1", self.root, "smoke", None, 30, 2, 0, fixture_dir=self.root / "DevTests/Fixtures")
        self.assertEqual(request["FixtureDir"], str(self.root / "DevTests/Fixtures"))
        self.assertIsNone(tbtest.build_request("run-1", self.root, "smoke", None, 30, 2, 0)["FixtureDir"])


class ReleaseCheckTest(TempCase):
    def test_a_clean_package_has_no_problems(self):
        self.write("Mod/version-1.1/MyMod.dll", "plain production code")
        self.write("Mod/manifest.json", json.dumps({"Id": "My.Mod"}))
        self.assertEqual(tbtest.release_problems(self.root / "Mod"), [])

    def test_developer_dlls_runner_references_and_runner_files_are_flagged(self):
        self.write("Mod/MyMod.DevTests.dll")
        # A production DLL built against the runner carries its assembly name as a reference.
        self.write("Mod/MyMod.dll", "...TimberbornDevTests\0...")
        self.write("Mod/request.json", "{}")
        self.write("Mod/Runner/manifest.json", json.dumps({"Id": tbtest.RUNNER_ID}))
        problems = tbtest.release_problems(self.root / "Mod")
        self.assertEqual(problems, [
            f"DevTests assembly present: {self.root / 'Mod/MyMod.DevTests.dll'}",
            f"runner reference found in {self.root / 'Mod/MyMod.dll'}",
            f"runner request present: {self.root / 'Mod/request.json'}",
            f"runner manifest present: {self.root / 'Mod/Runner/manifest.json'}",
        ])


class PerfRuleTest(TempCase):
    """release-check against a fabricated package and run folders. Runs are ordered by their files' mtime, as real ones are."""

    def setUp(self):
        super().setUp()
        self.stamp = 1000
        self.package = self.root / "Package"
        self.write("Package/version-1.1/manifest.json", json.dumps({"Id": "My.Mod"}))
        self.write("Package/version-1.1/MyMod.dll", "build 1")
        self.batches = [{"id": "speed", "diagnostic": False, "cases": ["perf.place-many", "speed.correct"]},
                        {"id": "diagnostic", "diagnostic": True, "cases": ["perf.runner-only"]}]
        self.dev_build = self.write("MyMod/DevTests/bin/MyMod.DevTests.dll", "dev build 1")
        self.config = tbtest.Config("My Mod", "My.Mod", self.root / "MyMod", self.dev_build)

    def fake_run(self, name, cases, mod_id="My.Mod", dlls=None, batches=None, dev_hash=None):
        """A run folder as run() leaves it: launcher.json (mod under test, the measured DLLs and the DevTests build),
        report.json, batches.json."""
        import os
        folder = self.root / "runs" / name
        build = tbtest.mod_build(self.package) if dlls is None else dlls
        dev_hash = tbtest.sha256(self.dev_build) if dev_hash is None else dev_hash
        files = {"launcher.json": {"runId": name, "modUnderTest": mod_id, "modBuild": build, "devBuildHash": dev_hash},
                 "report.json": {"cases": [{"Id": i, "Result": r, "Reason": None if r == "pass" else "too slow"} for i, r in cases]},
                 "batches.json": {"modName": "My Mod", "batches": self.batches if batches is None else batches}}
        for file, data in files.items():
            path = self.write(f"runs/{name}/{file}", json.dumps(data))
            os.utime(path, (self.stamp, self.stamp))
        self.stamp += 10
        return folder

    def check(self, config="default"):
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = tbtest.release_check(self.package, self.config if config == "default" else config, None,
                                        evidence_root=self.root / "runs")
        return code, out.getvalue().splitlines()

    def test_a_perf_case_added_since_the_last_run_fails(self):
        # The newest run's list predates the current DevTests build, which may define perf cases no run has seen.
        self.fake_run("run-1", [("perf.place-many", "pass")])
        self.write("MyMod/DevTests/bin/MyMod.DevTests.dll", "dev build 2")
        code, lines = self.check()
        self.assertEqual(code, 1)
        self.assertTrue([l for l in lines if l.startswith("FAIL: no batch list from the current DevTests build of My.Mod")])

    def test_without_config_the_perf_rule_cannot_see_the_devtests_build(self):
        self.fake_run("run-1", [("perf.place-many", "pass")])
        code, lines = self.check(config=None)
        self.assertEqual(code, 1)
        self.assertTrue([l for l in lines if l.startswith("FAIL: no DevTests build to read My.Mod's perf.* cases from")])
        self.assertIn(f"PASS: no developer test runner in {self.package}", lines)

    def test_a_not_selected_case_record_is_not_a_measurement(self):
        self.fake_run("run-1", [("perf.place-many", "pass")])
        newer = self.fake_run("run-2", [("perf.place-many", "skip")])
        report = {"cases": [{"Id": "perf.place-many", "Result": "skip", "CoverageReason": "not-selected"}]}
        (newer / "report.json").write_text(json.dumps(report), encoding="utf-8")
        import os
        os.utime(newer / "report.json", (self.stamp, self.stamp))
        code, lines = self.check()
        self.assertEqual(code, 0)
        self.assertIn("PASS: perf perf.place-many in run run-1", lines)

    def test_a_passing_perf_case_on_the_packaged_dll_passes(self):
        self.fake_run("run-1", [("perf.place-many", "pass"), ("speed.correct", "pass")])
        code, lines = self.check()
        self.assertEqual(code, 0)
        self.assertIn("PASS: perf perf.place-many in run run-1", lines)
        self.assertFalse([l for l in lines if l.startswith(("FAIL", "WARN"))])

    def test_no_run_of_a_perf_case_fails(self):
        self.fake_run("run-1", [("speed.correct", "pass")])
        code, lines = self.check()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: no run of perf.place-many; run speed", lines)

    def test_the_newest_run_of_a_case_decides(self):
        self.fake_run("run-1", [("perf.place-many", "pass")])
        self.fake_run("run-2", [("perf.place-many", "fail")])
        code, lines = self.check()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: perf.place-many in run run-2 did not pass (fail): too slow", lines)

    def test_a_skipped_perf_case_is_not_a_pass(self):
        self.fake_run("run-1", [("perf.place-many", "skip")])
        self.assertEqual(self.check()[0], 1)

    def test_a_run_of_a_different_build_fails(self):
        self.fake_run("run-1", [("perf.place-many", "pass")])
        self.write("Package/version-1.1/MyMod.dll", "build 2")
        code, lines = self.check()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: newest perf.place-many run run-1 measured a different build of My.Mod; run speed", lines)

    def test_a_devtests_dll_beside_the_mod_during_the_run_still_matches_the_clean_package(self):
        build = tbtest.mod_build(self.package)
        self.write("Package/MyMod.DevTests.dll", "dev")
        self.assertEqual(tbtest.mod_build(self.package), build)

    def test_another_mods_newer_run_is_ignored(self):
        self.fake_run("run-1", [("perf.place-many", "pass")])
        self.fake_run("run-2", [("perf.place-many", "fail")], mod_id="Other.Mod", dlls={"hash": "other", "dlls": {}})
        code, lines = self.check()
        self.assertEqual(code, 0)
        self.assertIn("PASS: perf perf.place-many in run run-1", lines)

    def test_no_perf_cases_warns_without_failing(self):
        self.fake_run("run-1", [("speed.correct", "pass")], batches=[{"id": "speed", "diagnostic": False, "cases": ["speed.correct"]}])
        code, lines = self.check()
        self.assertEqual(code, 0)
        self.assertTrue([l for l in lines if l.startswith("WARN: no perf.* cases")])

    def test_no_batch_list_fails(self):
        code, lines = self.check()
        self.assertEqual(code, 1)
        self.assertTrue([l for l in lines if l.startswith("FAIL: no batch list from the current DevTests build of My.Mod")])

    def test_a_dev_dll_in_the_package_fails_even_with_perf_passing(self):
        self.fake_run("run-1", [("perf.place-many", "pass")])
        self.write("Package/MyMod.DevTests.dll", "dev")
        code, lines = self.check()
        self.assertEqual(code, 1)
        self.assertIn(f"FAIL: DevTests assembly present: {self.package / 'MyMod.DevTests.dll'}", lines)


class ListTest(TempCase):
    def batch_list(self, run, mod_id, batches, mod_name="renamed", dev_hash="dev-1"):
        # Matched by launcher.json's modUnderTest, as release-check does, so a renamed mod keeps its runs.
        self.write(f"runs/{run}/report.json", "{}")
        self.write(f"runs/{run}/launcher.json", json.dumps({"modUnderTest": mod_id, "devBuildHash": dev_hash}))
        return self.write(f"runs/{run}/batches.json", json.dumps({"modName": mod_name, "runAll": [], "batches": batches}))

    def listing(self, mod_id, dev_hash="dev-1"):
        import contextlib, io, os
        for i, folder in enumerate(sorted((self.root / "runs").iterdir()) if (self.root / "runs").is_dir() else []):
            os.utime(folder / "report.json", (1000 + i, 1000 + i))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = tbtest.list_batches(self.root / "runs", mod_id, dev_hash)
        return code, out.getvalue().splitlines()

    def test_lists_the_newest_batch_list_for_the_mod(self):
        self.batch_list("run-1", "My.Mod", [{"id": "old", "diagnostic": False, "cases": ["a"]}])
        self.batch_list("run-2", "My.Mod", [{"id": "smoke", "diagnostic": False, "cases": ["smoke.new-game"]},
                                            {"id": "diagnostic", "diagnostic": True, "cases": ["x", "y", "z"]}])
        self.batch_list("run-3", "Other.Mod", [{"id": "other", "diagnostic": False, "cases": []}], mod_name="renamed")
        code, lines = self.listing("My.Mod")
        self.assertEqual(code, 0)
        self.assertEqual(lines[1:], ["smoke: 1 cases", "diagnostic: 3 cases (runner self-check)"])
        self.assertIn("run-2", lines[0])

    def test_a_list_from_another_devtests_build_says_so(self):
        self.batch_list("run-1", "My.Mod", [{"id": "smoke", "diagnostic": False, "cases": ["smoke.new-game"]}])
        code, lines = self.listing("My.Mod", dev_hash="dev-2")
        self.assertEqual(code, 0)
        self.assertIn("Note: this list is from a different DevTests build than the one in the working tree.", lines)

    def test_no_list_yet_says_when_one_appears(self):
        code, lines = self.listing("My.Mod")
        self.assertEqual(code, 1)
        self.assertIn("No batch list yet", "\n".join(lines))


class SummaryTest(TempCase):
    def test_summary_lists_status_cases_and_problems(self):
        report = {"status": "complete", "overallPass": True, "errorCount": 0, "exceptionCount": 0,
                  "cases": [{"Id": "smoke.new-game", "Result": "pass", "Observed": {"gameHours": 2.1}}]}
        text = tbtest.write_summary(self.root, "run-1", report, {"problems": ["player data changed"]})
        self.assertIn("FAIL", text.splitlines()[0])
        self.assertIn("PASS smoke.new-game", text)
        self.assertIn("PROBLEM: player data changed", text)
        self.assertEqual((self.root / "summary.txt").read_text(encoding="utf-8"), text)

    def test_summary_without_a_report_says_so(self):
        text = tbtest.write_summary(self.root, "run-1", None, {"problems": []})
        self.assertIn("no report.json", text)

    # Field names below are copied from Harness/Report.cs (CaseRecord, BatchRecord).
    def diagnostic_report(self, gap_result="skip"):
        return {"status": "complete", "overallPass": gap_result == "skip", "errorCount": 1, "exceptionCount": 0,
                "batches": [{"Id": "diagnostic", "Status": "complete", "Reason": None}],
                "cases": [
                    {"Id": "diag.pass", "Batch": "diagnostic", "Result": "pass", "Reason": "", "Diagnostic": True, "ExpectedResult": "pass",
                     "Steps": ["  PASS  the new settlement starts with beavers"], "LoggedErrors": 0, "Evidence": [], "FixedGaps": 0},
                    {"Id": "diag.fail", "Batch": "diagnostic", "Result": "fail", "Reason": "intentional: 1 is 2", "Diagnostic": True,
                     "ExpectedResult": "fail", "Steps": ["  PASS  a step that holds", ">>FAIL  intentional: 1 is 2"], "LoggedErrors": 1,
                     "Evidence": ["logged error: Error: Intentional diagnostic error"], "FixedGaps": 0},
                    {"Id": "diag.known-gap", "Batch": "diagnostic", "Result": gap_result, "CoverageReason": "known-gap",
                     "Reason": "known gap, something: intentional", "Diagnostic": True, "ExpectedResult": "skip",
                     "Steps": ["  GAP   something: intentional"], "LoggedErrors": 0, "Evidence": [], "FixedGaps": 0},
                ]}

    def test_diagnostic_cases_show_their_intended_result_and_the_verdict_comes_from_the_report(self):
        text = tbtest.write_summary(self.root, "run-1", self.diagnostic_report(), {"problems": []})
        self.assertIn("PASS", text.splitlines()[0])
        self.assertIn("  FAIL diag.fail (intended fail): intentional: 1 is 2", text)
        self.assertIn("  SKIP [known-gap] diag.known-gap (intended skip): known gap, something: intentional", text)
        self.assertIn("  diagnostic: 3 of 3 reported as intended", text)

    def test_a_diagnostic_case_reported_otherwise_is_marked(self):
        text = tbtest.write_summary(self.root, "run-1", self.diagnostic_report(gap_result="pass"), {"problems": []})
        self.assertIn("FAIL", text.splitlines()[0])
        self.assertIn("  PASS diag.known-gap (intended skip, NOT AS INTENDED)", text)
        self.assertIn("  diagnostic: 2 of 3 reported as intended", text)

    def test_a_failing_case_prints_its_steps_and_logged_errors(self):
        text = tbtest.write_summary(self.root, "run-1", self.diagnostic_report(), {"problems": []})
        self.assertIn("      >>FAIL  intentional: 1 is 2", text)
        self.assertIn("    1 logged error(s): logged error: Error: Intentional diagnostic error", text)
        self.assertNotIn("the new settlement starts with beavers", text)

    def test_gameplay_skips_are_listed_as_not_covered_and_a_held_gap_is_flagged(self):
        report = {"status": "complete", "overallPass": True, "batches": [], "cases": [
            {"Id": "mod.gap", "Batch": "mod", "Result": "skip", "CoverageReason": "known-gap", "Reason": "known gap, x: y", "Diagnostic": False},
            {"Id": "mod.fixed", "Batch": "mod", "Result": "pass", "Reason": "", "Diagnostic": False, "FixedGaps": 1},
        ]}
        text = tbtest.write_summary(self.root, "run-1", report, {"problems": []})
        self.assertIn("  Not covered: 1 skipped case(s)\n    SKIP [known-gap] mod/mod.gap: known gap, x: y", text)
        self.assertIn("  KNOWN GAP NOW HOLDS in mod/mod.fixed: 1 step(s) marked FIXED; make each a Step", text)

    # Field names below are copied from Harness/Report.cs (RunReport.Finish); the wording follows RimWorld's Report.cs.
    def startup_report(self, startup, fail_on_mod_errors, mod_errors=0):
        return {"status": "complete", "overallPass": not (fail_on_mod_errors and (startup or mod_errors)), "errorCount": len(startup) + mod_errors,
                "exceptionCount": 0, "batches": [], "cases": [{"Id": "smoke.new-game", "Batch": "smoke", "Result": "pass"}],
                "errorMarker": "My Mod", "startupModErrors": startup, "failOnModErrors": fail_on_mod_errors, "modErrors": mod_errors, "loggedErrors": mod_errors}

    def test_startup_errors_naming_the_mod_are_listed_and_counted_under_fail_on_mod_errors(self):
        errors = [f"Error: boom {i} in MyMod.Starter" for i in range(6)]
        text = tbtest.write_summary(self.root, "run-1", self.startup_report(errors, True), {"problems": []})
        self.assertIn("FAIL", text.splitlines()[0])
        self.assertIn("  Startup: 6 error(s) naming 'My Mod' while the game loaded (FAILS the run)", text)
        self.assertIn("    STARTUP ERROR Error: boom 4 in MyMod.Starter", text)
        self.assertNotIn("boom 5", text)

    def test_startup_errors_without_fail_on_mod_errors_do_not_count(self):
        text = tbtest.write_summary(self.root, "run-1", self.startup_report(["Error: boom"], False), {"problems": []})
        self.assertIn("PASS", text.splitlines()[0])
        self.assertIn("  Startup: 1 error(s) naming 'My Mod' while the game loaded (not counted against the result)", text)

    def test_a_clean_startup_says_so_and_run_errors_naming_the_mod_are_counted(self):
        text = tbtest.write_summary(self.root, "run-1", self.startup_report([], True, mod_errors=2), {"problems": []})
        self.assertIn("  Startup: no errors naming 'My Mod' while the game loaded", text)
        self.assertIn("  Logged errors: 2 during the run, 2 naming 'My Mod' (FAILS the run)", text)

    def test_a_run_without_a_mod_under_test_has_no_startup_check(self):
        report = self.startup_report([], False)
        report["errorMarker"] = None
        text = tbtest.write_summary(self.root, "run-1", report, {"problems": []})
        self.assertIn("  Startup: not checked; no mod under test (run with --config)", text)

    def test_a_batch_that_ended_early_is_named(self):
        report = {"status": "complete", "overallPass": False, "cases": [],
                  "batches": [{"Id": "mod", "Status": "ended-early", "Reason": "exception in case code: SetupException: no spot"}]}
        text = tbtest.write_summary(self.root, "run-1", report, {"problems": []})
        self.assertIn("  BATCH mod ended-early: exception in case code: SetupException: no spot", text)


if __name__ == "__main__":
    unittest.main()
