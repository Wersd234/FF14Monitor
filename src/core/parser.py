# --- START OF FILE parser.py ---

from src.models.events import LogEvent, DamageEvent, BuffEvent, DeathEvent, PositionEvent, ZoneEvent, CombatantEvent


def safe_parse_int(val_str: str) -> int:
    if not val_str: return 0
    try:
        return int(val_str)
    except ValueError:
        try:
            return int(val_str, 16)
        except ValueError:
            return 0


def parse_ff14_damage(flag_str: str, val_str: str) -> int:
    try:
        if not flag_str or not val_str or val_str == "0": return 0
        flag_val = int(flag_str, 16)

        # 【坚持你的原版逻辑】：只放行 3, 5, 6，完美屏蔽平A和DoT干扰！
        action_type = flag_val & 0xFF
        if action_type not in (3, 5, 6): return 0

        val = int(val_str, 16)
        if val == 0: return 0

        # 你的原版特例处理，完美保留
        if (val & 0xFFFF) == 0 and val > 0xFFFF:
            return (val >> 16) & 0xFFFF

        # ================= 加入 Endwalker 0x40 大伤害解密 =================
        byte0 = val & 0xFF
        byte1 = (val >> 8) & 0xFF
        byte2 = (val >> 16) & 0xFF
        byte3 = (val >> 24) & 0xFF

        if byte1 == 0x40:
            return (byte0 << 16) | (byte3 << 8) | byte2
        # ================================================================

        # 对于普通伤害，依然使用你的完美逻辑：过滤最高位标志，保留低 3 字节！
        return val & 0xFFFFFF
    except Exception:
        return 0


