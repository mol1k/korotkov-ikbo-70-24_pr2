import json

from fastapi.testclient import TestClient
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle, RuleBasedStateMachine, initialize, invariant, multiple, rule)

from src.app import create_app
from src.client import REQUIRED_HEADERS, ApiClient, ApiError, compact
from src.runner import FakeRunner
from src.service import ThumbnailService
from src.storage import MemoryStorage
from tests.reference_model import ReferenceModel

NOW = 1_760_000_000
TIME_SPREAD = 1000
MAX_ID = 30
MAX_MISSING_ID = 10 ** 6
STATUS_OK = 200
STATUS_NOT_ACCEPTABLE = 406
STATUS_NOT_FOUND = 404
STATUS_CONFLICT = 409
STATUS_UNSUPPORTED_MEDIA = 415
STATUS_UNPROCESSABLE = 422

ids = st.integers(1, MAX_ID)
missing_ids = st.integers(MAX_ID + 10, MAX_MISSING_ID)
times = st.none() | st.integers(NOW - TIME_SPREAD, NOW + TIME_SPREAD)
platforms = st.none() | st.sampled_from(["linux", "macos", "windows", ""])
arguments = st.none() | st.sampled_from([
    "clip.mp4", "intro.mp4", "video_1.mp4", "../secret.mp4", "movie.avi", "",
])
valid_arguments = st.sampled_from(["clip.mp4", "intro.mp4", "video_1.mp4"])
tags = st.none() | st.sampled_from(["preview", "cover"])
stages = st.none() | st.sampled_from(["queued", "running", "done", "failed"])
cache_hits = st.none() | st.sampled_from([0, 1])
client_changes = st.fixed_dictionaries(
    {}, optional={"time": times, "platform": platforms})
prompt_changes = st.fixed_dictionaries({}, optional={
    "time": times, "argument": arguments, "tags": tags, "stage": stages,
})
wrong_values = (st.text(max_size=3) | st.booleans()
                | st.floats(allow_nan=False, allow_infinity=False)
                | st.lists(st.integers(), max_size=2))
bad_bodies = st.sampled_from([
    "", "{", "[]", "null", "42", '{"extra": 1}', '{"time": "1"}',
]) | st.dictionaries(
    st.sampled_from(["time", "client"]), wrong_values, min_size=1,
).map(json.dumps)
content_types = st.sampled_from(
    ["text/json", "text/json; charset=utf-8", "application/json"])
languages = st.sampled_from(["ru-RU", "en-US, ru-RU;q=0.5", "en-US", "ru"])
header_sets = st.fixed_dictionaries({}, optional={
    "Content-Type": content_types, "Accept-Language": languages,
})
CALLS = (
    ("private_api_client_register", (1,)),
    ("private_api_client_load", ()),
    ("private_api_client_alter", (1,)),
    ("private_api_prompt_register", (1, 1)),
    ("private_api_prompt_load", (1,)),
    ("private_api_prompt_alter", (1,)),
    ("private_api_result_load", (1,)),
    ("private_api_report_load", ()),
)


def fixed_now():
    return NOW


def make_storage():
    return MemoryStorage()


def header_parts(headers, name):
    return [
        part.split(";")[0].strip()
        for part in headers.get(name, "").split(",")
    ]


def expected_header_status(headers):
    if "text/json" not in header_parts(headers, "Content-Type"):
        return STATUS_UNSUPPORTED_MEDIA
    if "ru-RU" not in header_parts(headers, "Accept-Language"):
        return STATUS_NOT_ACCEPTABLE
    return STATUS_OK


def expect_status(status, method, /, *args, **kwargs):
    try:
        method(*args, **kwargs)
    except ApiError as error:
        assert error.status == status, error
        return
    raise AssertionError(f"ожидался код {status}")


def without_error(results):
    for result in results:
        assert (result.pop("error") is None) == (result["stage"] == "done")
    return results


