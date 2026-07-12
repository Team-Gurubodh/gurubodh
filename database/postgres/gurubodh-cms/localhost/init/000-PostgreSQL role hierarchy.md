# PostgreSQL Role Hierarchy for gurubodh_db
```
postgres / db_admin          ← superuser, server administration
└── strapi                   ← database owner, gurubodh_db
    ├── strapi_readonly      ← SELECT only (no login)
    │   └── (future read-only users)
    ├── strapi_data_editor    ← DML only, no DDL (no login)
    │   └── strapi_app        ← Next.js application user
    └── strapi_schema_editor  ← DML + DDL (no login)
        └── strapi_schema_migrator  ← deployment/migration user
```