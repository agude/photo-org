"""Find all albums containing a photo via hardlink detection."""

import subprocess
from pathlib import Path

import click


@click.command()
@click.argument("photo", type=click.Path(exists=True, path_type=Path))
@click.option("--archive", type=click.Path(exists=True, path_type=Path),
              help="Archive root (default: inferred from photo path)")
def main(photo: Path, archive: Path | None):
    """Find all albums containing PHOTO.

    Uses 'find -samefile' to locate all hardlinks to the given photo
    within the albums/ directory.
    """
    # Infer archive root if not provided
    if archive is None:
        # Walk up to find archive root (contains by-date/)
        for parent in photo.parents:
            if (parent / "by-date").is_dir():
                archive = parent
                break
        if archive is None:
            raise click.ClickException("Could not infer archive root. Use --archive.")

    albums_dir = archive / "albums"
    if not albums_dir.is_dir():
        raise click.ClickException(f"Albums directory not found: {albums_dir}")

    # Use find -samefile to locate hardlinks
    result = subprocess.run(
        ["find", str(albums_dir), "-samefile", str(photo)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise click.ClickException(f"find failed: {result.stderr}")

    links = result.stdout.strip().split("\n") if result.stdout.strip() else []

    if not links:
        click.echo(f"Photo not in any albums: {photo}")
        return

    click.echo(f"Photo {photo.name} is in {len(links)} album(s):")
    for link in links:
        link_path = Path(link)
        album_name = link_path.parent.name
        click.echo(f"  {album_name}")


if __name__ == "__main__":
    main()
