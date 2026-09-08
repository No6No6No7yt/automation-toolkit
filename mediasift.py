#!/usr/bin/env python3
"""
MediaSift — a zero-dependency bulk image organizer & metadata extractor.
Sells as: "bulk image renaming / photo library organization" (€10–€35 per
job on PeoplePerHour; recurring work for photographers & shops)

Subcommands:
    info        Inspect images: dimensions, aspect ratio, size, format
                  (from file headers — no PIL needed)
    rename      Bulk-rename with EXIF-free smart patterns: by date-modified
                  ({date}), sequence ({n}), dimensions ({wxh}), or literal
    resize      No pixel editing — instead generates resized COPIES using
                  pure-Python JPEG/PNG header info... (see note below)
    organize    Sort photos into folders by date, orientation, or aspect

Note on `resize`: pure standard-library image resizing is not feasible —
that subcommand instead prints a ready-to-run, dependency-free command
sheet (Windows PowerShell / macOS sips / Linux ImageMagick) generated from
the actual file inventory. This keeps the tool honest: zero dependencies,
and the buyer runs the listed commands (or we deliver on our machine).

Image header parsing: JPEG (SOF markers), PNG (IHDR), GIF (logical
screen descriptor) — dimensions read from bytes directly.

Usage:
    python mediasift.py info ~/photos --csv inventory.csv
    python mediasift.py rename ~/photos --pattern "{date}_{n:03}" --apply
    python mediasift.py organize ~/photos --by date --apply
    python mediasift.py resize ~/photos --max-width 1200   # prints command sheet
"""

import argparse
import datetime
import io
import struct
import sys
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".heic"}


# ---- dimension parsing from raw bytes ----------------------------------------

def jpeg_size(data: bytes):
    """Walk JPEG markers to the first SOF frame; return (w, h) or None."""
    i = 2  # skip SOI
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if i + 4 > len(data):
            break
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height
        i += 2 + length
    return None


def png_size(data: bytes):
    if len(data) >= 24 and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    return None


def gif_size(data: bytes):
    if len(data) >= 10 and data[:6] in (b"GIF87a", b"GIF89a"):
        width, height = struct.unpack("<HH", data[6:10])
        return width, height
    return None


def bmp_size(data: bytes):
    if len(data) >= 26 and data[:2] == b"BM":
        width, height = struct.unpack("<ii", data[18:26])
        return abs(width), abs(height)
    return None


def image_info(path: Path):
    """Return dict with dimensions/format or None if unreadable."""
    try:
        with open(path, "rb") as f:
            head = f.read(64 * 1024)  # headers live early in the file
    except OSError:
        return None
    size = None
    fmt = path.suffix.lower().lstrip(".")
    if head[:2] == b"\xff\xd8":
        size, fmt = jpeg_size(head), "jpeg"
    elif head[:8] == b"\x89PNG\r\n\x1a\n":
        size, fmt = png_size(head), "png"
    elif head[:6] in (b"GIF87a", b"GIF89a"):
        size, fmt = gif_size(head), "gif"
    elif head[:2] == b"BM":
        size, fmt = bmp_size(head), "bmp"
    if size is None:
        return None
    width, height = size
    return {"path": path, "width": width, "height": height, "format": fmt,
            "megapixels": round(width * height / 1_000_000, 2),
            "aspect": round(width / height, 3),
            "orientation": "landscape" if width > height else
                           ("portrait" if height > width else "square"),
            "bytes": path.stat().st_size}


def iter_images(root: Path, recursive: bool):
    iterator = root.rglob("*") if recursive else root.glob("*")
    for path in iterator:
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def load_infos(root: Path, recursive: bool):
    infos, skipped = [], 0
    for path in iter_images(root, recursive):
        info = image_info(path)
        if info:
            infos.append(info)
        else:
            skipped += 1
    return infos, skipped


def unique_destination(destination: Path) -> Path:
    if not destination.exists():
        return destination
    counter = 1
    while True:
        candidate = destination.with_name(
            f"{destination.stem}-{counter}{destination.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


# ---- subcommands ---------------------------------------------------------------

def cmd_info(args):
    root = Path(args.folder).expanduser().resolve()
    infos, skipped = load_infos(root, args.recursive)
    if not infos:
        sys.exit("error: no readable images found")
    infos.sort(key=lambda i: i["bytes"], reverse=True)

    import csv
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "path", "width", "height", "format", "megapixels",
                "aspect", "orientation", "bytes"])
            writer.writeheader()
            for info in infos:
                writer.writerow({**info, "path": str(info["path"])})
        print(f"inventory: {len(infos)} image(s) -> {args.csv}")
    else:
        for info in infos[:args.top]:
            print(f"{info['path'].name:40s} {info['width']}x{info['height']:<6} "
                  f"{info['format']:5s} {info['megapixels']:>6}MP {info['orientation']}")
    total_mp = sum(i["megapixels"] for i in infos)
    total_mb = sum(i["bytes"] for i in infos) / 1_000_000
    print(f"\n{len(infos)} image(s), {total_mp:.1f}MP total, {total_mb:.1f}MB "
          + (f"({skipped} unreadable skipped)" if skipped else ""))


