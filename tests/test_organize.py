"""Tests for organize module."""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from photo_org.organize import (
    batch_extract_dates,
    extract_description,
    sanitize_description,
    generate_filename,
    compute_destination,
    file_hash,
    parse_date_from_filename,
    write_exif_date,
)


class TestExtractDescription:
    def test_double_dash_format(self):
        assert extract_description("20130728-08-10-45--The Dress.jpg") == "The Dress"

    def test_space_dash_space_format(self):
        assert extract_description("2013-07-28 - The Dress.jpg") == "The Dress"

    def test_no_description(self):
        assert extract_description("IMG_1234.jpg") is None

    def test_underscore_placeholder(self):
        assert extract_description("20130728--_.jpg") is None


class TestSanitizeDescription:
    def test_spaces_to_underscores(self):
        assert sanitize_description("The Dress") == "The_Dress"

    def test_special_chars(self):
        assert sanitize_description("Alex & Connie's Wedding!") == "Alex_Connie_s_Wedding"

    def test_length_limit(self):
        long_desc = "A" * 100
        assert len(sanitize_description(long_desc)) == 50


class TestGenerateFilename:
    def test_basic(self):
        dt = datetime(2023, 12, 25, 14, 30, 45)
        assert generate_filename(dt, ".jpg", None) == "20231225-143045.jpg"

    def test_with_description(self):
        dt = datetime(2023, 12, 25, 14, 30, 45)
        assert generate_filename(dt, ".jpg", "Christmas") == "20231225-143045--Christmas.jpg"

    def test_with_collision(self):
        dt = datetime(2023, 12, 25, 14, 30, 45)
        assert generate_filename(dt, ".jpg", None, collision=1) == "20231225-143045-001.jpg"

    def test_lowercase_extension(self):
        dt = datetime(2023, 12, 25, 14, 30, 45)
        assert generate_filename(dt, ".JPG", None) == "20231225-143045.jpg"


class TestComputeDestination:
    def test_basic(self):
        archive = Path("/archive")
        dt = datetime(2023, 12, 5, 14, 30, 45)
        assert compute_destination(archive, dt) == Path("/archive/by-date/2023/12/05")


class TestFileHash:
    def test_consistent_hash(self, tmp_path):
        f = tmp_path / "test.jpg"
        f.write_bytes(b"test content")
        h1 = file_hash(f)
        h2 = file_hash(f)
        assert h1 == h2

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "test1.jpg"
        f2 = tmp_path / "test2.jpg"
        f1.write_bytes(b"content 1")
        f2.write_bytes(b"content 2")
        assert file_hash(f1) != file_hash(f2)


class TestParseDateFromFilename:
    def test_yyyymmdd_hhmmss_dashes(self):
        """Pattern: 20130728-11-58-57"""
        dt = parse_date_from_filename("20130728-11-58-57--The Dress.jpg")
        assert dt == datetime(2013, 7, 28, 11, 58, 57)

    def test_yyyymmdd_hhmmss_compact(self):
        """Pattern: 20130728-115857"""
        dt = parse_date_from_filename("20130728-115857.jpg")
        assert dt == datetime(2013, 7, 28, 11, 58, 57)

    def test_yyyy_mm_dd_hh_mm_ss_dots(self):
        """Pattern: 2012-07-21 16.12.48"""
        dt = parse_date_from_filename("2012-07-21 16.12.48.jpg")
        assert dt == datetime(2012, 7, 21, 16, 12, 48)

    def test_yyyy_mm_dd_only(self):
        """Pattern: 2012-07-21 (date only, time defaults to 00:00:00)"""
        dt = parse_date_from_filename("2012-07-21 vacation.jpg")
        assert dt == datetime(2012, 7, 21, 0, 0, 0)

    def test_img_pattern(self):
        """Pattern: IMG_20130728_115857"""
        dt = parse_date_from_filename("IMG_20130728_115857.jpg")
        assert dt == datetime(2013, 7, 28, 11, 58, 57)

    def test_vid_pattern(self):
        """Pattern: VID_20191223_121236"""
        dt = parse_date_from_filename("VID_20191223_121236.mp4")
        assert dt == datetime(2019, 12, 23, 12, 12, 36)

    def test_no_date_in_filename(self):
        """Files without recognizable date patterns return None."""
        assert parse_date_from_filename("vacation_photo.jpg") is None
        assert parse_date_from_filename("IMG_1234.jpg") is None

    def test_invalid_date_returns_none(self):
        """Invalid dates (like month 13) should return None."""
        assert parse_date_from_filename("20131328-115857.jpg") is None


