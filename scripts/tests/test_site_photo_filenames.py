"""Tests for cardinal site photo filename parsing."""

from lib.site_photo_filenames import (
    PHOTO_PREFIX,
    parse_site_key_from_filename,
    photo_stem,
    years_in_filename,
)


class TestPhotoStem:
    def test_strips_cardinal_prefix_and_extension(self):
        name = "CardinalPhotoComposite_DENATOKO_20160513.jpg"
        assert photo_stem(name) == "DENATOKO_20160513"

    def test_leaves_plain_site_name_unchanged(self):
        assert photo_stem("DENATOKO_2016.jpg") == "DENATOKO_2016"


class TestParseSiteKeyFromFilename:
    def test_cardinal_composite_with_full_date(self):
        name = "CardinalPhotoComposite_DENATOKO_20160513.jpg"
        assert parse_site_key_from_filename(name) == "DENATOKO"

    def test_short_site_year_name(self):
        assert parse_site_key_from_filename("DENATOKO_2016.jpg") == "DENATOKO"

    def test_numeric_site_code_with_year(self):
        assert parse_site_key_from_filename("DENAHIG1_2016.jpg") == "DENAHIG1"

    def test_site_key_without_year(self):
        assert parse_site_key_from_filename("DENATOKO.jpg") == "DENATOKO"

    def test_rejects_non_site_names(self):
        assert parse_site_key_from_filename("2024.jpg") is None
        assert parse_site_key_from_filename("ab.jpg") is None


class TestYearsInFilename:
    def test_full_yyyymmdd_date(self):
        name = f"{PHOTO_PREFIX}DENATOKO_20160513.jpg"
        assert years_in_filename(name) == {"2016"}

    def test_short_yyyy_suffix(self):
        assert years_in_filename("DENATOKO_2019.jpg") == {"2019"}

    def test_does_not_treat_yyyymmdd_as_bare_year_suffix(self):
        assert years_in_filename("DENATOKO_20160513.jpg") == {"2016"}

    def test_empty_when_no_year_present(self):
        assert years_in_filename("DENATOKO.jpg") == set()
