from collections import deque
from PyQt6.QtCore import QObject, pyqtSignal
from src.models.events import LogEvent, DamageEvent, DeathEvent
from src.core.parser import parse_line


class CombatAnalyzer(QObject):
    death_recap_ready_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        # 滑动窗口：只保留最近的 1500 条日志
        self.event_buffer = deque(maxlen=1500)

    def process_new_line(self, raw_line: str):
        event = parse_line(raw_line)
        if not event:
            return

        self.event_buffer.append(event)

        if isinstance(event, DeathEvent):
            self.analyze_death(event)

    def analyze_death(self, death_event: DeathEvent):
        # 倒序遍历（从死亡瞬间往前找）
        history = list(self.event_buffer)
        history.reverse()

        fatal_damage = None
        for past_event in history:
            # 找到最近一次对该死者造成伤害的事件
            if isinstance(past_event, DamageEvent) and past_event.target_name == death_event.target_name:
                fatal_damage = past_event
                break

        if fatal_damage:
            report = {
                "victim": death_event.target_name,
                "killer": fatal_damage.source_name,
                "action": fatal_damage.action_name,
                "damage": fatal_damage.damage_amount,
                "overkill": fatal_damage.overkill_amount
            }
            self.death_recap_ready_signal.emit(report)