"""NYSE session boundaries, including holidays, early closes and DST."""
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

@lru_cache(maxsize=1)
def calendar():
    import exchange_calendars
    return exchange_calendars.get_calendar('XNYS')


def session(now=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ValueError('clock must be timezone aware')
    day=now.astimezone(ZoneInfo('America/New_York')).date().isoformat()
    cal=calendar()
    if not cal.is_session(day): return {'open':False,'date':day,'close_at':None}
    start=cal.session_open(day).to_pydatetime()
    end=cal.session_close(day).to_pydatetime()
    return {'open':start<=now<end,'date':day,'open_at':start,'close_at':end}
