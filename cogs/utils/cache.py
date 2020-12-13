import asyncio
import functools
import inspect
import collections

class LRUDict(collections.OrderedDict):
    def __init__(self, max_legnth = 10, *args, **kwargs):
        if max_legnth <= 0:
            raise ValueError()
        self.max_legnth = max_legnth

        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)

        if len(self) > 10:
            super().__delitem__(list(self)[0])

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

def cache(max_legnth = 100):
    def decorator(func):
        cache = LRUDict(max_legnth=max_legnth)

        def __len__():
            return len(cache)

        def _get_key(*args, **kwargs):
            return f"{':'.join([repr(arg) for arg in args])}{':'.join([f'{repr(kwarg)}={repr(value)}' for kwarg, value in kwargs.items()])}"

        def invalidate(*args, **kwargs):
            if not args:
                cache.clear()
                return

            try:
                key = _get_key(*args, **kwargs)
                cache.pop(key)
                return True
            except KeyError:
                return False

        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            key = _get_key(*args, **kwargs)

            try:
                value = cache[key]
                if asyncio.iscoroutinefunction(func):
                    async def coro():
                        return value
                    return coro()
                return value

            except KeyError:
                value = func(*args, **kwargs)
                if inspect.isawaitable(value):
                    async def coro():
                        result = await value
                        cache[key] = result
                        return result
                    return coro()

                cache[key] = value
                return value


        wrapped.invalidate = invalidate
        wrapped.cache = cache
        wrapped._get_key = _get_key
        wrapped.__len__ = __len__
        return wrapped

    return decorator
