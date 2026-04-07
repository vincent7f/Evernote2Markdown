#!/usr/bin/env bash
# Export Evernote China (印象笔记) notes. Output dir: $OUTPUT_DIR, else first arg if not a flag, else ./output
set -eo pipefail
cd "$(dirname "$0")"

_token_compact="${EVERNOTE_TOKEN-}"
_token_compact="${_token_compact//[[:space:]]/}"
if [[ -z "$_token_compact" ]]; then
  cat <<'EOF'

  === EVERNOTE_TOKEN not set or only whitespace ===

  For China 印象笔记 (Yinxiang Biji), log in in your browser, then open:
    https://app.yinxiang.com/api/DeveloperToken.action

  In this shell, before ./run_china.sh:
    export EVERNOTE_TOKEN='paste_your_token_here'

  To persist for future sessions, add that line to ~/.zshrc or ~/.bash_profile
  (or use your desktop environment’s “Environment Variables” settings).

  Optional: edit run_china.sh and add after the cd line:
    export EVERNOTE_TOKEN='your_token_here'

EOF
  exit 1
fi

out="${OUTPUT_DIR-}"
if [[ -n "${1-}" && "$1" != -* ]]; then
  out="$1"
  shift
fi
out="${out:-output}"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Error: neither python3 nor python found in PATH." >&2
  exit 1
fi

exec "$PYTHON" export_recent_md_titles.py "$out" --china --days 7 --title md "$@"
