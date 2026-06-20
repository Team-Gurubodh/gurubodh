# Content Preparation

Python utilities for preparing Gurubodh CMS-ready content from DOCX source files.

## Setup

Run these commands from the monorepo root:

```bash
cd tools/content-preparation
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
gurubodh-utils run --config jobs/002_spand_rahasya.json
```

## What These Commands Do

`cd tools/content-preparation` moves into this Python tool project.

`python3 -m venv .venv` creates a local virtual environment named `.venv`.

`. .venv/bin/activate` activates the virtual environment so dependencies and console commands are isolated to this project.

`pip install -e .` installs the package in editable mode. This exposes the `gurubodh-utils` command while keeping it linked to the source files in this directory.

`gurubodh-utils run --config jobs/002_spand_rahasya.json` runs a sample content-preparation job.

## Project Root Detection

The CLI detects this tool's root by finding both:

```text
config/conversion_job.schema.json
jobs/
```

If running from another directory, pass the root explicitly:

```bash
gurubodh-utils run \
  --project-root /Users/rajeev/Applications/gurubodh/tools/content-preparation \
  --config jobs/002_spand_rahasya.json
```
