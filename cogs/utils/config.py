import asyncio
import json
import os
import itertools

class Config:
    """Represents a configuration file."""

    def __init__(self, filename, *, loop=None):
        self.filename = filename
        self.loop = loop
        self.lock = asyncio.Lock(loop=loop)

        self.load()

    def load(self):
        """Loads the data from the file."""

        if os.path.exists(self.filename):
            with open(self.filename, "r") as file:
                self.data = json.load(file)
        else:
            self.data = {}

    def dump(self):
        """Dumps the data into the file."""

        with open(self.filename, "w") as file:
            json.dump(self.data, file)

    async def add(self, key, value):
        """Safely add adds a key."""

        # Use lock to insure that we don't modify the file twice at the same time
        async with self.lock:
            self.data[str(key)] = value
            self.dump()

    async def remove(self, key):
        """Safely removes a key."""

        # Use lock to insure that we don't modify the file twice at the same time
        async with self.lock:
            del self.data[str(key)]
            self.dump()

    def get(self, key, default=None):
        """Gets an item from the data."""

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
