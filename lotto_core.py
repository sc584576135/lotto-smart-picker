# -*- coding: utf-8 -*-
"""大乐透核心纯逻辑模块（无 GUI / 无三方依赖，可单元测试）。

把易出错的纯算法（奇偶比、区间比、注数计算）从主文件抽出，
避免与 tkinter / sklearn 耦合，便于回归测试与独立维护。
"""
from math import comb


def recommend_odd_even(records, periods=30):
    """按最近 periods 期统计最常出现的奇偶分布，返回 (奇, 偶)。"""
    if not records:
        return (3, 2)
    cnt = {}
    for r in records[:periods]:
        odd = sum(1 for n in (r.get('front') or []) if n % 2)
        cnt[odd] = cnt.get(odd, 0) + 1
    most = max(cnt, key=cnt.__getitem__)
    return (most, 5 - most)


def recommend_zone_ratio(records, periods=30, broken_zones=None, total=5):
    """按最近 periods 期估算三区占比，区间 [1-12][13-24][25-35]。

    broken_zones: 断区列表 [1|2|3]，对应区间强制为 0。
    返回值总和恒等于 total（除非全部断区），绝不把断区重新填回。
    """
    if broken_zones is None:
        broken_zones = []
    bz = {z for z in broken_zones if z in (1, 2, 3)}
    counts = [0, 0, 0]
    for r in records[:periods]:
        for n in (r.get('front') or []):
            if n <= 12:
                counts[0] += 1
            elif n <= 24:
                counts[1] += 1
            else:
                counts[2] += 1
    total_hits = sum(counts)
    if total_hits == 0:
        base = [2, 2, 1]
    else:
        base = [c * total // total_hits for c in counts]
        rem = total - sum(base)
        order = sorted(range(3), key=lambda i: counts[i], reverse=True)
        for i in order:
            if rem <= 0:
                break
            base[i] += 1
            rem -= 1

    active = [i for i in range(3) if (i + 1) not in bz]
    if not active:
        return (0, 0, 0)
    ratio = list(base)
    for i in range(3):
        if (i + 1) in bz:
            ratio[i] = 0
    s = sum(ratio)
    active_sorted = sorted(active, key=lambda i: ratio[i], reverse=True)
    k = 0
    if s < total:
        deficit = total - s
        while deficit > 0 and active_sorted:
            i = active_sorted[k % len(active_sorted)]
            ratio[i] += 1
            deficit -= 1
            k += 1
    elif s > total:
        excess = s - total
        while excess > 0 and active_sorted:
            i = active_sorted[k % len(active_sorted)]
            if ratio[i] > 0:
                ratio[i] -= 1
                excess -= 1
            k += 1
    return tuple(ratio)


def calc_front_bets(dan_count, tuo_count, need=5):
    """前区注数：胆码 dan_count + 拖码 tuo_count 取 need-dan_count 的组合数。"""
    dan_count = max(int(dan_count or 0), 0)
    tuo_count = max(int(tuo_count or 0), 0)
    if dan_count >= need:
        return 1
    need_f = need - dan_count
    if tuo_count < need_f:
        return 0
    return comb(tuo_count, need_f)


def calc_back_bets(dan_count, tuo_count, need=2):
    """后区注数（同上前区逻辑）。"""
    dan_count = max(int(dan_count or 0), 0)
    tuo_count = max(int(tuo_count or 0), 0)
    if dan_count >= need:
        return 1
    need_b = need - dan_count
    if tuo_count < need_b:
        return 0
    return comb(tuo_count, need_b)


def calc_fushi_bets(front_count, back_count):
    """复式注数：C(front_count,5) * C(back_count,2)。"""
    front_count = max(int(front_count or 0), 5)
    back_count = max(int(back_count or 0), 2)
    return comb(front_count, 5) * comb(back_count, 2)


def parse_ratio(text, expected_sum=5):
    """解析 '3:2' 这类比例，返回 tuple；总和不符返回 None。"""
    if not text or not text.strip():
        return None
    try:
        nums = [int(p) for p in text.strip().split(':')]
        return tuple(nums) if sum(nums) == expected_sum else None
    except (ValueError, TypeError):
        return None