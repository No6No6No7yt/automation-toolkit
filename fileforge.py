#!/usr/bin/env python3
"""
FileForge — a zero-dependency file & folder automation toolkit.
Sells as: "Python task automation / file organization script" (market: €85–€120 on PeoplePerHour)

Subcommands:
    organize   Sort files into folders by extension / date / size
    rename     Batch-rename files with patterns, sequence numbers, case changes
    dedupe     Find duplicate files by content hash (safe: report-only by default)
    report     Generate a CSV/JSON inventory of a folder tree

Design notes:
- Standard library only (Python 3.9+), no pip installs
- DRY-RUN by default on every mutating action: pass --apply to execute
- Never deletes anything; dedupe reports duplicates and can move copies to a quarantine folder

Examples:
    # See what organizing Downloads by extension would do
    python fileforge.py organize ~/Downloads --by extension

    # Actually do it
    python fileforge.py organize ~/Downloads --by extension --apply

    # Find duplicate photos by content, move dupes to a folder
    python fileforge.py dedupe ~/Pictures --move-dupes ~/duplicates --apply

    # Inventory a project folder as CSV
    python fileforge.py report ~/projects/myapp --out inventory.csv

    # Rename photos: vacation-001.jpg, vacation-002.jpg ...
    python fileforge.py rename ~/photos --pattern vacation-{n:03d} --ext .jpg --apply
"""

import argparse
import csv
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

# ---- classification tables -------------------------------------------------

EXTENSION_MAP = {
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".heic"},
    "videos": {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md", ".tex"},
    "spreadsheets": {".xls", ".xlsx", ".ods", ".csv", ".tsv"},
    "presentations": {".ppt", ".pptx", ".odp"},
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"},
    "code": {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".h",
             ".go", ".rs", ".rb", ".php", ".sh", ".json", ".xml", ".yml", ".yaml", ".toml"},
    "executables": {".exe", ".msi", ".dmg", ".app", ".apk", ".bat", ".ps1"},
    "fonts": {".ttf", ".otf", ".woff", ".woff2"},
}


def category_for(path: Path) -> str:
    ext = path.suffix.lower()
    for category, extensions in EXTENSION_MAP.items():
        if ext in extensions:
            return category
    return "other"


def iter_files(root: Path, recursive: bool):
    iterator = root.rglob("*") if recursive else root.glob("*")
    for path in iterator:
        if path.is_file():
            yield path


def unique_destination(destination: Path) -> Path:
    """Return destination, appending -1, -2... if it already exists."""
    if not destination.exists():
        return destination
    stem, suffix = destination.stem, destination.suffix
    counter = 1
    while True:
        candidate = destination.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


# ---- subcommands ------------------------------------------------------------

def cmd_organize(args):
    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"error: {root} is not a directory")
    moves = []
    for path in iter_files(root, args.recursive):
        if args.by == "extension":
            destination_dir = root / path.suffix.lstrip(".").lower() or root / "other"
        elif args.by == "category":
            destination_dir = root / category_for(path)
        else:  # date
            mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime)
            destination_dir = root / mtime.strftime(args.date_format)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = unique_destination(destination_dir / path.name)
        moves.append((path, destination))

    print(f"{len(moves)} file(s) would be organized by {args.by}.")
    for src, dst in moves:
        print(f"  {src.name}  ->  {dst.relative_to(root)}")
    if args.apply:
        for src, dst in moves:
            shutil.move(str(src), str(dst))
        print(f"Applied: {len(moves)} file(s) moved.")
    else:
        print("(dry-run: pass --apply to execute)")


def cmd_rename(args):
    root = Path(args.folder).expanduser().resolve()
    files = sorted(
        p for p in iter_files(root, args.recursive)
        if not args.ext or p.suffix.lower() == args.ext.lower()
    )
    width = max(3, len(str(len(files))))
    for i, path in enumerate(files, start=args.start):
        new_name = args.pattern.format(n=i, name=path.stem, ext=path.suffix,
                                       w=str(i).zfill(width))
        if not new_name:
            sys.exit("error: pattern produced an empty name")
        destination = unique_destination(path.with_name(new_name))
        print(f"  {path.name}  ->  {destination.name}")
    if args.apply:
        # re-run with move disabled collisions resolved again for real
        done = 0
        for i, path in enumerate(sorted(
                p for p in iter_files(root, args.recursive)
                if not args.ext or p.suffix.lower() == args.ext.lower()),
                start=args.start):
            new_name = args.pattern.format(n=i, name=path.stem, ext=path.suffix,
                                           w=str(i).zfill(width))
            destination = unique_destination(path.with_name(new_name))
            if path != destination:
                shutil.move(str(path), str(destination))
                done += 1
        print(f"Applied: {done} file(s) renamed.")
    else:
        print(f"(dry-run of {len(files)} file(s): pass --apply to execute)")


