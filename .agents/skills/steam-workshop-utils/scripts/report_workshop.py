#!/usr/bin/env python3
"""Generate Markdown, JSON, or HTML reports from a steam-workshop-utils SQLite DB."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import http.server
import json
import os
import re
import secrets
import sqlite3
import sys
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

DEFAULT_DB = Path.home() / ".codex" / "data" / "steam-workshop" / "steam-workshop.sqlite"
DEFAULT_CATEGORIES = [
    "incompatibility",
    "multiplayer",
    "dependencies",
    "version",
    "errors",
    "load_order",
    "overlap",
    "compatibility",
    "alternatives",
    "performance",
    "sentiment_negative",
    "resolved",
]
DEFAULT_FORMAT = "markdown"
WORKSHOP_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id={item_id}"
QUESTION_EVIDENCE_LIMIT = 10
DEFAULT_SERVE_HOST = "127.0.0.1"
DEFAULT_SERVE_PORT = 8765
STATUS_PRIORITY = {
    "missing": 0,
    "between_selected_mods": 1,
    "compatible_selected_mods": 2,
    "uncertain": 3,
    "evidence": 4,
    "external_or_uncertain": 5,
    "fulfilled": 6,
}
VERSION_PROBLEM_RE = re.compile(
    r"\b(not compatible|incompatible|unsupported|outdated|old version|wrong version|broken on|does not work with|"
    r"doesn't work with|needs update|update needed|no longer works|obsolete)\b",
    re.I,
)
PERFORMANCE_POSITIVE_RE = re.compile(
    r"\b(reduces? lag|no performance impact|minimal performance impact|minor performance impact|"
    r"performance friendly|improves? fps|better fps|less lag|optimized|optimised)\b",
    re.I,
)
PERFORMANCE_PROBLEM_RE = re.compile(
    r"\b(lags? the game|heavy lag|bad performance|fps drops?|frame drops?|stutter(?:ing)?|"
    r"slowdown|memory leak|causes? lag|performance issue|performance problem|high memory|tps drops?|heavy mod)\b",
    re.I,
)
RESOLVED_FAMILY_CATEGORIES = {"incompatibility", "version", "errors", "load_order", "performance", "sentiment_negative"}


def default_db_path() -> Path:
    return Path(os.environ.get("STEAM_WORKSHOP_DB", DEFAULT_DB)).expanduser()


def template_path() -> Path:
    return Path(__file__).resolve().parents[1] / "references" / "check-templates.json"


def parse_ids_text(text: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item_id in re.findall(r"\b\d{5,}\b", text):
        if item_id not in seen:
            seen.add(item_id)
            result.append(item_id)
    return result


def load_ids_from_json(value: Any) -> list[str]:
    if isinstance(value, list):
        return parse_ids_text(" ".join(str(item) for item in value))
    if isinstance(value, dict):
        ids: list[str] = []
        for key in ("ids", "workshop_ids", "publishedfileids", "publishedfile_ids", "mods"):
            if key in value:
                ids.extend(load_ids_from_json(value[key]))
        for key in ("id", "workshop_id", "publishedfileid", "publishedfile_id"):
            if key in value:
                ids.extend(parse_ids_text(str(value[key])))
        return list(dict.fromkeys(ids))
    return []


def load_ids_from_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        ids = load_ids_from_json(json.loads(text))
        if ids:
            return ids
    except json.JSONDecodeError:
        pass
    return parse_ids_text(text)


def load_templates(path: Path | None = None) -> dict[str, Any]:
    path = path or template_path()
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    templates = data.get("templates", data)
    if not isinstance(templates, dict):
        raise SystemExit(f"Invalid template file: {path}")
    return templates


def connect_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(f"DB does not exist: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_report_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS resolved_evidence (
            fingerprint TEXT PRIMARY KEY,
            publishedfileid TEXT NOT NULL,
            question_id TEXT NOT NULL,
            category TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_key TEXT NOT NULL,
            snippet_hash TEXT NOT NULL,
            resolved_at TEXT NOT NULL,
            resolved_by TEXT NOT NULL DEFAULT 'local',
            note TEXT
        );

        CREATE TABLE IF NOT EXISTS modlists (
            name TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS modlist_items (
            list_name TEXT NOT NULL,
            publishedfileid TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('active', 'archived')),
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            archived_at TEXT,
            PRIMARY KEY (list_name, publishedfileid),
            FOREIGN KEY (list_name) REFERENCES modlists(name) ON DELETE CASCADE
        );
        """
    )
    conn.commit()


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone()
    return row is not None


def collect_ids(conn: sqlite3.Connection, args: argparse.Namespace) -> list[str]:
    if args.list_name:
        statuses = ("active", "archived") if args.include_archived else ("active",)
        placeholders = ",".join("?" for _ in statuses)
        rows = conn.execute(
            f"""
            SELECT publishedfileid
            FROM modlist_items
            WHERE list_name = ? AND status IN ({placeholders})
            ORDER BY status, publishedfileid
            """,
            (args.list_name, *statuses),
        ).fetchall()
        return [row["publishedfileid"] for row in rows]
    if args.all:
        return [row["publishedfileid"] for row in conn.execute("SELECT publishedfileid FROM workshop_items ORDER BY title, publishedfileid")]
    ids: list[str] = []
    if args.ids:
        ids.extend(parse_ids_text(args.ids))
    if args.input:
        ids.extend(load_ids_from_file(args.input))
    return list(dict.fromkeys(ids))


def collect_membership_status(conn: sqlite3.Connection, args: argparse.Namespace) -> dict[str, str]:
    if not args.list_name:
        return {}
    statuses = ("active", "archived") if args.include_archived else ("active",)
    placeholders = ",".join("?" for _ in statuses)
    rows = conn.execute(
        f"""
        SELECT publishedfileid, status
        FROM modlist_items
        WHERE list_name = ? AND status IN ({placeholders})
        """,
        (args.list_name, *statuses),
    ).fetchall()
    return {row["publishedfileid"]: row["status"] for row in rows}


