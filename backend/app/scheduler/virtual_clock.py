from datetime import datetime, timezone, timedelta
from typing import Dict, Any

class VirtualClock:
    def __init__(self):
        self._offset = timedelta(0)
        self._frozen_at: datetime | None = None

    def now(self) -> datetime:
        if self._frozen_at:
            return self._frozen_at
        return datetime.now(timezone.utc) + self._offset

    def advance(self, seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0) -> datetime:
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours, days=days)
        if self._frozen_at:
            self._frozen_at += delta
            return self._frozen_at
        self._offset += delta
        return self.now()

    def set_time(self, target_time: datetime):
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)
        self._offset = target_time - datetime.now(timezone.utc)
        self._frozen_at = None

    def reset(self):
        self._offset = timedelta(0)
        self._frozen_at = None

    def to_dict(self) -> Dict[str, Any]:
        curr = self.now()
        real = datetime.now(timezone.utc)
        return {
            "current_time": curr.isoformat(),
            "real_time": real.isoformat(),
            "offset_seconds": self._offset.total_seconds(),
            "is_frozen": self._frozen_at is not None
        }

clock = VirtualClock()
