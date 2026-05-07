# Photo Archive Consolidation Plan

Detailed execution plan for consolidating photo sources into a single organized archive.

**Reference:** `~/Documents/90-99 Reference/91 Library/91.11 Tech Runbook/Photo Archive Consolidation Plan.md`

---

## Current Status

- [x] Directory structure created (`Archive/photos/{by-date,albums,no-date,staging}`)
- [x] Scripts written and tested (`organize-photos`, `audit-albums`, `find-photo-albums`, `generate-album-map`)
- [x] Test run completed (6 photos, hardlinks verified)
- [ ] Full migration not started

---

## Phase 0: Infrastructure Setup

### 0.1 Ansible Integration (Optional, can defer)
- [ ] Add photo tools to workstation Ansible role
  - exiftool, czkawka-cli, uv
  - GooglePhotosTakeoutHelper (`uv tool install google-photos-takeout-helper`)
- [ ] Add `find-photo-albums` wrapper to synology role (runs via SSH)

### 0.2 Install Tools Locally (Do now if skipping Ansible)
```bash
# On dirac/einstein
sudo apt install libimage-exiftool-perl
cargo install czkawka_cli  # or download release
uv tool install google-photos-takeout-helper
```

---

## Phase 1: Clean Up Source Data

### 1.1 Fix Duplicate Albums in cleaned_up
There are 9 albums with `?` / `—` naming variants that are likely duplicates.

```bash
# List them
cd ~/synology/Archive/photo_backups/google_photo_backups/cleaned_up
ls -d *' ? '*

# For each pair, verify identical and remove one:
diff -rq "2004 ? Mount Diablo Senior Prom" "2004 — Mount Diablo Senior Prom"
# If identical, remove the ? version
rm -rf "2004 ? Mount Diablo Senior Prom"
```

**Albums to check:**
- [ ] `2004 ? Mount Diablo Senior Prom` ↔ `2004 — Mount Diablo Senior Prom`
- [ ] `2008-08-23 ? Lime Ridge` ↔ `2008-08-23 — Lime Ridge`
- [ ] `2015-06 ? Drive Home To California` ↔ `2015-06 — Drive Home To California`
- [ ] `2015-09 ? Vienna` ↔ `2015-09 — Vienna`
- [ ] `2015-12 ? Monterey` ↔ `2015-12 — Monterey`
- [ ] `2015 ? CERN` ↔ `2015 — CERN`
- [ ] (check for others with `ls -d *'?'*`)

### 1.2 Rename Source Directory
```bash
mv ~/synology/Archive/photo_backups ~/synology/Archive/photo_sources
```

---

## Phase 2: Initial Migration

### 2.1 Generate Album Map for cleaned_up

The existing structure has albums as top-level folders. Need to generate a map.

```bash
cd ~/Projects/photo-org

# Generate album map from cleaned_up structure
# Each top-level folder becomes an album (except date-only folders)
uv run generate-album-map \
  ~/synology/Archive/photo_sources/google_photo_backups/cleaned_up \
  -o ~/synology/Archive/photos/staging/cleaned_up_albums.json
```

**Review the output** — some folders may be date-based auto-folders that shouldn't become albums.

### 2.2 Copy cleaned_up to Staging
```bash
# Copy (don't move yet) to staging for processing
cp -r ~/synology/Archive/photo_sources/google_photo_backups/cleaned_up/* \
      ~/synology/Archive/photos/staging/
```

### 2.3 Dry Run
```bash
cd ~/Projects/photo-org
just organize \
  --staging ~/synology/Archive/photos/staging \
  --archive ~/synology/Archive/photos \
  --album-map ~/synology/Archive/photos/staging/cleaned_up_albums.json \
  --dry-run 2>&1 | tee dry-run.log

# Review dry-run.log for issues
grep -E "(ERROR|SKIP|no-date)" dry-run.log | head -50
```

### 2.4 Full Migration Run
```bash
just organize \
  --staging ~/synology/Archive/photos/staging \
  --archive ~/synology/Archive/photos \
  --album-map ~/synology/Archive/photos/staging/cleaned_up_albums.json \
  --log ~/synology/Archive/photos/organize.log
```

