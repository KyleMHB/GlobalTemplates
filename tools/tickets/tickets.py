"""Print one line per local Markdown ticket under a repo's `.scratch/<feature>/issues/`.

Answers "what's left?" without reading every spec and ticket into context.

    python tools/tickets/tickets.py <repo> [--open] [--feature <slug>]
"""
import argparse
import re
import sys
from pathlib import Path

# Matches `Status: x` and the older bold `**Status:** x`.
STATUS = re.compile(r"^\s*\**status:?\**:?\s*(.+?)\s*$", re.I)
BLOCKED = re.compile(r"^\s*\**blocked by:?\**:?\s*(.+?)\s*$", re.I)
DONE = {"resolved", "done", "closed", "wontfix", "won't fix", "duplicate"}


def read_ticket(path):
    title, status, blocked = path.stem, "?", ""
    with path.open(encoding="utf-8", errors="replace") as handle:
        for index, line in enumerate(handle):
            if index > 40:
                break
            if line.startswith("# ") and title == path.stem:
                title = line[2:].strip()
            elif status == "?" and (match := STATUS.match(line)):
                status = match.group(1).strip("*` ").lower()
            elif not blocked and (match := BLOCKED.match(line)):
                blocked = match.group(1).strip("*` ")
    return title, status, blocked


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--open", action="store_true", help="hide resolved, closed and wontfix tickets")
    parser.add_argument("--feature", help="only this .scratch/<feature> folder")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    scratch = Path(args.repo) / ".scratch"
    features = [scratch / args.feature] if args.feature else sorted(p for p in scratch.glob("*") if p.is_dir())
    for feature in features:
        tickets = sorted((feature / "issues").glob("*.md"))
        rows = [(path, *read_ticket(path)) for path in tickets]
        shown = [row for row in rows if not (args.open and row[2] in DONE)]
        open_count = sum(row[2] not in DONE for row in rows)
        if not shown and args.open:
            continue
        print(f"== {feature.name}: {open_count} open of {len(rows)}")
        for path, title, status, blocked in shown:
            suffix = f"  (blocked by: {blocked[:60]})" if blocked and status not in DONE and not blocked.lower().startswith("none") else ""
            print(f"  {status:<16} {path.name:<44} {title}{suffix}")


if __name__ == "__main__":
    main()
