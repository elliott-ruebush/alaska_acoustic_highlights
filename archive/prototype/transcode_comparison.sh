#!/usr/bin/env bash
# Transcode representative NPS audio samples to lossy formats and record metrics.
# Source files are read-only from the network volume; outputs go to output/audio_samples/.

set -euo pipefail

FFMPEG="/opt/homebrew/bin/ffmpeg"
OUT_DIR="/Users/eruebush/dev/nps_acoustic_highlights/output/audio_samples"
CSV="${OUT_DIR}/compression_comparison.csv"
SRC_BASE="/Volumes/NPS_ADSB_Data/NPS_Type_1_Acoustic_Audio_Highlights"

mkdir -p "$OUT_DIR"

# Representative samples: geologic, mammal, bird, insect
declare -a SOURCES=(
  "${SRC_BASE}/DENABMUL_20210330_001843 Muldrow surge long cut.wav"
  "${SRC_BASE}/MAMMAL REFERENCE/WRSTBLMT_20170128_072543 excellent wolf pack howling.wav"
  "${SRC_BASE}/MAMMAL REFERENCE/GLBAMCLEOD_20220903_234345 Humpback Whale breathing, breaching.wav"
  "${SRC_BASE}/BIRD ID/2019_metadata entered/GAARFLOR_20180609_105204 Orange-crowned Warbler song.wav"
  "${SRC_BASE}/INSECTS/DENABICR_20130715_230139 insect flight with pulsed behavior.wav"
)

# Optional truncate flag for very long files (empty = full encode)
TRUNCATE_FLAG=""

# Use Python for reliable CSV writing (source filenames may contain commas)
python3 - "$CSV" <<'PY'
import csv, sys
with open(sys.argv[1], "w", newline="") as f:
    csv.writer(f).writerow(["source_file","source_size_mb","format","bitrate","output_size_mb","pct_reduction","encode_seconds"])
PY

slugify() {
  local name
  name=$(basename "$1" .wav)
  echo "$name" | tr ' ' '_' | tr -cd '[:alnum:]_-.'
}

encode_one() {
  local src="$1"
  local format="$2"
  local bitrate="$3"
  local ext="$4"
  local extra_args=("${@:5}")

  local slug
  slug=$(slugify "$src")
  local out="${OUT_DIR}/${slug}_${format}_${bitrate}.${ext}"

  local src_bytes src_mb
  src_bytes=$(stat -f%z "$src")
  src_mb=$(echo "scale=4; $src_bytes / 1048576" | bc)

  local start end elapsed
  start=$(date +%s.%N)

  "$FFMPEG" -y -hide_banner -loglevel error \
    $TRUNCATE_FLAG \
    -i "$src" \
    "${extra_args[@]}" \
    "$out"

  end=$(date +%s.%N)
  elapsed=$(echo "scale=3; $end - $start" | bc)

  local out_bytes out_mb pct
  out_bytes=$(stat -f%z "$out")
  out_mb=$(printf "%.4f" "$(echo "scale=4; $out_bytes / 1048576" | bc)")
  pct=$(printf "%.2f" "$(echo "scale=4; (1 - $out_bytes / $src_bytes) * 100" | bc)")
  elapsed_fmt=$(printf "%.3f" "$elapsed")

  local src_name
  src_name=$(basename "$src")

  python3 - "$CSV" "$src_name" "$src_mb" "$format" "$bitrate" "$out_mb" "$pct" "$elapsed_fmt" <<'PY'
import csv, sys
path, *row = sys.argv[1:]
with open(path, "a", newline="") as f:
    csv.writer(f).writerow(row)
PY
  echo "  ${format} ${bitrate}: ${out_mb} MB (${pct}% reduction) in ${elapsed}s"
}

echo "=== NPS Audio Compression Comparison ==="
echo "Output directory: $OUT_DIR"
echo ""

for src in "${SOURCES[@]}"; do
  if [[ ! -f "$src" ]]; then
    echo "ERROR: source not found: $src" >&2
    exit 1
  fi

  src_mb=$(echo "scale=2; $(stat -f%z "$src") / 1048576" | bc)
  echo "Encoding: $(basename "$src") (${src_mb} MB)"

  encode_one "$src" "mp3" "128k" "mp3" -c:a libmp3lame -b:a 128k
  encode_one "$src" "mp3" "192k" "mp3" -c:a libmp3lame -b:a 192k
  encode_one "$src" "aac" "128k" "m4a" -c:a aac -b:a 128k
  encode_one "$src" "opus" "96k" "opus" -c:a libopus -b:a 96k -application audio
  encode_one "$src" "opus" "64k" "opus" -c:a libopus -b:a 64k -application audio

  echo ""
done

echo "=== Done. Results written to $CSV ==="