### 2.5 Verify
```bash
# Check counts
find ~/synology/Archive/photos/by-date -type f | wc -l
find ~/synology/Archive/photos/albums -type f | wc -l
find ~/synology/Archive/photos/no-date -type f | wc -l

# Run audit
just audit-main

# Spot-check hardlinks on NAS
ssh synology 'ls -lai ~/Archive/photos/by-date/2013/07/28/ | head -5'
ssh synology 'ls -lai ~/Archive/photos/albums/"2013-07-28 -- Alex and Connie_s Wedding"/ | head -5'
```

---

## Phase 3: Wedding Photos (connie_hdd)

### 3.1 Assess Overlap
```bash
# The cleaned_up wedding album has 90 curated photos
# connie_hdd has 2,143 photos (full set from all photographers)
# 91 in connie_hdd have descriptions (overlap with curated)

# Find unique photos in connie_hdd
cd ~/Projects/photo-org
# Use Czkawka to compare
czkawka_cli dup \
  -d ~/synology/Archive/connie_hdd/Wedding/wedding_pictures \
  -d ~/synology/Archive/photos/by-date \
  -x IMAGE \
  -f results.txt
```

### 3.2 Copy Unique Photos to Staging
```bash
# After identifying unique photos, copy to staging
mkdir ~/synology/Archive/photos/staging/wedding-full
# Copy unique files (method TBD based on Czkawka output)
```

### 3.3 Create Album Map
```bash
# All wedding photos go to "2013-07-28 -- Wedding All" album
# Generate map manually or via script
```

### 3.4 Organize
```bash
just organize \
  --staging ~/synology/Archive/photos/staging/wedding-full \
  --archive ~/synology/Archive/photos \
  --album-map ~/synology/Archive/photos/staging/wedding-albums.json \
  --log ~/synology/Archive/photos/organize.log
```

---

## Phase 4: Other Sources

### 4.1 Flickr Backup
```bash
# Check metadata state
exiftool -DateTimeOriginal ~/synology/Archive/photo_sources/flickr_backup/data-download-1/*.jpg | head -20

# Dedup against archive
czkawka_cli dup \
  -d ~/synology/Archive/photo_sources/flickr_backup \
  -d ~/synology/Archive/photos/by-date \
  -x IMAGE

# Process unique photos (likely no album assignment)
```

### 4.2 MobileBackup
```bash
# Dedup against archive
czkawka_cli dup \
  -d ~/synology/Photos/MobileBackup \
  -d ~/synology/Archive/photos/by-date \
  -x IMAGE

# Review unique photos, copy to staging, organize
```

### 4.3 Verify Takeout tgz Redundancy
```bash
# Spot-check that tgz contents are in the archive
tar -tzf ~/synology/Archive/photo_sources/google_photo_backups/takeout-20240806T135006Z-001.tgz | head -20

# If confirmed redundant, tgz files can stay as cold backup
# Don't delete — just note they're archived
```

---

## Phase 5: Ongoing Workflow

See runbook for quarterly Takeout update process.

---

## Rollback Plan

If something goes wrong:

1. **Files moved but hardlinks failed:** Files are still in by-date, just not in albums. Re-run with album-map.

2. **Wrong files moved:** Check organize.log for what was done. Files came from staging (which was a copy), originals still in photo_sources.

3. **Need to start over:**
   ```bash
   rm -rf ~/synology/Archive/photos/by-date/*
   rm -rf ~/synology/Archive/photos/albums/*
   rm -rf ~/synology/Archive/photos/no-date/*
   # Re-run from Phase 2.2
   ```

---

## Time Estimates

| Phase | Estimated Time | Notes |
|-------|---------------|-------|
| Phase 1 (cleanup) | 30 min | Manual verification of 9 album pairs |
| Phase 2 (migration) | 2-4 hours | 39k files, mostly waiting |
| Phase 3 (wedding) | 1 hour | Dedup + organize ~2k files |
| Phase 4 (other) | 1-2 hours | Flickr + MobileBackup |

---

## Next Action

**Start with Phase 1.1:** Fix the duplicate `?`/`—` albums in cleaned_up.

```bash
cd ~/synology/Archive/photo_backups/google_photo_backups/cleaned_up
ls -d *' ? '*
```