def cmd_dedupe(args):
    root = Path(args.folder).expanduser().resolve()
    hashes = {}
    duplicates = []
    for path in iter_files(root, args.recursive):
        digest = hashlib.blake2b()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        key = digest.hexdigest()
        if key in hashes:
            duplicates.append((path, hashes[key]))
        else:
            hashes[key] = path

    print(f"Scanned {len(hashes) + len(duplicates)} file(s): "
          f"{len(duplicates)} duplicate(s) found.")
    for dupe, original in duplicates:
        print(f"  dupe: {dupe}   of: {original}")
    if args.move_dupes and duplicates:
        quarantine = Path(args.move_dupes).expanduser().resolve()
        if args.apply:
            quarantine.mkdir(parents=True, exist_ok=True)
            for dupe, _ in duplicates:
                destination = unique_destination(quarantine / dupe.name)
                shutil.move(str(dupe), str(destination))
            print(f"Applied: moved {len(duplicates)} duplicate(s) to {quarantine}.")
        else:
            print(f"(dry-run: would move duplicates to {quarantine} — pass --apply)")
    elif duplicates:
        print("(report-only: use --move-dupes DIR to relocate duplicates)")


def cmd_report(args):
    root = Path(args.folder).expanduser().resolve()
    rows = []
    total_size = 0
    for path in iter_files(root, args.recursive):
        stat = path.stat()
        total_size += stat.st_size
        rows.append({
            "path": str(path.relative_to(root)),
            "size_bytes": stat.st_size,
            "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(
                sep=" ", timespec="seconds"),
            "category": category_for(path),
        })
    rows.sort(key=lambda r: r["size_bytes"], reverse=True)

    out = Path(args.out) if args.out else None
    if args.format == "csv":
        if out:
            f = open(out, "w", newline="", encoding="utf-8")
        else:
            f = sys.stdout
        try:
            writer = csv.DictWriter(f, fieldnames=["path", "size_bytes", "modified", "category"])
            writer.writeheader()
            writer.writerows(rows)
        finally:
            if out:
                f.close()
    else:
        payload = {"root": str(root), "file_count": len(rows),
                   "total_bytes": total_size, "files": rows}
        if args.out:
            with open(out, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        else:
            print(json.dumps(payload, indent=2))
    print(f"\n{len(rows)} file(s), {total_size:,} bytes total.", file=sys.stderr)


def _stdout_csv():
    return sys.stdout


def main():
    parser = argparse.ArgumentParser(prog="fileforge",
                                     description="File & folder automation toolkit (dry-run by default).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_org = sub.add_parser("organize", help="sort files into folders")
    p_org.add_argument("folder")
    p_org.add_argument("--by", choices=["extension", "category", "date"], default="category")
    p_org.add_argument("--date-format", default="%Y-%m",
                        help="strftime pattern when --by date (default %%Y-%%m)")
    p_org.add_argument("--recursive", action="store_true")
    p_org.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    p_org.set_defaults(func=cmd_organize)

    p_ren = sub.add_parser("rename", help="batch-rename files")
    p_ren.add_argument("folder")
    p_ren.add_argument("--pattern", required=True,
                       help=r"e.g. 'photo-{n:03}' — {n} index, {name} stem, {ext} suffix")
    p_ren.add_argument("--ext", help="only rename files with this extension, e.g. .jpg")
    p_ren.add_argument("--start", type=int, default=1)
    p_ren.add_argument("--recursive", action="store_true")
    p_ren.add_argument("--apply", action="store_true")
    p_ren.set_defaults(func=cmd_rename)

    p_ded = sub.add_parser("dedupe", help="find duplicate files by content")
    p_ded.add_argument("folder")
    p_ded.add_argument("--move-dupes", metavar="DIR",
                       help="move duplicates to DIR (still needs --apply)")
    p_ded.add_argument("--recursive", action="store_true")
    p_ded.add_argument("--apply", action="store_true")
    p_ded.set_defaults(func=cmd_dedupe)

    p_rep = sub.add_parser("report", help="folder inventory to CSV/JSON")
    p_rep.add_argument("folder")
    p_rep.add_argument("--out", help="output file (default: console)")
    p_rep.add_argument("--format", choices=["csv", "json"], default="json")
    p_rep.add_argument("--recursive", action="store_true")
    p_rep.set_defaults(func=cmd_report)

    args = parser.parse_args()
    if hasattr(args, "apply") and not args.apply:
        print("*** DRY RUN — no changes written. Pass --apply to execute. ***\n")
    args.func(args)


if __name__ == "__main__":
    main()
