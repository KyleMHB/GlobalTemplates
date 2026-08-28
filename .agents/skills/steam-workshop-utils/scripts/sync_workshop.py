#!/usr/bin/env python3
"""Sync Steam Workshop metadata and public comments into a local SQLite DB."""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

APP_NAME = "steam-workshop-utils"
DEFAULT_DB = Path.home() / ".codex" / "data" / "steam-workshop" / "steam-workshop.sqlite"
DETAILS_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
COLLECTION_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"
COMMENTS_URL = "https://steamcommunity.com/comment/PublishedFile_Public/render/{creator_id}/{item_id}/"
USER_AGENT = "steam-workshop-utils/1.0 (+https://steamcommunity.com/)"
MAX_METADATA_BATCH = 100
STALE_AFTER = timedelta(hours=24)

PERFORMANCE_POSITIVE_RE = re.compile(
    r"\b(reduces? lag|no performance impact|minimal performance impact|minor performance impact|"
    r"performance friendly|improves? fps|better fps|less lag|optimized|optimised)\b",
    re.I,
)
NEGATIVE_COMPATIBILITY_PREFIX_RE = re.compile(
    r"\b(not|doesn't|does not|isn't|is not|incompatible|partially)\s*$",
    re.I,
)

EVIDENCE_PATTERNS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "incompatibility": [
        ("incompatible", re.compile(r"\b(incompatible|not compatible|conflicts? with|breaks with|does not work with)\b", re.I)),
        ("compatibility", re.compile(r"\b(compatib(?:le|ility)|conflict)\b", re.I)),
    ],
    "multiplayer": [
        ("multiplayer", re.compile(r"\b(multiplayer|multi-player|mp compatible|works in mp|server|dedicated server|co-?op)\b", re.I)),
        ("singleplayer_only", re.compile(r"\b(singleplayer only|not multiplayer|not mp|does not work in multiplayer)\b", re.I)),
    ],
    "dependencies": [
        ("dependency", re.compile(r"\b(requires?|dependencies|dependency|load before|load after|must be loaded|requires .{0,80}mod)\b", re.I)),
    ],
    "version": [
        ("version", re.compile(r"\b(build\s*\d+|version\s*\d+(?:\.\d+)*|game version|updated for|supports\s+\d+(?:\.\d+)*)\b", re.I)),
    ],
    "errors": [
        ("error", re.compile(r"\b(error|exception|crash(?:es|ed|ing)?|bug|broken|log spam|stack trace|red error|doesn't work|does not work)\b", re.I)),
    ],
    "load_order": [
        ("load_order", re.compile(r"\b(load order|load before|load after|above .{0,40}below|below .{0,40}above)\b", re.I)),
    ],
    "overlap": [
        (
            "overlap",
            re.compile(
                r"\b(overlaps? with|overlapping (?:features?|functionality)|redundant with|duplicate[sd]? "
                r"(?:features?|functionality)|does the same thing as|both mods? (?:change|modify|add))\b",
                re.I,
            ),
        ),
    ],
    "compatibility": [
        (
            "compatible",
            re.compile(
                r"\b(works? (?:well )?(?:with|alongside)|compatible with|compatibility (?:patch|support)|"
                r"supported alongside|integrates? with|integration with)\b",
                re.I,
            ),
        ),
    ],
    "alternatives": [
        ("alternative", re.compile(r"\b(use .{1,80} instead|replacement|replace(?:s|d)? by|try .{1,80} instead|better alternative|alternative to)\b", re.I)),
    ],
    "performance": [
        (
            "performance_problem",
            re.compile(
                r"\b(lags? the game|heavy lag|bad performance|fps drops?|frame drops?|stutter(?:ing)?|"
                r"slowdown|memory leak|causes? lag|performance issue|performance problem|high memory|tps drops?|"
                r"heavy mod)\b",
                re.I,
            ),
        ),
    ],
    "sentiment_negative": [
        ("negative_sentiment", re.compile(r"\b(terrible|awful|bad mod|broken mod|unusable|do not use|don't use|not worth|avoid this|abandoned|outdated|disappointed|worse than|trash|garbage)\b", re.I)),
    ],
    "resolved": [
        (
            "resolved",
            re.compile(
                r"\b(fixed|resolved|works now|working now|no longer crashes|no longer broken|patched|"
                r"issue is gone|problem is gone|fixed in update|author fixed)\b",
                re.I,
            ),
        ),
    ],
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def get_text(self) -> str:
        return " ".join(self.parts)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_db_path() -> Path:
    return Path(os.environ.get("STEAM_WORKSHOP_DB", DEFAULT_DB)).expanduser()


