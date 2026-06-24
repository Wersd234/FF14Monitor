import os
import json

# ==========================================
# 在这里填写你想删除的关键词
# ==========================================
KEYWORDS_TO_DELETE = [
    "失传", "文理", "试用", "连击", "攻击", "强击", "爆发",
    "PvP", "复制", "拟态", "变身", "未用", "Unknown",
    "跳跃", "冲刺", "以太", "强心", "恢复药", "仙药"
]


def clean_local_skill_db():
    # 动态获取项目根目录下的 assets/db 路径
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # 如果你把这个脚本放在根目录运行，请使用这行：
    # base_dir = os.path.abspath(os.path.dirname(__file__))

    db_path = os.path.join(base_dir, "assets", "db", "skills_db.json")

    if not os.path.exists(db_path):
        print(f"❌ 找不到技能数据库文件: {db_path}")
        return

    # 读取旧数据
    with open(db_path, 'r', encoding='utf-8') as f:
        skills = json.load(f)

    initial_count = len(skills)
    cleaned_skills = {}
    deleted_count = 0

    print("🧹 开始清理脏技能数据...\n")

    for skill_name, info in skills.items():
        # 如果技能名包含了黑名单里的任意一个词汇
        if any(keyword in skill_name for keyword in KEYWORDS_TO_DELETE):
            print(f"🗑️ 删除技能 -> {skill_name}")
            deleted_count += 1
        else:
            # 安全保留
            cleaned_skills[skill_name] = info

    # 覆盖保存回原文件
    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_skills, f, ensure_ascii=False, indent=4)

    print("\n✅ 清理完成！")
    print(f"📊 原始技能数: {initial_count}")
    print(f"💥 删除了 {deleted_count} 个垃圾技能")
    print(f"🛡️ 剩余有效排轴技能数: {len(cleaned_skills)}")


if __name__ == "__main__":
    clean_local_skill_db()