"""Organize photos from staging into archive with hardlink-based albums."""

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import click

EXIFTOOL_BATCH_SIZE = 100


def batch_extract_dates(files: list[Path]) -> dict[Path, datetime | None]:
    """Extract DateTimeOriginal from multiple files using batch exiftool call.

    Much faster than per-file calls since exiftool only starts once per batch.
    """
    if not files:
        return {}

    result: dict[Path, datetime | None] = {f: None for f in files}

    # Process in batches to avoid command line length limits
    for i in range(0, len(files), EXIFTOOL_BATCH_SIZE):
        batch = files[i:i + EXIFTOOL_BATCH_SIZE]
        try:
            proc = subprocess.run(
                ["exiftool", "-json", "-DateTimeOriginal", *[str(f) for f in batch]],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                continue

            data = json.loads(proc.stdout)
            for entry in data:
                source_file = Path(entry.get("SourceFile", ""))
                date_str = entry.get("DateTimeOriginal")
                if date_str:
                    try:
                        dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                        result[source_file] = dt
                    except ValueError:
                        pass
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            pass

    return result


def file_hash(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_description(filename: str) -> str | None:
    """Extract description from filename if present.

    Handles formats like:
    - 20130728-08-10-45--The Dress.jpg
    - 2013-07-28-08-10-45 - The Dress.jpg
    - IMG_1234--Description.jpg
    """
    # Pattern: anything followed by -- or " - " and then the description
    patterns = [
        r"--(.+?)(?:\.[^.]+)?$",  # --Description.ext
        r" - ([^-].+?)(?:\.[^.]+)?$",  # " - Description.ext" (but not " - _.ext")
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            desc = match.group(1).strip()
            # Skip placeholder descriptions
            if desc and desc != "_":
                return desc
    return None


def sanitize_description(desc: str) -> str:
    """Convert description to safe filename component."""
    # Replace spaces and special chars with underscores
    sanitized = re.sub(r"[^\w]+", "_", desc)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")
    # Limit length
    return sanitized[:50] if sanitized else ""


def generate_filename(dt: datetime, ext: str, description: str | None, collision: int = 0) -> str:
    """Generate filename in standard format."""
    base = dt.strftime("%Y%m%d-%H%M%S")

    if collision > 0:
        base = f"{base}-{collision:03d}"

    if description:
        safe_desc = sanitize_description(description)
        if safe_desc:
            base = f"{base}--{safe_desc}"

    return f"{base}{ext.lower()}"


def compute_destination(archive: Path, dt: datetime) -> Path:
    """Compute destination directory based on date."""
    return archive / "by-date" / str(dt.year) / f"{dt.month:02d}" / f"{dt.day:02d}"


def find_available_path(dest_dir: Path, filename: str, source: Path) -> tuple[Path, bool]:
    """Find available path, handling collisions.

    Returns (path, is_duplicate) where is_duplicate means exact same file exists.
    Hashes are computed lazily only when destination exists (collision check).
    """
    dest = dest_dir / filename

    if not dest.exists():
        return dest, False

    # Only compute source hash when we need to check for duplicates
    source_hash = file_hash(source)

    # Check if it's the same file
    if file_hash(dest) == source_hash:
        return dest, True

    # Collision - find available suffix
    stem = dest.stem
    ext = dest.suffix

    # Remove existing collision suffix if present
    match = re.match(r"(.+)-(\d{3})(--.*)?$", stem)
    if match:
        base = match.group(1)
        desc_part = match.group(3) or ""
    else:
        # Check for description
        match = re.match(r"(.+?)(--.*)?$", stem)
        if match:
            base = match.group(1)
            desc_part = match.group(2) or ""
        else:
            base = stem
            desc_part = ""

    for i in range(1, 1000):
        new_stem = f"{base}-{i:03d}{desc_part}"
        new_dest = dest_dir / f"{new_stem}{ext}"
        if not new_dest.exists():
            return new_dest, False
        if file_hash(new_dest) == source_hash:
            return new_dest, True

    raise RuntimeError(f"Too many collisions for {filename}")


@click.command()
@click.option("--staging", required=True, type=click.Path(exists=True, path_type=Path),
              help="Source directory with photos to organize")
@click.option("--archive", required=True, type=click.Path(exists=True, path_type=Path),
              help="Archive root (contains by-date/, albums/, etc.)")
@click.option("--album-map", type=click.Path(exists=True, path_type=Path),
              help="JSON file mapping photos to albums")
@click.option("--dry-run", is_flag=True, help="Show what would be done without doing it")
@click.option("--log", type=click.Path(path_type=Path), help="Log file for actions")
def main(staging: Path, archive: Path, album_map: Path | None, dry_run: bool, log: Path | None):
    """Organize photos from staging into archive."""
    by_date = archive / "by-date"
    no_date = archive / "no-date"
    albums_dir = archive / "albums"

    # Load album map if provided
    albums: dict[str, list[str]] = {}
    if album_map:
        with open(album_map) as f:
            albums = json.load(f)

    log_file = open(log, "a") if log else None

    def log_action(msg: str):
        click.echo(msg)
        if log_file:
            log_file.write(f"{datetime.now().isoformat()} {msg}\n")

    # Find all media files
    media_extensions = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif",
                        ".mov", ".mp4", ".avi", ".mkv", ".webp", ".raw", ".cr2", ".nef"}

    files = [f for f in staging.rglob("*") if f.is_file() and f.suffix.lower() in media_extensions]

    log_action(f"Found {len(files)} media files in {staging}")
    log_action("Extracting dates (batch mode)...")

    # Batch extract all dates upfront - much faster than per-file
    dates = batch_extract_dates(files)
    log_action(f"Extracted dates for {sum(1 for d in dates.values() if d)} files")

    stats = {"moved": 0, "skipped_dup": 0, "no_date": 0, "hardlinked": 0}

    for source in files:
        description = extract_description(source.name)
        dt = dates.get(source)

        if dt is None:
            # No date - move to no-date folder
            dest_dir = no_date
            # Use original filename but sanitize
            dest = dest_dir / source.name
            if dest.exists():
                # Only hash when we need to check for duplicates
                if file_hash(dest) == file_hash(source):
                    log_action(f"SKIP (dup): {source} -> {dest}")
                    stats["skipped_dup"] += 1
                    if not dry_run:
                        source.unlink()
                    continue
                # Find unique name
                stem = dest.stem
                ext = dest.suffix
                for i in range(1, 1000):
                    dest = dest_dir / f"{stem}-{i:03d}{ext}"
                    if not dest.exists():
                        break

            if dry_run:
                log_action(f"WOULD MOVE (no-date): {source} -> {dest}")
            else:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(source, dest)
                log_action(f"MOVE (no-date): {source} -> {dest}")
            stats["no_date"] += 1
            continue

        # Has date - compute destination
        dest_dir = compute_destination(archive, dt)
        filename = generate_filename(dt, source.suffix, description)
        dest, is_dup = find_available_path(dest_dir, filename, source)

        if is_dup:
            log_action(f"SKIP (dup): {source} -> {dest}")
            stats["skipped_dup"] += 1
            if not dry_run:
                source.unlink()  # Remove duplicate from staging
            continue

        if dry_run:
            log_action(f"WOULD MOVE: {source} -> {dest}")
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(source, dest)
            log_action(f"MOVE: {source} -> {dest}")
        stats["moved"] += 1

        # Create album hardlinks
        relative_dest = dest.relative_to(archive)
        source_key = str(source.relative_to(staging))

        for album_name in albums.get(source_key, []):
            album_dir = albums_dir / album_name
            album_link = album_dir / dest.name

            if dry_run:
                log_action(f"WOULD LINK: {album_link} -> {dest}")
            else:
                album_dir.mkdir(parents=True, exist_ok=True)
                if album_link.exists():
                    if os.path.samefile(album_link, dest):
                        continue  # Already linked
                    # Different file with same name - add suffix
                    stem = album_link.stem
                    ext = album_link.suffix
                    for i in range(1, 1000):
                        album_link = album_dir / f"{stem}-{i:03d}{ext}"
                        if not album_link.exists():
                            break
                os.link(dest, album_link)
                log_action(f"LINK: {album_link} -> {dest}")
            stats["hardlinked"] += 1

    log_action(f"Done: {stats['moved']} moved, {stats['skipped_dup']} duplicates skipped, "
               f"{stats['no_date']} no-date, {stats['hardlinked']} album links created")

    if log_file:
        log_file.close()


if __name__ == "__main__":
    main()
