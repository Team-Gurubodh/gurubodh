.PHONY: cms-install cms-dev cms-build cli-venv cli-install cli-help cli-run-sample

cms-install:
	cd apps/gurubodh-cms && npm ci

cms-dev:
	cd apps/gurubodh-cms && npm run develop

cms-build:
	cd apps/gurubodh-cms && npm run build

cli-venv:
	cd tools/gurubodh-cli && python3.12 -m venv .venv
	# Python 3.12 can generate a doubled prompt for ".venv"; keep activation tidy.
	perl -0pi -e 's/    PS1=.*\$$\{PS1:-\}.*\n/    PS1="\$$\{VIRTUAL_ENV_PROMPT\}\$$\{PS1:-\}"\n/' tools/gurubodh-cli/.venv/bin/activate

cli-install:
	tools/gurubodh-cli/.venv/bin/python -m pip install -e tools/gurubodh-cli

cli-help:
	tools/gurubodh-cli/.venv/bin/gurubodh --help

cli-run-sample:
	tools/gurubodh-cli/.venv/bin/gurubodh prep-subject --project-root tools/gurubodh-cli --config jobs/002_spand_rahasya.local.json
