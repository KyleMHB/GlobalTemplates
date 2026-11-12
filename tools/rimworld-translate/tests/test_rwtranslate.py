"""The shared translation tool against small throwaway mods."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import checker  # noqa: E402
import def_text  # noqa: E402
import exchange  # noqa: E402
import extract  # noqa: E402
from modlayout import Mod, load_folders, read_language_data  # noqa: E402

DEFS = """<Defs>
  <ThingDef Name="Base" Abstract="True">
    <description>Shared text.</description>
    <comps><li Class="A"><effect>parent effect</effect></li></comps>
  </ThingDef>
  <ThingDef ParentName="Base">
    <defName>KM_Child</defName>
    <label>child</label>
    <comps><li Class="B"><effect>child effect</effect></li></comps>
  </ThingDef>
</Defs>"""


def language_data(entries):
    body = "".join(f"<{k}>{v}</{k}>" for k, v in entries.items())
    return f'<?xml version="1.0" encoding="utf-8"?><LanguageData>{body}</LanguageData>'


class ModTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "Source").mkdir()
        (self.root / "Defs").mkdir()
        (self.root / "Defs/Things.xml").write_text(DEFS, encoding="utf-8")
        self.write("translation.json", json.dumps({"keyPrefix": "Mod_", "hardcodedCheck": True, "gameDir": str(self.root / "none")}))

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def mod(self):
        return Mod(self.root)

    def check(self, notes=None):
        return checker.check(self.mod(), notes)


class CheckTest(ModTest):
    def test_matching_keys_pass(self):
        self.write("Source/A.cs", 'x = "Mod_A".Translate(n);')
        self.write("Languages/English/Keyed/A.xml", language_data({"Mod_A": "Count: {0}"}))
        self.assertEqual(self.check(), [])

    def test_missing_and_unused_keys_fail(self):
        self.write("Source/A.cs", 'x = "Mod_A".Translate();')
        self.write("Languages/English/Keyed/A.xml", language_data({"Mod_B": "b"}))
        problems = self.check()
        self.assertTrue(any("Mod_A is used" in p for p in problems))
        self.assertTrue(any("Mod_B is defined" in p for p in problems))

    def test_runtime_prefix_counts_as_use(self):
        self.write("Source/A.cs", 'x = ("Mod_Tab_" + name).Translate();')
        self.write("Languages/English/Keyed/A.xml", language_data({"Mod_Tab_Glacite": "Glacite"}))
        self.assertEqual(self.check(), [])

    def test_placeholder_beyond_arguments_fails(self):
        self.write("Source/A.cs", 'x = "Mod_A".Translate(n);')
        self.write("Languages/English/Keyed/A.xml", language_data({"Mod_A": "{0} of {1}"}))
        self.assertTrue(any("uses {1}" in p for p in self.check()))

    def test_translation_placeholders_must_match_english(self):
        self.write("Source/A.cs", 'x = "Mod_A".Translate(n);')
        self.write("Languages/English/Keyed/A.xml", language_data({"Mod_A": "Count: {0}"}))
        self.write("Languages/German/Keyed/A.xml", language_data({"Mod_A": "Anzahl"}))
        self.assertTrue(any("placeholders differ" in p for p in self.check()))

    def test_real_line_break_where_english_uses_backslash_n_fails(self):
        self.write("Source/A.cs", 'x = "Mod_A".Translate();')
        self.write("Languages/English/Keyed/A.xml", language_data({"Mod_A": "One.\\n\\nTwo."}))
        self.write("Languages/German/Keyed/A.xml", language_data({"Mod_A": "Eins.\n\nZwei."}))
        self.assertTrue(any("real line break" in p for p in self.check()))

    def test_job_tokens_count_as_placeholders_beside_cjk(self):
        self.write("Languages/English/Keyed/A.xml", language_data({"Mod_A": "attuning TargetB."}))
        self.write("Languages/ChineseSimplified/Keyed/A.xml", language_data({"Mod_A": "正在调谐TargetB。"}))
        self.write("Source/A.cs", 'x = "Mod_A".Translate();')
        self.assertEqual(self.check(), [])

    def test_hardcoded_ui_text_fails_unless_marked_or_a_key(self):
        self.write("Source/A.cs", 'Messages.Message("Something broke.");')
        self.assertTrue(self.check())
        self.write("Source/A.cs", 'Messages.Message("Something broke."); // not translated')
        self.assertEqual(self.check(), [])
        self.write("Source/A.cs", 'list.Label("Nobody".Translate()); var d = DefDatabase<ThingDef>.GetNamed("KM_Thing"); return x ? "Core" : "Work";')
        self.assertEqual(self.check(), [])

    def test_stale_def_injected_key_fails_but_vanilla_defs_are_left_alone(self):
        self.write("Languages/Russian/DefInjected/ThingDef/Things.xml",
                   language_data({"KM_Child.label": "ребёнок", "KM_Child.gone": "x", "Wall.label": "стена"}))
        problems = self.check()
        self.assertEqual(len(problems), 1)
        self.assertIn("KM_Child.gone", problems[0])

    def test_untranslated_and_outdated_are_only_counted(self):
        self.write("Languages/Russian/DefInjected/ThingDef/Things.xml", language_data({"KM_Child.label": "ребёнок"}))
        self.write("translation/record/Russian.json", json.dumps({"DefInjected:ThingDef:KM_Child.label": "old child"}))
        notes = []
        self.assertEqual(self.check(notes), [])
        self.assertEqual(notes, ["Russian: 3 untranslated, 1 outdated (English changed since translation)"])


class DefTextTest(ModTest):
    def test_inherits_fields_and_appends_list_items(self):
        found = {e.key: e.english for e in def_text.entries(self.mod())}
        self.assertEqual(found, {"KM_Child.description": "Shared text.", "KM_Child.label": "child",
                                 "KM_Child.comps.0.effect": "parent effect", "KM_Child.comps.1.effect": "child effect"})

    def test_english_def_injected_overrides_def_text(self):
        self.write("Languages/English/DefInjected/ThingDef/Things.xml", language_data({"KM_Child.label": "young one"}))
        found = {e.key: e.english for e in def_text.entries(self.mod())}
        self.assertEqual(found["KM_Child.label"], "young one")


class LoadFoldersTest(ModTest):
    def test_newest_version_block_is_used(self):
        (self.root / "Common").mkdir()
        (self.root / "1.7").mkdir()
        self.write("LoadFolders.xml", "<loadFolders><v1.6><li>/</li></v1.6><v1.7><li>Common</li><li>1.7</li></v1.7></loadFolders>")
        self.assertEqual([p.name for p in load_folders(self.root)], ["Common", "1.7"])

    def test_without_load_folders_root_common_and_newest_version_load(self):
        for name in ("Common", "1.5", "1.6"):
            (self.root / name).mkdir()
        self.assertEqual([p.name for p in load_folders(self.root)][1:], ["Common", "1.6"])


class ExchangeTest(ModTest):
    def test_export_import_round_trip_and_record(self):
        self.write("Languages/English/Keyed/A.xml", language_data({"Mod_A": "Hello {0}", "Mod_B": "child"}))
        mod = self.mod()
        texts, chunks = exchange.export(mod, "German")
        self.assertEqual((texts, chunks), (5, 1))  # "child" is shared by Mod_B and the def label
        chunk = json.loads((mod.work_dir / "German/chunk-00.json").read_text(encoding="utf-8"))
        done = {i: e.replace("Hello", "Hallo").replace("child", "Kind") for i, e in chunk["texts"].items()}
        (mod.work_dir / "German/chunk-00.done.json").write_text(json.dumps(done), encoding="utf-8")
        written, problems, left = exchange.import_(mod, "German")
        self.assertEqual((written, problems, left), (5, [], []))
        keyed = dict(read_language_data(self.root / "Languages/German/Keyed/A.xml"))
        self.assertEqual(keyed, {"Mod_A": "Hallo {0}", "Mod_B": "Kind"})
        injected = dict(read_language_data(self.root / "Languages/German/DefInjected/ThingDef/Things.xml"))
        self.assertEqual(injected["KM_Child.label"], "Kind")
        self.assertEqual(exchange.status(mod, "German"), ([], []))
        self.write("Languages/English/Keyed/A.xml", language_data({"Mod_A": "Hi {0}", "Mod_B": "child"}))
        missing, outdated = exchange.status(self.mod(), "German")
        self.assertEqual(([t.ident for t in missing], [t.ident for t in outdated]), ([], ["Keyed:Mod_A"]))

    def test_import_refuses_a_lost_placeholder(self):
        self.write("Languages/English/Keyed/A.xml", language_data({"Mod_A": "Hello {0}"}))
        mod = self.mod()
        exchange.export(mod, "German")
        (mod.work_dir / "German/chunk-00.done.json").write_text(json.dumps({"0": "Hallo"}), encoding="utf-8")
        written, problems, _ = exchange.import_(mod, "German")
        self.assertEqual(written, 0)
        self.assertIn("placeholders differ", problems[0])
        self.assertFalse((self.root / "Languages/German").exists())


class WriteLanguageDataTest(ModTest):
    def test_edit_keeps_formatting_and_appends_in_the_files_style(self):
        from modlayout import write_language_data
        original = ('<?xml version="1.0" encoding="utf-8"?>\r\n<LanguageData>\r\n  <!-- note -->\r\n  <A>old</A>\r\n\r\n'
                    '  <B>keep &amp; this</B>\r\n</LanguageData>')
        path = self.root / "Languages/German/Keyed/X.xml"
        path.parent.mkdir(parents=True)
        path.write_bytes(original.encode("utf-8"))
        write_language_data(path, {"A": "neu", "B": "keep & this", "C": "neu & mehr"})
        self.assertEqual(path.read_bytes().decode("utf-8"),
                         '<?xml version="1.0" encoding="utf-8"?>\r\n<LanguageData>\r\n  <!-- note -->\r\n  <A>neu</A>\r\n\r\n'
                         '  <B>keep &amp; this</B>\r\n  <C>neu &amp; mehr</C>\r\n</LanguageData>')


class ExtractTest(ModTest):
    def test_batch_replaces_and_writes_english_keys_keeping_crlf(self):
        (self.root / "Source/A.cs").write_bytes(b'x = "Hello";\r\ny = 1;\r\n')
        self.write("batch.py", 'SPECS = [dict(FILE="A.cs", R=[(\'"Hello"\', \'"Mod_Hello".Translate()\')], K={"Mod_Hello": "Hello"})]')
        extract.apply(self.mod(), [self.root / "batch.py"], out=lambda _: None)
        self.assertEqual((self.root / "Source/A.cs").read_bytes(), b'x = "Mod_Hello".Translate();\r\ny = 1;\r\n')
        self.assertEqual(dict(read_language_data(self.root / "Languages/English/Keyed/A.xml")), {"Mod_Hello": "Hello"})

    def test_failing_batch_writes_nothing(self):
        self.write("Source/A.cs", 'x = "Hello";')
        self.write("batch.py", 'SPECS = [dict(FILE="A.cs", R=[(\'"Missing"\', "y")], K={"Mod_X": "x"})]')
        with self.assertRaises(SystemExit):
            extract.apply(self.mod(), [self.root / "batch.py"], out=lambda _: None)
        self.assertFalse((self.root / "Languages").exists())


if __name__ == "__main__":
    unittest.main()
