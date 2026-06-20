.PHONY: cms-install cms-dev cms-build content-prep-venv content-prep-install content-prep-help content-prep-run-sample

cms-install:
	cd apps/gurubodh-cms && npm ci

cms-dev:
	cd apps/gurubodh-cms && npm run develop

cms-build:
	cd apps/gurubodh-cms && npm run build

content-prep-venv:
	cd tools/content-preparation && python3 -m venv .venv

content-prep-install:
	cd tools/content-preparation && pip install -e .

content-prep-help:
	cd tools/content-preparation && gurubodh-utils --help

content-prep-run-sample:
	cd tools/content-preparation && gurubodh-utils run --config jobs/002_spand_rahasya.json
