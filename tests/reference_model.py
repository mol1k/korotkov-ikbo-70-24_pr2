import re

VALID_ARGUMENT = re.compile(r"[\w.-]+\.mp4")
WINDOW_SECONDS = 7 * 60


class ReferenceModel:

    def __init__(self, now):
        self.now = now
        self.clients = {}
        self.prompts = {}
        self.results = []

    def add_client(self, uid, time, platform):
        self.clients[uid] = {"id": uid, "time": time, "platform": platform}
        return dict(self.clients[uid])

    def add_prompt(self, uid, client, time, argument, tags):
        prompt = {
            "id": uid, "time": time, "argument": argument,
            "client": client, "tags": tags, "stage": "queued",
        }
        self.prompts[uid] = prompt
        answer = dict(prompt)
        self.process(uid, argument)
        return answer

    def cached(self, argument):
        for result in self.results:
            source = self.prompts[result["prompt"]]
            fresh = result["stage"] == "done" and not result["cache_hit"]
            if fresh and source["argument"] == argument:
                return result["result"]
        return None

    def process(self, uid, argument):
        path = self.cached(argument)
        hit = int(path is not None)
        valid = argument is not None and VALID_ARGUMENT.fullmatch(argument)
        if path is None and valid:
            path = f"prompt-{uid}.jpg"
        stage = "done" if path is not None else "failed"
        self.results.append({
            "id": len(self.results) + 1, "time": self.now,
            "result": path, "stage": stage, "prompt": uid, "cache_hit": hit,
        })
        self.prompts[uid]["stage"] = stage

    def select(self, records, filters):
        return [
            dict(record) for _, record in sorted(records.items())
            if all(record[key] == value for key, value in filters.items())
        ]

    def results_of(self, prompt, filters):
        found = [r for r in self.results if r["prompt"] == prompt]
        return [
            dict(result) for result in found
            if all(result[key] == value for key, value in filters.items())
        ]

    def report(self):
        rows = []
        for _, prompt in sorted(self.prompts.items()):
            client = self.clients[prompt["client"]]
            moment = client["time"]
            fresh = moment is not None and self.now - moment <= WINDOW_SECONDS
            row = {
                "platform": client["platform"] if fresh else None,
                "argument": prompt["argument"],
            }
            if row not in rows:
                rows.append(row)
        return rows
