#!/usr/bin/env bash
# Apply a Korean ldstr map to Assembly-CSharp.dll with Mono.Cecil, in the .NET SDK container.
# Usage: scripts/build_dll.sh <in.dll> <map.json> <out.dll>
#   Paths are repo-relative or absolute; the output file is chowned to the host user.
#
# The container runs as root because `dotnet` fails to create its named mutex when the
# container uid has no /etc/passwd entry; ownership is fixed by an explicit chown and
# build artifacts stay in /tmp, so nothing root-owned lands in the repo.
set -euo pipefail
S="$(cd "$(dirname "$0")/.." && pwd)"; cd "$S"
IMG="mcr.microsoft.com/dotnet/sdk:8.0"
if [ $# -ne 3 ]; then
  echo "usage: $0 <in.dll> <map.json> <out.dll>" >&2
  exit 2
fi
IN="$1"; MAP="$2"; OUT="$3"
for p in "$IN" "$MAP"; do
  [ -f "$S/$p" ] || [ -f "$p" ] || { echo "missing file: $p" >&2; exit 2; }
done

VMOUNTS=(-v "$S:/work" -v "bxm-dllpatch-nuget:/nuget")
_seen=" $S "
# Extra host dirs are mounted at the same path inside the container.
add_host_dir() {
  case "$_seen" in *" $1 "*) return ;; esac
  _seen="$_seen$1 "
  VMOUNTS+=(-v "$1:$1${2:-}")
}
repo_rel() {
  case "$1" in "$S"/*) printf '%s' "${1#"$S"/}" ;; *) printf '%s' "$1" ;; esac
}

OUT_HOST="$(realpath -m "$OUT")"
mkdir -p "$(dirname "$OUT_HOST")"
OUT_REL="$(repo_rel "$OUT_HOST")"
for p in "$IN" "$MAP" "$OUT_HOST"; do
  f="$(realpath -m "$p")"
  case "$f" in "$S"/*) ;; *) add_host_dir "$(dirname "$f")" ;; esac
done

exec docker run --rm \
  -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
  -e HOME=/tmp -e DOTNET_CLI_HOME=/tmp/dotnet-home \
  -e DOTNET_CLI_TELEMETRY_OPTOUT=1 -e DOTNET_NOLOGO=1 \
  -e NUGET_PACKAGES=/nuget \
  "${VMOUNTS[@]}" -w /work \
  "$IMG" bash -c '
    set -e
    dotnet build scripts/dllpatch/dllpatch.csproj -c Release \
      -p:BaseIntermediateOutputPath=/tmp/obj/ -o /tmp/bin --nologo -v q >/dev/null
    dotnet /tmp/bin/dllpatch.dll patch --dll "$1" --map "$2" --out "$3" --strings locales/dll_strings.json
    chown "$HOST_UID:$HOST_GID" "$3"
  ' _ "$(repo_rel "$(realpath -m "$IN")")" "$(repo_rel "$(realpath -m "$MAP")")" "$OUT_REL"
