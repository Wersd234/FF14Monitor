import os
from collections import deque
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal
# 导入你写的牛逼解析类
from src.core.parser import FFLogsParser
from src.models.events import LogEvent, DamageEvent, BuffEvent, DeathEvent, PositionEvent, ZoneEvent, CombatantEvent


def parse_time(ts_str: str) -> datetime:
    try:
        return datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.now()


class HistoryLogReader(QThread):
    history_parsed_signal = pyqtSignal(list)
    progress_signal = pyqtSignal(str)

    def __init__(self, log_file_path: str):
        super().__init__()
        self.log_file_path = log_file_path

    def run(self):
        self.progress_signal.emit(f"启用高级记账本引擎提取战斗明细...")
        event_buffer = deque(maxlen=3000)
        pos_buffer = deque(maxlen=10000)

        encounters = []
        current_enc = None
        enc_id = 1
        active_buffs = {}

        current_zone_id = "Unknown"
        current_zone_name = "未知区域"
        job_dict = {}

        # 【核心适配】：实例化你的状态机解析器！
        parser = FFLogsParser()

        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # 【核心适配】：调用类的解析方法，获取事件列表
                    for event in parser.parse_line(line.strip()):
                        if type(event) is LogEvent: continue

                        evt_time = parse_time(event.timestamp)

                        if isinstance(event, ZoneEvent):
                            current_zone_id = event.zone_id
                            current_zone_name = event.zone_name

                        elif isinstance(event, CombatantEvent):
                            job_dict[event.entity_id] = event.job_id

                        elif isinstance(event, PositionEvent):
                            pos_buffer.append(event)

                        elif isinstance(event, BuffEvent):
                            if event.target_name not in active_buffs:
                                active_buffs[event.target_name] = set()
                            if event.event_type == '26':
                                active_buffs[event.target_name].add(event.status_name)
                            elif event.event_type == '30':
                                active_buffs[event.target_name].discard(event.status_name)

                        elif isinstance(event, DamageEvent):
                            event.active_buffs = list(active_buffs.get(event.target_name, []))
                            event_buffer.append(event)

                            if not current_enc:
                                current_enc = {"id": enc_id, "start": evt_time, "last": evt_time, "deaths": []}
                                enc_id += 1
                            elif (evt_time - current_enc["last"]).total_seconds() > 40:
                                if current_enc["deaths"]: encounters.append(current_enc)
                                current_enc = {"id": enc_id, "start": evt_time, "last": evt_time, "deaths": []}
                                enc_id += 1
                                active_buffs.clear()
                                # 注意：这里保留你的记账本跨回合不断，以便处理跨回合 DOT 等边界情况
                            else:
                                current_enc["last"] = evt_time

                        elif isinstance(event, DeathEvent):
                            if event.target_name != "Unknown":
                                if not current_enc:
                                    current_enc = {"id": enc_id, "start": evt_time, "last": evt_time, "deaths": []}
                                    enc_id += 1
                                report = self._analyze_death(event, event_buffer, pos_buffer, current_enc["start"])
                                if report:
                                    report["zone"] = current_zone_name
                                    report["zone_id"] = current_zone_id
                                    report["jobs"] = job_dict.copy()
                                    current_enc["deaths"].append(report)
                                    current_enc["last"] = evt_time

            if current_enc and current_enc["deaths"]:
                encounters.append(current_enc)
        except Exception as e:
            self.progress_signal.emit(f"读取报错: {str(e)}")
            return

        self.progress_signal.emit(f"解析完成！发现 {len(encounters)} 场战斗。")
        self.history_parsed_signal.emit(encounters)

    def _analyze_death(self, death_event: DeathEvent, buffer: deque, pos_buffer: deque, start_time: datetime):
        history = list(buffer)
        history.reverse()

        timeline = []
        for past_event in history:
            if isinstance(past_event, DamageEvent) and past_event.target_name == death_event.target_name:
                timeline.append(past_event)
                if len(timeline) >= 4: break

        fatal_dmg = None
        for evt in timeline:
            if int(evt.overkill_amount) > 0:
                fatal_dmg = evt
                break

        if not fatal_dmg and timeline:
            fatal_dmg = max(timeline, key=lambda x: int(x.damage_amount) + int(x.overkill_amount))

        death_time = parse_time(death_event.timestamp)
        replay_data = []
        for pos in pos_buffer:
            p_time = parse_time(pos.timestamp)
            delta = (p_time - death_time).total_seconds()
            if -15.0 <= delta <= 1.0:
                replay_data.append({
                    "id": pos.entity_id, "name": pos.entity_name,
                    "t": delta, "x": pos.x, "y": pos.y, "h": pos.heading
                })

        def get_rel_time(ts_string: str) -> str:
            t = parse_time(ts_string)
            delta = max(0, int((t - start_time).total_seconds()))
            return f"{delta // 60:02d}:{delta % 60:02d}"

        timeline_texts = []
        for t_event in reversed(timeline):
            t_time_str = get_rel_time(t_event.timestamp)
            actual_dmg = int(t_event.damage_amount)
            overkill = int(t_event.overkill_amount)

            if t_event == fatal_dmg and overkill > 0:
                timeline_texts.append(
                    f"[{t_time_str}] 受到 <{t_event.action_name}> 伤害: {actual_dmg:,} (O: {overkill:,})")
            else:
                timeline_texts.append(f"[{t_time_str}] 受到 <{t_event.action_name}> 伤害: {actual_dmg:,}")

        return {
            "time": get_rel_time(death_event.timestamp),
            "victim": death_event.target_name,
            "killer": fatal_dmg.source_name if fatal_dmg else "极致死亡",
            "action": fatal_dmg.action_name if fatal_dmg else "衰弱",
            "damage": int(fatal_dmg.damage_amount) if fatal_dmg else 0,
            "overkill": int(fatal_dmg.overkill_amount) if fatal_dmg else 0,
            "buffs": fatal_dmg.active_buffs if fatal_dmg and fatal_dmg.active_buffs else [],
            "timeline": timeline_texts,
            "replay_data": replay_data
        }