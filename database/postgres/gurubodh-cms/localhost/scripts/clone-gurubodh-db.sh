#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Clone a Gurubodh CMS PostgreSQL database.

Required environment:
  DUMP_DIR or DUMP_FILE
      DUMP_DIR is used to create a timestamped SQL dump file.
      DUMP_FILE may be set to an explicit SQL dump file path.

Optional environment:
  PGHOST              PostgreSQL host. Defaults to localhost.
  PGPORT              PostgreSQL port. Defaults to 5432.
  PGSSLMODE           PostgreSQL SSL mode, when needed.
  POSTGRES_USER       Admin role used for dump/create/restore. Defaults to postgres.
  POSTGRES_PASSWORD   Password for POSTGRES_USER. If unset, libpq defaults apply.
  MAINTENANCE_DB      Database used for server-level checks. Defaults to postgres.
  SOURCE_DB           Source database. Defaults to gurubodh_db.
  TARGET_DB           Target database. Defaults to gurubodh_db_copy.
  TARGET_OWNER        Owner role for the copied database. Defaults to strapi.
  DROP_TARGET_DB      Set to true to drop TARGET_DB when it already exists.

Example:
  export PGHOST=localhost
  export PGPORT=5432
  export POSTGRES_USER=postgres
  export POSTGRES_PASSWORD='...'
  export DUMP_DIR="$HOME/postgres-dumps/gurubodh"
  DROP_TARGET_DB=true ./database/postgres/gurubodh-cms/localhost/scripts/clone-gurubodh-db.sh
USAGE
}

log() {
  printf '[clone-gurubodh-db] %s\n' "$*"
}

die() {
  printf '[clone-gurubodh-db] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

with_admin_password() {
  if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
    PGPASSWORD="$POSTGRES_PASSWORD" "$@"
  else
    "$@"
  fi
}

psql_admin() {
  local database="$1"
  shift
  with_admin_password psql \
    --set=ON_ERROR_STOP=1 \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$POSTGRES_USER" \
    --dbname="$database" \
    "$@"
}

database_exists() {
  local database="$1"
  local exists

  exists="$(
    psql_admin "$MAINTENANCE_DB" \
      --tuples-only \
      --no-align \
      --set=database="$database" \
      --command="SELECT 1 FROM pg_database WHERE datname = :'database';"
  )"

  [[ "$exists" == "1" ]]
}

