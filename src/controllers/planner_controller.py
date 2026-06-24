import json
import csv
from PyQt6.QtCore import QObject, pyqtSignal, QUrl
from PyQt6.QtWebSockets import QWebSocket
from src.models.skills_db import SKILL_DB


class PlannerController(QObject):
    data_updated = pyqtSignal(list)
    error_occurred = pyqtSignal(str, str)
    info_occurred = pyqtSignal(str, str)
    sync_status_changed = pyqtSignal(str, bool)

    def __init__(self):
        super().__init__()
        self.timeline_data = []

        # 【核心升级】：双重动态参数
        self.baseline_hp = 150000
        self.potency_multiplier = 35.0  # 1点恢复力 = 35点血

        self.ws = QWebSocket()
        self.ws.connected.connect(self.on_ws_connected)
        self.ws.disconnected.connect(self.on_ws_disconnected)
        self.ws.textMessageReceived.connect(self.on_ws_message)
        self.ws.errorOccurred.connect(self.on_ws_error)

        self.is_online = False
        self.sync_action = "pull"

    # ===============================================
    # 动态参数修改接口
    # ===============================================
    def set_baseline_hp(self, hp_value: int):
        self.baseline_hp = hp_value
        self.recalculate_all()
        self.broadcast_state()

    def set_potency_multiplier(self, multiplier: float):
        """【新增】：动态设置恢复力换算系数"""
        self.potency_multiplier = multiplier
        self.recalculate_all()
        self.broadcast_state()

    # ===============================================
    # 联机同步逻辑
    # ===============================================
    def connect_to_server(self, url: str, action: str):
        self.sync_action = action
        self.sync_status_changed.emit("🔄 正在连接服务器...", False)
        self.ws.open(QUrl(url))

    def disconnect_server(self):
        self.ws.close()

    def on_ws_connected(self):
        self.is_online = True
        self.sync_status_changed.emit("🟢 已连接 (实时同步中)", True)
        if self.sync_action == "push":
            self.broadcast_state()

    def on_ws_disconnected(self):
        self.is_online = False
        self.sync_status_changed.emit("🔴 离线模式 (单机编辑)", False)

    def on_ws_error(self, error):
        self.is_online = False
        self.sync_status_changed.emit(f"🔴 连接失败", False)
        self.error_occurred.emit("网络错误", f"无法连接到服务器，请检查地址或服务器状态。")

    def broadcast_state(self):
        if self.is_online and self.ws.isValid():
            payload = {
                "type": "update",
                "data": self.timeline_data,
                "hp": self.baseline_hp,
                "potency_mult": self.potency_multiplier  # 联机同步恢复力系数
            }
            self.ws.sendTextMessage(json.dumps(payload))

    def on_ws_message(self, message):
        try:
            payload = json.loads(message)
            msg_type = payload.get("type")

            if msg_type == "init" and self.sync_action == "push":
                self.sync_action = "pull"
                return

            if msg_type in ["init", "update"]:
                if "hp" in payload: self.baseline_hp = payload["hp"]
                if "potency_mult" in payload: self.potency_multiplier = payload["potency_mult"]
                self.timeline_data = payload.get("data", [])
                self.recalculate_all()
        except:
            pass

    # ===============================================
    # 排轴核心逻辑
    # ===============================================
    def load_initial_data(self):
        self.timeline_data = [
            {"time": 0, "time_str": "00:00", "skill": "===== 战斗开始 =====", "row_type": "divider"},
            {"time": 10, "time_str": "00:10", "skill": "光之暴走", "dmg_type": "魔法", "raw_dmg": 200000, "mits": [],
             "row_type": "normal"}
        ]
        self.recalculate_all()

    def import_fflogs_timeline(self, new_timeline):
        if new_timeline:
            for row in new_timeline:
                row["row_type"] = "normal"
                row["note"] = ""
            self.timeline_data = new_timeline
            self.recalculate_all()
            self.broadcast_state()

    def update_note(self, row_idx, text):
        if 0 <= row_idx < len(self.timeline_data):
            self.timeline_data[row_idx]["note"] = text
            self.broadcast_state()

    def insert_custom_row(self, index, row_data):
        self.timeline_data.insert(index, row_data)
        self.recalculate_all()
        self.broadcast_state()

    def delete_row(self, index):
        if 0 <= index < len(self.timeline_data):
            self.timeline_data.pop(index)
            self.recalculate_all()
            self.broadcast_state()

    def toggle_highlight(self, index):
        if 0 <= index < len(self.timeline_data):
            current = self.timeline_data[index].get("highlight", False)
            self.timeline_data[index]["highlight"] = not current
            self.data_updated.emit(self.timeline_data)
            self.broadcast_state()

    def add_mitigation(self, row_idx, skill_name):
        if not skill_name or skill_name == "UNDO":
            if skill_name == "UNDO" and self.timeline_data[row_idx].get("mits"):
                self.timeline_data[row_idx]["mits"].pop()
                self.recalculate_all()
                self.broadcast_state()
            return

        current_time = self.timeline_data[row_idx].get("time", 0)
        skill_cd = SKILL_DB.get(skill_name, {}).get("cd", 0)

        if skill_name in self.timeline_data[row_idx].get("mits", []): return

        for i in range(row_idx - 1, -1, -1):
            if self.timeline_data[i].get("row_type", "normal") != "normal": continue
            prev_time = self.timeline_data[i].get("time", 0)
            if skill_name in self.timeline_data[i].get("mits", []):
                if (current_time - prev_time) < skill_cd:
                    wait_time = int(skill_cd - (current_time - prev_time))
                    self.error_occurred.emit("⛔ 技能冷却冲突！", f"【{skill_name}】冷却还剩 {wait_time} 秒！")
                    self.data_updated.emit(self.timeline_data)
                    return

        self.timeline_data[row_idx].setdefault("mits", []).append(skill_name)
        self.recalculate_all()
        self.broadcast_state()

    def remove_mitigation(self, row_idx, mit_name):
        if mit_name in self.timeline_data[row_idx].get("mits", []):
            self.timeline_data[row_idx]["mits"].remove(mit_name)
            self.recalculate_all()
            self.broadcast_state()

    def clear_all_mitigations(self):
        for row in self.timeline_data:
            if row.get("row_type", "normal") == "normal":
                row["mits"] = []
        self.recalculate_all()
        self.broadcast_state()

    def recalculate_all(self):
        for row_idx, row_data in enumerate(self.timeline_data):
            row_type = row_data.get("row_type", "normal")
            if row_type != "normal":
                continue

            raw_dmg = int(row_data.get("raw_dmg", 0))
            current_time = row_data.get("time", 0)

            explicit_mits = row_data.get("mits", [])
            inherited_mits = []
            total_heal_potency = 0

            for i in range(row_idx + 1):
                if self.timeline_data[i].get("row_type", "normal") != "normal": continue

                prev_time = self.timeline_data[i].get("time", 0)
                time_diff = current_time - prev_time

                for mit in self.timeline_data[i].get("mits", []):
                    skill_info = SKILL_DB.get(mit, {})
                    duration = float(skill_info.get("duration", 0))
                    base_pot = int(skill_info.get("potency", 0))
                    hot_pot = int(skill_info.get("hot_potency", 0))

                    if time_diff == 0:
                        total_heal_potency += base_pot
                    elif 0 < time_diff <= duration:
                        ticks = int(time_diff // 3)
                        total_heal_potency += (ticks * hot_pot)
                        tick_str = f" (已跳 {ticks} 次)" if hot_pot > 0 else ""
                        inherited_mits.append(f"{mit}{tick_str}")

            all_active = explicit_mits + [m.split(" (")[0] for m in inherited_mits]

            mit_ratio = 1.0
            total_shield_percent = 0.0
            total_shield_potency = 0.0
            mechanic_tags = []

            for mit_name in all_active:
                skill = SKILL_DB.get(mit_name, {})
                stype = skill.get("type", "")

                sval = float(skill.get("value", 0)) if skill.get("value") else 0.0
                shp = float(skill.get("shield", 0)) if skill.get("shield") else 0.0
                spot = float(skill.get("shield_potency", 0)) if skill.get("shield_potency") else 0.0

                if stype in ["mitigation", "invuln"] and sval > 0:
                    mit_ratio *= (1.0 - sval)
                elif stype == "shield":
                    total_shield_percent += shp
                    total_shield_potency += spot

                if "宏观宇宙" in mit_name:
                    mechanic_tags.append("🌌 大宇宙")
                elif "礼仪之铃" in mit_name:
                    mechanic_tags.append("🔔 铃铛")

            shield_val_from_hp = int(self.baseline_hp * (total_shield_percent / 100.0))

            # 【核心修改】：使用动态的 potency_multiplier 进行计算！
            shield_val_from_potency = int(total_shield_potency * self.potency_multiplier)
            total_shield_val = shield_val_from_hp + shield_val_from_potency

            actual_dmg = int(raw_dmg * mit_ratio) - total_shield_val
            actual_dmg = max(0, actual_dmg)

            row_data["calc_inherited"] = inherited_mits
            row_data["calc_mit_ratio_str"] = f"{(1.0 - mit_ratio) * 100:.1f}%"
            row_data["calc_total_shield_val"] = total_shield_val
            row_data["calc_total_shield_pct"] = int(total_shield_percent)
            row_data["calc_total_shield_potency"] = int(total_shield_potency)
            row_data["calc_total_heal_potency"] = total_heal_potency
            row_data["calc_mechanic_tags"] = mechanic_tags
            row_data["calc_actual_dmg"] = actual_dmg

        self.broadcast_state()
        self.data_updated.emit(self.timeline_data)

    def import_csv(self, file_path):
        try:
            new_data = []
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    time_str = row.get("时间", "00:00")
                    parts = time_str.split(":")
                    time_sec = int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0

                    mits_str = row.get("当前安排", "")
                    mits = [m.strip() for m in mits_str.split("+") if m.strip()]

                    new_data.append({
                        "time": time_sec,
                        "time_str": time_str,
                        "skill": row.get("Boss技能/文本", ""),
                        "note": row.get("备注", ""),
                        "dmg_type": row.get("类型", "魔法"),
                        "raw_dmg": int(row.get("原始伤害", 0)),
                        "row_type": row.get("行类型", "normal"),
                        "highlight": str(row.get("高亮", "False")).lower() == "true",
                        "mits": mits
                    })
            self.timeline_data = new_data
            self.recalculate_all()
            self.broadcast_state()
            self.info_occurred.emit("导入成功", f"成功从 CSV 加载了 {len(new_data)} 行排轴数据！")
        except Exception as e:
            self.error_occurred.emit("导入失败", f"读取 CSV 失败：\n{str(e)}")

    def export_csv(self, file_path):
        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["时间", "Boss技能/文本", "备注", "类型", "原始伤害", "当前安排", "综合减免", "实际伤害", "行类型",
                     "高亮"])
                for row in self.timeline_data:
                    row_type = row.get("row_type", "normal")
                    hl = str(row.get("highlight", False))
                    note = row.get("note", "")
                    if row_type != "normal":
                        writer.writerow(
                            [row.get("time_str", ""), row.get("skill", ""), note, "", "", "", "", "", row_type, hl])
                    else:
                        mits = " + ".join(row.get("mits", []))
                        writer.writerow([
                            row.get("time_str", ""), row.get("skill", ""), note, row.get("dmg_type", ""),
                            row.get("raw_dmg", 0), mits, row.get("calc_mit_ratio_str", "0%"),
                            row.get("calc_actual_dmg", 0), row_type, hl
                        ])
            self.info_occurred.emit("导出成功", f"排轴已成功保存在：\n{file_path}")
        except Exception as e:
            self.error_occurred.emit("导出失败", str(e))