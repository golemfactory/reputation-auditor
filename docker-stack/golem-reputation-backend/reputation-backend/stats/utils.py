def process_downtime(start_time, end_time):
    duration = (end_time - start_time).total_seconds()
    days, remainder = divmod(duration, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    date_format = "%d %B, %Y"
    down_date = start_time.strftime(date_format)

    parts = []
    if days:
        parts.append(f"{int(days)} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{int(hours)} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{int(minutes)} minute{'s' if minutes != 1 else ''}")
    if seconds or not parts:
        parts.append(f"{int(seconds)} second{'s' if seconds != 1 else ''}")

    human_readable = f"Down for {' and '.join(parts)}"

    time_period = (
        f"From {start_time.strftime('%I:%M %p')} to {end_time.strftime('%I:%M %p')}"
    )

    return {
        "date": down_date,
        "human_period": human_readable,
        "time_period": time_period,
    }
