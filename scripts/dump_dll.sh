#!/usr/bin/env bash
# Regenerate locales/dll_strings.json from Assembly-CSharp.dll + the curated filter.
# Usage: scripts/dump_dll.sh [in.dll] [out.json] [--raw]
#   --raw lists every CJK ldstr without applying scripts/dllpatch/strings.json.
set -euo pipefail
S="$(cd "$(dirname "$0")/.." && pwd)"; cd "$S"
IMG="mcr.microsoft.com/dotnet/sdk:8.0"
IN="${1:-source/BXM Tutorial_Data/Managed/Assembly-CSharp.dll}"
OUT="${2:-locales/dll_strings.json}"
RAW=""
[ "${3:-}" = "--raw" ] && RAW="--raw"
[ -f "$S/$IN" ] || [ -f "$IN" ] || { echo "missing dll: $IN" >&2; exit 2; }

OUT_HOST="$(realpath -m "$OUT")"
mkdir -p "$(dirname "$OUT_HOST")"
case "$OUT_HOST" in
  "$S"/*) OUT_IN="/work/${OUT_HOST#"$S"/}"; EXTRA=() ;;
  *)      OUT_IN="$OUT_HOST"; EXTRA=(-v "$(dirname "$OUT_HOST"):$(dirname "$OUT_HOST")") ;;
esac

exec docker run --rm \
  -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
  -e HOME=/tmp -e DOTNET_CLI_HOME=/tmp/dotnet-home \
  -e DOTNET_CLI_TELEMETRY_OPTOUT=1 -e DOTNET_NOLOGO=1 \
  -e NUGET_PACKAGES=/nuget \
  -v "$S:/work" -v "bxm-dllpatch-nuget:/nuget" "${EXTRA[@]}" -w /work \
  "$IMG" bash -c '
    set -e
    dotnet build scripts/dllpatch/dllpatch.csproj -c Release \
      -p:BaseIntermediateOutputPath=/tmp/obj/ -o /tmp/bin --nologo -v q >/dev/null
    dotnet /tmp/bin/dllpatch.dll dump --dll "$1" --out "$2" \
      --strings scripts/dllpatch/strings.json $4
    chown "$HOST_UID:$HOST_GID" "$2"
  ' _ "$IN" "$OUT_IN" "" "$RAW"
