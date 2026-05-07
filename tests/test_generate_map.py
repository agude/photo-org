"""Tests for generate_map module."""

import json
from pathlib import Path

from click.testing import CliRunner

from photo_org.generate_map import main, is_date_folder


class TestIsDateFolder:
    def test_photos_from_year(self):
        assert is_date_folder("Photos from 2023")

    def test_iso_date(self):
        assert is_date_folder("2023-01-15")

    def test_year_only(self):
        assert is_date_folder("2023")

    def test_album_name_not_date(self):
        assert not is_date_folder("2023 Christmas Party")
        assert not is_date_folder("Wedding Photos")

    def test_month_numbers_not_date_folders(self):
        # Month numbers like "01", "12" should NOT match date folder patterns
        assert not is_date_folder("01")
        assert not is_date_folder("12")


class TestGenerateAlbumMap:
    def test_uses_top_level_folder_as_album(self, tmp_path):
        """Album name should be top-level folder, not nested year/month folders."""
        # Create: album/year/month/file.jpg
        album = tmp_path / "2023 Christmas Party" / "2023" / "12"
        album.mkdir(parents=True)
        (album / "photo1.jpg").touch()
        (album / "photo2.jpg").touch()

        runner = CliRunner()
        result = runner.invoke(main, [str(tmp_path)])

        assert result.exit_code == 0
        data = json.loads(result.output)

        # Both files should map to the top-level album name
        assert len(data) == 2
        for albums in data.values():
            assert albums == ["2023 Christmas Party"]

    def test_excludes_all_photos_folder(self, tmp_path):
        """ALL_PHOTOS folder should be excluded entirely."""
        # Create ALL_PHOTOS structure
        all_photos = tmp_path / "ALL_PHOTOS" / "2023" / "12"
        all_photos.mkdir(parents=True)
        (all_photos / "photo.jpg").touch()

        # Create a real album too
        album = tmp_path / "My Album"
        album.mkdir()
        (album / "photo.jpg").touch()

        runner = CliRunner()
        result = runner.invoke(main, [str(tmp_path)])

        assert result.exit_code == 0
        data = json.loads(result.output)

        # Only the real album should be included
        assert len(data) == 1
        assert "My Album/photo.jpg" in data

    def test_skips_date_folders_by_default(self, tmp_path):
        """Top-level date-only folders should be skipped."""
        # Date folder (should be skipped)
        date_folder = tmp_path / "2023"
        date_folder.mkdir()
        (date_folder / "photo.jpg").touch()

        # Real album (should be included)
        album = tmp_path / "2023 Christmas"
        album.mkdir()
        (album / "photo.jpg").touch()

        output_file = tmp_path / "output.json"
        runner = CliRunner()
        result = runner.invoke(main, [str(tmp_path), "-o", str(output_file)])

        assert result.exit_code == 0
        data = json.loads(output_file.read_text())

        assert len(data) == 1
        assert "2023 Christmas/photo.jpg" in data

    def test_include_date_folders_flag(self, tmp_path):
        """--include-date-folders should include date-based folders."""
        date_folder = tmp_path / "2023"
        date_folder.mkdir()
        (date_folder / "photo.jpg").touch()

        runner = CliRunner()
        result = runner.invoke(main, [str(tmp_path), "--include-date-folders"])

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert len(data) == 1
        assert data["2023/photo.jpg"] == ["2023"]

    def test_skips_root_level_files(self, tmp_path):
        """Files directly in source root should be skipped."""
        (tmp_path / "orphan.jpg").touch()

        album = tmp_path / "Album"
        album.mkdir()
        (album / "photo.jpg").touch()

        runner = CliRunner()
        result = runner.invoke(main, [str(tmp_path)])

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert len(data) == 1
        assert "Album/photo.jpg" in data

    def test_output_to_file(self, tmp_path):
        """--output should write to a file."""
        album = tmp_path / "Album"
        album.mkdir()
        (album / "photo.jpg").touch()

        output_file = tmp_path / "output.json"

        runner = CliRunner()
        result = runner.invoke(main, [str(tmp_path), "-o", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "Album/photo.jpg" in data
