import time as clock

from src.errors import ConflictError, NotFoundError
from src.runner import TaskOutcome

RECENT_WINDOW_SECONDS = 7 * 60
STAGE_QUEUED = "queued"
STAGE_RUNNING = "running"
STAGE_DONE = "done"
STAGE_FAILED = "failed"
CACHE_MISS = 0
CACHE_HIT = 1


def current_time():
    return int(clock.time())


class ThumbnailService:

    def __init__(self, storage, runner, now=current_time):
        self.storage = storage
        self.runner = runner
        self.now = now

    def require(self, table, uid):
        record = self.storage.get(table, uid)
        if record is None:
            raise NotFoundError(f"{table}: запись с id={uid} не найдена")
        return record

    def create(self, table, record):
        if self.storage.get(table, record["id"]) is not None:
            raise ConflictError(
                f"{table}: запись с id={record['id']} уже существует")
        return self.storage.insert(table, record)

    def register_client(self, uid, time, platform):
        record = {"id": uid, "time": time, "platform": platform}
        return self.create("Client", record)

    def load_clients(self, filters):
        return self.storage.search("Client", filters)

    def alter_client(self, uid, changes):
        self.require("Client", uid)
        return self.storage.update("Client", uid, changes)

    def register_prompt(self, uid, client, time, argument, tags):
        self.require("Client", client)
        record = {
            "id": uid, "time": time, "argument": argument,
            "client": client, "tags": tags, "stage": STAGE_QUEUED,
        }
        return self.create("Prompt", record)

    def load_prompts(self, client, filters):
        self.require("Client", client)
        return self.storage.search("Prompt", {**filters, "client": client})

    def alter_prompt(self, uid, changes):
        self.require("Prompt", uid)
        if "client" in changes:
            self.require("Client", changes["client"])
        return self.storage.update("Prompt", uid, changes)

    def load_results(self, prompt, filters):
        self.require("Prompt", prompt)
        return self.storage.search("Result", {**filters, "prompt": prompt})

    def find_cached(self, argument):
        filters = {"stage": STAGE_DONE, "cache_hit": CACHE_MISS}
        for result in self.storage.search("Result", filters):
            source = self.storage.get("Prompt", result["prompt"])
            if source["argument"] == argument:
                return result
        return None

    def execute(self, uid, argument):
        cached = self.find_cached(argument)
        if cached is not None:
            return TaskOutcome(True, cached["result"], None), CACHE_HIT
        return self.runner.run(uid, argument), CACHE_MISS

    def process_prompt(self, uid):
        prompt = self.storage.update("Prompt", uid, {"stage": STAGE_RUNNING})
        outcome, cache_hit = self.execute(uid, prompt["argument"])
        stage = STAGE_DONE if outcome.ok else STAGE_FAILED
        self.storage.insert("Result", {
            "id": self.storage.next_id("Result"), "time": self.now(),
            "result": outcome.result, "stage": stage,
            "error": outcome.error, "prompt": uid, "cache_hit": cache_hit,
        })
        self.storage.update("Prompt", uid, {"stage": stage})

    def report(self):
        border = self.now() - RECENT_WINDOW_SECONDS
        recent = {
            client["id"]: client
            for client in self.storage.search("Client", {})
            if client["time"] is not None and client["time"] >= border
        }
        rows = []
        for prompt in self.storage.search("Prompt", {}):
            client = recent.get(prompt["client"])
            platform = None if client is None else client["platform"]
            row = {"platform": platform, "argument": prompt["argument"]}
            if row not in rows:
                rows.append(row)
        return rows
