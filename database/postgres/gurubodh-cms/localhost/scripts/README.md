# Localhost Helper Scripts

Helper scripts in this directory are intended for a self-managed PostgreSQL
server on localhost or a developer-owned virtual machine. They are not assumed
to be compatible with Amazon RDS.

## Clone the CMS Database

`clone-gurubodh-db.sh` clones the CMS PostgreSQL database by using `pg_dump`,
`createdb`, `psql`, and `dropdb`.

The script:

- dumps the source database with `--no-owner --no-acl`;
- creates a target database owned by `strapi` by default;
- restores the dump into the target database;
- grants `strapi` full privileges on the copied database and `public` schema
  objects;
- transfers ownership of non-extension-owned `public` schema objects to
  `strapi`;
- leaves `PUBLIC` privileges unchanged.

Required environment:

```bash
export DUMP_DIR="$HOME/postgres-dumps/gurubodh"
```

Optional environment:

```bash
export PGHOST=localhost
export PGPORT=5432
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD='...'
export MAINTENANCE_DB=postgres
export SOURCE_DB=gurubodh_db
export TARGET_DB=gurubodh_db_copy
export TARGET_OWNER=strapi
```

Run the script:

```bash
database/postgres/gurubodh-cms/localhost/scripts/clone-gurubodh-db.sh
```

If the target database already exists, the script fails unless replacement is
explicitly requested:

```bash
DROP_TARGET_DB=true database/postgres/gurubodh-cms/localhost/scripts/clone-gurubodh-db.sh
```

`DUMP_FILE` may be set instead of `DUMP_DIR` when an explicit dump path is
preferred.
