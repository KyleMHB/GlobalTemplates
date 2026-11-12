"""Pure policies for extracting version evidence from Workshop metadata and artifacts."""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import PurePosixPath


VERSION_TOKEN = r"\d+(?:\.\d+){1,3}(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?(?:\+[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?"
MOD_VERSION_RE = re.compile(rf"(?im)^\s*(?:\[b\])?\s*mod\s+version\s*[:=-]?\s*(?:\[/b\])?\s*v?({VERSION_TOKEN})\b")
CURRENT_RELEASE_RE = re.compile(
    rf"(?im)^\s*(?:\[h[1-6]\]\s*)?what(?:'|’)?s\s+new\s+in\s+v?({VERSION_TOKEN})\b\s*(?:\[/h[1-6]\])?\s*$"
)
TITLE_VERSION_RE = re.compile(rf"\bv?({VERSION_TOKEN})\s*$", re.I)
HISTORY_SECTION_RE = re.compile(r"(?im)^\s*(?:\[h[1-6]\])?\s*(?:old\s+)?(?:release\s+)?history\b")


class ArtifactInspectionError(RuntimeError):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


def description_version_evidence(title: str | None, description: str | None) -> dict[str, str | None]:
    description_text = description or ""
    history = HISTORY_SECTION_RE.search(description_text)
    current_description = description_text[: history.start()] if history else description_text
    explicit = [(match.group(1), match.group(0).strip()) for match in MOD_VERSION_RE.finditer(current_description)]
    explicit_versions = {version for version, _ in explicit}
    limitations = "Author-declared description evidence does not verify the published artifact bytes or the freshness of other description text."
    if explicit:
        if len(explicit_versions) == 1:
            version, excerpt = explicit[0]
            return {"status": "declared", "version": version, "source_field": "description", "excerpt": excerpt, "limitations": limitations}
        return {"status": "ambiguous", "version": None, "source_field": "description", "excerpt": " | ".join(excerpt for _, excerpt in explicit), "limitations": limitations}

    candidates: list[tuple[str, str, str]] = []
    title_text = title or ""
    title_match = TITLE_VERSION_RE.search(title_text)
    title_prefix = title_text[: title_match.start()] if title_match else ""
    if title_match and not re.search(r"\b(?:for|supports?)\s+[^0-9]*$", title_prefix, re.I):
        candidates.append((title_match.group(1), "title", title_text.strip()))

    candidates.extend(
        (match.group(1), "description", match.group(0).strip())
        for match in CURRENT_RELEASE_RE.finditer(current_description)
    )
    versions = {version for version, _, _ in candidates}
    if len(versions) == 1:
        version = candidates[0][0]
        source_fields = {source_field for _, source_field, _ in candidates}
        return {
            "status": "declared", "version": version,
            "source_field": "+".join(sorted(source_fields)),
            "excerpt": " | ".join(dict.fromkeys(excerpt for _, _, excerpt in candidates)),
            "limitations": limitations,
        }
    if candidates:
        return {
            "status": "ambiguous", "version": None,
            "source_field": "+".join(sorted({source_field for _, source_field, _ in candidates})),
            "excerpt": " | ".join(excerpt for _, _, excerpt in candidates), "limitations": limitations,
        }
    return {"status": "missing", "version": None, "source_field": None, "excerpt": None, "limitations": limitations}


def inspect_artifact_manifest(
    body: bytes,
    *,
    max_entries: int,
    max_uncompressed_bytes: int,
    max_manifest_bytes: int,
) -> dict[str, str | None]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(body))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ArtifactInspectionError("malformed", f"Artifact is not a readable ZIP archive: {exc}") from exc
    with archive:
        entries = archive.infolist()
        if len(entries) > max_entries:
            raise ArtifactInspectionError("bounded", f"ZIP contains more than {max_entries} entries.")
        if sum(entry.file_size for entry in entries) > max_uncompressed_bytes:
            raise ArtifactInspectionError("bounded", f"ZIP declares more than {max_uncompressed_bytes} uncompressed bytes.")
        candidates = [entry for entry in entries if not entry.is_dir() and PurePosixPath(entry.filename).name.lower() == "mod.json"]
        if not candidates:
            return {"status": "missing", "version": None, "source_path": None, "source_field": None}

        release_manifests = [entry for entry in candidates if len(PurePosixPath(entry.filename).parts) == 1]
        if not release_manifests:
            release_manifests = [
                entry for entry in candidates
                if len(PurePosixPath(entry.filename).parts) == 2
                and PurePosixPath(entry.filename).parts[0].lower() not in {"dependencies", "dependency", "mods"}
            ]
        if not release_manifests:
            return {"status": "missing", "version": None, "source_path": None, "source_field": None}
        declarations: list[tuple[str, str]] = []
        for entry in release_manifests:
            if entry.flag_bits & 0x1:
                raise ArtifactInspectionError("unsupported", f"Manifest {entry.filename} is encrypted.")
            if entry.file_size > max_manifest_bytes:
                raise ArtifactInspectionError("bounded", f"Manifest {entry.filename} exceeds the {max_manifest_bytes}-byte limit.")
            try:
                manifest = json.loads(archive.read(entry).decode("utf-8-sig"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError, zipfile.BadZipFile) as exc:
                raise ArtifactInspectionError("malformed", f"Manifest {entry.filename} is unreadable JSON: {exc}") from exc
            version = manifest.get("version") if isinstance(manifest, dict) else None
            if isinstance(version, str) and re.fullmatch(VERSION_TOKEN, version.strip()):
                declarations.append((version.strip(), entry.filename))
        if not declarations:
            return {"status": "missing", "version": None, "source_path": release_manifests[0].filename, "source_field": "version"}
        versions = {version for version, _ in declarations}
        if len(versions) > 1:
            return {"status": "ambiguous", "version": None, "source_path": " | ".join(path for _, path in declarations), "source_field": "version"}
        version, source_path = min(declarations, key=lambda pair: pair[1])
        return {"status": "declared", "version": version, "source_path": source_path, "source_field": "version"}
