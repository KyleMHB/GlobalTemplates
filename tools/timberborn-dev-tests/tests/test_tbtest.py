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

    def manifest(self, relative, mod_id):
        return self.write(relative, json.dumps({"Name": mod_id, "Id": mod_id, "Version": "1.0", "MinimumGameVersion": "1.0"}))


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

    def test_lists_workshop_and_local_mods_except_the_runner(self):
        self.manifest("workshop/111/manifest.json", "Harmony")
        self.manifest("Mods/Local/manifest.json", "My.Local")
        self.manifest(f"Mods/{tbtest.RUNNER_FOLDER}/manifest.json", tbtest.RUNNER_ID)
        self.write("Mods/NotAMod/readme.txt")
        found = tbtest.installed_mods(self.root / "workshop", self.root / "Mods", (1, 1, 2, 8))
        self.assertEqual(found, [tbtest.InstalledMod("Steam Workshop", "111", "Harmony"), tbtest.InstalledMod("Local", "Local", "My.Local")])


class IsolationPlanTest(unittest.TestCase):
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


class RequestAndLaunchTest(TempCase):
    def test_request_carries_the_batch_map_and_deadline(self):
        request = tbtest.build_request("run-1", self.root / "run-1", "smoke", "_Mini", speed=30, hours=2, deadline_ms=123, probe_keys=["k"])
        self.assertEqual(request["Batch"], "smoke")
        self.assertEqual(request["Map"], "_Mini")
        self.assertEqual(request["DeadlineUtcMs"], 123)
        self.assertEqual(request["RunDir"], str(self.root / "run-1"))
        self.assertEqual(request["ProbePrefKeys"], ["k"])
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


if __name__ == "__main__":
    unittest.main()
