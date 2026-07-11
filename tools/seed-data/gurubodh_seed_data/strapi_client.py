import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class StrapiResponse:
    status_code: int
    body: object


class StrapiClientError(RuntimeError):
    def __init__(self, method, url, status_code=None, message=None):
        self.method = method
        self.url = url
        self.status_code = status_code
        self.message = message or "Strapi request failed."
        status = f" status={status_code}" if status_code is not None else ""
        super().__init__(f"{method} {url}{status}: {self.message}")


class StrapiClient:
    def __init__(self, config, opener=None):
        self.config = config
        self._opener = opener or urlopen

    def get_collection(
        self,
        plural_api_id,
        filters=None,
        locale=None,
        status=None,
        page_size=100,
        page=None,
        populate=None,
    ):
        params = {
            "pagination[pageSize]": page_size,
        }
        if page:
            params["pagination[page]"] = page
        if locale:
            params["locale"] = locale
        if status:
            params["status"] = status
        if populate:
            params["populate"] = populate
        for field, value in (filters or {}).items():
            params[f"filters[{field}][$eq]"] = value
        return self.request("GET", f"/api/{plural_api_id}", params=params).body

    def get_document(self, plural_api_id, document_id, locale=None):
        params = {"locale": locale} if locale else None
        return self.request("GET", f"/api/{plural_api_id}/{document_id}", params=params).body

    def get_locales(self):
        return self.request("GET", "/api/i18n/locales").body

    def create_document(self, plural_api_id, data, locale=None, publish=False):
        params = {}
        if locale:
            params["locale"] = locale
        if publish:
            params["status"] = "published"
        return self.request(
            "POST",
            f"/api/{plural_api_id}",
            params=params,
            data={"data": data},
        ).body

    def create_localization(self, plural_api_id, document_id, data, locale=None, publish=False):
        params = {}
        if locale:
            params["locale"] = locale
        if publish:
            params["status"] = "published"
        return self.request(
            "PUT",
            f"/api/{plural_api_id}/{document_id}",
            params=params,
            data={"data": data},
        ).body

    def update_document(self, plural_api_id, document_id, data, locale=None, publish=False):
        params = {}
        if locale:
            params["locale"] = locale
        if publish:
            params["status"] = "published"
        return self.request(
            "PUT",
            f"/api/{plural_api_id}/{document_id}",
            params=params,
            data={"data": data},
        ).body

    def publish_document(self, plural_api_id, document_id, locale=None):
        return self.update_document(
            plural_api_id,
            document_id,
            data={},
            locale=locale,
            publish=True,
        )

    def request(self, method, path, params=None, data=None):
        url = self._url(path, params)
        headers = {
            "Authorization": f"Bearer {self.config.api_token}",
            "Accept": "application/json",
        }
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener(request, timeout=self.config.timeout_seconds) as response:
                status_code = response.getcode()
                response_body = response.read()
        except HTTPError as error:
            raise StrapiClientError(
                method,
                url,
                status_code=error.code,
                message=_decode_error_body(error),
            ) from error
        except URLError as error:
            raise StrapiClientError(method, url, message=str(error.reason)) from error

        return StrapiResponse(
            status_code=status_code,
            body=_decode_response_body(response_body),
        )

    def _url(self, path, params=None):
        normalized_path = path if path.startswith("/") else f"/{path}"
        query = urlencode(params or {})
        if query:
            return f"{self.config.base_url}{normalized_path}?{query}"
        return f"{self.config.base_url}{normalized_path}"


def _decode_response_body(response_body):
    if not response_body:
        return None
    return json.loads(response_body.decode("utf-8"))


def _decode_error_body(error):
    raw_body = error.read()
    if not raw_body:
        return error.reason
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return raw_body.decode("utf-8", errors="replace")
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        return body["error"].get("message") or str(body["error"])
    return str(body)
