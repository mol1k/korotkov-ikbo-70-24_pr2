import json

import httpx

DEFAULT_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 30
REQUIRED_HEADERS = {"Content-Type": "text/json", "Accept-Language": "ru-RU"}
STATUS_OK = 200
API_PREFIX = "/private/api"


class ApiError(Exception):

    def __init__(self, status, detail):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


def compact(**values):
    return {key: value for key, value in values.items() if value is not None}


class ApiClient:

    def __init__(self, base_url=DEFAULT_URL, http=None, headers=None):
        self.http = http or httpx.Client(
            base_url=base_url, timeout=DEFAULT_TIMEOUT)
        self.headers = dict(REQUIRED_HEADERS if headers is None else headers)

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def send(self, method, route, params=None, content=None):
        response = self.http.request(
            method, API_PREFIX + route, params=params, content=content,
            headers=self.headers)
        data = response.json()
        if response.status_code != STATUS_OK:
            raise ApiError(response.status_code, data["detail"])
        return data

    def send_json(self, method, route, body):
        return self.send(method, route, content=json.dumps(body))

    def private_api_client_register(self, uid, time=None, platform=None):
        params = compact(time=time, platform=platform)
        return self.send("PUT", f"/client-register/{uid}", params)

    def private_api_client_load(self, platform=None, time=None):
        params = compact(platform=platform, time=time)
        return self.send("POST", "/client-load", params)

    def private_api_client_alter(self, uid, **changes):
        return self.send_json("PATCH", f"/client-alter/{uid}", changes)

    def private_api_prompt_register(self, uid, client, time=None,
                                    argument=None, tags=None):
        params = compact(
            client=client, time=time, argument=argument, tags=tags)
        return self.send("PUT", f"/prompt-register/{uid}", params)

    def private_api_prompt_load(self, client, stage=None, tags=None,
                                argument=None):
        params = compact(stage=stage, tags=tags, argument=argument)
        return self.send("POST", f"/prompt-load/{client}", params)

    def private_api_prompt_alter(self, uid, **changes):
        return self.send_json("PATCH", f"/prompt-alter/{uid}", changes)

    def private_api_result_load(self, prompt, stage=None, cache_hit=None):
        params = compact(stage=stage, cache_hit=cache_hit)
        return self.send("POST", f"/result-load/{prompt}", params)

    def private_api_report_load(self):
        return self.send("POST", "/report-load")
