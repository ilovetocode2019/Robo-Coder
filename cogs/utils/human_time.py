import datetime
import re

import dateutil
import parsedatetime
from discord.ext import commands


class ShortTime:
    """Attempts to parse a time using regex."""

    regex = re.compile(
        """(?:(?P<years>[0-9])(?:years?|y))?
           (?:(?P<months>[0-9])(?:months?|mo))?
           (?:(?P<weeks>[0-9])(?:weeks?|w))?
           (?:(?P<days>[0-9])(?:days?|d))?
           (?:(?P<hours>[0-9])(?:hours?|h))?
           (?:(?P<minutes>[0-9])(?:minutes?|m))?
           (?:(?P<seconds>[0-9])(?:seconds?|s))?""",
           re.VERBOSE)

    def __init__(self, argument, *, now=None):
        now = now or datetime.datetime.utcnow()
        match = self.regex.fullmatch(argument)
        if not match or not match.group(0):
            raise commands.BadArgument("You provided an invalid time")

        data = {key: int(value) for key, value in match.groupdict(default=0).items()}
        delta = dateutil.relativedelta.relativedelta(**data)

        self.delta = delta
        self.time = datetime.datetime.utcnow()+delta
        self.past = self.time < now

    @classmethod
    async def convert(cls, ctx, arg):
        return cls(arg, now=ctx.message.created_at)

class HumanTime:
    """Attempts to parse a time using parsedatetime."""

    calendar = parsedatetime.Calendar(version=parsedatetime.VERSION_CONTEXT_STYLE)

    def __init__(self, argument, *, now=None):
        now = now or datetime.datetime.utcnow()
        time, context = self.calendar.parseDT(argument, sourceTime=now)
        if not context.hasDateOrTime:
            # No date or time data
            raise commands.BadArgument("I couldn't recognize your time. Try something like `tomorrow` or `3 days`.")
        if not context.hasTime:
            # We have the date, but not the time, so replace it with the time
            time = time.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)

        self.time = time
        self.past = time < now

    @classmethod
    async def convert(cls, ctx, arg):
        return cls(arg, now=ctx.message.created_at)

class Time:
    """Attempts to parse the time using HumanTime and then ShortTime."""

    def __init__(self, argument, *, now=None):
        now = now or datetime.datetime.utcnow()
        try:
            # Attempt to parse the time through ShortTime
            parsed = ShortTime(argument, now=now)
        except commands.BadArgument:
            # Otherwise use HumanTime
            parsed = HumanTime(argument, now=now)

        self.time = parsed.time
        self.past = parsed.past

    @classmethod
    async def convert(cls, ctx, arg):
        return cls(arg, now=ctx.message.created_at)

class FutureTime(Time):
    """Attempts to parse a time using Time but then checks if it's in the future."""

    def __init__(self, argument, *, now=None):
        super().__init__(argument, now=now)
        if self.past:
            raise commands.BadArgument("That time is in the past")

class TimeWithContent(Time):
    """Attempts to parse a time by using ShortTime regex or parsedatetime.Calendar.nlp and then stripping the content from the time."""

    def __init__(self, argument, *, now=None):
        now = now or datetime.datetime.utcnow()

        # Attempt to parse the time using ShortTime regex
        match = ShortTime.regex.match(argument)
        if match and match.group(0):
            data = {key: int(value) for key, value in match.groupdict(default=0).items()}
            time = now+dateutil.relativedelta.relativedelta(**data)
            content = argument[match.end():].strip()
        else:
            # Parsedatetime doesn't work with 'from now' so handle that here
            if argument.endswith("from now"):
                argument = argument[:-8].strip()

            parsed = HumanTime.calendar.nlp(argument, sourceTime=now)
            if not parsed:
                raise commands.BadArgument("I couldn't recognize your time. Try something like `tomorrow` or `3 days`.")
            time, context, start, end, text = parsed[0]

            if not context.hasDateOrTime:
                raise commands.BadArgument("I couldn't recognize your time. Try something like `tomorrow` or `3 days`.")
            if not context.hasTime:
                # We have date data data, but not time, so replace it with time data
                time = time.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)
            if context.accuracy == parsedatetime.pdtContext.ACU_HALFDAY:
                time = time.replace(day=now.day+1)
    
            if start != 0 and end != len(argument):
                # Time does not start at the start but it doesn't end at the end either
                raise commands.BadArgument("The time must be at the start or end of the argument not the middle, like `do homework in 3 hours` or `in 3 hours do homework`")
            if time < now:
                raise commands.BadArgument("That time is in the past")

            if start:
                content = argument[:start].strip()
            else:
                content = argument[end:].strip()

        if not content:
            content = "..."

        self.time = time
        self.past = time < now
        self.content = content
