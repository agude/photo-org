"""Generate album-map JSON from folder structure."""

import json
import re
from collections import defaultdict
from pathlib import Path

import click


def is_date_folder(name: str) -> bool:
    """Check if folder name is a date-based auto-folder (not a real album)."""
    # Patterns like "Photos from 2023", "2023-01-15", etc.
    patterns = [
        r"^Photos from \d{4}$",
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{4}$",
    ]
    return any(re.match(p, name) for p in patterns)


@click.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path),
              help="Output JSON file (default: stdout)")
@click.option("--include-date-folders", is_flag=True,
              help="Include auto-generated date folders as albums")
def main(source: Path, output: Path | None, include_date_folders: bool):
    """Generate album map from folder structure.

    Reads SOURCE directory and creates a JSON mapping of relative file paths
    to album names based on their parent folder.

    Skips date-based auto-folders (like 'Photos from 2023') unless
    --include-date-folders is specified.
    """
    media_extensions = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif",
                        ".mov", ".mp4", ".avi", ".mkv", ".webp", ".raw", ".cr2", ".nef"}

    album_map: dict[str, list[str]] = defaultdict(list)
    skipped_folders = set()

    for path in source.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in media_extensions:
            continue

        relative_path = path.relative_to(source)

        # Skip root-level files
        if path.parent == source:
            continue

        # Get top-level folder as album name (first component of relative path)
        album_name = relative_path.parts[0]

        # Skip if it's a date folder or ALL_PHOTOS (which has no album)
        if album_name == "ALL_PHOTOS":
            continue
        if not include_date_folders and is_date_folder(album_name):
            skipped_folders.add(album_name)
            continue

        album_map[str(relative_path)].append(album_name)

    result = dict(album_map)

    if output:
        with open(output, "w") as f:
            json.dump(result, f, indent=2)
        click.echo(f"Wrote {len(result)} entries to {output}")
    else:
        click.echo(json.dumps(result, indent=2))

    if skipped_folders:
        click.echo(f"Skipped {len(skipped_folders)} date-based folders: {sorted(skipped_folders)[:5]}...",
                   err=True)


if __name__ == "__main__":
    main()
