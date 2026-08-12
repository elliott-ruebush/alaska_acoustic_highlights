"""Tests for ingest_clips photo planning."""

from pathlib import Path
from unittest.mock import patch

import ingest_clips


class TestClipIdCollisions:
    def test_warns_when_ingest_files_share_prefix(self, tmp_path):
        ingest_audio = tmp_path / "ingest" / "audio" / "BIRDS"
        highlights_audio = tmp_path / "highlights" / "audio" / "BIRDS"
        ingest_audio.mkdir(parents=True)
        highlights_audio.mkdir(parents=True)

        first = ingest_audio / (
            "DENATRLA_20260610_005302_Dark-eyed Junco with Varied Thrush and Swainson's Thrush.wav"
        )
        second = ingest_audio / (
            "DENATRLA_20260610_005302_Varied Frequencies of Varied Thrush with Swainson's Thrush in Background.wav"
        )
        first.write_bytes(b"wav")
        second.write_bytes(b"wav")

        with patch.object(ingest_clips, "HIGHLIGHTS_AUDIO", highlights_audio):
            plans = ingest_clips.plan_audio([first, second], force=False)
            messages = ingest_clips.clip_id_collision_messages(plans)

        assert any("clip id denatrla_20260610_005302" in message for message in messages)
        assert any("Dark-eyed Junco" in message for message in messages)
        assert any("Varied Frequencies" in message for message in messages)

    def test_warns_when_ingest_conflicts_with_existing_highlight(self, tmp_path):
        ingest_audio = tmp_path / "ingest" / "audio" / "BIRDS"
        highlights_audio = tmp_path / "highlights" / "audio" / "BIRDS"
        ingest_audio.mkdir(parents=True)
        highlights_audio.mkdir(parents=True)

        existing = highlights_audio / (
            "DENATRLA_20260610_005302_Varied Frequencies of Varied Thrush with Swainson's Thrush in Background.mp3"
        )
        incoming = ingest_audio / (
            "DENATRLA_20260610_005302_Dark-eyed Junco with Varied Thrush and Swainson's Thrush.wav"
        )
        existing.write_bytes(b"mp3")
        incoming.write_bytes(b"wav")

        with patch.object(ingest_clips, "HIGHLIGHTS_AUDIO", highlights_audio):
            plans = ingest_clips.plan_audio([incoming], force=False)
            messages = ingest_clips.clip_id_collision_messages(plans)

        assert any("clip id denatrla_20260610_005302" in message for message in messages)
        assert any("Varied Frequencies" in message for message in messages)
        assert any("Dark-eyed Junco" in message for message in messages)

    def test_allows_wav_mp3_transcode_pair(self, tmp_path):
        ingest_audio = tmp_path / "ingest" / "audio" / "BIRDS"
        highlights_audio = tmp_path / "highlights" / "audio" / "BIRDS"
        ingest_audio.mkdir(parents=True)
        highlights_audio.mkdir(parents=True)

        wav = ingest_audio / "DENATOKO_20160513_130223 Animal Movement.wav"
        mp3 = ingest_audio / "DENATOKO_20160513_130223 Animal Movement.mp3"
        wav.write_bytes(b"wav")
        mp3.write_bytes(b"mp3")

        with patch.object(ingest_clips, "HIGHLIGHTS_AUDIO", highlights_audio):
            plans = ingest_clips.plan_audio([wav, mp3], force=False)
            messages = ingest_clips.clip_id_collision_messages(plans)

        assert messages == []


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
