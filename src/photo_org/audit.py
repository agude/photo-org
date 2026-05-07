"""Audit photo archive for issues."""

import os
from collections import defaultdict
from pathlib import Path

import click


@click.command()
@click.option("--archive", required=True, type=click.Path(exists=True, path_type=Path),
              help="Archive root (contains by-date/, albums/, etc.)")
def main(archive: Path):
    """Audit archive for naming issues, orphan links, empty folders."""
    by_date = archive / "by-date"
    albums_dir = archive / "albums"
    no_date = archive / "no-date"

    issues = []

    # Check for empty directories
    click.echo("Checking for empty directories...")
    for root, dirs, files in os.walk(archive):
        root_path = Path(root)
        if not dirs and not files and root_path != archive:
            issues.append(f"EMPTY DIR: {root_path}")

    # Check album naming consistency
    click.echo("Checking album naming...")
    if albums_dir.is_dir():
        album_names = [d.name for d in albums_dir.iterdir() if d.is_dir()]

        # Check for duplicate-ish names (? vs —)
        normalized = defaultdict(list)
        for name in album_names:
            norm = name.replace("?", "—").replace(" - ", " -- ")
            normalized[norm].append(name)

        for norm, names in normalized.items():
            if len(names) > 1:
                issues.append(f"SIMILAR ALBUMS: {names}")

    # Check for broken hardlinks (link count = 1 in albums means by-date copy deleted)
    click.echo("Checking album hardlinks...")
    if albums_dir.is_dir():
        for album in albums_dir.iterdir():
            if not album.is_dir():
                continue
            for photo in album.iterdir():
                if photo.is_file():
                    stat = photo.stat()
                    if stat.st_nlink == 1:
                        issues.append(f"ORPHAN (link count 1): {photo}")

    # Check by-date structure
    click.echo("Checking by-date structure...")
    if by_date.is_dir():
        for year_dir in by_date.iterdir():
            if not year_dir.is_dir():
                continue
            if not year_dir.name.isdigit() or len(year_dir.name) != 4:
                issues.append(f"BAD YEAR DIR: {year_dir}")
                continue

            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                if not month_dir.name.isdigit() or len(month_dir.name) != 2:
                    issues.append(f"BAD MONTH DIR: {month_dir}")
                    continue

                for day_dir in month_dir.iterdir():
                    if not day_dir.is_dir():
                        continue
                    if not day_dir.name.isdigit() or len(day_dir.name) != 2:
                        issues.append(f"BAD DAY DIR: {day_dir}")

    # Check no-date folder
    if no_date.is_dir():
        no_date_count = sum(1 for f in no_date.iterdir() if f.is_file())
        if no_date_count > 0:
            click.echo(f"INFO: {no_date_count} photos in no-date/")

    # Report
    click.echo()
    if issues:
        click.echo(f"Found {len(issues)} issues:")
        for issue in issues:
            click.echo(f"  {issue}")
    else:
        click.echo("No issues found.")


if __name__ == "__main__":
    main()
