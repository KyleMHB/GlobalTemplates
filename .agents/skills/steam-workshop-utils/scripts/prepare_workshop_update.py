"""Prepare a description-only SteamCMD VDF. No network or publishing actions."""

import argparse
import json
import re
from pathlib import Path


def positive_id(value, label):
    text = str(value)
    if not re.fullmatch(r"[1-9][0-9]*", text):
        raise ValueError(f"{label} must be a nonzero numeric ID")
    return text


def quote_vdf(text):
    # Quoted KeyValues tokens preserve literal line breaks. Escape quotes and
    # backslashes so description text cannot introduce additional VDF fields.
    if any(ord(char) < 32 and char not in "\n\t" for char in text):
        raise ValueError("Description contains unsupported control characters")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def prepare(mod_dir, appid, description_file=None, item_id=None):
    mod_dir = Path(mod_dir).resolve(strict=True)
    manifest_path = mod_dir / "mod.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig")) if manifest_path.exists() else {}
    manifest_id = manifest.get("publishedFileId")
    if manifest_id is not None:
        manifest_id = positive_id(manifest_id, "Manifest Workshop item ID")
    if item_id is not None:
        item_id = positive_id(item_id, "Workshop item ID")
    if manifest_id and item_id and manifest_id != item_id:
        raise ValueError("Supplied Workshop item ID differs from mod.json")
    selected_id = item_id or manifest_id
    if selected_id is None:
        raise ValueError("An existing Workshop item ID is required; this helper cannot create items")
    appid = positive_id(appid, "Consumer App ID")
    source = Path(description_file) if description_file else mod_dir / "steam-description.md"
    description = source.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if not description.strip():
        raise ValueError("Description must not be empty")
    return '\n'.join([
        '"workshopitem"', '{', f'    "appid" "{appid}"',
        f'    "publishedfileid" "{selected_id}"',
        f'    "description" {quote_vdf(description)}', '}', '',
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod-dir", type=Path, required=True)
    parser.add_argument("--appid", required=True)
    parser.add_argument("--item-id")
    parser.add_argument("--description-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing local VDF draft")
    args = parser.parse_args()
    try:
        content = prepare(args.mod_dir, args.appid, args.description_file, args.item_id)
        protected = [args.mod_dir / "mod.json", args.description_file or args.mod_dir / "steam-description.md"]
        if args.output.resolve() in [path.resolve() for path in protected]:
            raise ValueError("Output must not overwrite the manifest or description source")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w" if args.overwrite else "x", encoding="utf-8", newline="\n") as output:
            output.write(content)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Prepared description-only draft: {args.output.resolve()}")
    print("Nothing was submitted to Steam. Verify item ownership and App ID before publishing.")


if __name__ == "__main__":
    main()
