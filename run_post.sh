#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

python3 "$SCRIPT_DIR/post_new_episode.py"
