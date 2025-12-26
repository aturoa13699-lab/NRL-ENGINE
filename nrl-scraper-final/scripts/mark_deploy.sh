#!/usr/bin/env bash
set -euo pipefail
STAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
mkdir -p nrlscraper
cat > nrlscraper/__version__.py <<PY
# generated: do not edit by hand
VERSION = {"commit": "${SHA}", "touched": "${STAMP}"}
PY
# also touch a marker so RAILPACK always rebuilds a new image
echo "${STAMP} ${SHA}" > .deploy_marker
echo "Marked deploy: ${SHA} @ ${STAMP}"
