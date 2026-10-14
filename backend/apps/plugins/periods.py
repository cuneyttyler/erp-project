"""Date-bucket helpers shared by every app's dashboard widgets."""

import datetime

from django.utils import timezone


def month_start(date: datetime.date, months_back: int = 0) -> datetime.date:
    """The 1st of the month `months_back` calendar months before `date`'s."""
    total = date.year * 12 + (date.month - 1) - months_back
    return datetime.date(total // 12, total % 12 + 1, 1)


def month_starts(months: int, today: datetime.date | None = None) -> list[datetime.date]:
    """The last `months` month-starts, oldest first, ending with this month."""
    today = today or timezone.localdate()
    return [month_start(today, months - 1 - i) for i in range(months)]


def month_key(date: datetime.date) -> str:
    return f"{date.year:04d}-{date.month:02d}"


def last_days(days: int, today: datetime.date | None = None) -> list[datetime.date]:
    today = today or timezone.localdate()
    return [today - datetime.timedelta(days=days - 1 - i) for i in range(days)]
