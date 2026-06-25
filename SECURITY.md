# Security

## Reporting Security Issues

Do not report security vulnerabilities in public issues.

While the repository is private, report security concerns directly to the Gurubodh maintainers through the team's private communication channel or GitHub repository administrators.

When GitHub private vulnerability reporting or security advisories are enabled for the repository, use that channel for sensitive reports.

## Secrets Policy

Never commit:

- `.env` files with real values.
- API keys, tokens, passwords, or private keys.
- Database credentials.
- Production data exports.
- Private content that is not approved for repository storage.

Use `.env.example` files to document required variables without real values.

## Supported Versions

Gurubodh is in early private development. Security fixes apply to the active `main` branch unless a separate release support policy is introduced.
