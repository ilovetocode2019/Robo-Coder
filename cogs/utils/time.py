def snowstamp(snowflake):
    timestamp = (int(snowflake) >> 22) + 1420070400000
    timestamp /= 1000

    return d.utcfromtimestamp(timestamp).strftime('%b %d, %Y at %#I:%M %p')    


def readable(time):
    days = time.days

    seconds = time.seconds % (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60

    days_text, hours_text, minutes_text, seconds_text = "day", "hour", "minute", "second"

    if days != 1:
        days_text += "s"
    if hours != 1:
        hours_text += "s"
    if minutes != 1:
        minutes_text += "s"
    if seconds != 1:
        seconds_text += "s"

    return f"{days} {days_text}, {hours} {hours_text}, {minutes} {minutes_text}, and {seconds} seconds"

def from_human(human_string):
    pass