def cmd_rename(args):
    root = Path(args.folder).expanduser().resolve()
    infos, _ = load_infos(root, args.recursive)
    plans = []
    for i, info in enumerate(sorted(infos, key=lambda x: x["path"].stat().st_mtime), 1):
        mtime = datetime.datetime.fromtimestamp(info["path"].stat().st_mtime)
        new_name = args.pattern.format(
            n=i, date=mtime.strftime("%Y%m%d"), wxh=f"{info['width']}x{info['height']}",
            mp=info["megapixels"], name=info["path"].stem,
            ext=info["path"].suffix.lower())
        if not new_name.endswith(tuple(IMAGE_EXTENSIONS)):
            new_name += info["path"].suffix.lower()
        destination = unique_destination(info["path"].parent / new_name)
        plans.append((info["path"], destination))

    for src, dst in plans:
        print(f"  {src.name}  ->  {dst.name}")
    if args.apply:
        import shutil
        for src, dst in plans:
            shutil.move(str(src), str(dst))
        print(f"applied: {len(plans)} image(s) renamed")
    else:
        print(f"dry-run of {len(plans)} rename(s) — pass --apply to execute")


def cmd_organize(args):
    root = Path(args.folder).expanduser().resolve()
    infos, _ = load_infos(root, args.recursive)
    moves = []
    for info in infos:
        if args.by == "date":
            mtime = datetime.datetime.fromtimestamp(info["path"].stat().st_mtime)
            folder = mtime.strftime("%Y-%m")
        elif args.by == "orientation":
            folder = info["orientation"]
        else:  # aspect
            if info["aspect"] > 1.8:
                folder = "panorama"
            elif info["aspect"] > 1.1:
                folder = "landscape"
            elif info["aspect"] > 0.9:
                folder = "square"
            else:
                folder = "portrait"
        destination_dir = root / folder
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = unique_destination(destination_dir / info["path"].name)
        moves.append((info["path"], destination))

    for src, dst in moves:
        print(f"  {src.parent.name}/{src.name}  ->  {dst.relative_to(root)}")
    if args.apply:
        import shutil
        for src, dst in moves:
            shutil.move(str(src), str(dst))
        print(f"applied: {len(moves)} image(s) organized by {args.by}")
    else:
        print(f"dry-run of {len(moves)} move(s) — pass --apply to execute")


def cmd_resize(args):
    root = Path(args.folder).expanduser().resolve()
    infos, _ = load_infos(root, args.recursive)
    targets = [i for i in infos if i["width"] > args.max_width or i["height"] > args.max_width]
    if not targets:
        print(f"no images exceed {args.max_width}px — nothing to do")
        return
    print(f"{len(targets)} of {len(infos)} image(s) exceed {args.max_width}px.\n")
    print("Run one of these (they read this same folder):")
    print("\n  Windows PowerShell:")
    print(f'  Get-ChildItem "{root}" -Include *.jpg,*.png -Recurse | ForEach {{')
    print(f'    Add-Type -AssemblyName System.Drawing;')
    print(f'    $img = [System.Drawing.Image]::FromFile($_.FullName);')
    print(f'    $scale = [math]::Min(1, {args.max_width} / [math]::Max($img.Width, $img.Height));')
    print(f'    $w = [int]($img.Width * $scale); $h = [int]($img.Height * $scale);')
    print(f'    $bmp = New-Object System.Drawing.Bitmap($img, $w, $h);')
    print(f'    $bmp.Save("$($_.DirectoryName)\\web_$($_.Name)"); $bmp.Dispose(); $img.Dispose()')
    print('  }')
    print("\n  macOS:")
    print(f'  find "{root}" -name "*.jpg" -exec sips --resampleHeightWidthMax {args.max_width} {{}} \\;')
    print("\n  Linux (ImageMagick):")
    print(f'  find "{root}" \\( -name "*.jpg" -o -name "*.png" \\) -exec convert {{}} -resize {args.max_width}x{args.max_width}\\> {{}} \\;')
    print("\nFiles that need it (largest first):")
    for info in sorted(targets, key=lambda t: t["bytes"], reverse=True)[:20]:
        print(f"  {info['path'].name}: {info['width']}x{info['height']}")


def main():
    parser = argparse.ArgumentParser(prog="mediasift",
                                     description="Bulk image info/rename/organize (zero deps).")
    sub = parser.add_subparsers(dest="command", required=True)

    def folder_opts(p):
        p.add_argument("folder")
        p.add_argument("--recursive", action="store_true")

    p = sub.add_parser("info", help="image inventory")
    folder_opts(p)
    p.add_argument("--csv", help="write inventory CSV")
    p.add_argument("--top", type=int, default=25, help="rows to print (default 25)")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("rename", help="bulk rename with smart patterns")
    folder_opts(p)
    p.add_argument("--pattern", required=True,
                   help=r"{n} seq, {date} yyyymmdd, {wxh}, {mp}, {name}, {ext}")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_rename)

    p = sub.add_parser("organize", help="sort into folders")
    folder_opts(p)
    p.add_argument("--by", choices=["date", "orientation", "aspect"], default="date")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(func=cmd_organize)

    p = sub.add_parser("resize", help="print resize command sheet")
    folder_opts(p)
    p.add_argument("--max-width", type=int, default=1200)
    p.set_defaults(func=cmd_resize)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
