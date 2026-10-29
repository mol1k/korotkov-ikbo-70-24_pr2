TABLES = ("Client", "Prompt", "Result")
FIRST_ID = 1


def matches(record, filters):
    return all(record.get(key) == value for key, value in filters.items())


class MemoryStorage:

    def __init__(self):
        self.tables = {name: {} for name in TABLES}

    def get(self, table, uid):
        record = self.tables[table].get(uid)
        return None if record is None else dict(record)

    def insert(self, table, record):
        self.tables[table][record["id"]] = dict(record)
        return dict(record)

    def update(self, table, uid, changes):
        record = self.tables[table][uid]
        record.update(changes)
        return dict(record)

    def search(self, table, filters):
        records = sorted(self.tables[table].values(), key=record_id)
        return [dict(item) for item in records if matches(item, filters)]

    def next_id(self, table):
        return max(self.tables[table], default=FIRST_ID - 1) + 1


def record_id(record):
    return record["id"]
