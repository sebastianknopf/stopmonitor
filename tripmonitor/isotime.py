import datetime
import pytz

def timestamp(additional_seconds=0) -> str:
    ts = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

    if additional_seconds > 0:
        ts = ts + datetime.timedelta(seconds=additional_seconds)
    
    return ts.isoformat()

def localtime(isotime: str|None) -> datetime.datetime:    
    if isotime is None:
        return None
    
    if isotime.endswith('Z'):
        isotime = isotime[:-1] + '+00:00'
    
    ts = datetime.datetime.fromisoformat(isotime)    
    return ts.astimezone(pytz.timezone('Europe/Berlin'))

def interval(years: int, months: int, days: int, hours: int, minutes: int, seconds: int) -> str:
    result = 'P'

    if years > 0:
        result = result + f"{years}Y"
    
    if months > 0:
        result = result + f"{months}M"

    if days > 0:
        result = result + f"{days}D"
    
    result = result + 'T'

    if hours > 0:
        result = result + f"{hours}H"
    
    if minutes > 0:
        result = result + f"{minutes}M"

    if seconds > 0:
        result = result + f"{seconds}S"

    return result

