# Strapi Database Migrations

This directory is reserved for Strapi application migrations.

Strapi automatically detects JavaScript or TypeScript migration files placed here and runs them once during application startup.

Do not place raw PostgreSQL bootstrap, role, privilege, Amazon RDS, or infrastructure SQL scripts here.

Those scripts live under:

```text
database/postgres/gurubodh-cms/
```

