import os
import csv
import json
import re
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QPushButton, QComboBox, QHeaderView, QMessageBox, QLabel, QDialog,
                             QGridLayout, QCheckBox, QFileDialog, QMenu, QFormLayout, QLineEdit,
                             QRadioButton, QButtonGroup, QInputDialog)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRect
from PyQt6.QtGui import QIcon, QFont, QColor, QBrush, QAction, QPainter, QPixmap, QPen

from src.models.skills_db import SKILL_DB
from src.ui.fflogs_import_dialog import FFLogsImportDialog

# ==============================================================
# 【绝对严格职业映射字典】：杜绝一切模糊匹配导致串台！
# ==============================================================
STRICT_JOB_MAP = {
    "骑士": ["骑士", "剑术师 骑士", "剑术师"],
    "战士": ["战士", "斧术师 战士", "斧术师"],
    "暗骑": ["暗黑骑士", "暗骑"],
    "绝枪": ["绝枪战士", "绝枪"],
    "白魔": ["白魔法师", "幻术师 白魔法师", "幻术师", "白魔"],
    "学者": ["学者", "秘术师 学者"],
    "占星": ["占星术士", "占星"],
    "贤者": ["贤者"],
    "坦克通用": ["坦克通用", "剑术师 斧术师 骑士 战士 暗黑骑士 绝枪战士"],
    "治疗通用": ["治疗通用", "幻术师 白魔法师 学者 占星术士 贤者"],
    "近战通用": ["近战通用", "格斗家 枪术师 双剑师 武僧 龙骑士 忍者 武士 钐镰客 蝰蛇剑士"],
    "法系通用": ["法系通用", "咒术师 秘术师 黑魔法师 召唤师 赤魔法师 青魔法师 画魔"],
    "远敏通用": ["远敏通用", "弓箭手 吟游诗人 机工士 舞者"],
    "通用": ["通用", "全部职业"]
}


class SkillIconLabel(QLabel):
    clicked = pyqtSignal(str)

    def __init__(self, skill_name, icon_path, is_deletable=False, tick_str="", parent=None):
        super().__init__(parent)
        self.skill_name = skill_name
        self.is_deletable = is_deletable
        self.tick_str = tick_str
        self.hovered = False

        self.setFixedSize(36, 36)

        self.pixmap = QPixmap(icon_path) if icon_path and os.path.exists(icon_path) else QPixmap()
        if not self.pixmap.isNull():
            self.pixmap = self.pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)

        tt = f"<b style='color:#00FFCC; font-size:14px;'>{skill_name}</b>"
        if tick_str:
            tt += f"<br><span style='color:#32CD32;'>{tick_str}</span>"
        if is_deletable:
            tt += "<br><span style='color:#FF4444;'>[点击移除此减伤]</span>"
        self.setToolTip(tt)

        if self.is_deletable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event):
        if self.is_deletable:
            self.hovered = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.is_deletable:
            self.hovered = False
            self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_deletable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.skill_name)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = self.rect()

        if not self.is_deletable:
            painter.setOpacity(0.55)

        if not self.pixmap.isNull():
            x = (rect.width() - self.pixmap.width()) // 2
            y = (rect.height() - self.pixmap.height()) // 2
            painter.drawPixmap(x, y, self.pixmap)
        else:
            painter.setBrush(QBrush(QColor("#444")))
            painter.setPen(Qt.GlobalColor.transparent)
            painter.drawRoundedRect(4, 4, 28, 28, 4, 4)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.skill_name[:1])

        painter.setOpacity(1.0)

        if self.hovered and self.is_deletable:
            painter.fillRect(rect, QColor(0, 0, 0, 180))
            pen = QPen(QColor("#FF3333"), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            margin = 8
            painter.drawLine(margin, margin, rect.width() - margin, rect.height() - margin)
            painter.drawLine(rect.width() - margin, margin, margin, rect.height() - margin)

        if self.tick_str:
            nums = re.findall(r'\d+', self.tick_str)
            if nums:
                tick_num = nums[0]
                painter.setPen(QPen(QColor("#111"), 1))
                painter.setBrush(QBrush(QColor("#32CD32")))
                badge_rect = QRect(rect.width() - 15, rect.height() - 15, 14, 14)
                painter.drawEllipse(badge_rect)
                painter.setPen(Qt.GlobalColor.white)
                painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
                painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, tick_num)


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


SYNC_CONFIG_PATH = os.path.join(os.getcwd(), "assets", "sync_config.json")


class SyncDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌐 多人联机同步配置")
        self.setFixedSize(450, 320)
        self.setStyleSheet("background-color: #1E1E1E; color: #FFF; font-size: 14px;")
        layout = QFormLayout(self)
        self.url_input = QLineEdit()
        self.url_input.setStyleSheet("background: #333; border: 1px solid #555; padding: 4px;")
        layout.addRow("服务器地址:", self.url_input)
        self.room_input = QLineEdit()
        self.room_input.setStyleSheet("background: #333; border: 1px solid #555; padding: 4px;")
        layout.addRow("小队房间号:", self.room_input)
        layout.addRow(QLabel("<hr>"))
        layout.addRow(QLabel("<b>连接策略：</b>"))
        self.radio_pull = QRadioButton("⬇️ 拉取: 用云端的轴覆盖本地")
        self.radio_pull.setStyleSheet("color: #32CD32; font-weight: bold;")
        self.radio_push = QRadioButton("⬆️ 推送: 用本地的轴覆盖云端")
        self.radio_push.setStyleSheet("color: #FF4444; font-weight: bold;")
        self.radio_pull.setChecked(True)
        self.bg = QButtonGroup(self)
        self.bg.addButton(self.radio_pull)
        self.bg.addButton(self.radio_push)
        layout.addRow(self.radio_pull)
        layout.addRow(self.radio_push)
        btn_box = QHBoxLayout()
        btn_ok = QPushButton("🚀 立即连接")
        btn_ok.setStyleSheet("background-color: #4169E1; font-weight: bold; padding: 8px;")
        btn_ok.clicked.connect(self.on_connect_clicked)
        btn_box.addStretch()
        btn_box.addWidget(btn_ok)
        self.load_config()

    def load_config(self):
        default_url = "ws://127.0.0.1:8000/ws/"
        default_room = "static_team_1"
        if os.path.exists(SYNC_CONFIG_PATH):
            try:
                with open(SYNC_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.url_input.setText(data.get('url', default_url))
                    self.room_input.setText(data.get('room', default_room))
                return
            except:
                pass
        self.url_input.setText(default_url)
        self.room_input.setText(default_room)

    def save_config(self):
        os.makedirs(os.path.dirname(SYNC_CONFIG_PATH), exist_ok=True)
        with open(SYNC_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump({"url": self.url_input.text().strip(), "room": self.room_input.text().strip()}, f)

    def on_connect_clicked(self):
        if self.radio_push.isChecked():
            reply = QMessageBox.warning(
                self, "⚠️ 危险操作确认",
                "你选择了【⬆️ 推送】模式！\n如果你不是队长，请取消并改选【拉取】。\n确定覆盖云端吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel: return
        self.save_config()
        self.accept()

    def get_config(self):
        url = self.url_input.text().strip()
        room = self.room_input.text().strip()
        action = "push" if self.radio_push.isChecked() else "pull"
        if not url.endswith('/'): url += '/'
        return f"{url}{room}", action


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

        self.btn_set_hp = QPushButton("🎯 设置基准血量")
        self.btn_set_hp.setStyleSheet(
            "background-color: #8A2BE2; color: white; padding: 6px; font-weight: bold; border-radius: 3px;")
        self.btn_set_hp.clicked.connect(self.open_hp_dialog)

        self.btn_set_potency = QPushButton("💉 恢复力系数")
        self.btn_set_potency.setStyleSheet(
            "background-color: #20B2AA; color: white; padding: 6px; font-weight: bold; border-radius: 3px;")
        self.btn_set_potency.clicked.connect(self.open_potency_dialog)

        self.btn_sync = QPushButton("🔌 联机同步")
        self.btn_sync.setStyleSheet("background-color: #696969; color: white; padding: 6px; font-weight: bold;")
        self.btn_sync.clicked.connect(self.toggle_sync)

        self.sync_label = QLabel("🔴 离线模式")
        self.sync_label.setStyleSheet("color: #FF4444; font-weight: bold; margin-left: 10px;")

        self.param_label = QLabel(self.get_param_text())
        self.param_label.setStyleSheet("color: #00FFCC; font-weight: bold; margin-left: 10px; margin-right: 15px;")

        top_bar.addWidget(btn_import_ff)
        top_bar.addWidget(btn_import_csv)
        top_bar.addWidget(btn_export)
        top_bar.addWidget(btn_clear)
        top_bar.addSpacing(10)
        top_bar.addWidget(btn_filter)
        top_bar.addWidget(self.btn_set_hp)
        top_bar.addWidget(self.btn_set_potency)
        top_bar.addWidget(self.param_label)
        top_bar.addSpacing(10)
        top_bar.addWidget(self.btn_sync)
        top_bar.addWidget(self.sync_label)
        top_bar.addStretch()

        self.table = QTableWidget()
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

    def get_param_text(self):
        return f"当前基准: {self.controller.baseline_hp:,} HP | 恢复力系数: {self.controller.potency_multiplier}"

    def update_labels(self):
        self.param_label.setText(self.get_param_text())

    def open_hp_dialog(self):
        new_hp, ok = QInputDialog.getInt(self, "设置基准血量", "请输入测试用基准血量 (法系约13万, 坦克约23万):",
                                         value=self.controller.baseline_hp, min=1000, max=999999, step=5000)
        if ok:
            self.controller.set_baseline_hp(new_hp)
            self.update_labels()

    def open_potency_dialog(self):
        new_mult, ok = QInputDialog.getDouble(self, "设置恢复力转换系数", "请输入 1 点恢复力等效的治疗量:",
                                              value=self.controller.potency_multiplier, min=1.0, max=200.0, decimals=1)
        if ok:
            self.controller.set_potency_multiplier(new_mult)
            self.update_labels()

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
        self.update_labels()

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

        self.update_labels()
        current_hp = self.controller.baseline_hp

        # 【核心去重逻辑】：强行去除在 combobox 里重复的脏技能
        seen_skills_in_combo = set()

        for row_idx, row_data in enumerate(timeline_data):
            row_type = row_data.get("row_type", "normal")
            is_highlight = row_data.get("highlight", False)
            bg_color = QColor("#4B3E00") if is_highlight else None

            if row_type in ["divider", "remark"]:
                self.table.setSpan(row_idx, 0, 1, 11)
                text = row_data.get("skill", "")
                for col in range(11):
                    blank_item = QTableWidgetItem("")
                    blank_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
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

            def _create_item(text, color=None, font=None):
                it = QTableWidgetItem(str(text))
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if bg_color: it.setBackground(QBrush(bg_color))
                if color: it.setForeground(color)
                if font: it.setFont(font)
                return it

            self.table.setItem(row_idx, 0, _create_item(row_data.get("time_str", "")))
            self.table.setItem(row_idx, 1, _create_item(row_data.get("skill", "")))

            note_edit = QLineEdit(row_data.get("note", ""))
            note_edit.setPlaceholderText("")
            if bg_color: note_edit.setStyleSheet(f"background-color: {bg_color.name()}; border: none; padding: 2px;")
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
                icon_path = SKILL_DB.get(mit, {}).get("icon_path", "")
                icon_lbl = SkillIconLabel(mit, icon_path, is_deletable=True)
                icon_lbl.clicked.connect(lambda m=mit, r=row_idx: self.controller.remove_mitigation(r, m))
                cast_layout.addWidget(icon_lbl)

            cast_layout.addStretch()
            self.table.setCellWidget(row_idx, 5, cast_widget)

            inherited_mits = row_data.get("calc_inherited", [])
            cov_widget = QWidget()
            if bg_color: cov_widget.setStyleSheet(f"background-color: {bg_color.name()};")
            cov_layout = QHBoxLayout(cov_widget)
            cov_layout.setContentsMargins(4, 4, 4, 4)
            cov_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            for mit_raw in inherited_mits:
                mit_name = mit_raw.split(" (")[0]
                tick_str = mit_raw.replace(mit_name, "").strip()
                icon_path = SKILL_DB.get(mit_name, {}).get("icon_path", "")
                icon_lbl = SkillIconLabel(mit_name, icon_path, is_deletable=False, tick_str=tick_str)
                cov_layout.addWidget(icon_lbl)

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

            # 【终极精准匹配】：绝对摒弃任何包含关系的误伤，并开启强制去重！
            seen_skills_in_combo.clear()
            for skill_name, info in SKILL_DB.items():
                db_job = info.get("job", "")

                is_match = False
                for sj in self.selected_jobs:
                    allowed_jobs = STRICT_JOB_MAP.get(sj, [sj])
                    if db_job in allowed_jobs:
                        is_match = True
                        break

                if is_match and skill_name not in seen_skills_in_combo:
                    seen_skills_in_combo.add(skill_name)

                    icon_path = info.get("icon_path", "")
                    icon = QIcon(icon_path) if icon_path and os.path.exists(icon_path) else QIcon()

                    # 寻找用户勾选的对应简称，作为前缀展示（如把 幻术师 变回 白魔）
                    display_job = db_job
                    for sj, allowed in STRICT_JOB_MAP.items():
                        if db_job in allowed and sj in self.selected_jobs:
                            display_job = sj
                            break

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
                    f"{row_data['calc_total_shield_potency']}算力")
                heal_str += f"🛡️ 盾 -{total_shield_val:,} ({' + '.join(details)})  "
            if total_heal_pot > 0:
                est_heal_hp = int(total_heal_pot * self.controller.potency_multiplier)
                heal_str += f"💖 奶 +{total_heal_pot} 恢复力 (约 {est_heal_hp:,} 血)"
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
        file_path, _ = QFileDialog.getOpenFileName(self, "导入 CSV", "", "CSV Files (*.csv);;All Files (*)")
        if file_path: self.controller.import_csv(file_path)

    def open_csv_export(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "选择导出保存位置", "mitigation_plan.csv",
                                                   "CSV Files (*.csv);;All Files (*)")
        if file_path: self.controller.export_csv(file_path)

    def show_error(self, title, msg):
        QMessageBox.critical(self, title, msg)

    def show_info(self, title, msg):
        QMessageBox.information(self, title, msg)