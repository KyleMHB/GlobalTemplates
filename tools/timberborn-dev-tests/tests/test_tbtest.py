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
        state = self.write("work/state.json", json.dumps({"runId": "run-1", "prefs": {"a": [4, 1]}}))
        self.write(f"Mods/{tbtest.RUNNER_FOLDER}/request.json")
        prefs = FakePrefs()
        message = tbtest.recover(state, self.root / "Mods", prefs)
        self.assertEqual(prefs.restored, [{"a": [4, 1]}])
        self.assertFalse(state.exists())
        self.assertFalse((self.root / "Mods" / tbtest.RUNNER_FOLDER).exists())
        self.assertIn("run-1", message)

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

    def test_launch_goes_through_steam_with_the_log_in_the_run_folder(self):
        command = tbtest.launch_command("C:/Steam/steam.exe", self.root / "run/Player.log")
        self.assertEqual(command, ["C:/Steam/steam.exe", "-applaunch", "1062090", "-skipModManager", "-logFile", str(self.root / "run/Player.log")])

    def test_install_writes_only_the_runner_manifest_and_request(self):
        dll = self.write("build/TimberbornDevTests.dll")
        self.write(f"Mods/{tbtest.RUNNER_FOLDER}/stale.dll")
        folder = tbtest.install_runner([dll], self.root / "Mods", {"RunId": "r"})
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["TimberbornDevTests.dll", "manifest.json", "request.json"])
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["Id"], tbtest.RUNNER_ID)
        self.assertEqual(json.loads((folder / "request.json").read_text(encoding="utf-8")), {"RunId": "r"})


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

    def test_a_batch_that_ended_early_is_named(self):
        report = {"status": "complete", "overallPass": False, "cases": [],
                  "batches": [{"Id": "mod", "Status": "ended-early", "Reason": "exception in case code: SetupException: no spot"}]}
        text = tbtest.write_summary(self.root, "run-1", report, {"problems": []})
        self.assertIn("  BATCH mod ended-early: exception in case code: SetupException: no spot", text)


if __name__ == "__main__":
    unittest.main()
