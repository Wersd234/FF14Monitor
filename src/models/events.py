from dataclasses import dataclass
from typing import List

@dataclass
class LogEvent:
    timestamp: str
    event_type: str
    raw_line: str

@dataclass
class PositionEvent(LogEvent):
    entity_id: str
    entity_name: str
    x: float
    y: float
    heading: float

@dataclass
class ZoneEvent(LogEvent):
    zone_id: str
    zone_name: str

@dataclass
class CombatantEvent(LogEvent):
    entity_id: str
    entity_name: str
    job_id: int # 职业的十六进制代号

@dataclass
class DamageEvent(LogEvent):
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    action_id: str
    action_name: str
    damage_amount: str
    overkill_amount: str = "0"
    active_buffs: List[str] = None

@dataclass
class BuffEvent(LogEvent):
    status_id: str
    status_name: str
    target_id: str
    target_name: str

@dataclass
class DeathEvent(LogEvent):
    target_id: str
    target_name: str