#!/usr/bin/env bash
set -euo pipefail

RESULTS_DIR="${TEST_RESULTS_DIR:-/src/TestResults}"
TRX_NAME="${TEST_RESULTS_TRX_NAME:-TestResults.trx}"

mkdir -p "$RESULTS_DIR"

exec dotnet test -c Release HL7UnitTests/HL7UnitTests.csproj \
  --no-build \
  --no-restore \
  --results-directory "$RESULTS_DIR" \
  --logger "trx;LogFileName=${TRX_NAME}" \
  "$@"
