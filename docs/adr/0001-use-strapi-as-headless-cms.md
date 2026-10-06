# 0001 — Use Strapi as Headless CMS

## Status

Accepted

## Decision and rationale

Use self-hosted Strapi for structured content, relations, editorial publication,
and API access. It supplies content modeling and administration without building
a custom CMS, while retaining control of hosting and the content store and
avoiding recurring content-volume or editor-seat SaaS charges.

## Tradeoff and review trigger

The team owns database operations, upgrades, scaling, and security patching.
Reconsider if content modeling or localization needs exceed Strapi's practical
capabilities or the cost of self-hosting exceeds the value of that control.

See the [implemented CMS](../../apps/gurubodh-cms/README.md) and
[API scope](0004-strapi-api-style.md); this decision does not select deployment
or network-access policy.
