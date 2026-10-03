from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

GMT_PLUS_7 = timezone(timedelta(hours=7))
HONG_KONG_TIME = ZoneInfo("Asia/Hong_Kong")
SINGAPORE_TIME = ZoneInfo("Asia/Singapore")
KUALA_LUMPUR_TIME = ZoneInfo("Asia/Kuala_Lumpur")
CHINA_TIME = ZoneInfo("Asia/Shanghai")  # SZSE (Shenzhen) and SSE (Shanghai)
DEFAULT_MAX_TRIES = 5
