.PHONY: cms-install cms-dev cms-build content-venv content-install content-help content-run-sample

cms-install:
	cd apps/gurubodh-cms && npm ci

cms-dev:
	cd apps/gurubodh-cms && npm run develop

cms-build:
	cd apps/gurubodh-cms && npm run build

content-venv:
	cd tools/content && python3.12 -m venv .venv

content-install:
	tools/content/.venv/bin/python -m pip install -e tools/content

content-help:
	tools/content/.venv/bin/gurubodh --help

content-run-sample:
	tools/content/.venv/bin/gurubodh prep-subject --project-root tools/content --config jobs/002_spand_rahasya.local.json