class ApiStateMachine(RuleBasedStateMachine):
    clients = Bundle("clients")
    prompts = Bundle("prompts")

    def __init__(self):
        super().__init__()
        service = ThumbnailService(make_storage(), FakeRunner(), fixed_now)
        self.api = ApiClient(http=TestClient(create_app(service)))
        self.model = ReferenceModel(NOW)

    @initialize(target=prompts, client=ids, time=times,
                argument=valid_arguments, tag=tags)
    def seed_cached_pair(self, client, time, argument, tag):
        self.register_client(client, time, "linux")
        first = self.register_prompt(MAX_ID + 1, client, time, argument, tag)
        second = self.register_duplicate_prompt(MAX_ID + 2, first)
        assert self.model.results[-1]["cache_hit"]
        self.alter_prompt(first, {"tags": tag}, client, False)
        self.load_results(second, None, None)
        return multiple(first, second)

    def teardown(self):
        with self.api:
            pass

    @rule(target=clients, uid=ids, time=times, platform=platforms)
    def register_client(self, uid, time, platform):
        if uid in self.model.clients:
            expect_status(STATUS_CONFLICT,
                          self.api.private_api_client_register, uid)
            return multiple()
        answer = self.api.private_api_client_register(uid, time, platform)
        assert answer == self.model.add_client(uid, time, platform)
        return uid

    @rule(uid=clients)
    def register_existing_client(self, uid):
        expect_status(STATUS_CONFLICT,
                      self.api.private_api_client_register, uid)

    @rule(uid=prompts, client=clients)
    def register_existing_prompt(self, uid, client):
        expect_status(STATUS_CONFLICT,
                      self.api.private_api_prompt_register, uid, client)

    @rule(platform=platforms, time=times)
    def load_clients(self, platform, time):
        filters = compact(platform=platform, time=time)
        expected = self.model.select(self.model.clients, filters)
        assert self.api.private_api_client_load(platform, time) == expected

    @rule(uid=clients, changes=client_changes)
    def alter_client(self, uid, changes):
        answer = self.api.private_api_client_alter(uid, **changes)
        self.model.clients[uid].update(changes)
        assert answer == self.model.clients[uid]

    @rule(uid=clients, body=bad_bodies)
    def alter_client_with_bad_body(self, uid, body):
        expect_status(STATUS_UNPROCESSABLE, self.api.send,
                      "PATCH", f"/client-alter/{uid}", content=body)

    @rule(uid=missing_ids)
    def alter_missing_client(self, uid):
        expect_status(STATUS_NOT_FOUND, self.api.private_api_client_alter,
                      uid, platform="linux")

    @rule(target=prompts, uid=ids, client=clients, time=times,
          argument=arguments, tag=tags)
    def register_prompt(self, uid, client, time, argument, tag):
        if uid in self.model.prompts:
            expect_status(STATUS_CONFLICT,
                          self.api.private_api_prompt_register, uid, client)
            return multiple()
        answer = self.api.private_api_prompt_register(
            uid, client, time, argument, tag)
        assert answer == self.model.add_prompt(
            uid, client, time, argument, tag)
        return uid

    @rule(target=prompts, uid=ids, source=prompts)
    def register_duplicate_prompt(self, uid, source):
        if uid in self.model.prompts:
            return multiple()
        original = self.model.prompts[source]
        client, argument = original["client"], original["argument"]
        answer = self.api.private_api_prompt_register(
            uid, client, argument=argument)
        assert answer == self.model.add_prompt(
            uid, client, None, argument, None)
        self.load_report()
        return uid

    @rule(uid=ids, client=missing_ids)
    def register_prompt_for_missing_client(self, uid, client):
        expect_status(STATUS_NOT_FOUND,
                      self.api.private_api_prompt_register, uid, client)

    @rule(client=clients, stage=stages, tag=tags, argument=arguments)
    def load_prompts(self, client, stage, tag, argument):
        filters = compact(stage=stage, tags=tag, argument=argument)
        filters["client"] = client
        expected = self.model.select(self.model.prompts, filters)
        answer = self.api.private_api_prompt_load(client, stage, tag, argument)
        assert answer == expected

    @rule(client=missing_ids)
    def load_prompts_of_missing_client(self, client):
        expect_status(STATUS_NOT_FOUND,
                      self.api.private_api_prompt_load, client)

    @rule(uid=prompts, changes=prompt_changes, client=clients,
          move=st.booleans())
    def alter_prompt(self, uid, changes, client, move):
        if move:
            changes = {**changes, "client": client}
        answer = self.api.private_api_prompt_alter(uid, **changes)
        self.model.prompts[uid].update(changes)
        assert answer == self.model.prompts[uid]

    @rule(uid=prompts, client=st.none() | missing_ids)
    def move_prompt_to_bad_client(self, uid, client):
        status = STATUS_UNPROCESSABLE if client is None else STATUS_NOT_FOUND
        expect_status(status, self.api.private_api_prompt_alter,
                      uid, client=client)

    @rule(uid=prompts, body=bad_bodies)
    def alter_prompt_with_bad_body(self, uid, body):
        expect_status(STATUS_UNPROCESSABLE, self.api.send,
                      "PATCH", f"/prompt-alter/{uid}", content=body)

    @rule(uid=missing_ids)
    def alter_missing_prompt(self, uid):
        expect_status(STATUS_NOT_FOUND, self.api.private_api_prompt_alter,
                      uid, stage="done")

    @rule(prompt=prompts, stage=stages, cache_hit=cache_hits)
    def load_results(self, prompt, stage, cache_hit):
        filters = compact(stage=stage, cache_hit=cache_hit)
        answer = self.api.private_api_result_load(prompt, stage, cache_hit)
        assert without_error(answer) == self.model.results_of(prompt, filters)

    @rule(prompt=missing_ids)
    def load_results_of_missing_prompt(self, prompt):
        expect_status(STATUS_NOT_FOUND,
                      self.api.private_api_result_load, prompt)

    @rule()
    def load_report(self):
        assert self.api.private_api_report_load() == self.model.report()

    @rule(call=st.sampled_from(CALLS), headers=header_sets)
    def send_with_headers(self, call, headers):
        status = expected_header_status(headers)
        self.api.headers = headers
        try:
            if status == STATUS_OK:
                self.load_report()
            else:
                name, args = call
                expect_status(status, getattr(self.api, name), *args)
        finally:
            self.api.headers = dict(REQUIRED_HEADERS)

    @invariant()
    def clients_match_model(self):
        expected = self.model.select(self.model.clients, {})
        assert self.api.private_api_client_load() == expected


class TestApiStateMachine(ApiStateMachine.TestCase):
    settings = settings(max_examples=100, stateful_step_count=30,
                        deadline=None)
