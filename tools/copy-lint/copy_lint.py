"""Check public copy for em dashes and the banned words in writing-copy.md.

Covers the unslop scope in writing-copy.md: README.md, CHANGELOG.md and steam-description.md,
plus only the description field of About.xml, mod.json and a Timberborn manifest.json.

    python copy_lint.py --staged      # pre-commit: added lines and changed description fields only
    python copy_lint.py FILE...       # whole files

A line containing `copy-lint: allow` is skipped, for a name or quote that needs a banned word.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[2]
PROSE = {"readme.md", "changelog.md", "steam-description.md"}
FIELDS = {"about.xml": "xml", "mod.json": "description", "manifest.json": "Description"}
EM_DASH = "—"


def banned_words():
    """Read the quoted word list from writing-copy.md so the rule has one source."""
    text = (TEMPLATES / "writing-copy.md").read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if "cliché words such as" in l)
    return [w.rstrip(",.") for w in re.findall(r'"([^"]+)"', line)]


def pattern(words):
    stems = "|".join(re.escape(w) for w in words)
    return re.compile(rf"\b(?:{stems})\w*", re.I)


def field(text, kind):
    """The description field of a structured file, or None when it has none."""
    if not text:
        return None
    if kind == "xml":
        match = re.search(r"<description>(.*?)</description>", text, re.S)
        return match.group(1) if match else None
    try:
        value = json.loads(text).get(kind)
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, str) else None


def lint_lines(name, lines, banned):
    problems = []
    for number, line in lines:
        if "copy-lint: allow" in line:
            continue
        if EM_DASH in line:
            problems.append(f"{name}:{number}: em dash; use a period or comma")
        for match in banned.finditer(line):
            problems.append(f"{name}:{number}: '{match.group(0)}' is on writing-copy.md's banned list")
    return problems


def git(repo, *args):
    result = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else ""


def staged(repo, banned):
    problems = []
    for path in git(repo, "diff", "--cached", "--name-only", "--diff-filter=AM").splitlines():
        base = Path(path).name.lower()
        if base in PROSE:
            added, number = [], 0
            for line in git(repo, "diff", "--cached", "-U0", "--no-color", "--", path).splitlines():
                if line.startswith("@@"):
                    number = int(re.search(r"\+(\d+)", line).group(1))
                elif line.startswith("+") and not line.startswith("+++"):
                    added.append((number, line[1:]))
                    number += 1
            problems += lint_lines(path, added, banned)
        elif base in FIELDS:
            new = field(git(repo, "show", f":{path}"), FIELDS[base])
            if new is not None and new != field(git(repo, "show", f"HEAD:{path}"), FIELDS[base]):
                problems += lint_lines(f"{path} (description)", enumerate(new.splitlines(), 1), banned)
    return problems


def whole(paths, banned):
    problems = []
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        base = Path(path).name.lower()
        if base in FIELDS:
            text = field(text, FIELDS[base]) or ""
        problems += lint_lines(path, enumerate(text.splitlines(), 1), banned)
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--staged", action="store_true", help="check what is staged in the current repo")
    parser.add_argument("--repo", default=".")
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    banned = pattern(banned_words())
    problems = staged(args.repo, banned) if args.staged else whole(args.files, banned)
    if problems:
        print("\n".join(problems))
        print(f"copy lint: FAILED ({len(problems)}). Fix the copy, or add `copy-lint: allow` to a line that must keep it.")
        return 1
    print("copy lint: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
