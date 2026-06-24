import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QPushButton, QComboBox, QHeaderView, QMessageBox, QLabel, QDialog,
                             QGridLayout, QCheckBox, QFileDialog, QSpinBox, QMenu, QFormLayout,
                             QLineEdit, QRadioButton, QButtonGroup, QInputDialog)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont, QColor, QBrush, QAction

from src.models.skills_db import SKILL_DB
from src.ui.fflogs_import_dialog import FFLogsImportDialog
from src.controllers.planner_controller import BASELINE_HP


# ==============================================================
# 联机同步设置弹窗
# ==============================================================
class SyncDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌐 多人联机同步配置")
        self.setFixedSize(450, 300)
        self.setStyleSheet("background-color: #1E1E1E; color: #FFF; font-size: 14px;")

        layout = QFormLayout(self)

        self.url_input = QLineEdit("ws://127.0.0.1:8000/ws/")
        self.url_input.setStyleSheet("background: #333; border: 1px solid #555; padding: 4px;")
        layout.addRow("服务器地址:", self.url_input)

        self.room_input = QLineEdit("static_team_1")
        self.room_input.setStyleSheet("background: #333; border: 1px solid #555; padding: 4px;")
        layout.addRow("小队房间号:", self.room_input)

        layout.addRow(QLabel("<hr>"))
        layout.addRow(QLabel("<b>连接时的冲突解决策略：</b>"))

        self.radio_pull = QRadioButton("⬇️ 拉取: 用云端的轴覆盖我本地的数据 (加入他人房间时使用)")
        self.radio_push = QRadioButton("⬆️ 推送: 用我本地的轴覆盖云端的数据 (我是队长创建新轴时使用)")
        self.radio_pull.setChecked(True)

        self.bg = QButtonGroup(self)
        self.bg.addButton(self.radio_pull)
        self.bg.addButton(self.radio_push)

        layout.addRow(self.radio_pull)
        layout.addRow(self.radio_push)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("🚀 立即连接")
        btn_ok.setStyleSheet("background-color: #2E8B57; font-weight: bold; padding: 8px;")
        btn_ok.clicked.connect(self.accept)
        btn_box.addStretch()
        btn_box.addWidget(btn_ok)
        layout.addRow(btn_box)

    def get_config(self):
        url = self.url_input.text().strip()
        room = self.room_input.text().strip()
        action = "push" if self.radio_push.isChecked() else "pull"
        if not url.endswith('/'): url += '/'
        return f"{url}{room}", action


# ... [保留原有的 CustomRowDialog 和 JobFilterDialog 不变] ...
class CustomRowDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("✍️ 插入自定义内容")
        self.setFixedSize(400, 250)
        self.setStyleSheet("background-color: #1E1E1E; color: #FFF; font-size: 14px;")
        layout = QFormLayout(self)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["正常机制技能", "===== 阶段分割线 =====", "💡 文字备注"])
        self.type_combo.setStyleSheet("background: #333; padding: 5px;")
        layout.addRow("行类型:", self.type_combo)
        self.time_input = QLineEdit("00:00")
        self.time_input.setStyleSheet("background: #333; border: 1px solid #555; padding: 4px;")
        layout.addRow("时间 (分:秒):", self.time_input)
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("例如: P2 索尼阶段 / 坦克无敌换嘲")
        self.text_input.setStyleSheet("background: #333; border: 1px solid #555; padding: 4px;")
        layout.addRow("内容/技能名:", self.text_input)
        self.dmg_combo = QComboBox()
        self.dmg_combo.addItems(["魔法", "物理", "特殊(暗)", "AOE (全队)", "单体 (死刑)", "DOT (跳血)"])
        self.dmg_combo.setStyleSheet("background: #333; padding: 5px;")
        layout.addRow("伤害类型:", self.dmg_combo)
        self.dmg_input = QLineEdit("0")
        self.dmg_input.setStyleSheet("background: #333; border: 1px solid #555; padding: 4px;")
        layout.addRow("原始伤害:", self.dmg_input)
        self.type_combo.currentIndexChanged.connect(self.toggle_fields)
        btn_box = QHBoxLayout()
        btn_ok = QPushButton("✅ 确定插入")
        btn_ok.setStyleSheet("background-color: #4169E1; font-weight: bold; padding: 8px;")
        btn_ok.clicked.connect(self.accept)
        btn_box.addStretch()
        btn_box.addWidget(btn_ok)
        layout.addRow(btn_box)

    def toggle_fields(self):
        is_normal = (self.type_combo.currentIndex() == 0)
        self.dmg_combo.setVisible(is_normal)
        self.dmg_input.setVisible(is_normal)

    def get_data(self):
        t_str = self.time_input.text().strip()
        parts = t_str.split(":")
        t_sec = int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0
        idx = self.type_combo.currentIndex()
        row_type = "normal" if idx == 0 else ("divider" if idx == 1 else "remark")
        return {
            "time": t_sec, "time_str": t_str, "skill": self.text_input.text().strip(),
            "note": "", "dmg_type": self.dmg_combo.currentText() if idx == 0 else "",
            "raw_dmg": int(self.dmg_input.text() or 0) if idx == 0 else 0,
            "row_type": row_type, "highlight": False, "mits": []
        }


