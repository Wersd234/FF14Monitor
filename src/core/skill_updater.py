import os
import json
import urllib.request
import re
import time
import sqlite3  # 【新增】：导入 SQLite3

# 高精度正则引擎（由你优化的究极形态！）
RE_DURATION = re.compile(r'持续时间[：:为\s]+(\d+)秒')
RE_POTENCY = re.compile(r'恢复力[：:为\s]+(\d+)')
RE_HOT = re.compile(r'持续恢复.*?恢复力[：:为\s]+(\d+)', re.DOTALL)

# ====== 盾与减伤正则 ======
RE_SHIELD_ABS = re.compile(r'相当于恢复力(\d+)的防护罩')
RE_SHIELD_PCT = re.compile(r'相当于治疗量(\d+)%的(?:伤害|防护罩)')
RE_SHIELD_HP = re.compile(r'最大体力值?(?:的)?(\d+)%的(?:伤害|防护罩)')
RE_MITI_VAL = re.compile(r'伤害[^\d]{0,15}?(?:减轻|降低|减少)[^\d]{0,10}?(\d+)%')

# 黑名单过滤
BLACKLIST_NAMES = ['失传', '文理', 'PvP', '未用', 'Unknown', '试用', '复制', '拟态', '变身', '连击', '跳跃', '冲刺',
                   '以太', '恢复药', '仙药']
BLACKLIST_DESC = ['耐久度', '消耗量减少', '作业精度', '加工精度', '采集力', '获得力']


def clean_html(text):
    if not text: return ""
    text = text.replace('<br>', '\n').replace('<br/>', '\n')
    return re.sub(r'<[^>]+>', '', text)


def is_valid_job(job_name):
    if not job_name or "全部职业" in job_name: return False
    return True


