#!/bin/bash
# Watch Swift sources and project.yml, regenerating the Xcode project on changes.

set -euo pipefail

cd "$(dirname "$0")"

if ! command -v fswatch >/dev/null 2>&1; then
  echo "fswatch is required. Install with: brew install fswatch"
  exit 1
fi

echo "Watching App/ and project.yml for changes. Press Ctrl+C to stop."
fswatch -or App project.yml | while read -r _; do
  echo "Change detected -> regenerating Xcode project..."
  ./regenerate_project.sh || echo "Regeneration failed (see output above)"
done