validate_identifier() {
  local name="$1"
  local value="$2"

  [[ "$value" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] ||
    die "$name must be a simple PostgreSQL identifier, got: $value"
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
MAINTENANCE_DB="${MAINTENANCE_DB:-postgres}"
SOURCE_DB="${SOURCE_DB:-gurubodh_db}"
TARGET_DB="${TARGET_DB:-gurubodh_db_copy}"
TARGET_OWNER="${TARGET_OWNER:-strapi}"
DROP_TARGET_DB="${DROP_TARGET_DB:-false}"

require_command pg_dump
require_command psql
require_command createdb
require_command dropdb

validate_identifier SOURCE_DB "$SOURCE_DB"
validate_identifier TARGET_DB "$TARGET_DB"
validate_identifier TARGET_OWNER "$TARGET_OWNER"
validate_identifier POSTGRES_USER "$POSTGRES_USER"
validate_identifier MAINTENANCE_DB "$MAINTENANCE_DB"

umask 077

if [[ -z "${DUMP_FILE:-}" ]]; then
  [[ -n "${DUMP_DIR:-}" ]] || die "Set DUMP_DIR or DUMP_FILE before running this script."
  mkdir -p "$DUMP_DIR"
  DUMP_FILE="$DUMP_DIR/${SOURCE_DB}_$(date +%Y%m%d%H%M%S).sql"
else
  DUMP_DIR="$(dirname "$DUMP_FILE")"
  mkdir -p "$DUMP_DIR"
fi

if [[ "$DROP_TARGET_DB" != "true" && "$DROP_TARGET_DB" != "false" ]]; then
  die "DROP_TARGET_DB must be either true or false."
fi

log "Checking source database '$SOURCE_DB'."
database_exists "$SOURCE_DB" || die "Source database does not exist: $SOURCE_DB"

log "Checking target owner role '$TARGET_OWNER'."
owner_exists="$(
  psql_admin "$MAINTENANCE_DB" \
    --tuples-only \
    --no-align \
    --set=target_owner="$TARGET_OWNER" \
    --command="SELECT 1 FROM pg_roles WHERE rolname = :'target_owner';"
)"
[[ "$owner_exists" == "1" ]] || die "Target owner role does not exist: $TARGET_OWNER"

target_exists=false
if database_exists "$TARGET_DB"; then
  target_exists=true
  if [[ "$DROP_TARGET_DB" == "true" ]]; then
    log "Target database '$TARGET_DB' exists and will be replaced after the source dump succeeds."
  else
    die "Target database already exists: $TARGET_DB. Set DROP_TARGET_DB=true to replace it."
  fi
fi

log "Dumping '$SOURCE_DB' to '$DUMP_FILE'."
with_admin_password pg_dump \
  --host="$PGHOST" \
  --port="$PGPORT" \
  --username="$POSTGRES_USER" \
  --dbname="$SOURCE_DB" \
  --format=plain \
  --no-owner \
  --no-acl \
  --file="$DUMP_FILE"

if [[ "$target_exists" == "true" ]]; then
  log "Dropping existing target database '$TARGET_DB'."
  with_admin_password dropdb \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$POSTGRES_USER" \
    "$TARGET_DB"
fi

log "Creating target database '$TARGET_DB' owned by '$TARGET_OWNER'."
with_admin_password createdb \
  --host="$PGHOST" \
  --port="$PGPORT" \
  --username="$POSTGRES_USER" \
  --owner="$TARGET_OWNER" \
  "$TARGET_DB"

log "Restoring dump into '$TARGET_DB'."
psql_admin "$TARGET_DB" --file="$DUMP_FILE"

log "Granting control of '$TARGET_DB' public objects to '$TARGET_OWNER'."
psql_admin "$TARGET_DB" \
  --set=target_db="$TARGET_DB" \
  --set=target_owner="$TARGET_OWNER" <<'SQL'
GRANT ALL PRIVILEGES ON DATABASE :"target_db" TO :"target_owner";
ALTER DATABASE :"target_db" OWNER TO :"target_owner";

ALTER SCHEMA public OWNER TO :"target_owner";
GRANT ALL PRIVILEGES ON SCHEMA public TO :"target_owner";

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO :"target_owner";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :"target_owner";
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO :"target_owner";

CREATE TEMP TABLE clone_script_config (
  target_owner name NOT NULL
) ON COMMIT DROP;

INSERT INTO clone_script_config (target_owner) VALUES (:'target_owner');

DO $do$
DECLARE
  configured_owner name := (SELECT target_owner FROM clone_script_config LIMIT 1);
  object_record record;
BEGIN
  FOR object_record IN
    SELECT
      n.nspname,
      c.relname,
      CASE c.relkind
        WHEN 'r' THEN 'TABLE'
        WHEN 'p' THEN 'TABLE'
        WHEN 'v' THEN 'VIEW'
        WHEN 'm' THEN 'MATERIALIZED VIEW'
        WHEN 'S' THEN 'SEQUENCE'
        WHEN 'f' THEN 'FOREIGN TABLE'
      END AS object_type
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
      AND NOT EXISTS (
        SELECT 1
        FROM pg_depend d
        WHERE d.classid = 'pg_class'::regclass
          AND d.objid = c.oid
          AND d.deptype = 'e'
      )
  LOOP
    EXECUTE format(
      'ALTER %s %I.%I OWNER TO %I',
      object_record.object_type,
      object_record.nspname,
      object_record.relname,
      configured_owner
    );
  END LOOP;

  FOR object_record IN
    SELECT
      n.nspname,
      p.proname,
      pg_get_function_identity_arguments(p.oid) AS identity_args,
      CASE p.prokind
        WHEN 'p' THEN 'PROCEDURE'
        WHEN 'a' THEN 'AGGREGATE'
        ELSE 'FUNCTION'
      END AS object_type
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND NOT EXISTS (
        SELECT 1
        FROM pg_depend d
        WHERE d.classid = 'pg_proc'::regclass
          AND d.objid = p.oid
          AND d.deptype = 'e'
      )
  LOOP
    EXECUTE format(
      'ALTER %s %I.%I(%s) OWNER TO %I',
      object_record.object_type,
      object_record.nspname,
      object_record.proname,
      object_record.identity_args,
      configured_owner
    );
  END LOOP;

  FOR object_record IN
    SELECT
      n.nspname,
      t.typname,
      CASE t.typtype
        WHEN 'd' THEN 'DOMAIN'
        ELSE 'TYPE'
      END AS object_type
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'public'
      AND t.typtype IN ('b', 'd', 'e', 'm')
      AND NOT EXISTS (
        SELECT 1
        FROM pg_depend d
        WHERE d.classid = 'pg_type'::regclass
          AND d.objid = t.oid
          AND d.deptype = 'e'
      )
  LOOP
    EXECUTE format(
      'ALTER %s %I.%I OWNER TO %I',
      object_record.object_type,
      object_record.nspname,
      object_record.typname,
      configured_owner
    );
  END LOOP;
END
$do$;

ALTER DEFAULT PRIVILEGES FOR ROLE :"target_owner" IN SCHEMA public
  GRANT ALL PRIVILEGES ON TABLES TO :"target_owner";
ALTER DEFAULT PRIVILEGES FOR ROLE :"target_owner" IN SCHEMA public
  GRANT ALL PRIVILEGES ON SEQUENCES TO :"target_owner";
ALTER DEFAULT PRIVILEGES FOR ROLE :"target_owner" IN SCHEMA public
  GRANT ALL PRIVILEGES ON FUNCTIONS TO :"target_owner";
SQL

log "Clone complete."
log "Source database: $SOURCE_DB"
log "Target database: $TARGET_DB"
log "Target owner: $TARGET_OWNER"
log "Dump file: $DUMP_FILE"
