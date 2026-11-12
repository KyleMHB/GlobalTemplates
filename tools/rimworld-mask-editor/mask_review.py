"""Manage requested and completed mask reviews."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from editor_project import ROOT, settings
QUEUE = Path("artwork/mask-reviews.json")


def relative(path, root=ROOT):
    path = Path(path)
    path = (path if path.is_absolute() else root / path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Review artwork must be inside the project")
    return path.relative_to(root.resolve()).as_posix()


def read_reviews(root=ROOT):
    path = root / QUEUE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_reviews(reviews, root=ROOT):
    path = root / QUEUE
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(reviews, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def current_recipes(root=ROOT):
    registry_path = root / 'artwork/objects.json'
    registry = json.loads(registry_path.read_text(encoding='utf-8')) if registry_path.is_file() else {'objects': []}
    recipes = {}
    for obj in registry['objects']:
        master = obj.get('approvedMaster', {})
        master_path = root / 'Textures' / master.get('path', '')
        approved = master_path.is_file() and hashlib.sha256(master_path.read_bytes()).hexdigest() == master.get('sha256')
        for direction, recipe in obj.get('recipes', {}).items():
            suffix = '' if direction == 'single' else '_' + direction
            color = root / 'Textures' / (obj['texture'] + suffix + '.png')
            mask = color.with_name(color.stem + ('_m.png' if direction == 'single' else 'm.png'))
            recipes.setdefault(recipe, []).append((obj['label'], direction, approved, color, mask))
        for direction in obj.get('directions', []) or ['single']:
            suffix = '' if direction == 'single' else '_' + direction
            color = root / 'Textures' / (obj['texture'] + suffix + '.png')
            mask = color.with_name(color.stem + ('_m.png' if direction == 'single' else 'm.png'))
            recipes.setdefault(relative(color, root), []).append((obj['label'], direction, approved, color, mask))
    return recipes


def review_context(key, recipes):
    matches = recipes.get(key, [])
    if matches:
        return 'current approved' if all(item[2] for item in matches) else 'current; approval hash differs'
    return 'candidate or historical'


def promote_review(path, apply=False, root=ROOT):
    """Plan or apply a saved mask to all current directions of a recipe."""
    key = relative(path, root)
    if not key.lower().endswith('.json'):
        raise ValueError('Promotion requires a current recipe')
    targets = current_recipes(root).get(key, [])
    if not targets or not all(item[2] for item in targets):
        raise ValueError('Recipe is not current approved artwork')
    entry = read_reviews(root).get(key, {})
    if entry.get('status') != 'reviewed' or not entry.get('saves'):
        raise ValueError('The current recipe needs a saved review')
    saved = entry['saves'][-1]
    snapshot = root / relative(saved['savedSnapshot'], root)
    data = snapshot.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != saved['maskSha256']:
        raise ValueError('Saved mask snapshot hash differs from review')
    recipe = root / key
    manifest = json.loads(recipe.read_text(encoding='utf-8'))
    if (recipe.parent / manifest['paintedMask']).read_bytes() != data:
        raise ValueError('Recipe mask differs from the saved review; reconcile first')
    reviewed_image = root / relative(saved['image'], root)
    if not reviewed_image.is_file():
        raise ValueError('Reviewed colour image is unavailable; review the current recipe again')
    if not saved.get('imageSha256'):
        raise ValueError('Legacy review has no colour hash; review the current recipe again')
    if hashlib.sha256(reviewed_image.read_bytes()).hexdigest() != saved['imageSha256']:
        raise ValueError('Reviewed colour image changed after the save; review again')
    from PIL import Image, ImageChops
    (root / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root / 'work') as folder:
        subprocess.run([sys.executable, str(Path(__file__).with_name("export-layered-artwork.py")), str(recipe),
                        '--output', folder], capture_output=True, text=True, check=True)
        exported = Path(folder) / manifest['colorFilename']
        with Image.open(reviewed_image) as a, Image.open(exported) as b:
            if a.size != b.size or ImageChops.difference(a.convert('RGBA'), b.convert('RGBA')).getbbox(alpha_only=False):
                raise ValueError('Reviewed colour differs from current export; review again')
        if (Path(folder) / manifest['maskFilename']).read_bytes() != data:
            raise ValueError('Exported mask differs from saved review')
        known = {digest} | {s.get('previousMaskSha256') for s in entry['saves']}
        plan = []
        for label, direction, _, color, mask in targets:
            with Image.open(color) as a, Image.open(exported) as b:
                if a.size != b.size or ImageChops.difference(a.convert('RGBA'), b.convert('RGBA')).getbbox(alpha_only=False):
                    raise ValueError(f'{label} {direction}: production colour differs from reviewed export')
            old = mask.read_bytes()
            before = hashlib.sha256(old).hexdigest()
            if before not in known:
                raise ValueError(f'{relative(mask, root)} has unrelated changes ({before}); '
                                 f'reviewed mask is {digest}; reconcile first')
            plan.append((mask, old, before))
    result = [{'path': relative(mask, root), 'beforeSha256': before, 'afterSha256': digest}
              for mask, _, before in plan]
    if apply:
        written = []
        try:
            for mask, old, _ in plan:
                written.append((mask, old))
                mask.write_bytes(data)
                if hashlib.sha256(mask.read_bytes()).hexdigest() != digest:
                    raise OSError(f'Failed to verify {mask}')
        except OSError:
            for mask, old in written:
                mask.write_bytes(old)
            raise
    return result


def mark_review(path, note="", mask=None, root=ROOT):
    key = relative(path, root)
    target = root / key
    if not target.is_file():
        raise ValueError(f"Artwork does not exist: {key}")
    reviews = read_reviews(root)
    entry = reviews.get(key, {}).copy()
    entry.update(note=note.strip(), status="pending")
    if target.suffix.lower() == ".json":
        data = json.loads(target.read_text(encoding="utf-8"))
        if not all(name in data for name in ("layers", "colorFilename", "maskFilename")):
            raise ValueError("Recipe must declare layers, colour and mask filenames")
        entry["kind"] = "recipe"
    elif target.suffix.lower() == ".png":
        suffix = "m.png" if re.search(r"_(north|east|south|west)$", target.stem, re.I) else "_m.png"
        mask_path = relative(mask, root) if mask else relative(target.with_name(target.stem + suffix), root)
        if not (root / mask_path).is_file():
            raise ValueError(f"Matching mask does not exist: {mask_path}")
        entry.update(kind="image", mask=mask_path)
    else:
        raise ValueError("Use a colour PNG or an artwork recipe JSON")
    reviews[key] = entry
    write_reviews(reviews, root)
    return key


def record_reviewed(image, mask, recipe=None, key=None, before_bytes=None, changed_pixels=None, root=ROOT):
    image_key = relative(image, root)
    reviews = read_reviews(root)
    recipe_key = relative(recipe, root) if recipe else None
    if key:
        key = relative(key, root)
    else:
        candidates = [candidate for candidate in (recipe_key, image_key) if candidate]
        key = next((candidate for candidate in candidates if candidate in reviews
                    and reviews[candidate].get("status", "pending") == "pending"), candidates[0])
    mask = Path(mask).resolve()
    try:
        saved_mask = relative(mask, root)
    except ValueError:
        saved_mask = str(mask)
    entry = reviews.get(key, {}).copy()
    entry.setdefault("kind", "recipe" if recipe or key.lower().endswith(".json") else "image")
    entry.setdefault("note", "")
    entry["status"] = "reviewed"
    if entry["kind"] == "image":
        entry["mask"] = saved_mask
    history = root / "work/mask-review-history"
    history.mkdir(parents=True, exist_ok=True)

    def snapshot(data):
        digest = hashlib.sha256(data).hexdigest()
        path = history / (digest + ".png")
        if not path.exists():
            path.write_bytes(data)
        return digest, relative(path, root)

    after_hash, after_snapshot = snapshot(mask.read_bytes())
    before_hash, before_snapshot = snapshot(before_bytes) if before_bytes else (None, None)
    entry.setdefault("saves", []).append({
        "at": datetime.now(timezone.utc).isoformat(),
        "image": image_key,
        "imageSha256": hashlib.sha256((root / image_key).read_bytes()).hexdigest(),
        "mask": saved_mask,
        "maskSha256": after_hash,
        "savedSnapshot": after_snapshot,
        "previousMaskSha256": before_hash,
        "previousSnapshot": before_snapshot,
        "changedPixels": changed_pixels,
        "recipeUpdated": bool(recipe),
    })
    reviews[key] = entry
    write_reviews(reviews, root)
    return key


def clear_review(path, root=ROOT):
    key = relative(path, root)
    reviews = read_reviews(root)
    if key not in reviews:
        raise ValueError(f"No pending mask review: {key}")
    del reviews[key]
    write_reviews(reviews, root)


def clear_request(path, root=ROOT):
    key = relative(path, root)
    reviews = read_reviews(root)
    if key not in reviews:
        raise ValueError(f"No pending mask review: {key}")
    if reviews[key].get("saves"):
        reviews[key]["status"] = "reviewed"
    else:
        del reviews[key]
    write_reviews(reviews, root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("add", "clear", "list", "promote"))
    parser.add_argument("path", nargs="?", type=Path, help="Colour PNG or recipe JSON")
    parser.add_argument("--mask", type=Path, help="Matching mask when its name is nonstandard")
    parser.add_argument("--note", default="", help="What to inspect")
    parser.add_argument('--apply', action='store_true', help='Apply a verified promotion plan')
    parser.add_argument('--current', action='store_true', help='List only current approved artwork awaiting review')
    args = parser.parse_args()
    try:
        if args.action == "list":
            if args.path or args.mask or args.note or args.apply:
                parser.error("list takes no artwork or options")
            reviews = read_reviews()
            if args.current:
                recipes = current_recipes()
                reviews = {k: v for k, v in reviews.items() if v.get('status') == 'pending'
                           and review_context(k, recipes) == 'current approved'}
            print(json.dumps(reviews, indent=2, ensure_ascii=False))
        elif not args.path:
            parser.error("add and clear need a colour PNG or recipe JSON")
        elif args.action == "add":
            if args.apply or args.current:
                parser.error('add does not take --apply or --current')
            print("Marked for mask review:", mark_review(args.path, args.note, args.mask))
        elif args.action == 'promote':
            if args.mask or args.note or args.current:
                parser.error('promote takes only a recipe and optional --apply')
            print(json.dumps(promote_review(args.path, args.apply), indent=2))
        else:
            if args.mask or args.note or args.apply or args.current:
                parser.error("clear takes only the artwork path")
            clear_review(args.path)
            print("Cleared mask review:", args.path)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