def selected_categories(args: argparse.Namespace, template: dict[str, Any] | None) -> list[str]:
    if args.category:
        return args.category
    if template:
        categories: list[str] = []
        for question in template.get("questions", []):
            categories.extend(question.get("categories", []))
        if categories:
            return list(dict.fromkeys(categories))
    return DEFAULT_CATEGORIES


def resolve_format(args: argparse.Namespace, template: dict[str, Any] | None) -> str:
    if args.format:
        return args.format
    if template and template.get("default_format"):
        return str(template["default_format"])
    return DEFAULT_FORMAT


def fetch_report(
    conn: sqlite3.Connection,
    item_ids: list[str],
    categories: list[str],
    check_name: str | None,
    template: dict[str, Any] | None,
    membership_status: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not table_exists(conn, "workshop_items"):
        raise SystemExit("DB schema is missing workshop_items. Run sync_workshop.py first.")
    report_items: list[dict[str, Any]] = []
    query_categories = list(dict.fromkeys([*categories, "resolved"]))
    membership_status = membership_status or {}
    for item_id in item_ids:
        item = conn.execute("SELECT * FROM workshop_items WHERE publishedfileid = ?", (item_id,)).fetchone()
        if not item:
            report_items.append(
                {
                    "publishedfileid": item_id,
                    "missing": True,
                    "archived": membership_status.get(item_id) == "archived",
                    "membership_status": membership_status.get(item_id),
                    "url": WORKSHOP_URL.format(item_id=item_id),
                }
            )
            continue
        category_placeholders = ",".join("?" for _ in query_categories)
        evidence_rows = conn.execute(
            f"""
            SELECT e.category, e.source_type, e.source_key, e.term, e.snippet, e.confidence,
                   c.position AS comment_position
            FROM evidence e
            LEFT JOIN comments c
              ON e.publishedfileid = c.publishedfileid
             AND e.source_type = 'comment'
             AND e.source_key = c.comment_key
            WHERE e.publishedfileid = ? AND e.category IN ({category_placeholders})
            ORDER BY e.category, e.source_type, COALESCE(c.position, 999999), e.term, e.snippet
            """,
            (item_id, *query_categories),
        ).fetchall()
        failure_rows = conn.execute(
            "SELECT stage, message, last_seen FROM sync_failures WHERE publishedfileid = ? ORDER BY stage",
            (item_id,),
        ).fetchall()
        comment_count = conn.execute("SELECT COUNT(*) AS count FROM comments WHERE publishedfileid = ?", (item_id,)).fetchone()["count"]
        grouped: dict[str, list[dict[str, Any]]] = {category: [] for category in query_categories}
        flat_evidence: list[dict[str, Any]] = []
        for row in evidence_rows:
            entry = {
                "item_id": item_id,
                "title": item["title"] or item_id,
                "category": row["category"],
                "source_type": row["source_type"],
                "source_key": row["source_key"],
                "term": row["term"],
                "snippet": row["snippet"],
                "confidence": row["confidence"],
                "comment_position": row["comment_position"],
            }
            grouped[row["category"]].append(entry)
            flat_evidence.append(entry)
        report_items.append(
            {
                "publishedfileid": item_id,
                "title": item["title"],
                "archived": membership_status.get(item_id) == "archived",
                "membership_status": membership_status.get(item_id),
                "appid": item["appid"],
                "url": WORKSHOP_URL.format(item_id=item_id),
                "last_metadata_sync": item["last_metadata_sync"],
                "comment_count": comment_count,
                "evidence": grouped,
                "evidence_entries": flat_evidence,
                "failures": [dict(row) for row in failure_rows],
            }
        )
    report = {
        "check": check_name,
        "template": template,
        "items": report_items,
        "categories": categories,
    }
    if template:
        report["questions"] = build_question_results(report_items, template, load_manual_resolutions(conn))
    return report


def item_title_map(items: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(item["publishedfileid"]): str(item.get("title") or item["publishedfileid"])
        for item in items
        if not item.get("missing")
    }


def snippet_mentions_item(snippet: str, other_id: str, other_title: str) -> bool:
    if re.search(rf"\b{re.escape(other_id)}\b", snippet):
        return True
    return bool(other_title and re.search(rf"(?<!\w){re.escape(other_title)}(?!\w)", snippet, re.IGNORECASE))


def classify_dependency(entry: dict[str, str], selected_titles: dict[str, str]) -> str:
    mentioned_ids = parse_ids_text(entry.get("snippet", ""))
    if mentioned_ids:
        return "fulfilled" if any(item_id in selected_titles for item_id in mentioned_ids) else "missing"
    for item_id, title in selected_titles.items():
        if item_id != entry["item_id"] and snippet_mentions_item(entry.get("snippet", ""), item_id, title):
            return "fulfilled"
    return "uncertain"


def classify_conflict(entry: dict[str, str], selected_titles: dict[str, str]) -> str:
    for item_id, title in selected_titles.items():
        if item_id != entry["item_id"] and snippet_mentions_item(entry.get("snippet", ""), item_id, title):
            return "between_selected_mods"
    return "external_or_uncertain"


def classify_entry(entry: dict[str, str], question: dict[str, Any], selected_titles: dict[str, str]) -> str:
    mode = question.get("mode")
    if mode == "dependency_fulfillment":
        return classify_dependency(entry, selected_titles)
    if mode in {"selected_mod_conflicts", "selected_mod_overlap"}:
        return classify_conflict(entry, selected_titles)
    if mode == "selected_mod_compatibility":
        status = classify_conflict(entry, selected_titles)
        return "compatible_selected_mods" if status == "between_selected_mods" else status
    return "evidence"


def is_version_problem(entry: dict[str, str]) -> bool:
    return bool(VERSION_PROBLEM_RE.search(entry.get("snippet", "")))


def include_question_entry(entry: dict[str, str], question: dict[str, Any], template: dict[str, Any]) -> bool:
    if entry.get("category") == "performance" and not is_performance_problem_entry(entry):
        return False
    include_statuses = question.get("include_statuses")
    if include_statuses and entry.get("status") not in include_statuses:
        return False
    if question.get("mode") == "version_problems":
        return is_version_problem(entry)
    if template.get("problem_only") and question.get("mode") == "dependency_fulfillment":
        return entry.get("status") in {"missing", "uncertain"}
    if template.get("problem_only") and question.get("mode") == "selected_mod_conflicts":
        return entry.get("status") == "between_selected_mods"
    if template.get("problem_only") and question.get("mode") == "selected_mod_overlap":
        return entry.get("status") == "between_selected_mods"
    if question.get("mode") == "selected_mod_compatibility":
        return entry.get("status") == "compatible_selected_mods"
    return True


def normalize_snippet(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def snippet_hash(value: str) -> str:
    return hashlib.sha256(normalize_snippet(value).encode("utf-8")).hexdigest()


def evidence_fingerprint(question_id: str, entry: dict[str, Any]) -> str:
    parts = [
        str(entry.get("item_id", "")),
        question_id,
        str(entry.get("category", "")),
        str(entry.get("source_type", "")),
        str(entry.get("source_key", "")),
        snippet_hash(str(entry.get("snippet", ""))),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def load_manual_resolutions(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    if not table_exists(conn, "resolved_evidence"):
        return {}
    rows = conn.execute(
        """
        SELECT fingerprint, publishedfileid, question_id, category, source_type, source_key,
               snippet_hash, resolved_at, resolved_by, note
        FROM resolved_evidence
        """
    ).fetchall()
    return {row["fingerprint"]: dict(row) for row in rows}


def record_manual_resolution(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    fingerprint = str(payload.get("fingerprint") or "").strip()
    if not fingerprint:
        raise ValueError("fingerprint is required")
    expected = evidence_fingerprint(
        str(payload.get("question_id") or ""),
        {
            "item_id": str(payload.get("item_id") or payload.get("publishedfileid") or ""),
            "category": str(payload.get("category") or ""),
            "source_type": str(payload.get("source_type") or ""),
            "source_key": str(payload.get("source_key") or ""),
            "snippet": str(payload.get("snippet") or ""),
        },
    )
    if fingerprint != expected:
        raise ValueError("fingerprint does not match evidence payload")
    resolved_at = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    conn.execute(
        """
        INSERT OR REPLACE INTO resolved_evidence (
            fingerprint, publishedfileid, question_id, category, source_type, source_key,
            snippet_hash, resolved_at, resolved_by, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fingerprint,
            str(payload.get("item_id") or payload.get("publishedfileid") or ""),
            str(payload.get("question_id") or ""),
            str(payload.get("category") or ""),
            str(payload.get("source_type") or ""),
            str(payload.get("source_key") or ""),
            snippet_hash(str(payload.get("snippet") or "")),
            resolved_at,
            str(payload.get("resolved_by") or "local"),
            str(payload.get("note") or ""),
        ),
    )
    conn.commit()
    return {"fingerprint": fingerprint, "resolved_at": resolved_at}


def clear_manual_resolution(conn: sqlite3.Connection, fingerprint: str) -> None:
    conn.execute("DELETE FROM resolved_evidence WHERE fingerprint = ?", (fingerprint,))
    conn.commit()


def is_performance_problem_entry(entry: dict[str, Any]) -> bool:
    snippet = str(entry.get("snippet") or "")
    return bool(PERFORMANCE_PROBLEM_RE.search(snippet)) and not PERFORMANCE_POSITIVE_RE.search(snippet)


def problem_family_resolved(problem: dict[str, Any], resolved: dict[str, Any]) -> bool:
    if problem.get("item_id") != resolved.get("item_id"):
        return False
    if resolved.get("source_type") != "comment" or resolved.get("comment_position") is None:
        return False
    problem_position = problem.get("comment_position")
    if problem.get("source_type") == "comment" and problem_position is not None and int(resolved["comment_position"]) >= int(problem_position):
        return False
    category = problem.get("category")
    if category in RESOLVED_FAMILY_CATEGORIES:
        return True
    if category == "dependencies":
        text = str(resolved.get("snippet") or "")
        return bool(re.search(r"\b(dependenc(?:y|ies)|required|missing|load order)\b", text, re.I))
    return False


def dedupe_and_sort_entries(question_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for entry in entries:
        key = (
            question_id,
            entry.get("item_id", ""),
            entry.get("status", ""),
            entry.get("source_type", ""),
            normalize_snippet(entry.get("snippet", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return sorted(
        deduped,
        key=lambda entry: (
            STATUS_PRIORITY.get(entry.get("status", "evidence"), 99),
            0 if entry.get("source_type") == "comment" else 1,
            entry.get("title", "").lower(),
            normalize_snippet(entry.get("snippet", "")),
        ),
    )


def build_question_results(items: list[dict[str, Any]], template: dict[str, Any], manual_resolutions: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    selected_titles = item_title_map(items)
    manual_resolutions = manual_resolutions or {}
    resolved_by_item: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if item.get("missing"):
            continue
        for entry in item["evidence"].get("resolved", []):
            resolved_by_item.setdefault(str(item["publishedfileid"]), []).append(entry)
    results: list[dict[str, Any]] = []
    for question in template.get("questions", []):
        categories = question.get("categories", [])
        question_id = question.get("id", "")
        entries: list[dict[str, Any]] = []
        resolved_entries: list[dict[str, Any]] = []
        for item in items:
            if item.get("missing"):
                continue
            for category in categories:
                for entry in item["evidence"].get(category, []):
                    enriched = dict(entry)
                    enriched["status"] = classify_entry(enriched, question, selected_titles)
                    if not include_question_entry(enriched, question, template):
                        continue
                    enriched["question_id"] = question_id
                    enriched["fingerprint"] = evidence_fingerprint(question_id, enriched)
                    manual = manual_resolutions.get(enriched["fingerprint"])
                    if manual:
                        suppressed = dict(enriched)
                        suppressed["resolved_reason"] = "manual"
                        suppressed["resolved_by"] = manual.get("resolved_by", "local")
                        suppressed["resolved_at"] = manual.get("resolved_at", "")
                        suppressed["resolved_note"] = manual.get("note", "")
                        resolved_entries.append(suppressed)
                        continue
                    resolver = next(
                        (
                            resolved
                            for resolved in resolved_by_item.get(str(enriched["item_id"]), [])
                            if problem_family_resolved(enriched, resolved)
                        ),
                        None,
                    )
                    if resolver:
                        suppressed = dict(enriched)
                        suppressed["resolved_reason"] = "newer_comment"
                        suppressed["resolved_by"] = "comment"
                        suppressed["resolved_at"] = ""
                        suppressed["resolved_snippet"] = resolver.get("snippet", "")
                        suppressed["resolved_source_key"] = resolver.get("source_key", "")
                        suppressed["resolved_comment_position"] = resolver.get("comment_position")
                        resolved_entries.append(suppressed)
                        continue
                    entries.append(enriched)
        entries = dedupe_and_sort_entries(question_id, entries)
        resolved_entries = dedupe_and_sort_entries(question_id, resolved_entries)
        status = "no_evidence"
        if entries:
            statuses = {entry["status"] for entry in entries}
            if "missing" in statuses:
                status = "attention"
            elif "between_selected_mods" in statuses:
                status = "attention"
            elif "uncertain" in statuses:
                status = "uncertain"
            else:
                status = "evidence_found"
        results.append(
            {
                "id": question_id,
                "question": question.get("question"),
                "description": question.get("description", ""),
                "categories": categories,
                "mode": question.get("mode", "evidence"),
                "status": status,
                "evidence": entries,
                "resolved": resolved_entries,
            }
        )
    return results


def markdown_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").strip()


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = ["# Steam Workshop Evidence Report", ""]
    if report.get("check"):
        lines.extend([f"- Check: `{report['check']}`", ""])
    for question in report.get("questions", []):
        lines.extend([f"## {question['question']}", "", f"Status: `{question['status']}`", ""])
        if question.get("description"):
            lines.extend([question["description"], ""])
        if not question["evidence"] and not question.get("resolved"):
            lines.extend(["No matching evidence found.", ""])
            continue
        if question["evidence"]:
            lines.extend(["| Mod | Status | Source | Evidence |", "| --- | --- | --- | --- |"])
            for entry in question["evidence"][:50]:
                mod = f"{entry['title']} ({entry['item_id']})"
                lines.append(
                    f"| {markdown_escape(mod)} | {markdown_escape(entry['status'])} | "
                    f"{markdown_escape(entry['source_type'])} | {markdown_escape(entry['snippet'])} |"
                )
            lines.append("")
        if question.get("resolved"):
            lines.extend(["Resolved or suppressed evidence:", "", "| Mod | Reason | Evidence | Resolver |", "| --- | --- | --- | --- |"])
            for entry in question["resolved"][:25]:
                mod = f"{entry['title']} ({entry['item_id']})"
                resolver = entry.get("resolved_snippet") or entry.get("resolved_note") or entry.get("resolved_at") or ""
                lines.append(
                    f"| {markdown_escape(mod)} | {markdown_escape(entry.get('resolved_reason'))} | "
                    f"{markdown_escape(entry.get('snippet'))} | {markdown_escape(resolver)} |"
                )
            lines.append("")
    for item in report["items"]:
        if item.get("missing"):
            archived = " (archived)" if item.get("archived") else ""
            lines.extend([f"## Missing Item `{item['publishedfileid']}`{archived}", "", "No cached metadata found. Run sync first.", ""])
            continue
        archived = " (archived)" if item.get("archived") else ""
        lines.extend(
            [
                f"## {item.get('title') or item['publishedfileid']}{archived}",
                "",
                f"- Workshop ID: `{item['publishedfileid']}`",
                f"- List status: `{item.get('membership_status') or 'selected'}`",
                f"- URL: {item['url']}",
                f"- App ID: `{item.get('appid') or 'unknown'}`",
                f"- Cached comments: `{item['comment_count']}`",
                f"- Last metadata sync: `{item.get('last_metadata_sync')}`",
                "",
            ]
        )
        if item["failures"]:
            lines.extend(["### Sync Failures", ""])
            for failure in item["failures"]:
                lines.append(f"- `{failure['stage']}` at `{failure['last_seen']}`: {failure['message']}")
            lines.append("")
        any_evidence = False
        for category in report["categories"]:
            entries = item["evidence"].get(category, [])
            if not entries:
                continue
            any_evidence = True
            lines.extend([f"### {category.replace('_', ' ').title()}", "", "| Source | Confidence | Signal | Evidence |", "| --- | --- | --- | --- |"])
            for entry in entries[:20]:
                lines.append(
                    f"| {markdown_escape(entry['source_type'])} | {markdown_escape(entry['confidence'])} | "
                    f"{markdown_escape(entry['term'])} | {markdown_escape(entry['snippet'])} |"
                )
            if len(entries) > 20:
                lines.append(f"| ... | ... | ... | {len(entries) - 20} more snippets omitted |")
            lines.append("")
        if not any_evidence:
            lines.extend(["No configured evidence signals found in cached descriptions or comments.", ""])
    return "\n".join(lines).rstrip() + "\n"


def escape_html(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def linkify_text(value: Any, known_titles: dict[str, str]) -> str:
    raw = "" if value is None else str(value)
    title_lookup = {
        title.lower(): item_id
        for item_id, title in known_titles.items()
        if title
    }
    title_patterns = sorted((re.escape(title) for title in title_lookup), key=len, reverse=True)
    parts = []
    if title_patterns:
        parts.append(rf"(?P<title>(?<!\w)(?:{'|'.join(title_patterns)})(?!\w))")
    parts.append(r"(?P<id>\b\d{5,}\b)")
    pattern = re.compile("|".join(parts), re.IGNORECASE)
    output: list[str] = []
    last = 0
    for match in pattern.finditer(raw):
        output.append(escape_html(raw[last : match.start()]))
        text = match.group(0)
        if match.lastgroup == "title":
            item_id = title_lookup.get(text.lower())
        else:
            item_id = text
        output.append(f'<a href="{WORKSHOP_URL.format(item_id=item_id)}">{escape_html(text)}</a>')
        last = match.end()
    output.append(escape_html(raw[last:]))
    return "".join(output)


def evidence_counts(items: list[dict[str, Any]], categories: list[str]) -> dict[str, int]:
    counts = {category: 0 for category in categories}
    for item in items:
        if item.get("missing"):
            continue
        for category in categories:
            counts[category] += len(item["evidence"].get(category, []))
    return counts


def render_actions(entry: dict[str, Any], server_mode: bool, csrf_token: str = "") -> str:
    fingerprint = escape_html(entry.get("fingerprint", ""))
    payload_attrs = (
        f'data-fingerprint="{fingerprint}" '
        f'data-item-id="{escape_html(entry.get("item_id", ""))}" '
        f'data-question-id="{escape_html(entry.get("question_id", ""))}" '
        f'data-category="{escape_html(entry.get("category", ""))}" '
        f'data-source-type="{escape_html(entry.get("source_type", ""))}" '
        f'data-source-key="{escape_html(entry.get("source_key", ""))}" '
        f'data-snippet="{escape_html(entry.get("snippet", ""))}" '
        f'data-csrf-token="{escape_html(csrf_token)}"'
    )
    if server_mode:
        button = f'<button class="resolve-button" type="button" {payload_attrs}>Mark resolved</button>'
        note = '<input class="resolve-note" type="text" placeholder="Optional note">'
    else:
        button = '<button type="button" disabled>Mark resolved</button>'
        note = '<p class="muted">Persistent resolution requires running this report with <code>--serve</code>.</p>'
    return f"""
      <details class="actions">
        <summary>Actions</summary>
        {note}
        {button}
      </details>
    """


def render_resolved_section(entries: list[dict[str, Any]], known_titles: dict[str, str], server_mode: bool, csrf_token: str = "") -> str:
    if not entries:
        return ""
    rows = []
    for entry in entries:
        reason = entry.get("resolved_reason", "resolved")
        resolver = entry.get("resolved_snippet") or entry.get("resolved_note") or entry.get("resolved_at") or ""
        unresolve = ""
        if server_mode and reason == "manual":
            unresolve = (
                f'<button class="unresolve-button" type="button" '
                f'data-fingerprint="{escape_html(entry.get("fingerprint", ""))}" '
                f'data-csrf-token="{escape_html(csrf_token)}">Unresolve</button>'
            )
        rows.append(
            f"""
            <article class="evidence-row resolved-row" data-title="{escape_html(entry['title']).lower()}" data-id="{escape_html(entry['item_id'])}" data-category="{escape_html(entry['category'])}" data-source="{escape_html(entry['source_type'])}" data-confidence="{escape_html(entry['confidence'])}" data-text="{escape_html(entry['snippet']).lower()}">
              <div class="row-meta">
                <a href="{WORKSHOP_URL.format(item_id=entry['item_id'])}">{escape_html(entry['title'])}</a>
                <span>{escape_html(reason.replace('_', ' '))}</span>
                <span>{escape_html(entry['source_type'])}</span>
              </div>
              <p>{linkify_text(entry['snippet'], known_titles)}</p>
              {f'<p class="resolver">Resolved by: {linkify_text(resolver, known_titles)}</p>' if resolver else ''}
              {unresolve}
            </article>
            """
        )
    return f"""
      <details class="resolved-section">
        <summary>Resolved by newer comments or manual review ({len(entries)})</summary>
        {''.join(rows)}
      </details>
    """


def render_html(report: dict[str, Any], server_mode: bool = False, csrf_token: str = "") -> str:
    items = report["items"]
    categories = report["categories"]
    known_titles = item_title_map(items)
    missing_count = sum(1 for item in items if item.get("missing"))
    failure_count = sum(len(item.get("failures", [])) for item in items)
    comment_count = sum(int(item.get("comment_count") or 0) for item in items if not item.get("missing"))
    counts = evidence_counts(items, categories)
    title = "Steam Workshop Evidence Report"
    if report.get("check"):
        title += f" - {report['check']}"
    category_options = "\n".join(f'<option value="{escape_html(category)}">{escape_html(category.replace("_", " ").title())}</option>' for category in categories)
    count_cards = "\n".join(
        f'<div class="stat"><span>{escape_html(category.replace("_", " ").title())}</span><strong>{count}</strong></div>'
        for category, count in counts.items()
    )
    question_sections = []
    for question in report.get("questions", []):
        entries = question["evidence"]
        rows = []
        for index, entry in enumerate(entries):
            extra_class = " is-extra hidden-overflow" if index >= QUESTION_EVIDENCE_LIMIT else ""
            rows.append(
                f"""
                <article class="evidence-row{extra_class}" data-title="{escape_html(entry['title']).lower()}" data-id="{escape_html(entry['item_id'])}" data-category="{escape_html(entry['category'])}" data-source="{escape_html(entry['source_type'])}" data-confidence="{escape_html(entry['confidence'])}" data-text="{escape_html(entry['snippet']).lower()}">
                  <div class="row-meta">
                    <a href="{WORKSHOP_URL.format(item_id=entry['item_id'])}">{escape_html(entry['title'])}</a>
                    <span>{escape_html(entry['status'])}</span>
                    <span>{escape_html(entry['source_type'])}</span>
                    <span>{escape_html(entry['confidence'])}</span>
                  </div>
                  <p>{linkify_text(entry['snippet'], known_titles)}</p>
                  {render_actions(entry, server_mode, csrf_token)}
                </article>
                """
            )
        body = "\n".join(rows) if rows else '<p class="empty">No matching evidence found.</p>'
        more_button = (
            f'<button class="show-more" type="button" data-hidden-count="{len(entries) - QUESTION_EVIDENCE_LIMIT}">'
            f'Show {len(entries) - QUESTION_EVIDENCE_LIMIT} more</button>'
            if len(entries) > QUESTION_EVIDENCE_LIMIT
            else ""
        )
        clean_class = " no-evidence hidden-clean hidden" if question["status"] == "no_evidence" else ""
        question_sections.append(
            f"""
            <details class="panel question{clean_class}">
              <summary class="section-heading">
                <h2>{escape_html(question['question'])}</h2>
                <span class="status status-{escape_html(question['status'])}">{escape_html(question['status'].replace('_', ' '))}</span>
              </summary>
              <p>{escape_html(question.get('description', ''))}</p>
              {body}
              {more_button}
              {render_resolved_section(question.get('resolved', []), known_titles, server_mode, csrf_token)}
            </details>
            """
        )
    mod_cards = []
    for item in items:
        if item.get("missing"):
            status_badge = '<span class="badge">archived</span>' if item.get("archived") else ""
            mod_cards.append(
                f"""
                <details class="mod-card missing" data-title="" data-id="{escape_html(item['publishedfileid'])}" data-category="missing" data-source="" data-confidence="" data-text="missing">
                  <summary><h3>Missing item {escape_html(item['publishedfileid'])}</h3>{status_badge}</summary>
                  <p>No cached metadata found. <a href="{item['url']}">Open Workshop page</a>.</p>
                </details>
                """
            )
            continue
        evidence_html = []
        for category in categories:
            entries = item["evidence"].get(category, [])
            if not entries:
                continue
            rows = []
            for entry in entries:
                rows.append(
                    f"""
                    <li class="evidence-row" data-title="{escape_html(item.get('title') or item['publishedfileid']).lower()}" data-id="{escape_html(item['publishedfileid'])}" data-category="{escape_html(category)}" data-source="{escape_html(entry['source_type'])}" data-confidence="{escape_html(entry['confidence'])}" data-text="{escape_html(entry['snippet']).lower()}">
                      <span class="badge">{escape_html(entry['source_type'])}</span>
                      <span class="badge">{escape_html(entry['confidence'])}</span>
                      <span class="badge">{escape_html(entry['term'])}</span>
                      <p>{linkify_text(entry['snippet'], known_titles)}</p>
                    </li>
                    """
                )
            evidence_html.append(f"<details><summary>{escape_html(category.replace('_', ' ').title())} ({len(entries)})</summary><ul>{''.join(rows)}</ul></details>")
        failures = "".join(
            f"<li><strong>{escape_html(failure['stage'])}</strong> {escape_html(failure['last_seen'])}: {escape_html(failure['message'])}</li>"
            for failure in item.get("failures", [])
        )
        failure_html = f"<details><summary>Sync failures ({len(item['failures'])})</summary><ul>{failures}</ul></details>" if item.get("failures") else ""
        status_badge = '<span class="badge">archived</span>' if item.get("archived") else ""
        mod_cards.append(
            f"""
            <details class="mod-card" data-title="{escape_html(item.get('title') or item['publishedfileid']).lower()}" data-id="{escape_html(item['publishedfileid'])}" data-category="{escape_html(' '.join(category for category in categories if item['evidence'].get(category)))}" data-source="" data-confidence="" data-text="{escape_html(' '.join(entry['snippet'] for entry in item.get('evidence_entries', []))).lower()}">
              <summary class="section-heading">
                <h3><a href="{item['url']}">{escape_html(item.get('title') or item['publishedfileid'])}</a></h3>
                <span><span class="workshop-id">{escape_html(item['publishedfileid'])}</span> {status_badge}</span>
              </summary>
              <dl>
                <div><dt>App ID</dt><dd>{escape_html(item.get('appid') or 'unknown')}</dd></div>
                <div><dt>Comments</dt><dd>{escape_html(item.get('comment_count'))}</dd></div>
                <div><dt>Last sync</dt><dd>{escape_html(item.get('last_metadata_sync'))}</dd></div>
              </dl>
              {failure_html}
              {''.join(evidence_html) if evidence_html else '<p class="empty">No configured evidence signals found.</p>'}
            </details>
            """
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape_html(title)}</title>
  <style>
    :root {{ color-scheme: light; --bg:#f7f8fa; --panel:#fff; --text:#1f2933; --muted:#5f6b7a; --border:#d8dee6; --accent:#2563eb; --warn:#b45309; --bad:#b91c1c; --good:#047857; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; background: var(--bg); color: var(--text); }}
    header {{ padding: 24px; background: #111827; color: #fff; }}
    header h1 {{ margin: 0 0 8px; font-size: 28px; }}
    header p {{ margin: 0; color: #cbd5e1; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .dashboard {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .stat, .panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 8px; }}
    .stat {{ padding: 14px; }}
    .stat span {{ display:block; color: var(--muted); font-size: 12px; }}
    .stat strong {{ display:block; font-size: 24px; margin-top: 4px; }}
    .filters {{ display: grid; grid-template-columns: 1fr repeat(3, minmax(140px, 180px)); gap: 10px; padding: 12px; margin-bottom: 16px; position: sticky; top: 0; z-index: 2; }}
    input, select {{ width: 100%; border: 1px solid var(--border); border-radius: 6px; padding: 8px; background: #fff; color: var(--text); }}
    .panel {{ padding: 16px; margin-bottom: 16px; }}
    .section-heading {{ display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }}
    h2 {{ margin: 0 0 8px; font-size: 19px; }}
    h3 {{ margin: 0; font-size: 16px; }}
    dl {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin: 10px 0; }}
    dt {{ color: var(--muted); font-size: 12px; }}
    dd {{ margin: 0; font-weight: 600; }}
    details {{ border-top: 1px solid var(--border); padding-top: 10px; margin-top: 10px; }}
    details.panel {{ border-top: 1px solid var(--border); }}
    details.mod-card {{ border: 1px solid var(--border); border-radius: 6px; padding: 12px; margin: 8px 0; background: #fbfcfe; }}
    summary {{ cursor:pointer; font-weight: 700; }}
    ul {{ padding-left: 18px; }}
    .evidence-row {{ border: 1px solid var(--border); border-radius: 6px; padding: 10px; margin: 8px 0; background: #fbfcfe; }}
    .row-meta {{ display:flex; flex-wrap:wrap; gap: 8px; align-items:center; color: var(--muted); }}
    .badge, .status, .workshop-id {{ display:inline-block; border:1px solid var(--border); border-radius:999px; padding:2px 8px; font-size:12px; color: var(--muted); background:#fff; }}
    .status-attention, .status-between_selected_mods {{ color: var(--bad); border-color:#fecaca; background:#fff1f2; }}
    .status-uncertain {{ color: var(--warn); border-color:#fed7aa; background:#fff7ed; }}
    .status-evidence_found, .status-fulfilled {{ color: var(--good); border-color:#bbf7d0; background:#f0fdf4; }}
    .empty {{ color: var(--muted); }}
    .muted, .resolver {{ color: var(--muted); }}
    .actions {{ background:#fff; border:1px dashed var(--border); border-radius:6px; padding:8px; }}
    .actions button, .resolved-section button {{ border:1px solid var(--border); border-radius:6px; padding:7px 10px; background:#fff; color:var(--accent); cursor:pointer; }}
    .actions button[disabled] {{ color:var(--muted); cursor:not-allowed; }}
    .resolved-section {{ background:#f8fafc; border:1px solid var(--border); border-radius:6px; padding:10px; }}
    .resolved-row {{ opacity:.85; }}
    .hidden {{ display:none !important; }}
    .hidden-clean {{ }}
    .hidden-overflow {{ display:none; }}
    .show-more {{ border:1px solid var(--border); border-radius:6px; padding:7px 10px; background:#fff; color:var(--accent); cursor:pointer; }}
    @media (max-width: 760px) {{ .filters {{ grid-template-columns: 1fr; position: static; }} header {{ padding: 18px; }} main {{ padding: 12px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{escape_html(title)}</h1>
    <p>Local cached Steam Workshop metadata, descriptions, and comments. Links open Steam Workshop pages.</p>
  </header>
  <main>
    <section class="dashboard">
      <div class="stat"><span>Total mods</span><strong>{len(items)}</strong></div>
      <div class="stat"><span>Missing mods</span><strong>{missing_count}</strong></div>
      <div class="stat"><span>Sync failures</span><strong>{failure_count}</strong></div>
      <div class="stat"><span>Cached comments</span><strong>{comment_count}</strong></div>
      {count_cards}
    </section>
    <section class="panel filters">
      <input id="search" type="search" placeholder="Search title, ID, or evidence">
      <select id="category"><option value="">All categories</option>{category_options}</select>
      <select id="source"><option value="">All sources</option><option value="description">Description</option><option value="comment">Comment</option></select>
      <select id="confidence"><option value="">All confidence</option><option value="direct">Direct</option><option value="reported">Reported</option></select>
      <label class="toggle"><input id="showClean" type="checkbox"> Show no-evidence sections</label>
    </section>
    {''.join(question_sections)}
    <details class="panel mod-details">
      <summary><h2>Mod Details</h2></summary>
      {''.join(mod_cards)}
    </details>
    <p id="emptyState" class="empty hidden">No visible report items match the current filters.</p>
  </main>
  <script>
    const controls = ['search', 'category', 'source', 'confidence', 'showClean'].map(id => document.getElementById(id));
    function matches(el) {{
      const text = document.getElementById('search').value.trim().toLowerCase();
      const category = document.getElementById('category').value;
      const source = document.getElementById('source').value;
      const confidence = document.getElementById('confidence').value;
      const haystack = [el.dataset.title, el.dataset.id, el.dataset.text].join(' ');
      return (!text || haystack.includes(text)) &&
        (!category || (el.dataset.category || '').includes(category)) &&
        (!source || (el.dataset.source || '').includes(source)) &&
        (!confidence || (el.dataset.confidence || '').includes(confidence));
    }}
    function applyFilters() {{
      document.querySelectorAll('.evidence-row').forEach(el => {{
        el.classList.toggle('hidden', !matches(el));
      }});
      document.querySelectorAll('.hidden-clean').forEach(el => {{
        el.classList.toggle('hidden', !document.getElementById('showClean').checked);
      }});
      document.querySelectorAll('.question').forEach(section => {{
        const rows = Array.from(section.querySelectorAll(':scope > .evidence-row'));
        const hasVisibleRows = rows.some(row => !row.classList.contains('hidden'));
        const isClean = section.classList.contains('no-evidence');
        const showClean = document.getElementById('showClean').checked;
        section.classList.toggle('hidden', (!hasVisibleRows && !isClean) || (isClean && !showClean));
      }});
      let visibleModCards = 0;
      document.querySelectorAll('.mod-card').forEach(card => {{
        const cardOwnMatch = matches(card);
        const rows = Array.from(card.querySelectorAll('.evidence-row'));
        const hasVisibleRows = rows.length ? rows.some(row => !row.classList.contains('hidden')) : cardOwnMatch;
        const visible = rows.length ? hasVisibleRows : cardOwnMatch;
        card.classList.toggle('hidden', !visible);
        if (visible) visibleModCards += 1;
      }});
      document.getElementById('emptyState').classList.toggle('hidden', visibleModCards > 0);
    }}
    controls.forEach(control => {{
      control.addEventListener('input', applyFilters);
      control.addEventListener('change', applyFilters);
    }});
    document.querySelectorAll('.show-more').forEach(button => {{
      button.addEventListener('click', () => {{
        const section = button.closest('details');
        section.querySelectorAll('.hidden-overflow').forEach(row => row.classList.remove('hidden-overflow'));
        button.remove();
      }});
    }});
    document.querySelectorAll('.resolve-button').forEach(button => {{
      button.addEventListener('click', async () => {{
        const action = button.closest('.actions');
        const note = action.querySelector('.resolve-note')?.value || '';
        const payload = {{
          fingerprint: button.dataset.fingerprint,
          item_id: button.dataset.itemId,
          question_id: button.dataset.questionId,
          category: button.dataset.category,
          source_type: button.dataset.sourceType,
          source_key: button.dataset.sourceKey,
          snippet: button.dataset.snippet,
          csrf_token: button.dataset.csrfToken,
          note
        }};
        const response = await fetch('/api/resolve', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify(payload) }});
        if (response.ok) location.reload();
      }});
    }});
    document.querySelectorAll('.unresolve-button').forEach(button => {{
      button.addEventListener('click', async () => {{
        const response = await fetch('/api/unresolve', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{fingerprint: button.dataset.fingerprint, csrf_token: button.dataset.csrfToken}}) }});
        if (response.ok) location.reload();
      }});
    }});
    applyFilters();
  </script>
</body>
</html>
"""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", help="Comma, space, or newline-delimited Workshop IDs.")
    parser.add_argument("--input", type=Path, help="Text or JSON file containing Workshop IDs.")
    parser.add_argument("--list", dest="list_name", help="Report on active items in a named saved modlist.")
    parser.add_argument("--include-archived", action="store_true", help="Include archived items when reporting with --list.")
    parser.add_argument("--all", action="store_true", help="Report on every cached item.")
    parser.add_argument("--db", type=Path, default=default_db_path(), help=f"SQLite DB path. Default: {DEFAULT_DB}")
    parser.add_argument("--format", choices=("markdown", "json", "html"), help="Output format. Template default is used when omitted with --check.")
    parser.add_argument("--output", type=Path, help="Write report output to this path instead of stdout.")
    parser.add_argument("--open", action="store_true", help="Open an HTML --output file or --serve URL in the default browser.")
    parser.add_argument("--serve", action="store_true", help="Run a local report server with persistent resolved-state controls.")
    parser.add_argument("--host", default=DEFAULT_SERVE_HOST, help=f"Local server host for --serve. Default: {DEFAULT_SERVE_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_SERVE_PORT, help=f"Local server port for --serve. Default: {DEFAULT_SERVE_PORT}")
    parser.add_argument("--check", choices=sorted(load_templates().keys()), help="Named report template to run.")
    parser.add_argument("--category", action="append", choices=DEFAULT_CATEGORIES, help="Restrict report to one or more evidence categories.")
    return parser.parse_args(argv)


def write_output(content: str, output: Path | None) -> None:
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")


def build_report_from_args(args: argparse.Namespace, template: dict[str, Any] | None) -> dict[str, Any]:
    conn = connect_db(args.db)
    try:
        init_report_schema(conn)
        item_ids = collect_ids(conn, args)
        if not item_ids:
            raise SystemExit("No item IDs selected. Use --ids, --input, --list, or --all.")
        categories = selected_categories(args, template)
        return fetch_report(conn, item_ids, categories, args.check, template, collect_membership_status(conn, args))
    finally:
        conn.close()


class ReportRequestHandler(http.server.BaseHTTPRequestHandler):
    server_version = "steam-workshop-utils/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}", file=sys.stderr)

    def send_text(self, status: int, content: str, content_type: str) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        self.send_text(status, json.dumps(payload, ensure_ascii=False), "application/json")

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            report = build_report_from_args(self.server.report_args, self.server.report_template)
            self.send_text(200, render_html(report, server_mode=True, csrf_token=self.server.csrf_token), "text/html")
            return
        if parsed.path == "/api/report":
            report = build_report_from_args(self.server.report_args, self.server.report_template)
            self.send_json(200, report)
            return
        self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        try:
            payload = self.read_json()
            self.server.validate_csrf(payload)
            conn = connect_db(self.server.report_args.db)
            try:
                init_report_schema(conn)
                if parsed.path == "/api/resolve":
                    self.server.validate_report_fingerprint(payload, "active")
                    result = record_manual_resolution(conn, payload)
                    self.send_json(200, {"ok": True, **result})
                    return
                if parsed.path == "/api/unresolve":
                    self.server.validate_report_fingerprint(payload, "manual")
                    clear_manual_resolution(conn, str(payload.get("fingerprint") or ""))
                    self.send_json(200, {"ok": True})
                    return
            finally:
                conn.close()
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
            return
        self.send_json(404, {"error": "not found"})


class ReportServer(http.server.ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler: type[ReportRequestHandler], args: argparse.Namespace, template: dict[str, Any] | None):
        super().__init__(server_address, handler)
        self.report_args = args
        self.report_template = template
        self.csrf_token = secrets.token_urlsafe(24)

    def validate_csrf(self, payload: dict[str, Any]) -> None:
        if str(payload.get("csrf_token") or "") != self.csrf_token:
            raise ValueError("invalid csrf token")

    def validate_report_fingerprint(self, payload: dict[str, Any], scope: str) -> None:
        fingerprint = str(payload.get("fingerprint") or "")
        report = build_report_from_args(self.report_args, self.report_template)
        fingerprints = report_fingerprints(report, scope)
        if fingerprint not in fingerprints:
            raise ValueError("fingerprint is not part of the current report")


def report_fingerprints(report: dict[str, Any], scope: str = "active") -> set[str]:
    fingerprints: set[str] = set()
    for question in report.get("questions", []):
        if scope in {"active", "all"}:
            fingerprints.update(str(entry.get("fingerprint") or "") for entry in question.get("evidence", []))
        if scope in {"manual", "all"}:
            fingerprints.update(
                str(entry.get("fingerprint") or "")
                for entry in question.get("resolved", [])
                if entry.get("resolved_reason") == "manual"
            )
    return {fingerprint for fingerprint in fingerprints if fingerprint}


def serve_report(args: argparse.Namespace, template: dict[str, Any] | None) -> int:
    server = ReportServer((args.host, args.port), ReportRequestHandler, args, template)
    url = f"http://{server.server_address[0]}:{server.server_address[1]}/"
    print(f"Serving Steam Workshop report at {url}")
    print("Press Ctrl+C to stop.")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    templates = load_templates()
    template = templates.get(args.check) if args.check else None
    output_format = resolve_format(args, template)
    if args.serve:
        if output_format != "html":
            raise SystemExit("--serve requires HTML output. Omit --format or use --format html.")
        if args.host != DEFAULT_SERVE_HOST:
            raise SystemExit("--serve only supports binding to 127.0.0.1.")
        return serve_report(args, template)
    if args.open and (output_format != "html" or not args.output):
        raise SystemExit("--open requires --format html and --output.")
    report = build_report_from_args(args, template)
    if output_format == "json":
        content = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    elif output_format == "html":
        content = render_html(report, server_mode=False)
    else:
        content = render_markdown(report)
    write_output(content, args.output)
    if args.open and args.output:
        webbrowser.open(args.output.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
