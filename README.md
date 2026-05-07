# photo-org

Scripts for organizing a photo archive with hardlink-based albums.

## Architecture

- **by-date/**: All photos organized as `YYYY/MM/DD/filename.jpg`
- **albums/**: Curated selections as hardlinks into by-date
- **no-date/**: Photos without EXIF DateTimeOriginal
- **staging/**: Incoming photos before organization

## Naming Convention

```
YYYYMMDD-HHMMSS[-NNN][--Description].ext
```

- Timestamp from EXIF DateTimeOriginal
- Collision suffix (-001, -002) when multiple photos at same second
- Description preserved from original name or Google Photos title
- Extensions lowercase

## Scripts

| Script | Purpose |
|--------|---------|
| `organize-photos` | Move staging → by-date, create album hardlinks |
| `audit-albums` | Report naming issues, orphan links, empty folders |
| `find-photo-albums` | Find all albums containing a photo |
| `process-takeout` | Extract Takeout, run GooglePhotosTakeoutHelper |
| `dedup-photos` | Czkawka wrapper with standard settings |
| `generate-album-map` | Create album-map JSON from folder structure |

## Dependencies

- Python 3.10+
- exiftool
- czkawka-cli (for dedup-photos)

## Install

```bash
uv sync
```

## Usage

```bash
# Organize photos from staging into archive
uv run organize-photos --staging ~/staging --archive ~/Archive/photos

# With album assignments
uv run organize-photos --staging ~/staging --archive ~/Archive/photos --album-map albums.json

# Find all albums containing a photo
uv run find-photo-albums ~/Archive/photos/by-date/2013/07/28/photo.jpg
```
