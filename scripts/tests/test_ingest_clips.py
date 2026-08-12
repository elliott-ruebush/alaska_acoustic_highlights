"""Tests for ingest_clips photo planning."""

from pathlib import Path
from unittest.mock import patch

import ingest_clips


class TestBuildPipelineSteps:
    def test_audio_only_skips_photo_steps(self):
        audio = [
            ingest_clips.AudioPlan(
                source=Path("ingest/audio/BIRDS/foo.wav"),
                dest=Path("highlights/audio/BIRDS/foo.wav"),
                category_folder="BIRDS",
                clip_id="foo",
            )
        ]
        steps = ingest_clips.build_pipeline_steps(audio, skip_photos=True, photo_source=None)
        labels = [step.label for step in steps]
        assert labels == [
            "Generate spectrograms",
            "Transcode to MP3",
            "Fix MP3 metadata",
            "Build highlights catalog",
            "Validate catalog",
        ]

    def test_photos_only_runs_catalog_and_validate(self):
        steps = ingest_clips.build_pipeline_steps([], skip_photos=False, photo_source=None)
        labels = [step.label for step in steps]
        assert labels == [
            "Build highlights catalog",
            "Sync site photos to catalog",
            "Validate catalog",
        ]


class TestPlanPhotos:
    def test_skips_when_webp_destination_exists(self, tmp_path):
        highlights_photos = tmp_path / "highlights" / "site_photos"
        highlights_photos.mkdir(parents=True)
        dest = highlights_photos / "denatoko_20160513.webp"
        dest.write_bytes(b"webp")

        source = tmp_path / "ingest" / "CardinalPhotoComposite_DENATOKO_20160513.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"jpg")

        with patch.object(ingest_clips, "HIGHLIGHTS_SITE_PHOTOS", highlights_photos):
            plans = ingest_clips.plan_photos([source], force=False)

        assert len(plans) == 1
        assert plans[0].action == "skip"
        assert plans[0].dest == dest

    def test_copies_when_destination_missing(self, tmp_path):
        highlights_photos = tmp_path / "highlights" / "site_photos"
        highlights_photos.mkdir(parents=True)

        source = tmp_path / "ingest" / "CardinalPhotoComposite_DENATOKO_20160513.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"jpg")

        with patch.object(ingest_clips, "HIGHLIGHTS_SITE_PHOTOS", highlights_photos):
            plans = ingest_clips.plan_photos([source], force=False)

        assert len(plans) == 1
        assert plans[0].action == "copy"

    def test_force_overrides_existing_destination(self, tmp_path):
        highlights_photos = tmp_path / "highlights" / "site_photos"
        highlights_photos.mkdir(parents=True)
        dest = highlights_photos / "denatoko_20160513.webp"
        dest.write_bytes(b"webp")

        source = tmp_path / "ingest" / "CardinalPhotoComposite_DENATOKO_20160513.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"jpg")

        with patch.object(ingest_clips, "HIGHLIGHTS_SITE_PHOTOS", highlights_photos):
            plans = ingest_clips.plan_photos([source], force=True)

        assert len(plans) == 1
        assert plans[0].action == "copy"
