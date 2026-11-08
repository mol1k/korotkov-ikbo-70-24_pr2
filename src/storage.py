import os
import threading

from tinydb import Query, TinyDB
from tinydb.table import Document

TABLES = ("Client", "Prompt", "Result")
FIRST_ID = 1


def record_id(record):
    return record["id"]


class TinyStorage:

    def __init__(self, path):
        folder = os.path.dirname(os.path.abspath(path))
        os.makedirs(folder, exist_ok=True)
        self.db = TinyDB(path, ensure_ascii=False, encoding="utf-8")
        self.tables = {name: self.db.table(name) for name in TABLES}
        self.lock = threading.Lock()

    def close(self):
        self.db.close()

    def get(self, table, uid):
        with self.lock:
            record = self.tables[table].get(doc_id=uid)
        return None if record is None else dict(record)

    def insert(self, table, record):
        with self.lock:
            self.tables[table].insert(Document(record, doc_id=record["id"]))
        return dict(record)

    def update(self, table, uid, changes):
        with self.lock:
            self.tables[table].update(changes, doc_ids=[uid])
        return self.get(table, uid)

    def search(self, table, filters):
        with self.lock:
            found = self.tables[table].search(Query().fragment(filters))
        return sorted((dict(item) for item in found), key=record_id)

    def next_id(self, table):
        with self.lock:
            ids = [record["id"] for record in self.tables[table].all()]
        return max(ids, default=FIRST_ID - 1) + 1
