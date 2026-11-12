"""Export an ordered RGBA layer stack and its visible construction coverage together."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ownershipMap(entry, size):
    if ("constructionTint" in entry) == ("ownership" in entry):
        raise ValueError("Declare exactly one of constructionTint or ownership")
    if "ownership" not in entry:
        return None
    if entry.get("scale", 1) != 1:
        raise ValueError("Ownership layers cannot be scaled")
    polygons = entry["ownership"]
    if not isinstance(polygons, dict) or not polygons:
        raise ValueError("Ownership requires named polygons")
    label = Image.new("L", size)
    draw = ImageDraw.Draw(label)
    for name, points in polygons.items():
        if not name or not isinstance(points, list) or len(points) < 3 or any(
            not isinstance(point, list) or len(point) != 2 or any(type(v) is not int for v in point)
            or not (0 <= point[0] < size[0] and 0 <= point[1] < size[1]) for point in points
        ):
            raise ValueError(f"Invalid ownership polygon: {name}")
        if sum(points[i][0] * points[(i+1) % len(points)][1] - points[(i+1) % len(points)][0] * points[i][1] for i in range(len(points))) == 0:
            raise ValueError(f"Empty ownership polygon: {name}")
        region = Image.new("L", size)
        ImageDraw.Draw(region).polygon([tuple(point) for point in points], fill=255)
        if not region.getbbox() or sum(region.histogram()[1:]) < 3:
            raise ValueError(f"Empty ownership polygon: {name}")
        draw.polygon([tuple(point) for point in points], fill=255)
    return label


def export(manifestPath, output):
    manifest = json.loads(manifestPath.read_text(encoding="utf-8"))
    if not manifest.get("sourceRepair") or not manifest.get("alphaHandling"):
        raise ValueError("Declare sourceRepair and alphaHandling in the export manifest")
    sourceSize = tuple(manifest["sourceSize"])
    color = Image.new("RGBA", sourceSize)
    contribution = Image.new("L", sourceSize)
    sources = []
    for entry in manifest["layers"]:
        path = manifestPath.parent / entry["path"]
        layer = Image.open(path).convert("RGBA")
        label = ownershipMap(entry, layer.size)
        placed = "offset" in entry or "scale" in entry
        if layer.size != sourceSize and not placed:
            raise ValueError(f"Layer canvas differs from sourceSize: {path}")
        if placed:
            layerScale = entry.get("scale", 1)
            if not 0 < layerScale <= 1:
                raise ValueError("Layer scale must be greater than zero and at most one")
            layerOffset = tuple(entry.get("offset", (0, 0)))
            if len(layerOffset) != 2 or any(not isinstance(v, int) for v in layerOffset):
                raise ValueError("Layer offset must contain two integer source pixels")
            if layerScale != 1:
                layer = layer.resize(tuple(max(1, round(v * layerScale)) for v in layer.size),
                                     Image.Resampling.LANCZOS)
            positioned = Image.new("RGBA", sourceSize)
            positioned.paste(layer, layerOffset)
            layer = positioned
            if label is not None:
                positionedLabel = Image.new("L", sourceSize)
                positionedLabel.paste(label, layerOffset)
                label = positionedLabel
        alpha = layer.getchannel("A")
        # Later fixed-colour layers occlude earlier housing, just as in the colour stack.
        contribution = Image.composite(
            label if label is not None else Image.new("L", sourceSize, 255 if entry["constructionTint"] else 0),
            contribution, alpha,
        )
        color = Image.alpha_composite(color, layer)
        sources.append({"path": entry["path"], "sha256": digest(path)})
        if placed:
            sources[-1].update(offset=layerOffset, scale=layerScale)

    crop = tuple(manifest["crop"])
    if not (0 <= crop[0] < crop[2] <= sourceSize[0]
            and 0 <= crop[1] < crop[3] <= sourceSize[1]):
        raise ValueError("crop must be inside sourceSize")
    canvas = tuple(manifest["canvas"])
    target = tuple(manifest["targetBox"])
    if not (0 <= target[0] < target[2] <= canvas[0]
            and 0 <= target[1] < target[3] <= canvas[1]):
        raise ValueError("targetBox must be inside canvas")
    scale = min((target[2] - target[0]) / (crop[2] - crop[0]),
                (target[3] - target[1]) / (crop[3] - crop[1]))
    size = (max(1, round((crop[2] - crop[0]) * scale)),
            max(1, round((crop[3] - crop[1]) * scale)))
    offset = (target[0] + (target[2] - target[0] - size[0]) // 2,
              target[1] + (target[3] - target[1] - size[1]) // 2)
    # One shared crop, uniform scale and placement; no alpha remapping or edge expansion.
    reduced = color.crop(crop).resize(size, Image.Resampling.LANCZOS)
    visible = contribution.crop(crop).resize(size, Image.Resampling.LANCZOS)
    alpha = color.getchannel("A").crop(crop).resize(size, Image.Resampling.LANCZOS)
    # Coverage is conditional on visible colour alpha, not a second silhouette alpha.
    red = Image.new("L", size)
    red.putdata([min(255, round(255 * housing / opacity)) if opacity else 0
                 for housing, opacity in zip(visible.tobytes(), alpha.tobytes())])
    sprite = Image.new("RGBA", canvas)
    sprite.paste(reduced, offset)
    paintedColor = manifest.get("paintedColor")
    if paintedColor:
        paintedColorPath = manifestPath.parent / paintedColor
        with Image.open(paintedColorPath) as image:
            sprite = image.convert("RGBA")
        if sprite.size != canvas:
            raise ValueError("Painted colour dimensions must match the output canvas")
    maskRed = Image.new("L", canvas)
    maskRed.paste(red, offset)
    zero = Image.new("L", canvas)
    mask = Image.merge("RGBA", (maskRed, zero, zero, Image.new("L", canvas, 255)))
    paintedMask = manifest.get("paintedMask")
    if paintedMask:
        paintedPath = manifestPath.parent / paintedMask
        with Image.open(paintedPath) as image:
            mask = image.convert("RGBA")
        if mask.size != canvas:
            raise ValueError("Painted mask dimensions must match the output canvas")
        _, green, blue, maskAlpha = mask.split()
        if green.getextrema() != (0, 0) or blue.getextrema() != (0, 0) or maskAlpha.getextrema() != (255, 255):
            raise ValueError("Painted mask must use opaque-red encoding")
    output.mkdir(parents=True, exist_ok=True)
    for index, entry in enumerate(manifest["layers"]):
        if "ownership" in entry and "work" in output.resolve().parts:
            with Image.open(manifestPath.parent / entry["path"]) as source:
                ownershipMap(entry, source.size).save(output / f"ownership-{index}.png")
    colorPath = output / manifest["colorFilename"]
    maskPath = output / manifest["maskFilename"]
    sprite.save(colorPath)
    mask.save(maskPath)
    record = {
        "manifest": str(manifestPath.resolve()), "manifestSha256": digest(manifestPath),
        "layers": sources, "crop": crop, "canvas": canvas, "size": size,
        "sourceRepair": manifest["sourceRepair"], "alphaHandling": manifest["alphaHandling"],
        "offset": offset, "resampling": (
            "per-layer Lanczos placement, then one shared Lanczos reduction"
            if any(entry.get("scale", 1) != 1 for entry in manifest["layers"])
            else "one Lanczos reduction"),
        "color": {"path": str(colorPath.resolve()), "sha256": digest(colorPath)},
        "mask": {"path": str(maskPath.resolve()), "sha256": digest(maskPath)},
        "acceptance": "pending explicit in-game user acceptance",
    }
    if paintedMask:
        record["paintedMask"] = {"path": paintedMask, "sha256": digest(paintedPath)}
    if paintedColor:
        record["paintedColor"] = {"path": paintedColor, "sha256": digest(paintedColorPath)}
    (output / "export.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.manifest, args.output)
