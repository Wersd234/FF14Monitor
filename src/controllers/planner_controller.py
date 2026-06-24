import json
import csv
import os
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
                "potency_mult": self.potency_multiplier
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
                # 防回音壁卡顿死循环：如果云端和本地数据一致，直接拦截！
                if json.dumps(payload.get("data", [])) == json.dumps(self.timeline_data):
                    return

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

    # ===============================================
    # 🛡️ 绝境战级：真实护盾碎裂引擎与 HOT 跳数计算
    # ===============================================
    def recalculate_all(self):
        try:
            active_shields = []
            active_buffs = []

            for row_idx, row_data in enumerate(self.timeline_data):
                row_type = row_data.get("row_type", "normal")
                if row_type != "normal":
                    continue

                current_time = float(row_data.get("time", 0) or 0)
                raw_dmg = float(row_data.get("raw_dmg", 0) or 0)

                # 1. 清理过期或被打碎的护盾
                active_shields = [s for s in active_shields if s["expire"] > current_time and s["remain_hp"] > 0]
                active_buffs = [b for b in active_buffs if b["expire"] > current_time]

                row_mits = row_data.get("mits", [])
                hot_ticks = 0

                # 2. 载入本行释放的技能
                for mit_name in row_mits:
                    info = SKILL_DB.get(mit_name, {})
                    dur = float(info.get("duration", 15) or 15)
                    expire_time = current_time + dur

                    active_buffs.append({
                        "skill": mit_name,
                        "expire": expire_time,
                        "info": info
                    })

                    # HOT 计算 (3秒一跳)
                    heal_pot = float(info.get("heal_potency", 0) or 0)
                    if heal_pot > 0 and dur > 0:
                        hot_ticks += int(dur / 3)

                    # 护盾计算
                    shield_hp = 0.0
                    shield_pct = float(info.get("shield_pct", 0) or 0)
                    if shield_pct > 0:
                        shield_hp += float(self.baseline_hp) * (shield_pct / 100.0)

                    shield_potency = float(info.get("shield_potency", 0) or 0)
                    if shield_potency > 0:
                        shield_hp += shield_potency * float(self.potency_multiplier)

                    if shield_hp > 0:
                        active_shields.append({
                            "skill": mit_name,
                            "expire": expire_time,
                            "remain_hp": int(shield_hp)
                        })

                # 3. 统计减伤池
                mit_multiplier = 1.0
                calc_inherited = []

                for buff in active_buffs:
                    mit_val = float(buff["info"].get("mitigation", 0) or 0)
                    if mit_val > 0:
                        mit_multiplier *= (1.0 - (mit_val / 100.0))

                    if buff["skill"] not in row_mits:
                        remain_time = int(buff["expire"] - current_time)
                        calc_inherited.append(f"{buff['skill']} ({remain_time}s)")

                total_mit_pct = (1.0 - mit_multiplier) * 100
                row_data["calc_mit_ratio_str"] = f"{total_mit_pct:.1f}%"
                row_data["calc_inherited"] = calc_inherited

                # 4. 真实护盾扣血判定
                mitigated_dmg = raw_dmg * mit_multiplier
                dmg_to_absorb = mitigated_dmg
                total_shield_consumed = 0

                if dmg_to_absorb > 0:
                    for shield in active_shields:
                        if shield["remain_hp"] > 0 and dmg_to_absorb > 0:
                            absorb = min(shield["remain_hp"], dmg_to_absorb)
                            shield["remain_hp"] -= absorb
                            dmg_to_absorb -= absorb
                            total_shield_consumed += absorb

                actual_dmg = max(0, mitigated_dmg - total_shield_consumed)

                # 5. 写入 UI 所需的最新字段名
                row_data["calc_actual_dmg"] = int(actual_dmg)
                row_data["calc_total_shield_val"] = int(sum(s["remain_hp"] for s in active_shields))
                row_data["calc_hot_ticks"] = hot_ticks

            # 计算完后立刻通知 UI 刷新表格！
            self.data_updated.emit(self.timeline_data)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_occurred.emit("算力引擎崩溃", f"计算护盾覆盖时发生错误：\n{str(e)}")

    # ===============================================
    # 智能兼容性 CSV 导入导出
    # ===============================================
    def import_csv(self, file_path):
        try:
            new_data = []

            # 🛡️ 神级探测：自动判断 Excel 的 GBK 编码与标准 UTF-8，彻底消灭导入变空！
            try:
                f = open(file_path, mode='r', encoding='utf-8-sig')
                f.read(1)
                f.seek(0)
            except UnicodeDecodeError:
                f = open(file_path, mode='r', encoding='gbk')

            reader = csv.DictReader(f)

            for row in reader:
                time_str = row.get("时间", "00:00")
                parts = time_str.split(":")
                time_sec = int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0

                # 兼容多种列名，防止用户手动修改表头
                skill = row.get("Boss技能/内容", row.get("Boss技能/文本", row.get("Boss技能", "")))
                note = row.get("备注", row.get("备注/战术指南", ""))
                dmg_type = row.get("类型", "魔法")

                raw_dmg_str = str(row.get("原始伤害", "0")).replace(",", "")
                raw_dmg = int(float(raw_dmg_str)) if raw_dmg_str.replace('.', '', 1).isdigit() else 0

                row_type = row.get("行类型", row.get("row_type", "normal"))
                if "=====" in skill:
                    row_type = "divider"
                elif "💡" in skill:
                    row_type = "remark"

                hl_str = str(row.get("高亮", "False")).lower()
                highlight = (hl_str == "true" or hl_str == "1")

                # 兼容多种排列分隔符
                mits_str = row.get("当前安排", "")
                if "+" in mits_str:
                    mits = [m.strip() for m in mits_str.split("+") if m.strip()]
                elif "|" in mits_str:
                    mits = [m.strip() for m in mits_str.split("|") if m.strip()]
                else:
                    mits = [m.strip() for m in mits_str.split(",") if m.strip()]

                new_data.append({
                    "time": time_sec,
                    "time_str": time_str,
                    "skill": skill,
                    "note": note,
                    "dmg_type": dmg_type,
                    "raw_dmg": raw_dmg,
                    "row_type": row_type,
                    "highlight": highlight,
                    "mits": mits
                })

            f.close()

            # 读取成功，重置数据并推演全盘算力
            self.timeline_data = new_data
            self.recalculate_all()
            self.broadcast_state()
            self.info_occurred.emit("导入成功", f"成功从 CSV 满血复活了 {len(new_data)} 行排轴数据！")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_occurred.emit("导入失败", f"文件可能被占用或格式损坏：\n{str(e)}")

    def export_csv(self, file_path):
        try:
            # 强制带 BOM 头，防止 Windows 用户用 Excel 打开乱码
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["时间", "Boss技能/内容", "备注/战术指南", "类型", "原始伤害", "当前安排", "综合减免", "实际伤害",
                     "行类型", "高亮"])

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

            self.info_occurred.emit("导出成功", f"战术板已保存至：\n{file_path}")
        except Exception as e:
            self.error_occurred.emit("导出失败", f"无法保存，请检查文件是否被 Excel 打开占用：\n{str(e)}")