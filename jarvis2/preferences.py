"""Quiet hours mute speech only; the microphone and visual reminders remain."""
from datetime import datetime
import re
def quiet(cfg,now=None):
    if not cfg.get('quiet_enabled'):return False
    now=now or datetime.now()
    start,end=cfg.get('quiet_start','22:00'),cfg.get('quiet_end','07:00')
    if not all(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',t) for t in (start,end)):return False
    current=now.strftime('%H:%M')
    return start<=current<end if start<end else current>=start or current<end
