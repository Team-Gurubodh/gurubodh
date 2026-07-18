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
	cd tools/content && pip install -e .

content-help:
	cd tools/content && gurubodh --help

content-run-sample:
	cd tools/content && gurubodh prep-subject --config jobs/002_spand_rahasya.local.json
