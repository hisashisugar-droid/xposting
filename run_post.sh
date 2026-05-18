#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

if [[ ! -f "$SCRIPT_DIR/post_new_episode.py" ]]; then
  print -u2 "ERROR: post_new_episode.py not found in $SCRIPT_DIR"
  exit 1
fi

if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

required_envs=(
  X_CONSUMER_KEY
  X_CONSUMER_SECRET
  X_ACCESS_TOKEN
  X_ACCESS_TOKEN_SECRET
)

for name in "${required_envs[@]}"; do
  if [[ -z "${(P)name:-}" ]]; then
    print -u2 "ERROR: missing environment variable: $name"
    exit 1
  fi
done

python3 "$SCRIPT_DIR/post_new_episode.py"