class FFLogsParser:
    """
    状态机级别的日志解析器。
    拥有全场实体的“记账本”机制，用以精准还原 FFlogs 级别的连击减血和过量伤害。
    """

    def __init__(self):
        # 内部记账本：记录每个实体 (玩家/怪物) 的实时血量状态
        # 结构: { target_id: { 'tracked_hp': int, 'last_log_hp': int, 'max_hp': int } }
        self.entities = {}

    def parse_line(self, raw_line: str) -> list:
        parts = raw_line.split('|')
        if len(parts) < 4: return []

        event_type = parts[0]
        timestamp = parts[1]
        events = []

        try:
            # ==============================================================
            # 【网络状态主动同步包】(Type 37, 38, 39)
            # ==============================================================
            if event_type in ['37', '38', '39']:
                if len(parts) >= 7:
                    target_id = parts[2]
                    # 读取服务器主动下发的真实HP
                    sync_hp = safe_parse_int(parts[5])
                    sync_max_hp = safe_parse_int(parts[6])

                    # 同步刷新我们的内部“记账本”
                    if sync_hp >= 0 and sync_max_hp > 0:
                        if target_id not in self.entities:
                            self.entities[target_id] = {'tracked_hp': sync_hp, 'last_log_hp': sync_hp,
                                                        'max_hp': sync_max_hp}
                        else:
                            self.entities[target_id]['tracked_hp'] = sync_hp
                            self.entities[target_id]['last_log_hp'] = sync_hp
                            self.entities[target_id]['max_hp'] = sync_max_hp

                # 【保留原逻辑】：读取玩家职业信息 (隐藏在 38 行的状态代码里)
                if event_type == '38' and len(parts) >= 6:
                    job_hex = parts[4]  # 例如 "00646425"
                    try:
                        job_id = int(job_hex[-2:], 16) if len(job_hex) >= 2 else 0
                        if job_id > 0:
                            events.append(CombatantEvent(timestamp, event_type, raw_line, parts[2], parts[3], job_id))
                    except Exception:
                        pass

            # ==============================================================
            # 【伤害与技能结算】(Type 21, 22) - FFLogs 核心状态推演
            # ==============================================================
            elif event_type in ['21', '22']:
                if len(parts) < 25: return []

                target_id = parts[6]
                log_hp = safe_parse_int(parts[24])
                log_max_hp = safe_parse_int(parts[25]) if len(parts) > 25 else 0

                # 如果是新面孔，加入记账本
                if target_id not in self.entities:
                    self.entities[target_id] = {'tracked_hp': log_hp, 'last_log_hp': log_hp, 'max_hp': log_max_hp}

                entity = self.entities[target_id]

                # --------- 核心：侦测同快照的连击延迟 ---------
                # 如果日志里带的当前血量，和上一行的依然一模一样，说明服务器没更新快照。
                # 此时我们绝对不信任日志血量，改用我们内部记录的已受击血量 (tracked_hp)。
                if log_hp == entity['last_log_hp']:
                    effective_hp = entity['tracked_hp']
                else:
                    # 如果血量变了（通常是服务器刷新、或者被奶了），同步为新血量
                    effective_hp = log_hp
                    entity['last_log_hp'] = log_hp

                if log_max_hp > 0:
                    entity['max_hp'] = log_max_hp

                # 结算 8 个特效槽的伤害
                for i in range(8):
                    flag_idx = 8 + i * 2
                    val_idx = 9 + i * 2
                    if val_idx < len(parts):
                        dmg = parse_ff14_damage(parts[flag_idx], parts[val_idx])
                        if dmg > 0:
                            # 过量与真实伤害结算（基于推演出来的 effective_hp）
                            if entity['max_hp'] > 0:
                                if dmg > effective_hp:
                                    actual_damage = effective_hp
                                    overkill = dmg - effective_hp
                                else:
                                    actual_damage = dmg
                                    overkill = 0
                            else:
                                actual_damage = dmg
                                overkill = 0

                            # 【动态扣血】: 将剩余血量扣除，为该行的下一个伤害槽，或接下来的下一行攻击做准备
                            effective_hp = max(0, effective_hp - actual_damage)

                            events.append(DamageEvent(
                                timestamp=timestamp, event_type=event_type, raw_line=raw_line,
                                source_id=parts[2], source_name=parts[3], action_id=parts[4],
                                action_name=parts[5], target_id=parts[6], target_name=parts[7],
                                damage_amount=str(actual_damage), overkill_amount=str(overkill)
                            ))

                # 把计算完后的最新血量存回记账本，留给未来的攻击验证
                entity['tracked_hp'] = effective_hp

                # 【保留原逻辑】：读取位置坐标
                try:
                    tx, ty, th = float(parts[30]), float(parts[31]), float(parts[33])
                    events.append(PositionEvent(timestamp, 'Pos', raw_line, parts[6], parts[7], tx, ty, th))
                    sx, sy, sh = float(parts[39]), float(parts[40]), float(parts[42])
                    events.append(PositionEvent(timestamp, 'Pos', raw_line, parts[2], parts[3], sx, sy, sh))
                except Exception:
                    pass

            # ==============================================================
            # 【Buff与状态】(Type 26, 30)
            # ==============================================================
            elif event_type in ['26', '30']:
                if len(parts) >= 9:
                    events.append(BuffEvent(
                        timestamp=timestamp, event_type=event_type, raw_line=raw_line,
                        status_id=parts[2], status_name=parts[3],
                        target_id=parts[7], target_name=parts[8]
                    ))

            # ==============================================================
            # 【死亡】(Type 25)
            # ==============================================================
            elif event_type == '25':
                events.append(DeathEvent(
                    timestamp=timestamp, event_type=event_type, raw_line=raw_line,
                    target_id=parts[2], target_name=parts[3]
                ))

            # ==============================================================
            # 【纯移动与位置更新】(Type 261, 264)
            # ==============================================================
            elif event_type in ['261', '264']:
                eid = parts[3]
                x = y = h = None
                for i in range(4, len(parts) - 1, 2):
                    if parts[i] == 'PosX':
                        x = float(parts[i + 1])
                    elif parts[i] == 'PosY':
                        y = float(parts[i + 1])
                    elif parts[i] == 'Heading':
                        h = float(parts[i + 1])
                if x is not None and y is not None:
                    events.append(PositionEvent(timestamp, 'Pos', raw_line, eid, "Unknown", x, y, h or 0.0))

            # ==============================================================
            # 【副本地图变更】(Type 01)
            # ==============================================================
            elif event_type == '01':
                if len(parts) >= 4:
                    events.append(ZoneEvent(timestamp, event_type, raw_line, parts[2], parts[3]))

        except Exception:
            pass

        # 兜底返回
        if not events:
            events.append(LogEvent(timestamp=timestamp, event_type=event_type, raw_line=raw_line))

        return events

# --- END OF FILE parser.py ---