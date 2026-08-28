#!/usr/bin/env bash
# VideoTextExtractor (VTE) - Default Execution Script
#
# Usage:
#   ./run.sh [video_file] [mode] [format] [output_file] [extra_cli_flags]
#
# Examples:
#   ./run.sh
#   ./run.sh my_video.mp4 fast json result.json
#   ./run.sh claude_first60s.mp4 auto srt result.srt --line-target-height 48 --logo-ratio 0.85

set -e

VIDEO="${1:-claude_first60s.mp4}"
MODE="${2:-fast}"
FORMAT="${3:-json}"
OUTPUT="${4:-out.json}"

shift 4 2>/dev/null || shift $# 2>/dev/null || true

echo "=================================================="
echo "Starting VideoTextExtractor (VTE)"
echo "  Video input : ${VIDEO}"
echo "  Preset mode : ${MODE}"
echo "  Output fmt  : ${FORMAT}"
echo "  Output file : ${OUTPUT}"
if [ $# -gt 0 ]; then
    echo "  Extra flags : $*"
fi
echo "=================================================="

python3 -m vte.cli extract "${VIDEO}" \
    --mode "${MODE}" \
    --format "${FORMAT}" \
    --output "${OUTPUT}" \
    "$@"

echo ""
echo "Extraction completed successfully. Output saved to: ${OUTPUT}"
