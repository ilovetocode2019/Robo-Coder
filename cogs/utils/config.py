import asyncio
import json
import os

class Config:
    def __init__(self, filename):
        self.filename = filename
        self.lock = asyncio.Lock()
        self._load()

    def _load(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r") as file:
                self.data = json.load(file)
        else:
            self.data = {}

    def dump(self):
        with open(self.filename, "w") as file:
            json.dump(self.data, file)

    async def add(self, key, value):
        async with self.lock:
            self.data[str(key)] = value
            self.dump()

    async def remove(self, key):
        async with self.lock:
            if str(key) not in self.data:
                return

            del self.data[str(key)]
            self.dump()

    def get(self, key, default=None):
        return self.data.get(str(key), default)

    def __getitem__(self, key):
        return self.data[str(key)]

    def __setitem__(self, key, value):
        self.data[str(key)] = value
        self.dump()

    def __delitem__(self, key, value):
        del self.data[str(key)]
        self.dump()

    def __iter__(self):
        return self.data.__iter__()

    def __reversed__(self):
        return reversed(self.data)

    def __contains__(self, item):
        return str(item) in self.data

    def __len__(self):
        return len(self.data)

    def __bool__(self):
        return self.data.__bool__()