def parse_ids_text(text: str) -> list[str]:
    ids = re.findall(r"\b\d{5,}\b", text)
    return dedupe(ids)


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = str(value).strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def extract_id_from_url(value: str) -> str | None:
    parsed = urllib.parse.urlparse(value)
    params = urllib.parse.parse_qs(parsed.query)
    ids = params.get("id") or params.get("publishedfileid")
    return ids[0] if ids else None


def load_ids_from_json(value: Any) -> list[str]:
    if isinstance(value, list):
        return dedupe(str(item) for item in value if str(item).strip().isdigit())
    if isinstance(value, dict):
        candidates: list[str] = []
        for key in ("ids", "workshop_ids", "publishedfileids", "publishedfile_ids", "mods"):
            if key in value:
                candidates.extend(load_ids_from_json(value[key]))
        for key in ("id", "workshop_id", "publishedfileid", "publishedfile_id"):
            if key in value and str(value[key]).strip().isdigit():
                candidates.append(str(value[key]).strip())
        return dedupe(candidates)
    return []


def load_ids_from_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    with contextlib.suppress(json.JSONDecodeError):
        ids = load_ids_from_json(json.loads(text))
        if ids:
            return ids
    return parse_ids_text(text)


def request_json(url: str, data: dict[str, Any] | None = None, retries: int = 3, delay: float = 1.0) -> dict[str, Any]:
    encoded = None
    headers = {"User-Agent": USER_AGENT}
    if data is not None:
        encoded = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, data=encoded, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8", errors="replace")
            return json.loads(body)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(delay * (2**attempt))
    raise RuntimeError(f"request failed for {url}: {last_error}")


def fetch_details(ids: list[str], api_key: str | None) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for offset in range(0, len(ids), MAX_METADATA_BATCH):
        batch = ids[offset : offset + MAX_METADATA_BATCH]
        data: dict[str, Any] = {"itemcount": len(batch)}
        if api_key:
            data["key"] = api_key
        for index, item_id in enumerate(batch):
            data[f"publishedfileids[{index}]"] = item_id
        response = request_json(DETAILS_URL, data)
        details.extend(response.get("response", {}).get("publishedfiledetails", []))
    return details


def fetch_collection_children(collection_id: str, api_key: str | None) -> list[str]:
    data: dict[str, Any] = {"collectioncount": 1, "publishedfileids[0]": collection_id}
    if api_key:
        data["key"] = api_key
    response = request_json(COLLECTION_URL, data)
    details = response.get("response", {}).get("collectiondetails", [])
    if not details:
        return []
    children = details[0].get("children", []) or []
    return dedupe(str(child.get("publishedfileid")) for child in children if child.get("publishedfileid"))


def strip_html(value: str) -> str:
    parser = TextExtractor()
    parser.feed(html.unescape(value or ""))
    return re.sub(r"\s+", " ", parser.get_text()).strip()


def split_comment_fragments(comments_html: str) -> list[str]:
    if not comments_html:
        return []
    chunks = re.split(r'<div[^>]+class="[^"]*commentthread_comment[^"]*"[^>]*>', comments_html)
    fragments = chunks[1:] if len(chunks) > 1 else [comments_html]
    texts: list[str] = []
    for fragment in fragments:
        text = strip_html(fragment)
        text = re.sub(r"\bReply\b.*$", "", text).strip()
        if len(text) >= 3:
            texts.append(text)
    return texts


def fetch_comments(item_id: str, creator_id: str, limit: int) -> list[dict[str, Any]]:
    params = {
        "start": 0,
        "count": limit,
        "l": "english",
        "feature2": -1,
    }
    url = f"{COMMENTS_URL.format(creator_id=creator_id, item_id=item_id)}?{urllib.parse.urlencode(params)}"
    response = request_json(url, None, retries=2, delay=2.0)
    comments_html = response.get("comments_html", "")
    comments: list[dict[str, Any]] = []
    for index, text in enumerate(split_comment_fragments(comments_html)[:limit]):
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        digest = hashlib.sha256(f"{item_id}:{normalized}".encode("utf-8")).hexdigest()[:20]
        comments.append(
            {
                "comment_key": digest,
                "item_id": item_id,
                "position": index,
                "text": text,
                "raw_html": "",
            }
        )
    return comments