class JobFilterDialog(QDialog):
    def __init__(self, current_selection, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 筛选显示的职业减伤池")
        self.setFixedSize(450, 250)
        self.setStyleSheet("background-color: #1E1E1E; color: #FFF; font-size: 14px;")
        layout = QVBoxLayout(self)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.checkboxes = {}
        jobs = ["骑士", "战士", "暗骑", "绝枪", "坦克通用", "白魔", "学者", "占星", "贤者", "治疗通用", "近战通用",
                "法系通用", "远敏通用", "通用"]
        for idx, job in enumerate(jobs):
            cb = QCheckBox(job)
            cb.setStyleSheet("QCheckBox::indicator { width: 18px; height: 18px; }")
            cb.setChecked(job in current_selection)
            self.checkboxes[job] = cb
            grid.addWidget(cb, idx // 5, idx % 5)
        layout.addLayout(grid)
        btn_layout = QHBoxLayout()
        btn_all = QPushButton("全选")
        btn_all.setStyleSheet("background-color: #333; padding: 5px;")
        btn_none = QPushButton("全不选")
        btn_none.setStyleSheet("background-color: #333; padding: 5px;")
        btn_ok = QPushButton("确定筛选")
        btn_ok.setStyleSheet("background-color: #4169E1; font-weight: bold; padding: 5px 20px;")
        btn_all.clicked.connect(lambda: [cb.setChecked(True) for cb in self.checkboxes.values()])
        btn_none.clicked.connect(lambda: [cb.setChecked(False) for cb in self.checkboxes.values()])
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_none)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def get_selected_jobs(self):
        return [job for job, cb in self.checkboxes.items() if cb.isChecked()]


# ==============================================================
# 主排轴面板
# ==============================================================
class TimelinePlannerWidget(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.selected_jobs = ["通用", "坦克通用", "治疗通用", "战士", "骑士", "白魔", "学者"]
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(5, 5, 5, 5)

        btn_import_ff = QPushButton("🌐 FFLogs导入")
        btn_import_ff.setStyleSheet(
            "background-color: #4169E1; color: white; padding: 6px; font-weight: bold; border-radius: 3px;")
        btn_import_ff.clicked.connect(self.open_fflogs_import)

        btn_import_csv = QPushButton("📂 CSV导入")
        btn_import_csv.setStyleSheet(
            "background-color: #2E8B57; color: white; padding: 6px; font-weight: bold; border-radius: 3px;")
        btn_import_csv.clicked.connect(self.open_csv_import)

        btn_export = QPushButton("📤 导出")
        btn_export.setStyleSheet("background-color: #333; color: white; padding: 6px;")
        btn_export.clicked.connect(self.open_csv_export)

        btn_clear = QPushButton("🗑️ 清空")
        btn_clear.setStyleSheet("background-color: #8B0000; color: white; padding: 6px;")
        btn_clear.clicked.connect(self.request_clear)

        btn_filter = QPushButton("⚙️ 过滤职业")
        btn_filter.setStyleSheet("background-color: #B8860B; color: white; padding: 6px; font-weight: bold;")
        btn_filter.clicked.connect(self.open_job_filter)

        self.btn_set_hp = QPushButton("🎯 设置血量基数")
        self.btn_set_hp.setStyleSheet(
            "background-color: #8A2BE2; color: white; padding: 6px; font-weight: bold; border-radius: 3px;")
        self.btn_set_hp.clicked.connect(self.open_hp_dialog)

        # 【新增网络同步区】
        self.btn_sync = QPushButton("🔌 联机同步")
        self.btn_sync.setStyleSheet("background-color: #696969; color: white; padding: 6px; font-weight: bold;")
        self.btn_sync.clicked.connect(self.toggle_sync)

        self.sync_label = QLabel("🔴 离线模式")
        self.sync_label.setStyleSheet("color: #FF4444; font-weight: bold; margin-left: 10px;")

        top_bar.addWidget(btn_import_ff)
        top_bar.addWidget(btn_import_csv)
        top_bar.addWidget(btn_export)
        top_bar.addWidget(btn_clear)
        top_bar.addSpacing(10)
        top_bar.addWidget(btn_filter)
        top_bar.addWidget(self.btn_set_hp)
        top_bar.addSpacing(20)
        top_bar.addWidget(self.btn_sync)
        top_bar.addWidget(self.sync_label)
        top_bar.addStretch()

        self.table = QTableWidget()
        # 【列扩充至 11 列】：加入备注列
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "时间", "Boss技能/内容", "📝 备注 (可编辑)", "类型", "原始伤害", "📌 当前安排", "🛡️ 持续覆盖 / HOT",
            "➕ 选择技能", "减伤率", "护盾与奶", "最终实伤"
        ])

        header = self.table.horizontalHeader()
        for i in range(11): header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        self.table.setColumnWidth(0, 60);
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 200);
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 80);
        self.table.setColumnWidth(5, 200);
        self.table.setColumnWidth(6, 200)
        self.table.setColumnWidth(7, 160);
        self.table.setColumnWidth(8, 80);
        self.table.setColumnWidth(9, 200)
        header.setStretchLastSection(True)

        self.table.setStyleSheet("""
            QTableWidget { background-color: #1A1A1A; color: #EEE; gridline-color: #444; font-size: 14px; border: none;}
            QHeaderView::section { background-color: #252525; color: #FFF; padding: 6px; font-weight: bold; border: 1px solid #333;}
            QTableWidget::item { padding: 4px; border-bottom: 1px solid #333; }
            QLineEdit { background-color: #222; color: #00FFCC; border: none; padding: 2px; }
        """)

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        layout.addLayout(top_bar)
        layout.addWidget(self.table)

    def connect_signals(self):
        self.controller.data_updated.connect(self.render_table)
        self.controller.error_occurred.connect(self.show_error)
        self.controller.info_occurred.connect(self.show_info)
        self.controller.sync_status_changed.connect(self.update_sync_ui)

    def open_hp_dialog(self):
        new_hp, ok = QInputDialog.getInt(
            self, "设置基准血量", "请输入测试用基准血量 (法系约13万, 坦克约23万):",
            value=self.controller.baseline_hp, min=1000, max=999999, step=5000
        )
        if ok: self.controller.set_baseline_hp(new_hp)

    def toggle_sync(self):
        if self.controller.is_online:
            self.controller.disconnect_server()
        else:
            dialog = SyncDialog(self)
            if dialog.exec():
                url, action = dialog.get_config()
                self.controller.connect_to_server(url, action)

    def update_sync_ui(self, status_text, is_online):
        self.sync_label.setText(status_text)
        if is_online:
            self.sync_label.setStyleSheet("color: #32CD32; font-weight: bold; margin-left: 10px;")
            self.btn_sync.setText("🔌 断开联机")
            self.btn_sync.setStyleSheet("background-color: #B22222; color: white; padding: 6px; font-weight: bold;")
        else:
            self.sync_label.setStyleSheet("color: #FF4444; font-weight: bold; margin-left: 10px;")
            self.btn_sync.setText("🔌 联机同步")
            self.btn_sync.setStyleSheet("background-color: #696969; color: white; padding: 6px; font-weight: bold;")

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if item is None: return
        row_idx = item.row()

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #333; color: white; border: 1px solid #555; font-size: 14px; } QMenu::item:selected { background-color: #4169E1; }")

        menu.addAction(QAction("🔼 在此上方插入空行/分割线", self)).triggered.connect(
            lambda: self.trigger_insert_row(row_idx))
        menu.addAction(QAction("🔽 在此下方插入空行/分割线", self)).triggered.connect(
            lambda: self.trigger_insert_row(row_idx + 1))
        menu.addSeparator()
        menu.addAction(QAction("✨ 高亮 / 取消高亮此行", self)).triggered.connect(
            lambda: self.controller.toggle_highlight(row_idx))
        menu.addSeparator()
        menu.addAction(QAction("❌ 删除此行", self)).triggered.connect(lambda: self.controller.delete_row(row_idx))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def trigger_insert_row(self, index):
        dialog = CustomRowDialog(self)
        if dialog.exec():
            row_data = dialog.get_data()
            self.controller.insert_custom_row(index, row_data)

    def render_table(self, timeline_data):
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.table.clearSpans()
        self.table.setRowCount(0)
        self.table.setRowCount(len(timeline_data))
        self.table.verticalHeader().setDefaultSectionSize(45)

        current_hp = self.controller.baseline_hp

        for row_idx, row_data in enumerate(timeline_data):
            row_type = row_data.get("row_type", "normal")
            is_highlight = row_data.get("highlight", False)
            bg_color = QColor("#4B3E00") if is_highlight else None

            # 【分割线或备注】：跨列合并 11 列！
            if row_type in ["divider", "remark"]:
                self.table.setSpan(row_idx, 0, 1, 11)
                text = row_data.get("skill", "")

                for col in range(11):
                    blank_item = QTableWidgetItem("")
                    blank_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # 禁止编辑
                    if bg_color: blank_item.setBackground(QBrush(bg_color))
                    self.table.setItem(row_idx, col, blank_item)

                item = QTableWidgetItem(f" {row_data.get('time_str')} | {text}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)

                if row_type == "divider":
                    item.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
                    item.setBackground(QBrush(bg_color or QColor("#222222")))
                    item.setForeground(QColor("#00FFCC"))
                else:
                    item.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Normal))
                    item.setBackground(QBrush(bg_color or QColor("#1E3A5F")))
                    item.setForeground(QColor("#FFFFFF"))

                self.table.setItem(row_idx, 0, item)
                continue

            # 【正常行】
            def _create_item(text, color=None, font=None):
                it = QTableWidgetItem(str(text))
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)  # 禁止基础列被瞎改
                if bg_color: it.setBackground(QBrush(bg_color))
                if color: it.setForeground(color)
                if font: it.setFont(font)
                return it

            self.table.setItem(row_idx, 0, _create_item(row_data.get("time_str", "")))
            self.table.setItem(row_idx, 1, _create_item(row_data.get("skill", "")))

            # 【新增：可编辑的 QLineEdit 备注列】
            note_edit = QLineEdit(row_data.get("note", ""))
            note_edit.setPlaceholderText("")
            if bg_color: note_edit.setStyleSheet(f"background-color: {bg_color.name()}; border: none; padding: 2px;")
            # 当用户打完字回车或者失去焦点时，保存到大脑
            note_edit.editingFinished.connect(lambda r=row_idx, ed=note_edit: self.controller.update_note(r, ed.text()))
            self.table.setCellWidget(row_idx, 2, note_edit)

            type_c = QColor("#FF4444") if "DOT" in row_data.get("dmg_type", "") else QColor("#DDA0DD")
            self.table.setItem(row_idx, 3, _create_item(row_data.get("dmg_type", "魔法"), type_c))
            self.table.setItem(row_idx, 4, _create_item(f"{int(row_data.get('raw_dmg', 0)):,}"))

            explicit_mits = row_data.get("mits", [])
            cast_widget = QWidget()
            if bg_color: cast_widget.setStyleSheet(f"background-color: {bg_color.name()};")
            cast_layout = QHBoxLayout(cast_widget)
            cast_layout.setContentsMargins(4, 4, 4, 4)
            cast_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            for mit in explicit_mits:
                btn = QPushButton(f" {mit} ❌ ")
                btn.setStyleSheet(
                    "QPushButton { background-color: #2D5A27; color: white; border-radius: 4px; padding: 3px 8px; font-weight: bold;} QPushButton:hover { background-color: #FF4444; }")
                btn.clicked.connect(lambda checked, r=row_idx, m=mit: self.controller.remove_mitigation(r, m))
                cast_layout.addWidget(btn)
            cast_layout.addStretch()
            self.table.setCellWidget(row_idx, 5, cast_widget)

            inherited_mits = row_data.get("calc_inherited", [])
            cov_widget = QWidget()
            if bg_color: cov_widget.setStyleSheet(f"background-color: {bg_color.name()};")
            cov_layout = QHBoxLayout(cov_widget)
            cov_layout.setContentsMargins(4, 4, 4, 4)
            cov_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            for mit in inherited_mits:
                lbl = QLabel(f" {mit} ")
                color = "#32CD32" if "跳" in mit else "#AAAAAA"
                lbl.setStyleSheet(
                    f"background-color: #333333; color: {color}; border: 1px dashed #555; border-radius: 4px; padding: 3px 8px;")
                cov_layout.addWidget(lbl)
            cov_layout.addStretch()
            self.table.setCellWidget(row_idx, 6, cov_widget)

            combo = QComboBox()
            combo.setIconSize(QSize(24, 24))
            combo.setStyleSheet(
                "QComboBox { padding: 4px; background-color: #333; color: white; border: 1px solid #555;}")
            combo.addItem("--- 安排技能 ---", "")
            if explicit_mits:
                combo.addItem("❌ 撤销上一个技能", "UNDO")
                combo.insertSeparator(2)

            for skill_name, info in SKILL_DB.items():
                if info.get("job") in self.selected_jobs:
                    is_match = False
                    db_job = info.get("job", "")
                    for sj in self.selected_jobs:
                        if sj == "白魔" and ("白魔法师" in db_job or "白魔" in db_job):
                            is_match = True
                        elif sj == "暗骑" and ("暗黑骑士" in db_job or "暗骑" in db_job):
                            is_match = True
                        elif sj == "绝枪" and ("绝枪战士" in db_job or "绝枪" in db_job):
                            is_match = True
                        elif sj == "占星" and ("占星术士" in db_job or "占星" in db_job):
                            is_match = True
                        elif sj in db_job:
                            is_match = True
                        if is_match: break

                    if is_match:
                        icon_path = info.get("icon_path", "")
                        icon = QIcon(icon_path) if icon_path and os.path.exists(icon_path) else QIcon()
                        display_job = db_job.split(" ")[-1] if " " in db_job else db_job
                        combo.addItem(icon, f"[{display_job}] {skill_name} ({int(info.get('cd', 0))}s)", skill_name)

            combo.currentIndexChanged.connect(lambda idx, r=row_idx, c=combo: self.on_combobox_selected(r, c))

            combo_container = QWidget()
            if bg_color: combo_container.setStyleSheet(f"background-color: {bg_color.name()};")
            combo_layout = QVBoxLayout(combo_container)
            combo_layout.setContentsMargins(4, 4, 4, 4)
            combo_layout.addWidget(combo)
            self.table.setCellWidget(row_idx, 7, combo_container)

            self.table.setItem(row_idx, 8, _create_item(row_data.get("calc_mit_ratio_str", "0%")))

            heal_str = ""
            total_shield_val = row_data.get("calc_total_shield_val", 0)
            total_heal_pot = row_data.get("calc_total_heal_potency", 0)
            mechanic_tags = row_data.get("calc_mechanic_tags", [])

            if total_shield_val > 0:
                details = []
                if row_data.get("calc_total_shield_pct", 0) > 0: details.append(
                    f"{row_data['calc_total_shield_pct']}%HP")
                if row_data.get("calc_total_shield_potency", 0) > 0: details.append(
                    f"{row_data['calc_total_shield_potency']}恢复力")
                heal_str += f"🛡️ 盾 -{total_shield_val:,} ({' + '.join(details)})  "
            if total_heal_pot > 0: heal_str += f"💖 奶 +{total_heal_pot} 恢复力"
            if mechanic_tags: heal_str += f" [{' | '.join(mechanic_tags)}]"

            shield_item = _create_item(heal_str if heal_str else "0", QColor("#FFD700") if heal_str else QColor("#AAA"))
            if mechanic_tags: shield_item.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            self.table.setItem(row_idx, 9, shield_item)

            actual_dmg = row_data.get("calc_actual_dmg", 0)
            ac_font = QFont("Consolas", 12, QFont.Weight.Bold)
            ac_color = QColor("#FF4444") if actual_dmg > current_hp else QColor("#32CD32")
            self.table.setItem(row_idx, 10, _create_item(f"{actual_dmg:,}", ac_color, ac_font))

        self.table.setUpdatesEnabled(True)
        self.table.blockSignals(False)

    def on_combobox_selected(self, row_idx, combo_box: QComboBox):
        skill_name = combo_box.itemData(combo_box.currentIndex())
        if not skill_name: return
        combo_box.blockSignals(True)
        combo_box.setCurrentIndex(0)
        combo_box.blockSignals(False)
        self.controller.add_mitigation(row_idx, skill_name)

    def request_clear(self):
        reply = QMessageBox.question(self, '确认', '确定要清空所有排轴吗？',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.controller.clear_all_mitigations()

    def open_job_filter(self):
        dialog = JobFilterDialog(self.selected_jobs, self)
        if dialog.exec():
            self.selected_jobs = dialog.get_selected_jobs()
            self.controller.data_updated.emit(self.controller.timeline_data)

    def open_fflogs_import(self):
        dialog = FFLogsImportDialog(self)
        if dialog.exec():
            new_timeline = dialog.get_timeline_data()
            if new_timeline:
                self.controller.import_fflogs_timeline(new_timeline)
                QMessageBox.information(self, "导入完成", f"成功抓取并生成了 {len(new_timeline)} 行模板！")

    def open_csv_import(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "导入减伤轴 CSV", "", "CSV Files (*.csv);;All Files (*)")
        if file_path: self.controller.import_csv(file_path)

    def open_csv_export(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "选择导出保存位置", "mitigation_plan.csv",
                                                   "CSV Files (*.csv);;All Files (*)")
        if file_path: self.controller.export_csv(file_path)

    def show_error(self, title, msg):
        QMessageBox.critical(self, title, msg)

    def show_info(self, title, msg):
        QMessageBox.information(self, title, msg)