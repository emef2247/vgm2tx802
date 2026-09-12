#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 [--outdir DIR] INPUT_PATH" >&2
  echo "  INPUT_PATH  directory or file under inputs/ or tests/fixtures/" >&2
  echo "  --outdir    optional output directory. inferred when omitted." >&2
  exit 2
}

infer_outdir() {
  local target="$1"
  case "$target" in
    ./inputs/*|inputs/*)
      local rest="${target#./}"
      rest="${rest#inputs/}"
      echo "outputs/${rest}"
      ;;
    ./tests/fixtures/*|tests/fixtures/*)
      local rest="${target#./}"
      rest="${rest#tests/fixtures/}"
      echo "outputs/tests/${rest}"
      ;;
    *)
      echo "cannot infer --outdir from: $target" >&2
      echo "pass --outdir explicitly" >&2
      exit 2
      ;;
  esac
}

OUTDIR=""
TARGET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage ;;
    --outdir)
      [[ $# -ge 2 ]] || usage
      OUTDIR="$2"
      shift 2
      ;;
    --outdir=*)
      OUTDIR="${1#*=}"
      shift
      ;;
    -*)
      echo "unknown option: $1" >&2
      usage
      ;;
    *)
      [[ -z "$TARGET" ]] || usage
      TARGET="$1"
      shift
      ;;
  esac
done

[[ -n "$TARGET" ]] || usage
TARGET="${TARGET%/}"
[[ -e "$TARGET" ]] || { echo "not found: $TARGET" >&2; exit 1; }

if [[ -z "$OUTDIR" ]]; then
  OUTDIR="$(infer_outdir "$TARGET")"
fi
OUTDIR="${OUTDIR%/}"

PY=(python3 src/vgm2midi.py)
OPTS=(--target=tx802 --melody_mode=default --rhythm_mode=rx21)
FAIL_LOG="batch_failures.log"

: > "$FAIL_LOG"

collect_vgms() {
  if [[ -f "$TARGET" ]]; then
    printf '%s\n' "$TARGET"
    return
  fi
  find "$TARGET" -type f \( -name '*.vgm' -o -name '*.vgz' \) | sort
}

relpath_from_target() {
  local file="$1"
  local rel="${file#"$TARGET"/}"
  if [[ "$rel" == "$file" ]]; then
    echo "."
  else
    dirname "$rel"
  fi
}

count=0
fail=0
while IFS= read -r f; do
  [[ -n "$f" ]] || continue
  rel_dir="$(relpath_from_target "$f")"
  if [[ "$rel_dir" == "." ]]; then
    dest="$OUTDIR"
  else
    dest="$OUTDIR/$rel_dir"
  fi
  mkdir -p "$dest"

  echo "==> $f"
  echo "    out $dest"
  if ! "${PY[@]}" "${OPTS[@]}" --outdir "$dest" "$f"; then
    echo "FAILED $f" | tee -a "$FAIL_LOG"
    fail=$((fail + 1))
  fi
  count=$((count + 1))
done < <(collect_vgms)

if [[ "$count" -eq 0 ]]; then
  echo "no .vgm/.vgz under $TARGET" >&2
  exit 1
fi

echo "done: $count file(s), $fail failed, outdir=$OUTDIR"
if [[ "$fail" -gt 0 ]]; then
  echo "see $FAIL_LOG" >&2
  exit 1
fi
rm -f "$FAIL_LOG"