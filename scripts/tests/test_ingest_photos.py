"""Tests for ingest site photo id resolution."""

from pathlib import Path

from lib.ingest_photos import resolve_photo_id


class TestResolvePhotoId:
    def test_cardinal_composite_filename(self):
        photo_id, method = resolve_photo_id(
            Path("CardinalPhotoComposite_DENATOKO_20160513.jpg"),
        )
        assert photo_id == "denatoko_20160513"
        assert method == "filename"

    def test_short_site_year_filename(self):
        photo_id, method = resolve_photo_id(Path("DENATOKO_2019.jpg"))
        assert photo_id == "denatoko_20190101"
        assert method == "filename"

    def test_numeric_site_code_with_year(self):
        photo_id, method = resolve_photo_id(Path("DENAHIG1_2016.jpg"))
        assert photo_id == "denahig1_20160101"
        assert method == "filename"

    def test_unmatched_when_filename_unparseable(self):
        photo_id, method = resolve_photo_id(Path("mystery-photo.jpg"))
        assert photo_id is None
        assert method == "unmatched"

    def test_webp_extension(self):
        photo_id, method = resolve_photo_id(
            Path("CardinalPhotoComposite_DENATOKO_20190701.webp"),
        )
        assert photo_id == "denatoko_20190701"
        assert method == "filename"
