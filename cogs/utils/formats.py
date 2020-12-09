class plural:
    def __init__(self, value):
        self.value = value

    def __format__(self, format_spec):
        if self.value == 1:
            return f"{self.value} {format_spec}"
        else:
            return f"{self.value} {format_spec}s"

def join(iterable, seperator=", ", last="or"):
    if len(iterable) == 0:
        return ""
    if len(iterable) == 1:
        return iterable[0]

    return seperator.join(iterable[:-1]) + f" {last} {iterable[-1]}"
