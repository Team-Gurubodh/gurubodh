import json
import unittest
from urllib.error import HTTPError

from gurubodh_seed_data.ingestion_mode import IngestionMode
from gurubodh_seed_data.strapi_client import StrapiClient, StrapiClientError
from gurubodh_seed_data.strapi_config import load_strapi_config
from gurubodh_seed_data.strapi_preflight import run_preflight


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self.body = body if body is not None else {"data": []}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self):
        return self.status_code

    def read(self):
        return json.dumps(self.body).encode("utf-8")

    def close(self):
        pass


class RecordingOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class StrapiConfigTest(unittest.TestCase):
    def test_loads_strapi_config_from_environment(self):
        config = load_strapi_config(
            environ={
                "GURUBODH_STRAPI_URL": "http://localhost:1337/",
                "GURUBODH_STRAPI_API_TOKEN": "token",
            }
        )

        self.assertEqual("http://localhost:1337", config.base_url)
        self.assertEqual("token", config.api_token)
        self.assertEqual("en", config.default_locale)
        self.assertEqual("hi-IN", config.localized_locale)

    def test_rejects_missing_strapi_config(self):
        with self.assertRaisesRegex(ValueError, "Strapi base URL is required"):
            load_strapi_config(environ={})


class IngestionModeTest(unittest.TestCase):
    def test_dry_run_mode_cannot_write(self):
        mode = IngestionMode()

        with self.assertRaisesRegex(RuntimeError, "Dry-run mode cannot perform"):
            mode.require_write_allowed()

    def test_apply_mode_requires_explicit_flag(self):
        self.assertFalse(IngestionMode().can_write)
        self.assertTrue(IngestionMode(apply=True).can_write)


class StrapiClientTest(unittest.TestCase):
    def make_client(self, opener):
        config = load_strapi_config(
            base_url="http://localhost:1337",
            api_token="token",
            environ={},
        )
        return StrapiClient(config, opener=opener)

    def test_builds_authenticated_filtered_collection_query(self):
        opener = RecordingOpener((FakeResponse(body={"data": []}),))
        client = self.make_client(opener)

        result = client.get_collection(
            "categories",
            filters={"code": "CAT001"},
            locale="en",
            status="draft",
        )

        request, timeout = opener.requests[0]
        self.assertEqual({"data": []}, result)
        self.assertEqual(10.0, timeout)
        self.assertIn("/api/categories?", request.full_url)
        self.assertIn("filters%5Bcode%5D%5B%24eq%5D=CAT001", request.full_url)
        self.assertEqual("Bearer token", request.get_header("Authorization"))

    def test_builds_localized_create_as_document_locale_update(self):
        opener = RecordingOpener((FakeResponse(body={"data": {"documentId": "doc-id"}}),))
        client = self.make_client(opener)

        result = client.create_localization(
            "categories",
            "doc-id",
            {"name": "तत्त्वज्ञान"},
            locale="hi-IN",
            publish=True,
        )

        request, _timeout = opener.requests[0]
        self.assertEqual({"data": {"documentId": "doc-id"}}, result)
        self.assertEqual("PUT", request.get_method())
        self.assertIn("/api/categories/doc-id?", request.full_url)
        self.assertIn("locale=hi-IN", request.full_url)
        self.assertIn("status=published", request.full_url)

    def test_wraps_strapi_http_errors(self):
        error = HTTPError(
            "http://localhost:1337/api/categories",
            403,
            "Forbidden",
            hdrs=None,
            fp=FakeResponse(body={"error": {"message": "Forbidden"}}),
        )
        client = self.make_client(RecordingOpener((error,)))

        with self.assertRaises(StrapiClientError) as context:
            client.get_collection("categories")

        self.assertEqual(403, context.exception.status_code)
        self.assertIn("Forbidden", str(context.exception))


class StrapiPreflightTest(unittest.TestCase):
    def make_config(self):
        return load_strapi_config(
            base_url="http://localhost:1337",
            api_token="token",
            environ={},
        )

    def test_preflight_passes_for_accessible_endpoints_and_locales(self):
        opener = RecordingOpener(
            (
                FakeResponse(),
                FakeResponse(),
                FakeResponse(
                    body=[
                        {"code": "en", "isDefault": True},
                        {"code": "hi-IN", "isDefault": False},
                    ]
                ),
                FakeResponse(),
                FakeResponse(),
            )
        )
        config = self.make_config()

        result = run_preflight(StrapiClient(config, opener=opener), config)

        self.assertTrue(result.is_valid)
        self.assertEqual(6, len(result.checks))

    def test_preflight_fails_before_write_planning_when_locale_is_missing(self):
        opener = RecordingOpener(
            (
                FakeResponse(),
                FakeResponse(),
                FakeResponse(body=[{"code": "en", "isDefault": True}]),
                FakeResponse(),
                FakeResponse(),
            )
        )
        config = self.make_config()

        result = run_preflight(StrapiClient(config, opener=opener), config)

        self.assertFalse(result.is_valid)
        self.assertIn("Localized locale is missing: hi-IN.", result.errors)


if __name__ == "__main__":
    unittest.main()
