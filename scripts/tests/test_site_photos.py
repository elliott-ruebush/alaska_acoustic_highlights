"""Tests for site photo entities and clip assignment."""

from lib.site_photos import (
    assign_site_photo_ids,
    photo_record_from_filename,
    pick_closest_photo,
)


def denatoko_photos() -> list[dict]:
    return [
        {
            "id": "denatoko_20160513",
            "path": "highlights/site_photos/denatoko_20160513.webp",
            "site_key": "DENATOKO",
            "park_code": "DENA",
            "site_code": "TOKO",
            "taken_date": "2016-05-13",
            "source_filename": "CardinalPhotoComposite_DENATOKO_20160513.jpg",
        },
        {
            "id": "denatoko_20190101",
            "path": "highlights/site_photos/denatoko_20190101.webp",
            "site_key": "DENATOKO",
            "park_code": "DENA",
            "site_code": "TOKO",
            "taken_date": "2019-01-01",
            "source_filename": "DENATOKO_2019.jpg",
        },
    ]


class TestPhotoRecordFromFilename:
    def test_cardinal_composite_full_date(self):
        meta = photo_record_from_filename("CardinalPhotoComposite_DENATOKO_20160513.jpg")
        assert meta == {
            "id": "denatoko_20160513",
            "site_key": "DENATOKO",
            "park_code": "DENA",
            "site_code": "TOKO",
            "taken_date": "2016-05-13",
        }

    def test_short_site_year_uses_jan_first(self):
        meta = photo_record_from_filename("DENATOKO_2019.jpg")
        assert meta["id"] == "denatoko_20190101"
        assert meta["taken_date"] == "2019-01-01"

    def test_numeric_site_code(self):
        meta = photo_record_from_filename("DENAHIG1_2016.jpg")
        assert meta["id"] == "denahig1_20160101"
        assert meta["site_key"] == "DENAHIG1"

    def test_returns_none_without_site_key(self):
        assert photo_record_from_filename("2024.jpg") is None


class TestPickClosestPhoto:
    def test_returns_none_for_empty_photos(self):
        assert pick_closest_photo([], "DENATOKO", "2016-05-13") is None

    def test_returns_none_for_other_site(self):
        assert pick_closest_photo(denatoko_photos(), "DENABICR", "2016-05-13") is None

    def test_picks_closest_taken_date(self):
        photos = denatoko_photos()
        assert pick_closest_photo(photos, "DENATOKO", "2016-06-01") == "denatoko_20160513"
        assert pick_closest_photo(photos, "DENATOKO", "2018-12-31") == "denatoko_20190101"

    def test_picks_most_recent_without_recorded_date(self):
        photos = denatoko_photos()
        assert pick_closest_photo(photos, "DENATOKO", None) == "denatoko_20190101"


class TestAssignSitePhotoIds:
    def test_assigns_closest_photo_per_clip(self):
        clips = [
            {
                "id": "denatoko_20160513_130223",
                "park_code": "DENA",
                "site_code": "TOKO",
                "recorded_date": "2016-05-13",
            },
            {
                "id": "denatoko_20190701_100630",
                "park_code": "DENA",
                "site_code": "TOKO",
                "recorded_date": "2019-07-01",
            },
        ]
        assign_site_photo_ids(clips, denatoko_photos())
        assert clips[0]["site_photo_id"] == "denatoko_20160513"
        assert clips[1]["site_photo_id"] == "denatoko_20190101"

    def test_sets_null_without_site_codes(self):
        clips = [{"id": "orphan", "park_code": None, "site_code": None, "recorded_date": None}]
        assign_site_photo_ids(clips, denatoko_photos())
        assert clips[0]["site_photo_id"] is None

    def test_many_clips_share_one_photo(self):
        clips = [
            {
                "id": f"denatoko_2016_{index:02d}",
                "park_code": "DENA",
                "site_code": "TOKO",
                "recorded_date": f"2016-06-{index + 1:02d}",
            }
            for index in range(3)
        ]
        assign_site_photo_ids(clips, denatoko_photos())
        assert {clip["site_photo_id"] for clip in clips} == {"denatoko_20160513"}