class TestWriteExifDate:
    def test_writes_date_to_image(self, tmp_path):
        """write_exif_date should use DateTimeOriginal for images."""
        f = tmp_path / "photo.jpg"
        f.write_bytes(b"fake jpg")
        dt = datetime(2023, 12, 25, 14, 30, 45)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = write_exif_date(f, dt)

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "exiftool" in call_args
        assert "-overwrite_original" in call_args
        assert "-DateTimeOriginal=2023:12:25 14:30:45" in call_args

    def test_writes_date_to_video(self, tmp_path):
        """write_exif_date should use QuickTime tags for videos."""
        f = tmp_path / "video.mp4"
        f.write_bytes(b"fake mp4")
        dt = datetime(2023, 12, 25, 14, 30, 45)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = write_exif_date(f, dt)

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "-QuickTime:CreateDate=2023:12:25 14:30:45" in call_args
        assert "-QuickTime:ModifyDate=2023:12:25 14:30:45" in call_args

    def test_returns_false_on_failure(self, tmp_path):
        """write_exif_date should return False if exiftool fails."""
        f = tmp_path / "photo.jpg"
        f.write_bytes(b"fake jpg")
        dt = datetime(2023, 12, 25, 14, 30, 45)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = write_exif_date(f, dt)

        assert result is False


class TestMtimeSetting:
    def test_mtime_set_to_photo_date(self, tmp_path):
        """After moving, file mtime should match the photo date."""
        import os
        from photo_org.organize import main
        from click.testing import CliRunner

        # Set up staging and archive
        staging = tmp_path / "staging"
        archive = tmp_path / "archive"
        staging.mkdir()
        (archive / "by-date").mkdir(parents=True)
        (archive / "no-date").mkdir()
        (archive / "albums").mkdir()

        # Create a test file with a parseable filename
        test_file = staging / "20230725-143000--Test.jpg"
        test_file.write_bytes(b"fake jpg content")

        runner = CliRunner()
        result = runner.invoke(main, [
            "--staging", str(staging),
            "--archive", str(archive),
        ])

        assert result.exit_code == 0

        # Find the moved file
        moved = archive / "by-date" / "2023" / "07" / "25" / "20230725-143000--Test.jpg"
        assert moved.exists()

        # Check mtime matches the date from filename
        mtime = os.path.getmtime(moved)
        expected = datetime(2023, 7, 25, 14, 30, 0).timestamp()
        assert abs(mtime - expected) < 1  # within 1 second


class TestBatchExtractDates:
    def test_parses_exiftool_json_output(self, tmp_path):
        """batch_extract_dates should parse exiftool JSON output correctly."""
        # Create test files
        f1 = tmp_path / "photo1.jpg"
        f2 = tmp_path / "photo2.jpg"
        f1.write_bytes(b"fake jpg 1")
        f2.write_bytes(b"fake jpg 2")

        # Mock exiftool output
        mock_output = json.dumps([
            {"SourceFile": str(f1), "DateTimeOriginal": "2023:12:25 14:30:45"},
            {"SourceFile": str(f2), "DateTimeOriginal": "2024:01:01 00:00:00"},
        ])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
            )
            result = batch_extract_dates([f1, f2])

        assert result[f1] == datetime(2023, 12, 25, 14, 30, 45)
        assert result[f2] == datetime(2024, 1, 1, 0, 0, 0)

    def test_handles_missing_dates(self, tmp_path):
        """Files without DateTimeOriginal should return None."""
        f1 = tmp_path / "photo1.jpg"
        f1.write_bytes(b"fake jpg")

        mock_output = json.dumps([
            {"SourceFile": str(f1)},  # No DateTimeOriginal
        ])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
            )
            result = batch_extract_dates([f1])

        assert result[f1] is None

    def test_handles_empty_file_list(self):
        """Empty input should return empty dict without calling exiftool."""
        with patch("subprocess.run") as mock_run:
            result = batch_extract_dates([])

        mock_run.assert_not_called()
        assert result == {}

    def test_batches_large_file_lists(self, tmp_path):
        """Large file lists should be processed in batches to avoid arg limits."""
        # Create many files
        files = []
        for i in range(150):
            f = tmp_path / f"photo{i}.jpg"
            f.write_bytes(b"fake")
            files.append(f)

        # Mock should be called multiple times for batching
        mock_output = json.dumps([{"SourceFile": str(f)} for f in files[:100]])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
            )
            batch_extract_dates(files)

        # Should be called at least twice (150 files / 100 batch size)
        assert mock_run.call_count >= 2

    def test_handles_exiftool_error(self, tmp_path):
        """Exiftool errors should not crash, affected files get None."""
        f1 = tmp_path / "photo1.jpg"
        f1.write_bytes(b"fake")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
            )
            result = batch_extract_dates([f1])

        assert result[f1] is None
