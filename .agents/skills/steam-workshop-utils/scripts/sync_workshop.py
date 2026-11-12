#!/usr/bin/env python3
"""Sync Steam Workshop metadata and public comments into a local SQLite DB."""

from __future__ import annotations

import argparse
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
DEFAULT_DB = Path.home() / ".steam-workshop" / "steam-workshop.sqlite"
DETAILS_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
COLLECTION_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"
COMMENTS_URL = "https://steamcommunity.com/comment/PublishedFile_Public/render/{creator_id}/{item_id}/"
USER_AGENT = "steam-workshop-utils/1.0 (+https://steamcommunity.com/)"
MAX_METADATA_BATCH = 100
STALE_AFTER = timedelta(hours=24)
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2048
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
MAX_MANIFEST_BYTES = 256 * 1024

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workshop_evidence import (  # noqa: E402
    ArtifactInspectionError,
    VERSION_TOKEN,
    description_version_evidence,
    inspect_artifact_manifest as inspect_artifact_manifest_evidence,
)

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


def class_tokens(attrs: list[tuple[str, str | None]]) -> set[str]:
    return set((dict(attrs).get("class") or "").split())


class CommentExtractor(HTMLParser):
    """Extract complete top-level Steam comments without flattening nested elements."""

    def __init__(self, item_id: str) -> None:
        super().__init__(convert_charrefs=True)
        self.item_id = item_id
        self.comments: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.depth = 0
        self.author_depth: int | None = None
        self.timestamp_depth: int | None = None
        self.body_depth: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = class_tokens(attrs)
        if self.current is None and tag == "div" and "commentthread_comment" in classes:
            raw_id = values.get("data-commentid") or values.get("id") or ""
            match = re.search(r"(\d+)$", raw_id)
            if not match:
                return
            self.current = {
                "comment_id": match.group(1),
                "comment_key": match.group(1),
                "item_id": self.item_id,
                "author_id": None,
                "author_name": None,
                "author_profile_url": None,
                "posted_at": None,
                "timestamp_parts": [],
                "body_parts": [],
            }
            self.depth = 1
            return
        if self.current is None:
            return
        # Steam emits explicit </source> tags in avatar pictures, so source must
        # participate in depth tracking even though HTML normally treats it as void.
        is_void = tag in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "track", "wbr"}
        if not is_void:
            self.depth += 1
        if "commentthread_author_link" in classes:
            self.author_depth = self.depth
            self.current["author_profile_url"] = values.get("href")
            account_id = values.get("data-miniprofile")
            if account_id and account_id.isdigit():
                self.current["author_id"] = str(76561197960265728 + int(account_id))
            profile_match = re.search(r"/profiles/(\d+)", values.get("href") or "")
            if profile_match:
                self.current["author_id"] = profile_match.group(1)
        if "commentthread_comment_timestamp" in classes:
            self.timestamp_depth = self.depth
            timestamp = values.get("data-timestamp")
            if timestamp and timestamp.isdigit():
                self.current["posted_at"] = datetime.fromtimestamp(int(timestamp), timezone.utc).isoformat(timespec="seconds")
        if "commentthread_comment_text" in classes:
            self.body_depth = self.depth
        if self.body_depth is not None and tag in {"br", "p", "div", "li"}:
            self.current["body_parts"].append("\n")

    def handle_data(self, data: str) -> None:
        if self.current is None:
            return
        if self.author_depth is not None:
            self.current["author_name"] = (self.current["author_name"] or "") + data
        if self.timestamp_depth is not None:
            self.current["timestamp_parts"].append(data)
        if self.body_depth is not None:
            self.current["body_parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        if self.author_depth == self.depth:
            self.author_depth = None
        if self.timestamp_depth == self.depth:
            self.timestamp_depth = None
        if self.body_depth == self.depth:
            self.body_depth = None
        self.depth -= 1
        if self.depth != 0:
            return
        body = "\n".join(part.strip() for part in "".join(self.current.pop("body_parts")).splitlines() if part.strip())
        author = re.sub(r"\s+", " ", self.current.get("author_name") or "").strip() or None
        self.current["author_name"] = author
        timestamp_label = re.sub(r"\s+", " ", "".join(self.current.pop("timestamp_parts"))).strip() or None
        if body:
            timestamp = self.current.get("posted_at")
            suffix = f"&tscn={int(datetime.fromisoformat(timestamp).timestamp())}" if timestamp else ""
            self.current["text"] = body
            fragments = (("author", author), ("posted_time", timestamp_label), ("body", body))
            self.current["legacy_fragments"] = [
                {"key": legacy_fragment_key(self.item_id, text), "kind": kind, "text": re.sub(r"\s+", " ", text).strip()}
                for kind, text in fragments if text
            ]
            self.current["source_url"] = (
                f"https://steamcommunity.com/sharedfiles/filedetails/?id={urllib.parse.quote(self.item_id)}"
                f"{suffix}#comment_{self.current['comment_id']}"
            )
            self.comments.append(self.current)
        self.current = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_db_path() -> Path:
    if "STEAM_WORKSHOP_DB" in os.environ:
        return Path(os.environ["STEAM_WORKSHOP_DB"]).expanduser()
    legacy_db = Path.home() / ".codex" / "data" / "steam-workshop" / "steam-workshop.sqlite"
    # Keep existing caches usable without moving or replacing user data.
    return legacy_db if not DEFAULT_DB.exists() and legacy_db.is_file() else DEFAULT_DB


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


def fetch_artifact_bytes(url: str, max_bytes: int = MAX_ARTIFACT_BYTES) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                raise ArtifactInspectionError("bounded", f"Artifact exceeds the {max_bytes}-byte download limit.")
            body = response.read(max_bytes + 1)
    except ArtifactInspectionError:
        raise
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise ArtifactInspectionError("unavailable", f"Artifact download failed: {exc}") from exc
    if len(body) > max_bytes:
        raise ArtifactInspectionError("bounded", f"Artifact exceeds the {max_bytes}-byte download limit.")
    return body


def inspect_artifact_manifest(body: bytes) -> dict[str, str | None]:
    return inspect_artifact_manifest_evidence(
        body,
        max_entries=MAX_ARCHIVE_ENTRIES,
        max_uncompressed_bytes=MAX_ARCHIVE_UNCOMPRESSED_BYTES,
        max_manifest_bytes=MAX_MANIFEST_BYTES,
    )


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


def legacy_fragment_key(item_id: str, text: str) -> str:
    """Reproduce keys emitted by the pre-structured comment collector."""
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha256(f"{item_id}:{normalized}".encode("utf-8")).hexdigest()[:20]


def parse_comments(item_id: str, comments_html: str) -> list[dict[str, Any]]:
    parser = CommentExtractor(item_id)
    parser.feed(comments_html or "")
    return parser.comments


def fetch_comment_page(item_id: str, creator_id: str, start: int, count: int) -> tuple[list[dict[str, Any]], int | None]:
    params = {
        "start": start,
        "count": count,
        "l": "english",
        "feature2": -1,
    }
    url = f"{COMMENTS_URL.format(creator_id=creator_id, item_id=item_id)}?{urllib.parse.urlencode(params)}"
    response = request_json(url, None, retries=2, delay=2.0)
    comments_html = response.get("comments_html", "")
    comments = parse_comments(item_id, comments_html)[:count]
    for index, comment in enumerate(comments):
        comment["position"] = start + index
        comment["raw_html"] = ""
    total = response.get("total_count")
    return comments, int(total) if total is not None else None


def fetch_comments(item_id: str, creator_id: str, limit: int) -> list[dict[str, Any]]:
    """Compatibility wrapper for consumers that only need the newest page."""
    return fetch_comment_page(item_id, creator_id, 0, limit)[0]


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

        CREATE TABLE IF NOT EXISTS workshop_description_versions (
            publishedfileid TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK (status IN ('declared', 'missing', 'ambiguous')),
            version TEXT,
            source_field TEXT,
            excerpt TEXT,
            observed_at TEXT NOT NULL,
            limitations TEXT NOT NULL,
            FOREIGN KEY (publishedfileid) REFERENCES workshop_items(publishedfileid) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS workshop_artifact_versions (
            publishedfileid TEXT PRIMARY KEY,
            status TEXT CHECK (status IN ('declared', 'missing', 'ambiguous')),
            version TEXT,
            source_path TEXT,
            source_field TEXT,
            content_reference TEXT,
            observed_at TEXT,
            attempt_status TEXT NOT NULL CHECK (attempt_status IN ('succeeded', 'unavailable', 'unsupported', 'malformed', 'bounded')),
            attempted_content_reference TEXT,
            attempted_at TEXT NOT NULL,
            attempt_message TEXT,
            limitations TEXT NOT NULL,
            FOREIGN KEY (publishedfileid) REFERENCES workshop_items(publishedfileid) ON DELETE CASCADE
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
            comment_id TEXT,
            author_id TEXT,
            author_name TEXT,
            author_profile_url TEXT,
            posted_at TEXT,
            source_url TEXT,
            collected_at TEXT,
            legacy_fragments_json TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY (publishedfileid, comment_key)
        );

        CREATE TABLE IF NOT EXISTS comment_sync_state (
            publishedfileid TEXT PRIMARY KEY,
            coverage TEXT NOT NULL CHECK (coverage IN ('complete', 'partial', 'failed')),
            collected_count INTEGER NOT NULL DEFAULT 0,
            total_count INTEGER,
            backfill_next_start INTEGER NOT NULL DEFAULT 0,
            revisit_next_start INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            updated_at TEXT NOT NULL
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
    existing_comment_columns = {row[1] for row in conn.execute("PRAGMA table_info(comments)")}
    for column in ("comment_id", "author_id", "author_name", "author_profile_url", "posted_at", "source_url", "collected_at", "legacy_fragments_json"):
        if column not in existing_comment_columns:
            default = " NOT NULL DEFAULT '[]'" if column == "legacy_fragments_json" else ""
            conn.execute(f"ALTER TABLE comments ADD COLUMN {column} TEXT{default}")
    conn.commit()


def upsert_item(conn: sqlite3.Connection, detail: dict[str, Any]) -> None:
    item_id = str(detail.get("publishedfileid", "")).strip()
    if not item_id:
        return
    tags = detail.get("tags") or []
    observed_at = now_iso()
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
            observed_at,
        ),
    )
    version_evidence = description_version_evidence(detail.get("title"), detail.get("description"))
    conn.execute(
        """
        INSERT INTO workshop_description_versions (
            publishedfileid, status, version, source_field, excerpt, observed_at, limitations
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(publishedfileid) DO UPDATE SET
            status = excluded.status,
            version = excluded.version,
            source_field = excluded.source_field,
            excerpt = excluded.excerpt,
            observed_at = excluded.observed_at,
            limitations = excluded.limitations
        """,
        (
            item_id, version_evidence["status"], version_evidence["version"], version_evidence["source_field"],
            version_evidence["excerpt"], observed_at, version_evidence["limitations"],
        ),
    )


def inspect_and_record_artifact(conn: sqlite3.Connection, detail: dict[str, Any]) -> str:
    item_id = str(detail.get("publishedfileid", "")).strip()
    content_reference = str(detail.get("hcontent_file") or "").strip()
    artifact_url = str(detail.get("file_url") or "").strip()
    filename = str(detail.get("filename") or "").strip()
    attempted_at = now_iso()
    limitations = (
        "The version comes from a bounded, data-only mod.json inspection tied to the recorded Steam content reference; "
        "it does not prove byte-for-byte equality with any local artifact."
    )
    try:
        if not content_reference:
            raise ArtifactInspectionError("unavailable", "Steam metadata did not include an artifact content reference.")
        if not artifact_url:
            raise ArtifactInspectionError("unavailable", "Steam metadata did not include an artifact download URL.")
        if filename and not filename.lower().endswith(".zip"):
            raise ArtifactInspectionError("unsupported", f"Unsupported Workshop artifact format: {filename}")
        try:
            declared_size = int(detail.get("file_size") or 0)
        except (TypeError, ValueError) as exc:
            raise ArtifactInspectionError("malformed", "Steam metadata included an invalid artifact size.") from exc
        if declared_size > MAX_ARTIFACT_BYTES:
            raise ArtifactInspectionError("bounded", f"Artifact exceeds the {MAX_ARTIFACT_BYTES}-byte download limit.")
        result = inspect_artifact_manifest(fetch_artifact_bytes(artifact_url))
    except ArtifactInspectionError as exc:
        conn.execute(
            """
            INSERT INTO workshop_artifact_versions (
                publishedfileid, status, version, source_path, source_field, content_reference, observed_at,
                attempt_status, attempted_content_reference, attempted_at, attempt_message, limitations
            ) VALUES (?, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?, ?)
            ON CONFLICT(publishedfileid) DO UPDATE SET
                attempt_status = excluded.attempt_status,
                attempted_content_reference = excluded.attempted_content_reference,
                attempted_at = excluded.attempted_at,
                attempt_message = excluded.attempt_message,
                limitations = excluded.limitations
            """,
            (item_id, exc.status, content_reference or None, attempted_at, str(exc), limitations),
        )
        record_failure(conn, item_id, "artifact", str(exc))
        return exc.status
    conn.execute(
        """
        INSERT INTO workshop_artifact_versions (
            publishedfileid, status, version, source_path, source_field, content_reference, observed_at,
            attempt_status, attempted_content_reference, attempted_at, attempt_message, limitations
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'succeeded', ?, ?, NULL, ?)
        ON CONFLICT(publishedfileid) DO UPDATE SET
            status = excluded.status,
            version = excluded.version,
            source_path = excluded.source_path,
            source_field = excluded.source_field,
            content_reference = excluded.content_reference,
            observed_at = excluded.observed_at,
            attempt_status = excluded.attempt_status,
            attempted_content_reference = excluded.attempted_content_reference,
            attempted_at = excluded.attempted_at,
            attempt_message = NULL,
            limitations = excluded.limitations
        """,
        (
            item_id, result["status"], result["version"], result["source_path"], result["source_field"],
            content_reference, attempted_at, content_reference, attempted_at, limitations,
        ),
    )
    clear_failure(conn, item_id, "artifact")
    return "succeeded"


def upsert_comments(conn: sqlite3.Connection, item_id: str, comments: list[dict[str, Any]], limit: int | None = None) -> None:
    timestamp = now_iso()
    for comment in comments if limit is None else comments[:limit]:
        conn.execute(
            """
            INSERT INTO comments (
                publishedfileid, comment_key, position, text, raw_html, last_seen, comment_id,
                author_id, author_name, author_profile_url, posted_at, source_url, collected_at, legacy_fragments_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(publishedfileid, comment_key) DO UPDATE SET
                position = excluded.position,
                text = excluded.text,
                raw_html = excluded.raw_html,
                last_seen = excluded.last_seen,
                comment_id = COALESCE(excluded.comment_id, comments.comment_id),
                author_id = COALESCE(excluded.author_id, comments.author_id),
                author_name = COALESCE(excluded.author_name, comments.author_name),
                author_profile_url = COALESCE(excluded.author_profile_url, comments.author_profile_url),
                posted_at = COALESCE(excluded.posted_at, comments.posted_at),
                source_url = COALESCE(excluded.source_url, comments.source_url),
                collected_at = excluded.collected_at,
                legacy_fragments_json = CASE WHEN excluded.legacy_fragments_json = '[]' THEN comments.legacy_fragments_json ELSE excluded.legacy_fragments_json END
            """,
            (
                item_id,
                comment["comment_key"],
                int(comment["position"]),
                comment["text"],
                comment.get("raw_html", ""),
                timestamp,
                comment.get("comment_id"),
                comment.get("author_id"),
                comment.get("author_name"),
                comment.get("author_profile_url"),
                comment.get("posted_at"),
                comment.get("source_url"),
                timestamp,
                json.dumps(comment.get("legacy_fragments", []), ensure_ascii=False),
            ),
        )


def sync_comment_history(
    conn: sqlite3.Connection,
    item_id: str,
    creator_id: str,
    page_size: int,
    page_budget: int,
    fetch_page=fetch_comment_page,
) -> dict[str, Any]:
    """Collect a bounded history slice while persisting safe resume and revisit cursors."""
    previous = conn.execute("SELECT * FROM comment_sync_state WHERE publishedfileid = ?", (item_id,)).fetchone()
    known = {row[0] for row in conn.execute("SELECT comment_key FROM comments WHERE publishedfileid = ?", (item_id,))}
    previous_total = int(previous["total_count"]) if previous and previous["total_count"] is not None else None
    backfill = int(previous["backfill_next_start"]) if previous else 0
    revisit = int(previous["revisit_next_start"]) if previous else 0
    pages = 0
    total: int | None = previous_total
    error: str | None = None
    seen_starts: set[int] = set()

    def collect(start: int) -> tuple[list[dict[str, Any]], int | None]:
        nonlocal pages, total
        comments, observed_total = fetch_page(item_id, creator_id, start, page_size)
        pages += 1
        seen_starts.add(start)
        if observed_total is not None:
            total = observed_total
        upsert_comments(conn, item_id, comments)
        return comments, observed_total

    try:
        # Always refresh the leading edge. Continue until a known identity is reached,
        # so bursts larger than one page remain visible without losing backfill state.
        start = 0
        while pages < page_budget:
            page, _ = collect(start)
            if not known:
                backfill = start + len(page)
            if not page or any(comment["comment_key"] in known for comment in page):
                break
            if len(page) < page_size or (total is not None and start + len(page) >= total):
                break
            start += page_size

        # Offset cursors are adjusted by observed growth, so new leading comments shift
        # the resume point forward instead of creating a gap.
        growth = max(0, (total or 0) - (previous_total or 0)) if previous_total is not None else 0
        resume = max(0, backfill + growth)
        if pages < page_budget and (total is None or resume < total):
            page, _ = collect(resume)
            backfill = resume + len(page)
        if pages < page_budget and total and backfill >= total:
            revisit = revisit if 0 < revisit < total else page_size
            revisit_start = revisit
            if revisit_start not in seen_starts:
                page, _ = collect(revisit_start)
                revisit = revisit_start + max(len(page), page_size)
                if revisit >= total:
                    revisit = page_size
    except Exception as exc:
        error = str(exc)

    collected_count = int(conn.execute("SELECT COUNT(*) FROM comments WHERE publishedfileid = ?", (item_id,)).fetchone()[0])
    complete = total is not None and collected_count >= total and backfill >= total
    coverage = "failed" if error and pages == 0 else "partial" if error or not complete else "complete"
    conn.execute(
        """INSERT INTO comment_sync_state
        (publishedfileid, coverage, collected_count, total_count, backfill_next_start, revisit_next_start, last_error, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(publishedfileid) DO UPDATE SET coverage=excluded.coverage,
          collected_count=excluded.collected_count, total_count=excluded.total_count,
          backfill_next_start=excluded.backfill_next_start, revisit_next_start=excluded.revisit_next_start,
          last_error=excluded.last_error, updated_at=excluded.updated_at""",
        (item_id, coverage, collected_count, total, backfill, revisit, error[:1000] if error else None, now_iso()),
    )
    if error:
        record_failure(conn, item_id, "comments", error)
    else:
        clear_failure(conn, item_id, "comments")
    return {"coverage": coverage, "collected_count": collected_count, "total_count": total, "pages": pages, "error": error}


def record_comment_coverage_failure(conn: sqlite3.Connection, item_id: str, message: str) -> None:
    previous = conn.execute("SELECT * FROM comment_sync_state WHERE publishedfileid = ?", (item_id,)).fetchone()
    collected = int(conn.execute("SELECT COUNT(*) FROM comments WHERE publishedfileid = ?", (item_id,)).fetchone()[0])
    conn.execute(
        """INSERT INTO comment_sync_state
        (publishedfileid, coverage, collected_count, total_count, backfill_next_start, revisit_next_start, last_error, updated_at)
        VALUES (?, 'failed', ?, ?, ?, ?, ?, ?)
        ON CONFLICT(publishedfileid) DO UPDATE SET coverage='failed', collected_count=excluded.collected_count,
          last_error=excluded.last_error, updated_at=excluded.updated_at""",
        (item_id, collected, previous["total_count"] if previous else None,
         previous["backfill_next_start"] if previous else 0, previous["revisit_next_start"] if previous else 0,
         message[:1000], now_iso()),
    )
    record_failure(conn, item_id, "comments", message)


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


def clear_failure(conn: sqlite3.Connection, item_id: str, stage: str) -> None:
    """Remove a resolved stage failure after a successful current attempt."""
    conn.execute(
        "DELETE FROM sync_failures WHERE publishedfileid = ? AND stage = ?",
        (item_id, stage),
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
    parser.add_argument("--comments-limit", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--comment-page-size", type=int, default=50, help="Comments requested per Steam page.")
    parser.add_argument("--comment-page-budget", type=int, default=4, help="Maximum comment pages fetched per item per sync.")
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
    artifact_failures = 0
    try:
        returned_ids: set[str] = set()
        for detail in fetch_details(ids, args.api_key):
            item_id = str(detail.get("publishedfileid", ""))
            if item_id:
                returned_ids.add(item_id)
            if detail.get("result") not in (1, "1", None):
                metadata_failures += 1
                record_failure(conn, item_id or "unknown", "metadata", f"Steam result {detail.get('result')}")
                continue
            upsert_item(conn, detail)
            clear_failure(conn, item_id, "metadata")
            if inspect_and_record_artifact(conn, detail) != "succeeded":
                artifact_failures += 1
        for item_id in set(ids) - returned_ids:
            metadata_failures += 1
            record_failure(conn, item_id, "metadata", "Steam returned no metadata for the requested Workshop item")
    except Exception as exc:
        for item_id in ids:
            record_failure(conn, item_id, "metadata", str(exc))
        metadata_failures += len(ids)
    conn.commit()

    comment_failures = 0
    legacy_limit = getattr(args, "comments_limit", None)
    page_size = legacy_limit if legacy_limit is not None else getattr(args, "comment_page_size", 50)
    page_budget = getattr(args, "comment_page_budget", 4)
    if not args.skip_comments and page_size and page_budget:
        comment_targets, missing_creator_ids = collect_comment_targets(conn, ids)
        for item_id in missing_creator_ids:
            comment_failures += 1
            record_comment_coverage_failure(conn, item_id, "Missing creator SteamID; cannot fetch Steam Community comments.")
        conn.commit()
        for item_id, creator_id in comment_targets.items():
            try:
                outcome = sync_comment_history(conn, item_id, creator_id, page_size, page_budget)
                if outcome["error"]:
                    comment_failures += 1
            except Exception as exc:
                comment_failures += 1
                record_comment_coverage_failure(conn, item_id, str(exc))
            conn.commit()

    refresh_evidence(conn, ids)
    conn.commit()
    return {
        "requested_items": len(ids),
        "collections": {key: len(value) for key, value in collections.items()},
        "metadata_failures": metadata_failures,
        "artifact_failures": artifact_failures,
        "comment_failures": comment_failures,
        "comment_page_size": page_size,
        "comment_page_budget": page_budget,
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
    if hasattr(args, "comments_limit") and args.comments_limit is not None and args.comments_limit < 0:
        raise SystemExit("--comments-limit must be 0 or greater")
    if hasattr(args, "comment_page_size") and args.comment_page_size < 1:
        raise SystemExit("--comment-page-size must be greater than zero")
    if hasattr(args, "comment_page_budget") and args.comment_page_budget < 1:
        raise SystemExit("--comment-page-budget must be greater than zero")
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
