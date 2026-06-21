#!/usr/bin/env bash
# ----------------------------------------------------------------
# Run all database init scripts in order.
#
# Usage:
#   ./database/run-init.sh
#
# Prerequisites:
#   - A .env file in the project root with PWD_* variables set
#   - psql client installed and accessible in PATH
#   - PostgreSQL server running and accessible
#
# This script:
#   1. Sources the .env file to export all PWD_* variables
#   2. Runs each init script in alphabetical order via psql
# ----------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCALHOST_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(cd "$LOCALHOST_DIR/../../../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
INIT_DIR="$LOCALHOST_DIR/init"

# --- Load environment variables ---
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env file not found at $ENV_FILE"
  echo "Copy .env.example to .env and fill in the values."
  exit 1
fi

echo "Loading environment variables from $ENV_FILE ..."
set -a
# shellcheck disable=SC1091
source "$ENV_FILE"
set +a

# --- Validate that PWD_* variables are set ---
MISSING=()
for var in PWD_db_admin PWD_strapi PWD_strapi_app PWD_strapi_schema_migrator; do
  if [[ -z "${!var:-}" ]]; then
    MISSING+=("$var")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "ERROR: The following required variables are not set in .env:"
  for var in "${MISSING[@]}"; do
    echo "  - $var"
  done
  exit 1
fi

# --- Run init scripts ---
echo ""
echo "Running database init scripts ..."
echo "-----------------------------------"

for script in "$INIT_DIR"/00[0-9]*.sql; do
  if [[ -f "$script" ]]; then
    echo "Running $(basename "$script") ..."
    psql -v ON_ERROR_STOP=1 -f "$script"
    echo "  Done."
  fi
done

echo "-----------------------------------"
echo "All init scripts completed successfully."
