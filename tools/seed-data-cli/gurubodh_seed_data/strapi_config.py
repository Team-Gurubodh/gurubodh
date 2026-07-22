import os
from dataclasses import dataclass


DEFAULT_STRAPI_URL_ENV = "GURUBODH_STRAPI_URL"
DEFAULT_STRAPI_TOKEN_ENV = "GURUBODH_STRAPI_API_TOKEN"


@dataclass(frozen=True)
class StrapiConfig:
    base_url: str
    api_token: str
    default_locale: str = "en"
    localized_locale: str = "hi-IN"
    timeout_seconds: float = 10.0


def load_strapi_config(
    base_url=None,
    api_token=None,
    default_locale="en",
    localized_locale="hi-IN",
    timeout_seconds=10.0,
    environ=None,
):
    env = os.environ if environ is None else environ
    resolved_base_url = (base_url or env.get(DEFAULT_STRAPI_URL_ENV, "")).strip()
    resolved_api_token = (api_token or env.get(DEFAULT_STRAPI_TOKEN_ENV, "")).strip()

    errors = []
    if not resolved_base_url:
        errors.append(
            f"Strapi base URL is required via --strapi-url or {DEFAULT_STRAPI_URL_ENV}."
        )
    if not resolved_api_token:
        errors.append(
            f"Strapi API token is required via --strapi-token or {DEFAULT_STRAPI_TOKEN_ENV}."
        )
    if not default_locale:
        errors.append("Default locale must be a non-empty value.")
    if not localized_locale:
        errors.append("Localized locale must be a non-empty value.")
    if timeout_seconds <= 0:
        errors.append("Timeout seconds must be greater than zero.")
    if errors:
        raise ValueError("\n".join(errors))

    return StrapiConfig(
        base_url=resolved_base_url.rstrip("/"),
        api_token=resolved_api_token,
        default_locale=default_locale,
        localized_locale=localized_locale,
        timeout_seconds=timeout_seconds,
    )
