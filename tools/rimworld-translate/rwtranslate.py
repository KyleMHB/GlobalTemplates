"""RimWorld mod translation tool: check, list def text, export and import translation chunks, apply extraction batches.

  python rwtranslate.py --mod <mod root> check            fail on broken translations; count untranslated texts
  python rwtranslate.py --mod <mod root> status           untranslated and outdated counts per language
  python rwtranslate.py --mod <mod root> defs             every translatable def field after inheritance
  python rwtranslate.py --mod <mod root> export <Lang>    write chunks of what <Lang> still needs to <work>/<Lang>
  python rwtranslate.py --mod <mod root> import <Lang>    write the translated chunks into the language files
  python rwtranslate.py --mod <mod root> baseline <Lang>  accept existing <Lang> translations as current
  python rwtranslate.py --mod <mod root> extract <batch.py> ...   apply C# string extraction batches
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checker  # noqa: E402
import def_text  # noqa: E402
import exchange  # noqa: E402
import extract  # noqa: E402
from modlayout import Mod  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mod", default=".", help="mod root (default: current folder)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("status")
    sub.add_parser("defs")
    for name in ("export", "import", "baseline"):
        p = sub.add_parser(name)
        p.add_argument("language")
        if name == "export":
            p.add_argument("--chunk-chars", type=int, default=6000)
            p.add_argument("--all", action="store_true", help="export every text, not only untranslated and outdated")
    p = sub.add_parser("extract")
    p.add_argument("batches", nargs="+")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    mod = Mod(args.mod)

    if args.command == "check":
        notes = []
        problems = checker.check(mod, notes)
        for line in problems + notes:
            print(line)
        print(f"translations: {len(problems)} problem(s)" if problems else "translations: passed")
        return 1 if problems else 0
    if args.command == "status":
        for language in checker.translated_languages(mod):
            missing, outdated = exchange.status(mod, language)
            print(f"{language}: {len(missing)} untranslated, {len(outdated)} outdated")
        return 0
    if args.command == "defs":
        for e in def_text.entries(mod):
            print(f"{mod.rel(e.folder) or '.'}\t{e.def_type}\t{e.stem}\t{e.key}\t{e.english}")
        return 0
    if args.command == "export":
        texts, chunks = exchange.export(mod, args.language, args.chunk_chars, args.all)
        print(f"{texts} text(s) in {chunks} chunk(s) under {mod.rel(mod.work_dir / args.language)}")
        return 0
    if args.command == "import":
        written, problems, left = exchange.import_(mod, args.language)
        for problem in problems:
            print(problem)
        if problems:
            print("Nothing written.")
            return 1
        print(f"{written} text(s) written" + (f"; still untranslated ids: {', '.join(left)}" if left else ""))
        return 0
    if args.command == "baseline":
        print(f"{exchange.baseline(mod, args.language)} text(s) recorded for {args.language}")
        return 0
    if args.command == "extract":
        extract.apply(mod, [Path(b) for b in args.batches])
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
