from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit


class DeathRecapWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.title = QLabel("🛡️ 法医诊断报告")
        self.title.setStyleSheet("font-size: 20px; font-weight: bold; color: #00FFCC;")

        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setStyleSheet("""
            QTextEdit {
                background-color: #1A1A1A; color: #E0E0E0; 
                font-family: 'Consolas', monospace; font-size: 15px;
                border: 1px solid #333; border-radius: 5px;
                padding: 12px; line-height: 1.6;
            }
        """)
        layout.addWidget(self.title)
        layout.addWidget(self.report_text)

    def update_report(self, report_data: dict):
        victim = report_data.get('victim', '未知')
        killer = report_data.get('killer', '未知')
        action = report_data.get('action', '未知')
        damage = report_data.get('damage', 0)
        overkill = report_data.get('overkill', 0)
        buffs = report_data.get('buffs', [])
        timeline = report_data.get('timeline', [])

        buffs_str = "、".join(buffs) if buffs else "❌ 没有任何状态 (裸吃)"
        timeline_str = "\n".join(timeline) if timeline else "无"

        # 仅在头部致命伤汇总处，显示红色高亮的溢出伤害
        overkill_str = f" (O: {overkill:,})" if overkill > 0 else ""

        text = (
            f"💀 阵亡玩家 : 【{victim}】\n"
            f"⚔️ 致命来源 : {killer}\n"
            f"💥 致死技能 : <{action}>\n"
            f"🩸 最终伤害 : {damage:,}{overkill_str}\n"
            f"🛡️ 承伤状态 : {buffs_str}\n"
            f"========================================\n"
            f"⏪ 死前连招时间轴 (Timeline):\n"
            f"{timeline_str}\n"
        )
        self.report_text.setText(text)
        self.title.setText(f"🚨 【突发阵亡】: {victim}")
        self.title.setStyleSheet("color: #FF4444;")