from dataclasses import dataclass

from gurubodh_seed_data.strapi_client import StrapiClientError


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    passed: bool
    message: str


@dataclass(frozen=True)
class PreflightResult:
    checks: tuple[PreflightCheck, ...]

    @property
    def is_valid(self):
        return all(check.passed for check in self.checks)

    @property
    def errors(self):
        return tuple(check.message for check in self.checks if not check.passed)


def run_preflight(client, config):
    checks = []
    checks.append(_check_collection_access(client, "categories"))
    checks.append(_check_collection_access(client, "subjects"))
    checks.extend(_check_locales(client, config))
    checks.append(_check_draft_publish(client, "categories"))
    checks.append(_check_draft_publish(client, "subjects"))
    return PreflightResult(checks=tuple(checks))


def _check_collection_access(client, plural_api_id):
    try:
        client.get_collection(plural_api_id, page_size=1)
    except StrapiClientError as error:
        return PreflightCheck(
            name=f"{plural_api_id} access",
            passed=False,
            message=f"Cannot read {plural_api_id}: {error}",
        )
    return PreflightCheck(
        name=f"{plural_api_id} access",
        passed=True,
        message=f"{plural_api_id} endpoint is reachable.",
    )


def _check_locales(client, config):
    try:
        locales = client.get_locales()
    except StrapiClientError as error:
        return (
            PreflightCheck(
                name="locale access",
                passed=False,
                message=f"Cannot read Strapi locales: {error}",
            ),
        )

    locale_records = locales if isinstance(locales, list) else locales.get("data", ())
    by_code = {
        record.get("code"): record
        for record in locale_records
        if isinstance(record, dict)
    }
    checks = []
    default_record = by_code.get(config.default_locale)
    checks.append(
        PreflightCheck(
            name="default locale",
            passed=bool(default_record and default_record.get("isDefault")),
            message=(
                f"Default locale is {config.default_locale}."
                if default_record and default_record.get("isDefault")
                else f"Default locale must be {config.default_locale} for English fields."
            ),
        )
    )
    checks.append(
        PreflightCheck(
            name="localized locale",
            passed=config.localized_locale in by_code,
            message=(
                f"Localized locale {config.localized_locale} is available."
                if config.localized_locale in by_code
                else f"Localized locale is missing: {config.localized_locale}."
            ),
        )
    )
    return tuple(checks)


def _check_draft_publish(client, plural_api_id):
    try:
        client.get_collection(plural_api_id, status="draft", page_size=1)
    except StrapiClientError as error:
        return PreflightCheck(
            name=f"{plural_api_id} draft access",
            passed=False,
            message=f"Cannot query {plural_api_id} drafts: {error}",
        )
    return PreflightCheck(
        name=f"{plural_api_id} draft access",
        passed=True,
        message=f"{plural_api_id} supports Draft & Publish status queries.",
    )