def update_skill_database():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_dir = os.path.join(base_dir, "assets", "db")
    icon_dir = os.path.join(base_dir, "assets", "icons")
    os.makedirs(db_dir, exist_ok=True)
    os.makedirs(icon_dir, exist_ok=True)

    print("🔄 正在启动 FFXIV 高精度数值扫描器 (准备写入 SQLite 数据库)...")
    final_db = {}

    base_url = "https://cafemaker.wakingsands.com/Action"
    page = 1
    total_pages = 1

    while page <= total_pages:
        try:
            url = f"{base_url}?columns=ID,Name,Description,Icon,Recast100ms,ClassJobCategory.Name,IsPvP&page={page}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as res:
                data = json.loads(res.read().decode())

            total_pages = data.get("Pagination", {}).get("PageTotal", 1)
            results = data.get("Results", [])

            for skill in results:
                if skill.get("IsPvP") == 1: continue

                job_category = skill.get("ClassJobCategory", {})
                job_name = job_category.get("Name", "")
                if not is_valid_job(job_name): continue

                name = skill.get("Name")
                if not name or any(b in name for b in BLACKLIST_NAMES): continue

                desc = clean_html(skill.get("Description", ""))
                if not desc or any(b in desc for b in BLACKLIST_DESC):
                    continue

                # ==== 提取核心数值 ====
                s_type = None
                miti_val = 0.0
                shield_hp_percent = 0
                shield_potency = 0
                potency = 0
                hot_potency = 0
                duration = 0

                dur_match = RE_DURATION.findall(desc)
                if dur_match: duration = int(dur_match[-1])

                if "恢复力" in desc:
                    if "对目标发动" in desc and "恢复自身" in desc and "坦克" not in job_name and "剑术师" not in job_name:
                        pass
                    else:
                        pot_matches = RE_POTENCY.findall(desc)
                        if "持续恢复" in desc:
                            hot_m = RE_HOT.search(desc)
                            if hot_m:
                                hot_potency = int(hot_m.group(1))
                                if pot_matches and (pot_matches[0] != hot_m.group(1) or len(pot_matches) > 1):
                                    potency = int(pot_matches[0])
                            elif pot_matches:
                                hot_potency = int(pot_matches[-1])
                        else:
                            if pot_matches: potency = int(pot_matches[-1])

                if "减轻" in desc or "降低" in desc or "减少" in desc:
                    m_val = RE_MITI_VAL.search(desc)
                    if m_val:
                        miti_val = int(m_val.group(1)) / 100.0
                        s_type = "mitigation"

                if "防护罩" in desc:
                    s_type = "shield"
                    sh_abs = RE_SHIELD_ABS.search(desc)
                    sh_pct = RE_SHIELD_PCT.search(desc)
                    sh_hp = RE_SHIELD_HP.search(desc)

                    if sh_abs:
                        shield_potency = int(sh_abs.group(1))
                    elif sh_pct:
                        pct = int(sh_pct.group(1))
                        if potency > 0:
                            shield_potency = int(potency * pct / 100)
                        elif hot_potency > 0:
                            shield_potency = int(hot_potency * pct / 100)
                        else:
                            shield_hp_percent = pct
                    elif sh_hp:
                        shield_hp_percent = int(sh_hp.group(1))
                    else:
                        shield_hp_percent = 10

                if (potency > 0 or hot_potency > 0) and not s_type: s_type = "heal"
                if "恢复魔法的效果提高" in desc or "受治疗效果提高" in desc:
                    if not s_type: s_type = "heal_up"

                if "宏观宇宙" in name or "地星" in name or "礼仪之铃" in name:
                    s_type = "heal"
                    duration = 20 if not duration else duration
                elif "死斗" in name or "行尸走肉" in name or "神圣领域" in name or "超火流星" in name:
                    s_type = "invuln"
                    duration = 10

                if s_type:
                    icon_url = skill.get("Icon")
                    local_icon_path = ""
                    if icon_url:
                        local_icon_path = os.path.join(icon_dir, icon_url.split("/")[-1])
                        if not os.path.exists(local_icon_path):
                            try:
                                urllib.request.urlretrieve(f"https://cafemaker.wakingsands.com{icon_url}",
                                                           local_icon_path)
                            except:
                                pass

                    cooldown = skill.get("Recast100ms", 0) / 10

                    display_job = job_name
                    if "剑术师" in job_name and "斧术师" in job_name:
                        display_job = "坦克通用"
                    elif "幻术师" in job_name and "学者" in job_name:
                        display_job = "治疗通用"
                    elif "格斗家" in job_name and "枪术师" in job_name:
                        display_job = "近战通用"
                    elif "吟游诗人" in job_name and "机工士" in job_name:
                        display_job = "远敏通用"
                    elif "咒术师" in job_name and "秘术师" in job_name:
                        display_job = "法系通用"

                    final_db[name] = {
                        "id": skill["ID"], "job": display_job, "type": s_type,
                        "value": miti_val, "shield": shield_hp_percent, "shield_potency": shield_potency,
                        "potency": potency, "hot_potency": hot_potency, "duration": duration,
                        "cd": cooldown, "icon_path": local_icon_path
                    }
                    print(
                        f"✅ 捕获成功: [{display_job}] {name} (瞬抬:{potency}, HOT:{hot_potency}, 盾:{shield_hp_percent}%, 算力盾:{shield_potency}, 减伤:{miti_val}, 持续:{duration}s)")

            page += 1
            time.sleep(0.1)

        except Exception as e:
            print(f"❌ 第 {page} 页抓取失败: {e}")
            break

    # ==============================================================
    # 【核心修改】：将 dict 写入 SQLite 数据库
    # ==============================================================
    db_file = os.path.join(db_dir, "skills.db")

    # 建立连接
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 创建技能表 (如果不存在)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS skills (
            name TEXT PRIMARY KEY,
            skill_id INTEGER,
            job TEXT,
            type TEXT,
            miti_value REAL,
            shield_hp INTEGER,
            shield_potency INTEGER,
            potency INTEGER,
            hot_potency INTEGER,
            duration INTEGER,
            cd REAL,
            icon_path TEXT
        )
    ''')

    # 清空旧数据以防止冗余
    cursor.execute('DELETE FROM skills')

    # 遍历注入数据
    for name, info in final_db.items():
        cursor.execute('''
            INSERT INTO skills (name, skill_id, job, type, miti_value, shield_hp, shield_potency, potency, hot_potency, duration, cd, icon_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            name, info["id"], info["job"], info["type"],
            info["value"], info["shield"], info["shield_potency"],
            info["potency"], info["hot_potency"], info["duration"],
            info["cd"], info["icon_path"]
        ))

    # 提交事务并关闭连接
    conn.commit()
    conn.close()

    print(f"\n🎉 纯净版 SQLite 数据库构建完成！共收录 {len(final_db)} 个极品技能，已完美落地 {db_file}。")


if __name__ == "__main__":
    update_skill_database()