def connect_db(path: Path, create: bool = True) -> sqlite3.Connection:
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
        target = str(path)
    elif path.exists():
        target = f"file:{path.resolve()}?mode=ro"
    else:
        target = ":memory:"
    conn = sqlite3.connect(target, uri=target.startswith("file:"))
    conn.row_factory = sqlite3.Row
    if create:
        conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workshop_items (
            publishedfileid TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            creator TEXT,
            appid INTEGER,
            file_size INTEGER,
            time_created INTEGER,
            time_updated INTEGER,
            subscriptions INTEGER,
            favorited INTEGER,
            tags_json TEXT,
            raw_json TEXT NOT NULL,
            last_metadata_sync TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS collections (
            collection_id TEXT NOT NULL,
            child_id TEXT NOT NULL,
            last_sync TEXT NOT NULL,
            PRIMARY KEY (collection_id, child_id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            publishedfileid TEXT NOT NULL,
            comment_key TEXT NOT NULL,
            position INTEGER NOT NULL,
            text TEXT NOT NULL,
            raw_html TEXT,
            last_seen TEXT NOT NULL,
            PRIMARY KEY (publishedfileid, comment_key)
        );

        CREATE INDEX IF NOT EXISTS idx_comments_item ON comments (publishedfileid, position);

        CREATE TABLE IF NOT EXISTS evidence (
            publishedfileid TEXT NOT NULL,
            category TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_key TEXT NOT NULL,
            term TEXT NOT NULL,
            snippet TEXT NOT NULL,
            confidence TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            PRIMARY KEY (publishedfileid, category, source_type, source_key, term, snippet)
        );

        CREATE TABLE IF NOT EXISTS sync_failures (
            publishedfileid TEXT NOT NULL,
            stage TEXT NOT NULL,
            message TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            PRIMARY KEY (publishedfileid, stage)
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

        CREATE INDEX IF NOT EXISTS idx_modlist_items_status ON modlist_items (list_name, status, publishedfileid);
        """
    )
    conn.commit()


def upsert_item(conn: sqlite3.Connection, detail: dict[str, Any]) -> None:
    item_id = str(detail.get("publishedfileid", "")).strip()
    if not item_id:
        return
    tags = detail.get("tags") or []
    conn.execute(
        """
        INSERT INTO workshop_items (
            publishedfileid, title, description, creator, appid, file_size,
            time_created, time_updated, subscriptions, favorited, tags_json,
            raw_json, last_metadata_sync
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(publishedfileid) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            creator = excluded.creator,
            appid = excluded.appid,
            file_size = excluded.file_size,
            time_created = excluded.time_created,
            time_updated = excluded.time_updated,
            subscriptions = excluded.subscriptions,
            favorited = excluded.favorited,
            tags_json = excluded.tags_json,
            raw_json = excluded.raw_json,
            last_metadata_sync = excluded.last_metadata_sync
        """,
        (
            item_id,
            detail.get("title"),
            detail.get("description"),
            detail.get("creator"),
            int(detail.get("consumer_app_id") or detail.get("creator_app_id") or 0),
            int(detail.get("file_size") or 0),
            int(detail.get("time_created") or 0),
            int(detail.get("time_updated") or 0),
            int(detail.get("subscriptions") or 0),
            int(detail.get("favorited") or 0),
            json.dumps(tags, ensure_ascii=False),
            json.dumps(detail, ensure_ascii=False),
            now_iso(),
        ),
    )


def upsert_comments(conn: sqlite3.Connection, item_id: str, comments: list[dict[str, Any]], limit: int) -> None:
    timestamp = now_iso()
    retained_keys: set[str] = set()
    for comment in comments[:limit]:
        retained_keys.add(comment["comment_key"])
        conn.execute(
            """
            INSERT INTO comments (publishedfileid, comment_key, position, text, raw_html, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(publishedfileid, comment_key) DO UPDATE SET
                position = excluded.position,
                text = excluded.text,
                raw_html = excluded.raw_html,
                last_seen = excluded.last_seen
            """,
            (
                item_id,
                comment["comment_key"],
                int(comment["position"]),
                comment["text"],
                comment.get("raw_html", ""),
                timestamp,
            ),
        )
    if retained_keys:
        placeholders = ",".join("?" for _ in retained_keys)
        conn.execute(
            f"DELETE FROM comments WHERE publishedfileid = ? AND comment_key NOT IN ({placeholders})",
            (item_id, *retained_keys),
        )
    else:
        conn.execute("DELETE FROM comments WHERE publishedfileid = ?", (item_id,))


def record_failure(conn: sqlite3.Connection, item_id: str, stage: str, message: str) -> None:
    conn.execute(
        """
        INSERT INTO sync_failures (publishedfileid, stage, message, last_seen)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(publishedfileid, stage) DO UPDATE SET
            message = excluded.message,
            last_seen = excluded.last_seen
        """,
        (item_id, stage, message[:1000], now_iso()),
    )


def snippet_around(text: str, start: int, end: int, radius: int = 120) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = re.sub(r"\s+", " ", text[left:right]).strip()
    if left:
        snippet = "..." + snippet
    if right < len(text):
        snippet += "..."
    return snippet


def extract_evidence_for_text(item_id: str, source_type: str, source_key: str, text: str) -> list[tuple[str, str, str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    if not text:
        return rows
    for category, patterns in EVIDENCE_PATTERNS.items():
        for term, pattern in patterns:
            for match in pattern.finditer(text):
                if category == "compatibility" and NEGATIVE_COMPATIBILITY_PREFIX_RE.search(text[max(0, match.start() - 24) : match.start()]):
                    continue
                confidence = "direct" if source_type == "description" else "reported"
                snippet = snippet_around(text, match.start(), match.end())
                if category == "performance" and PERFORMANCE_POSITIVE_RE.search(snippet):
                    continue
                rows.append(
                    (
                        item_id,
                        category,
                        source_type,
                        source_key,
                        term,
                        snippet,
                        confidence,
                    )
                )
                break
    return rows


def refresh_evidence(conn: sqlite3.Connection, item_ids: list[str]) -> None:
    timestamp = now_iso()
    for item_id in item_ids:
        conn.execute("DELETE FROM evidence WHERE publishedfileid = ?", (item_id,))
        item = conn.execute("SELECT description FROM workshop_items WHERE publishedfileid = ?", (item_id,)).fetchone()
        rows: list[tuple[str, str, str, str, str, str, str]] = []
        if item:
            rows.extend(extract_evidence_for_text(item_id, "description", item_id, item["description"] or ""))
        for comment in conn.execute(
            "SELECT comment_key, text FROM comments WHERE publishedfileid = ? ORDER BY position ASC",
            (item_id,),
        ):
            rows.extend(extract_evidence_for_text(item_id, "comment", comment["comment_key"], comment["text"] or ""))
        for row in rows:
            conn.execute(
                """
                INSERT OR IGNORE INTO evidence (
                    publishedfileid, category, source_type, source_key, term, snippet, confidence, last_seen
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*row, timestamp),
            )


def collect_comment_targets(conn: sqlite3.Connection, item_ids: list[str]) -> tuple[dict[str, str], list[str]]:
    targets: dict[str, str] = {}
    missing_creator: list[str] = []
    for item_id in item_ids:
        row = conn.execute("SELECT creator FROM workshop_items WHERE publishedfileid = ?", (item_id,)).fetchone()
        creator_id = str(row["creator"]).strip() if row and row["creator"] is not None else ""
        if creator_id:
            targets[item_id] = creator_id
        else:
            missing_creator.append(item_id)
    return targets, missing_creator


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    with contextlib.suppress(ValueError):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def is_metadata_stale(conn: sqlite3.Connection, item_id: str, stale_after: timedelta = STALE_AFTER) -> bool:
    row = conn.execute("SELECT last_metadata_sync FROM workshop_items WHERE publishedfileid = ?", (item_id,)).fetchone()
    if not row:
        return True
    last_sync = parse_timestamp(row["last_metadata_sync"])
    if not last_sync:
        return True
    if last_sync.tzinfo is None:
        last_sync = last_sync.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last_sync > stale_after


def ensure_modlist(conn: sqlite3.Connection, list_name: str) -> None:
    timestamp = now_iso()
    conn.execute(
        """
        INSERT INTO modlists (name, created_at, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET updated_at = excluded.updated_at
        """,
        (list_name, timestamp, timestamp),
    )


def load_modlist_members(conn: sqlite3.Connection, list_name: str) -> dict[str, str]:
    if not table_exists(conn, "modlist_items"):
        return {}
    rows = conn.execute(
        "SELECT publishedfileid, status FROM modlist_items WHERE list_name = ?",
        (list_name,),
    ).fetchall()
    return {row["publishedfileid"]: row["status"] for row in rows}


def item_titles(conn: sqlite3.Connection, item_ids: Iterable[str]) -> dict[str, str]:
    ids = dedupe(item_ids)
    if not ids or not table_exists(conn, "workshop_items"):
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT publishedfileid, title FROM workshop_items WHERE publishedfileid IN ({placeholders})",
        ids,
    ).fetchall()
    return {row["publishedfileid"]: row["title"] or row["publishedfileid"] for row in rows}


def diff_modlist(conn: sqlite3.Connection, list_name: str, current_ids: list[str]) -> dict[str, Any]:
    members = load_modlist_members(conn, list_name)
    active = {item_id for item_id, status in members.items() if status == "active"}
    archived = {item_id for item_id, status in members.items() if status == "archived"}
    current = set(current_ids)
    added = [item_id for item_id in current_ids if item_id not in active]
    restored = [item_id for item_id in added if item_id in archived]
    removed = sorted(active - current, key=lambda value: int(value) if value.isdigit() else value)
    unchanged = [item_id for item_id in current_ids if item_id in active]
    missing_metadata = [
        item_id
        for item_id in current_ids
        if not table_exists(conn, "workshop_items") or not conn.execute("SELECT 1 FROM workshop_items WHERE publishedfileid = ?", (item_id,)).fetchone()
    ]
    titles = item_titles(conn, [*added, *removed, *unchanged])
    return {
        "list": list_name,
        "added": [{"id": item_id, "title": titles.get(item_id, item_id), "restored": item_id in restored} for item_id in added],
        "removed": [{"id": item_id, "title": titles.get(item_id, item_id)} for item_id in removed],
        "unchanged": [{"id": item_id, "title": titles.get(item_id, item_id)} for item_id in unchanged],
        "missing_metadata": [{"id": item_id, "title": titles.get(item_id, item_id)} for item_id in missing_metadata],
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "unchanged": len(unchanged),
            "missing_metadata": len(missing_metadata),
            "restored": len(restored),
        },
    }


def apply_modlist_diff(conn: sqlite3.Connection, list_name: str, current_ids: list[str], removed_ids: list[str]) -> None:
    ensure_modlist(conn, list_name)
    timestamp = now_iso()
    for item_id in current_ids:
        conn.execute(
            """
            INSERT INTO modlist_items (list_name, publishedfileid, status, first_seen, last_seen, archived_at)
            VALUES (?, ?, 'active', ?, ?, NULL)
            ON CONFLICT(list_name, publishedfileid) DO UPDATE SET
                status = 'active',
                last_seen = excluded.last_seen,
                archived_at = NULL
            """,
            (list_name, item_id, timestamp, timestamp),
        )
    for item_id in removed_ids:
        conn.execute(
            """
            UPDATE modlist_items
            SET status = 'archived', last_seen = ?, archived_at = COALESCE(archived_at, ?)
            WHERE list_name = ? AND publishedfileid = ? AND status = 'active'
            """,
            (timestamp, timestamp, list_name, item_id),
        )
    conn.commit()


def archived_ids_for_list(conn: sqlite3.Connection, list_name: str) -> list[str]:
    if not table_exists(conn, "modlist_items"):
        return []
    return [
        row["publishedfileid"]
        for row in conn.execute(
            "SELECT publishedfileid FROM modlist_items WHERE list_name = ? AND status = 'archived' ORDER BY publishedfileid",
            (list_name,),
        )
    ]


def purge_archived_items(conn: sqlite3.Connection, list_name: str, item_ids: list[str]) -> None:
    for item_id in item_ids:
        conn.execute("DELETE FROM modlist_items WHERE list_name = ? AND publishedfileid = ? AND status = 'archived'", (list_name, item_id))
        conn.execute("DELETE FROM comments WHERE publishedfileid = ?", (item_id,))
        conn.execute("DELETE FROM evidence WHERE publishedfileid = ?", (item_id,))
        conn.execute("DELETE FROM sync_failures WHERE publishedfileid = ?", (item_id,))
        conn.execute("DELETE FROM collections WHERE collection_id = ? OR child_id = ?", (item_id, item_id))
        conn.execute("DELETE FROM workshop_items WHERE publishedfileid = ?", (item_id,))
        if table_exists(conn, "resolved_evidence"):
            conn.execute("DELETE FROM resolved_evidence WHERE publishedfileid = ?", (item_id,))
    conn.commit()


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone()
    return row is not None


def parse_args(argv: list[str]) -> argparse.Namespace:
    if argv and argv[0] in {"resync", "purge-archived"}:
        parser = argparse.ArgumentParser(description=__doc__)
        subparsers = parser.add_subparsers(dest="command", required=True)

        resync = subparsers.add_parser("resync", help="Diff a supplied current mod set against a named saved modlist.")
        add_input_args(resync)
        add_common_args(resync)
        resync.add_argument("--list", required=True, dest="list_name", help="Named modlist to diff and update.")
        resync.add_argument("--apply", action="store_true", help="Persist the diff and refresh added/stale active mods.")
        resync.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")

        purge = subparsers.add_parser("purge-archived", help="Permanently delete archived entries for a named modlist.")
        purge.add_argument("--list", required=True, dest="list_name", help="Named modlist whose archived entries should be purged.")
        purge.add_argument("--db", type=Path, default=default_db_path(), help=f"SQLite DB path. Default: {DEFAULT_DB}")
        purge.add_argument("--apply", action="store_true", help="Perform deletion. Omit for preview.")
        purge.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
        return parser.parse_args(argv)

    parser = argparse.ArgumentParser(description=__doc__)
    add_input_args(parser)
    add_common_args(parser)
    parser.set_defaults(command="sync", apply=True, format="json", list_name=None)
    return parser.parse_args(argv)


def add_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ids", help="Comma, space, or newline-delimited Workshop IDs.")
    parser.add_argument("--input", type=Path, help="Text or JSON file containing Workshop IDs.")
    parser.add_argument("--collection-url", action="append", default=[], help="Steam collection URL to expand.")
    parser.add_argument("--collection-id", action="append", default=[], help="Steam collection ID to expand.")


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, default=default_db_path(), help=f"SQLite DB path. Default: {DEFAULT_DB}")
    parser.add_argument("--comments-limit", type=int, default=10, help="Newest public comments to retain per item.")
    parser.add_argument("--skip-comments", action="store_true", help="Sync metadata only.")
    parser.add_argument("--workers", type=int, default=4, help="Comment fetch worker count.")
    parser.add_argument("--api-key", default=os.environ.get("STEAM_WEB_API_KEY"), help="Steam Web API key. Defaults to STEAM_WEB_API_KEY.")


def collect_requested_ids(args: argparse.Namespace) -> tuple[list[str], dict[str, list[str]]]:
    ids: list[str] = []
    collections: dict[str, list[str]] = {}
    api_key = args.api_key
    if args.ids:
        ids.extend(parse_ids_text(args.ids))
    if args.input:
        ids.extend(load_ids_from_file(args.input))
    collection_ids = list(args.collection_id)
    for url in args.collection_url:
        item_id = extract_id_from_url(url)
        if item_id:
            collection_ids.append(item_id)
    for collection_id in dedupe(collection_ids):
        children = fetch_collection_children(collection_id, api_key)
        collections[collection_id] = children
        ids.extend(children)
    return dedupe(ids), collections


def sync_items(conn: sqlite3.Connection, ids: list[str], collections: dict[str, list[str]], args: argparse.Namespace) -> dict[str, Any]:
    for collection_id, children in collections.items():
        for child_id in children:
            conn.execute(
                "INSERT OR REPLACE INTO collections (collection_id, child_id, last_sync) VALUES (?, ?, ?)",
                (collection_id, child_id, now_iso()),
            )
    metadata_failures = 0
    try:
        for detail in fetch_details(ids, args.api_key):
            item_id = str(detail.get("publishedfileid", ""))
            if detail.get("result") not in (1, "1", None):
                metadata_failures += 1
                record_failure(conn, item_id or "unknown", "metadata", f"Steam result {detail.get('result')}")
                continue
            upsert_item(conn, detail)
    except Exception as exc:
        for item_id in ids:
            record_failure(conn, item_id, "metadata", str(exc))
        metadata_failures += len(ids)
    conn.commit()

    comment_failures = 0
    if not args.skip_comments and args.comments_limit:
        comment_targets, missing_creator_ids = collect_comment_targets(conn, ids)
        for item_id in missing_creator_ids:
            comment_failures += 1
            record_failure(conn, item_id, "comments", "Missing creator SteamID; cannot fetch Steam Community comments.")
        conn.commit()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            future_map = {
                executor.submit(fetch_comments, item_id, creator_id, args.comments_limit): item_id
                for item_id, creator_id in comment_targets.items()
            }
            for future in concurrent.futures.as_completed(future_map):
                item_id = future_map[future]
                try:
                    comments = future.result()
                    upsert_comments(conn, item_id, comments, args.comments_limit)
                except Exception as exc:
                    comment_failures += 1
                    record_failure(conn, item_id, "comments", str(exc))
                conn.commit()

    refresh_evidence(conn, ids)
    conn.commit()
    return {
        "requested_items": len(ids),
        "collections": {key: len(value) for key, value in collections.items()},
        "metadata_failures": metadata_failures,
        "comment_failures": comment_failures,
        "comments_limit": args.comments_limit,
    }


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def print_id_section(label: str, entries: list[dict[str, Any]]) -> None:
    print(f"{label}: {len(entries)}")
    for entry in entries:
        suffix = " (restored)" if entry.get("restored") else ""
        print(f"  - {entry['id']} {entry.get('title') or entry['id']}{suffix}")


def print_diff_summary(diff: dict[str, Any], applied: bool, refreshed_ids: list[str] | None = None) -> None:
    state = "applied" if applied else "preview"
    print(f"Modlist resync diff for '{diff['list']}' ({state})")
    print(
        "Counts: "
        f"added={diff['counts']['added']}, removed={diff['counts']['removed']}, "
        f"unchanged={diff['counts']['unchanged']}, missing_metadata={diff['counts']['missing_metadata']}"
    )
    print_id_section("Added", diff["added"])
    print_id_section("Removed", diff["removed"])
    print_id_section("Unchanged", diff["unchanged"])
    if refreshed_ids is not None:
        print(f"Refreshed on apply: {len(refreshed_ids)}")


def print_purge_summary(list_name: str, entries: list[dict[str, Any]], applied: bool) -> None:
    state = "applied" if applied else "preview"
    print(f"Archived purge for '{list_name}' ({state})")
    print_id_section("Purged" if applied else "Would purge", entries)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if hasattr(args, "comments_limit") and args.comments_limit < 0:
        raise SystemExit("--comments-limit must be 0 or greater")
    mutating = args.command == "sync" or bool(getattr(args, "apply", False))
    conn = connect_db(args.db, create=mutating)
    if mutating:
        init_schema(conn)
    if args.command == "purge-archived":
        archived_ids = archived_ids_for_list(conn, args.list_name)
        titles = item_titles(conn, archived_ids)
        entries = [{"id": item_id, "title": titles.get(item_id, item_id)} for item_id in archived_ids]
        if args.apply:
            purge_archived_items(conn, args.list_name, archived_ids)
        payload = {
            "command": "purge-archived",
            "list": args.list_name,
            "applied": bool(args.apply),
            "purged": entries,
            "counts": {"purged": len(entries)},
        }
        if args.format == "json":
            print_json(payload)
        else:
            print_purge_summary(args.list_name, entries, bool(args.apply))
        return 0

    ids, collections = collect_requested_ids(args)
    if not ids:
        raise SystemExit("No Workshop IDs found. Provide --ids, --input, --collection-url, or --collection-id.")
    if args.command == "resync":
        diff = diff_modlist(conn, args.list_name, ids)
        refreshed_ids: list[str] = []
        sync_result: dict[str, Any] | None = None
        if args.apply:
            apply_modlist_diff(conn, args.list_name, ids, [entry["id"] for entry in diff["removed"]])
            added_ids = [entry["id"] for entry in diff["added"]]
            stale_unchanged = [entry["id"] for entry in diff["unchanged"] if is_metadata_stale(conn, entry["id"])]
            refreshed_ids = dedupe([*added_ids, *stale_unchanged])
            if refreshed_ids:
                sync_result = sync_items(conn, refreshed_ids, collections, args)
        payload = {
            "command": "resync",
            "list": args.list_name,
            "applied": bool(args.apply),
            "diff": diff,
            "refreshed_ids": refreshed_ids,
            "sync": sync_result,
        }
        if args.format == "json":
            print_json(payload)
        else:
            print_diff_summary(diff, bool(args.apply), refreshed_ids if args.apply else None)
        return 0 if not sync_result or sync_result["metadata_failures"] == 0 else 1

    result = sync_items(conn, ids, collections, args)
    print_json({"db": str(args.db), **result})
    return 0 if result["metadata_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
