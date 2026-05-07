# Photo organization scripts

# Default: show available recipes
default:
    @just --list

# Install/sync dependencies
sync:
    uv sync

# Run organize-photos
organize *ARGS:
    uv run organize-photos {{ARGS}}

# Run audit-albums
audit *ARGS:
    uv run audit-albums {{ARGS}}

# Find albums containing a photo
find-albums *ARGS:
    uv run find-photo-albums {{ARGS}}

# Generate album map from folder structure
gen-map *ARGS:
    uv run generate-album-map {{ARGS}}

# Run tests
test *ARGS:
    uv run pytest {{ARGS}}

# Dry-run organize on staging
dry-run staging archive:
    uv run organize-photos --staging {{staging}} --archive {{archive}} --dry-run

# Full organize with logging
run staging archive:
    uv run organize-photos --staging {{staging}} --archive {{archive}} --log organize.log

# Audit the main archive
audit-main:
    uv run audit-albums --archive ~/synology/Archive/photos
