"""Tests for NPS audio filename parsing."""

from pathlib import Path

from lib.nps_filename import (
    category_from_path,
    file_prefix,
    parse_filename,
    split_processing,
)


class TestParseFilename:
    def test_standard_clip(self):
        parsed = parse_filename(
            "DENATOKO_20160513_130223 Animal Movement, Bird Chorus, and River.wav"
        )
        assert parsed["park_code"] == "DENA"
        assert parsed["site_code"] == "TOKO"
        assert parsed["recorded_date"] == "2016-05-13"
        assert parsed["recorded_time"] == "13:02:23"
        assert parsed["description"] == "Animal Movement, Bird Chorus, and River"
        assert parsed["prefix"] == "DENATOKO_20160513_130223"

    def test_processing_suffix_in_description(self):
        parsed = parse_filename(
            "DENABICR_20130809_020959 Great Grey Owl TRIM, NOISE REDUCTION.wav"
        )
        assert parsed["park_code"] == "DENA"
        assert parsed["site_code"] == "BICR"
        assert "Great Grey Owl" in parsed["description"]

    def test_numeric_site_code_in_full_audio_filename(self):
        parsed = parse_filename("DENAHIG1_20120802_035742 Willow Ptarmigan.wav")
        assert parsed["park_code"] == "DENA"
        assert parsed["site_code"] == "HIG1"
        assert parsed["prefix"] == "DENAHIG1_20120802_035742"

    def test_missing_prefix_falls_back_to_stem(self):
        parsed = parse_filename("not_a_standard_name.wav")
        assert parsed["park_code"] == ""
        assert parsed["site_code"] == ""
        assert parsed["recorded_date"] == ""
        assert parsed["description"] == "not_a_standard_name"
        assert parsed["prefix"] == ""


class TestFilePrefix:
    def test_extracts_prefix_from_full_name(self):
        name = "DENATOKO_20160513_130223 Animal Movement.wav"
        assert file_prefix(name) == "DENATOKO_20160513_130223"

    def test_returns_empty_when_missing(self):
        assert file_prefix("random_clip.wav") == ""


class TestSplitProcessing:
    def test_splits_trim_suffix(self):
        display, processing = split_processing("Fox Sparrow Song TRIM")
        assert display == "Fox Sparrow Song"
        assert processing == "TRIM"

    def test_leaves_plain_title_unchanged(self):
        display, processing = split_processing("Common Loon With Chorus")
        assert display == "Common Loon With Chorus"
        assert processing == ""

    def test_splits_compound_processing_suffixes(self):
        display, processing = split_processing("Fox Sparrow Song TRIM, NOISE REDUCTION")
        assert display == "Fox Sparrow Song"
        assert processing == "TRIM, NOISE REDUCTION"

    def test_splits_noise_reduction_alone(self):
        display, processing = split_processing("Great Grey Owl NOISE REDUCTION")
        assert display == "Great Grey Owl"
        assert processing == "NOISE REDUCTION"


class TestCategoryFromPath:
    def test_reads_category_folder(self, tmp_path: Path):
        audio = tmp_path / "BIRDS" / "clip.wav"
        audio.parent.mkdir()
        audio.touch()
        label, folder = category_from_path(audio, tmp_path)
        assert label == "Birds"
        assert folder == "BIRDS"

    def test_defaults_to_general(self, tmp_path: Path):
        audio = tmp_path / "clip.wav"
        audio.touch()
        label, folder = category_from_path(audio, tmp_path)
        assert label == "General"
        assert folder == "GENERAL"
