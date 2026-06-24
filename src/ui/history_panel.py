import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QComboBox, QPushButton, QTreeWidget, QTreeWidgetItem, QLabel)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor


class HistoryPanelWidget(QWidget):
    report_selected_signal = pyqtSignal(dict)
    parse_file_signal = pyqtSignal(str)

    def __init__(self, default_log_dir: str):
        super().__init__()
        self.log_dir = default_log_dir

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 顶部栏
        top_layout = QHBoxLayout()
        self.file_combo = QComboBox()
        self.file_combo.setStyleSheet("background-color: #333; color: white; padding: 5px;")
        self.refresh_btn = QPushButton("🔄 刷新")
        self.parse_btn = QPushButton("📂 解析")

        top_layout.addWidget(QLabel("日志:"))
        top_layout.addWidget(self.file_combo, stretch=1)
        top_layout.addWidget(self.refresh_btn)
        top_layout.addWidget(self.parse_btn)

        # 树状菜单
        self.death_tree = QTreeWidget()
        self.death_tree.setHeaderHidden(True)
        self.death_tree.setStyleSheet("""
            QTreeWidget { background-color: #1e1e1e; color: #ccc; font-size: 15px; border: none; outline: none; }
            QTreeWidget::item { padding: 5px; }
            QTreeWidget::item:selected { background-color: #661111; color: white; }
            QTreeWidget::item:hover { background-color: #333333; }
        """)

        layout.addLayout(top_layout)
        layout.addWidget(self.death_tree)

        self.refresh_btn.clicked.connect(self.load_log_files)
        self.parse_btn.clicked.connect(self.request_parse)
        self.death_tree.itemClicked.connect(self.on_item_clicked)

        self.load_log_files()

    def load_log_files(self):
        self.file_combo.clear()
        if not os.path.exists(self.log_dir):
            self.file_combo.addItem("未找到ACT日志文件夹")
            return

        files = [f for f in os.listdir(self.log_dir) if f.endswith('.log')]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(self.log_dir, x)), reverse=True)
        for f in files:
            self.file_combo.addItem(f, os.path.join(self.log_dir, f))

    def request_parse(self):
        file_path = self.file_combo.currentData()
        if file_path:
            self.death_tree.clear()
            self.death_tree.addTopLevelItem(QTreeWidgetItem(["⏳ 正在解析战斗与死因..."]))
            self.parse_file_signal.emit(file_path)

    def load_parsed_data(self, encounters: list):
        self.death_tree.clear()
        if not encounters:
            self.death_tree.addTopLevelItem(QTreeWidgetItem(["🎉 该日志中没有任何阵亡记录！"]))
            return

        # 渲染父子折叠树
        for enc in encounters:
            # 【修复了这里】：键名从 'start_time' 改为了 'start'
            start_str = enc['start'].strftime("%H:%M:%S")

            root_text = f"⚔️ 第 {enc['id']} 把 (起手 {start_str}) 灭团/击杀"
            root_item = QTreeWidgetItem([root_text])
            root_item.setBackground(0, QColor("#2A2A2A"))
            root_item.setForeground(0, QColor("#E2C08D"))  # FF14 金色风格

            for report in enc['deaths']:
                child_text = f"[{report['time']}] 💀 {report['victim']} : {report['action']}"
                child_item = QTreeWidgetItem([child_text])
                child_item.setData(0, Qt.ItemDataRole.UserRole, report)
                root_item.addChild(child_item)

            self.death_tree.addTopLevelItem(root_item)
            root_item.setExpanded(True)  # 默认展开

    def on_item_clicked(self, item: QTreeWidgetItem, column: int):
        report_data = item.data(0, Qt.ItemDataRole.UserRole)
        if report_data:
            self.report_selected_signal.emit(report_data)