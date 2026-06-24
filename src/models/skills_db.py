import os
import sqlite3

SKILL_DB = {}


def load_skill_db():
    global SKILL_DB

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(base_dir, "assets", "db", "skills.db")

    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 读取整张表
            cursor.execute("SELECT * FROM skills")
            # 获取数据库列名
            columns = [description[0] for description in cursor.description]

            for row in cursor.fetchall():
                # 将元组拼装成字典
                skill_data = dict(zip(columns, row))

                # 提取主键名字
                name = skill_data.pop("name")

                # 【字段名映射】：将 SQLite 的列名无缝转化为我们排轴 UI 依赖的格式
                skill_data["id"] = skill_data.pop("skill_id")
                skill_data["value"] = skill_data.pop("miti_value")
                skill_data["shield"] = skill_data.pop("shield_hp")

                SKILL_DB[name] = skill_data

            conn.close()
            print(f"✅ 成功从 SQLite 本地数据库加载 {len(SKILL_DB)} 个排轴技能。")
        except Exception as e:
            print(f"❌ 读取 SQLite 数据库失败: {e}")
    else:
        print(f"⚠️ 警告：未找到本地数据库 ({db_path})，请先运行 src/core/skill_updater.py 初始化！")


# 程序启动时自动载入内存
load_skill_db()