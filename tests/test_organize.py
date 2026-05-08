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
